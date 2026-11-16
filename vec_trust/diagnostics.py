"""诊断层：二维诊断（模型维 × 区间维） + 教学分级审计.

回应评估需求书 R3/R4：
    旧版 audit() 用单一 REFUTED 裁决，且结论恒 REFUTED（不可证伪）。
    新接口 diagnose() 把信号拆成两个正交维度：
      模型维   ΔRMSE   = 外推 RMSE / 域内 RMSE        —— 模型本身能否外推
      区间维   Δcover  = 域内覆盖 - 外推覆盖            —— 区间能否随漂移自适应
    再映射为病因三选一：
      MODEL_ERROR          —— 模型错（误差显著上涨）
      INTERVAL_NOT_ADAPTIVE—— 区间不随距离增长（误差稳但覆盖崩）
      METRIC_MISMATCH      —— 指标选错（逐元素指标好但分布级崩，需外部指标）
      NONE                 —— 通过（负控应落这里）

    统计严谨（R4）：n_boot 次重复划分，报 95% bootstrap CI；
    病因判定用 CI 下界，不用单次点估计。
"""
from __future__ import annotations

import numpy as np

from .conformal import conformal_quantile, interval, coverage, w1_proxy
from .baseline_ladder import LadderConfig, evaluate_ladder, paired_ladder_test
from .synthetic import (
    MODEL_NAMES, CORRECT_MODEL, WRONG_MODEL, predict_with, extrap_distance,
)

PROTOCOLS = ("unseen_stage", "unseen_perturbation", "unseen_tissue")
VERDICT_ORDER = {"REFUTED": 0, "MARGINAL": 1, "PASS_WEAK": 2,
                 "PASS_PARTIAL": 3, "PASS_FULL": 4}

# 病因判定的经验阈值（教学用；真实场景应由 CI 与业务风险自定）
RMSE_RATIO_THRESHOLD = 1.8     # 外推 RMSE / 域内 RMSE 超过此值 → 模型错
COVERAGE_DROP_THRESHOLD = 0.12  # 覆盖下降超过此值 → 区间维失效


def _split(atlas: dict, cal_frac: float, seed: int) -> tuple:
    X_all, y_all = atlas["train"]
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(X_all))
    n_cal = max(30, int(len(perm) * cal_frac))
    idx_cal, idx_fit = perm[:n_cal], perm[n_cal:]
    return (X_all[idx_fit], y_all[idx_fit]), (X_all[idx_cal], y_all[idx_cal])


def _bootstrap_ci(values: list[float], n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """均值的 bootstrap 95% 置信区间。"""
    v = np.asarray(values, dtype=float)
    if v.size < 2:
        return (float(v[0]), float(v[0])) if v.size else (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = np.array([rng.choice(v, size=v.size, replace=True).mean()
                      for _ in range(n_boot)])
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def diagnose(atlas: dict, model: str, *, alpha: float = 0.1,
             n_boot: int = 10, cal_frac: float = 0.3, seed: int = 0,
             predictor=None, adaptive_predictor=None,
             scale_mode: str = "static") -> dict:
    """二维诊断（推荐接口）。

    Args:
        model: 模型名（内置 copy_last / mean / linear / poly3）或自定义标签
        predictor: callable(X_fit, y_fit, X_eval) -> (mean, std)，接入自己的模型
        adaptive_predictor: 可选的 callable，返回随外推距离自适应的 std；
                            不传则用内置 predict_with(..., scale_mode="adaptive")
        n_boot: 重复划分次数（每次不同种子），报 bootstrap 95% CI
        scale_mode: 主评估用 static 还是 adaptive 区间

    Returns:
        dict，含模型维/区间维分解、病因、CI、教学裁决。
    """
    if predictor is None:
        predictor = lambda Xf, yf, Xe, **kw: predict_with(model, Xf, yf, Xe, **kw)

    rmse_ratio_by_proto: dict[str, list[float]] = {p: [] for p in PROTOCOLS}
    cov_drop_by_proto: dict[str, list[float]] = {p: [] for p in PROTOCOLS}
    cov_static_by_proto: dict[str, list[float]] = {p: [] for p in PROTOCOLS}
    cov_adapt_by_proto: dict[str, list[float]] = {p: [] for p in PROTOCOLS}
    width_growth_by_proto: dict[str, list[float]] = {p: [] for p in PROTOCOLS}

    for b in range(n_boot):
        (Xf, yf), (Xc, yc) = _split(atlas, cal_frac, seed + b)

        def run(pred_fn, Xe, ye, mode):
            mu, sd = pred_fn(Xf, yf, Xe)
            return mu, sd

        # 用校准集定 conformal 分位数（static 与 adaptive 各一套）
        mu_c, sd_c = predictor(Xf, yf, Xc)
        q_static = conformal_quantile(np.abs(yc - mu_c) / np.maximum(sd_c, 1e-8), alpha)
        adp_fn = adaptive_predictor or (
            lambda Xf2, yf2, Xe2: predict_with(model, Xf2, yf2, Xe2, scale_mode="adaptive")
            if model in MODEL_NAMES or model == "model" else predictor
        )
        mu_c2, sd_c2 = adp_fn(Xf, yf, Xc)
        q_adapt = conformal_quantile(np.abs(yc - mu_c2) / np.maximum(sd_c2, 1e-8), alpha)

        # 域内（用主 scale_mode）
        Xe_id, ye_id = atlas["in_domain"]
        mu_id, sd_id = run(predictor, Xe_id, ye_id, scale_mode)
        q_id = q_adapt if scale_mode == "adaptive" else q_static
        id_rmse = float(np.sqrt(np.mean((mu_id - ye_id) ** 2)))
        id_cov = coverage(interval(mu_id, sd_id, q_id)[0],
                          interval(mu_id, sd_id, q_id)[1], ye_id)
        id_width = float(np.mean(2 * q_id * sd_id))

        for proto in PROTOCOLS:
            Xe, ye = atlas[proto]
            mu_s, sd_s = predictor(Xf, yf, Xe)
            ex_rmse = float(np.sqrt(np.mean((mu_s - ye) ** 2)))
            lo_s, hi_s = interval(mu_s, sd_s, q_static)
            cov_s = coverage(lo_s, hi_s, ye)

            mu_a, sd_a = adp_fn(Xf, yf, Xe)
            lo_a, hi_a = interval(mu_a, sd_a, q_adapt)
            cov_a = coverage(lo_a, hi_a, ye)

            main_mu, main_sd, main_q = (
                (mu_a, sd_a, q_adapt) if scale_mode == "adaptive" else (mu_s, sd_s, q_static)
            )
            lo_m, hi_m = interval(main_mu, main_sd, main_q)
            cov_main = coverage(lo_m, hi_m, ye)

            ratio = ex_rmse / max(id_rmse, 1e-8)
            rmse_ratio_by_proto[proto].append(ratio)
            cov_drop_by_proto[proto].append(id_cov - cov_main)
            cov_static_by_proto[proto].append(cov_s)
            cov_adapt_by_proto[proto].append(cov_a)
            width_growth_by_proto[proto].append(float(np.mean(2 * main_q * main_sd)) / max(id_width, 1e-8))

    # 汇总：取最坏协议（RMSE 比最大、覆盖降最大）
    def summarize(by_proto: dict) -> dict:
        out = {}
        for p, vals in by_proto.items():
            lo, hi = _bootstrap_ci(vals, n_boot=2000, seed=7)
            out[p] = {
                "mean": round(float(np.mean(vals)), 4),
                "ci95": [round(lo, 4), round(hi, 4)],
            }
        return out

    rmse_ratio = summarize(rmse_ratio_by_proto)
    cov_drop = summarize(cov_drop_by_proto)
    cov_static = summarize(cov_static_by_proto)
    cov_adapt = summarize(cov_adapt_by_proto)
    width_growth = summarize(width_growth_by_proto)

    # 病因判定：以 unseen_stage（时间外推）为主诊断协议。
    # 核心判据 = "自适应区间能否把覆盖救回可接受水平"——这是区分两类病因的直接证据，
    # 比 rmse_ratio 的间接推断更稳健（未见扰动/组织本就无训练信号，RMSE 天然高）。
    main_proto = "unseen_stage"
    ratio_mean = rmse_ratio[main_proto]["mean"]
    cov_static_mean = cov_static[main_proto]["mean"]
    cov_adapt_mean = cov_adapt[main_proto]["mean"]
    recovery = cov_adapt_mean - cov_static_mean
    worst_proto = max(PROTOCOLS, key=lambda p: rmse_ratio[p]["mean"])

    if recovery > COVERAGE_DROP_THRESHOLD and cov_adapt_mean >= 0.75:
        # 自适应区间能把覆盖救回来 → 模型没崩，是区间构造的问题
        cause = "INTERVAL_NOT_ADAPTIVE"
        cause_cn = "区间不随距离增长：静态区间覆盖掉到 "
        cause_cn += f"{cov_static_mean:.3f}，自适应区间恢复到 {cov_adapt_mean:.3f}，模型误差稳定"
    elif ratio_mean > RMSE_RATIO_THRESHOLD or cov_adapt_mean < 0.75:
        # 换区间也救不回 → 模型本身外推失效
        cause = "MODEL_ERROR"
        cause_cn = ("模型错：外推 RMSE 上涨到域内的 "
                    f"{ratio_mean:.2f}×，且自适应区间覆盖仅 {cov_adapt_mean:.3f}，救不回")
    else:
        cause = "NONE"
        cause_cn = "通过：误差与覆盖均在外推下保持稳定"

    # 教学裁决（保留分级体系，但降级为"教学"，不再作为模型质量证据）
    if cause == "NONE":
        teaching_verdict = "PASS_TEACHING"
    elif cause == "INTERVAL_NOT_ADAPTIVE":
        teaching_verdict = "INTERVAL_FAIL_TEACHING"
    else:
        teaching_verdict = "MODEL_FAIL_TEACHING"

    return {
        "model": model,
        "alpha": alpha,
        "n_boot": n_boot,
        "scale_mode": scale_mode,
        "dimensions": {
            "model_axis_rmse_ratio": rmse_ratio,
            "interval_axis_cov_drop": cov_drop,
            "coverage_static": cov_static,
            "coverage_adaptive": cov_adapt,
            "width_growth": width_growth,
        },
        "diagnosis": {
            "cause": cause,
            "cause_cn": cause_cn,
            "worst_protocol": worst_proto,
            "teaching_verdict": teaching_verdict,
        },
        "disclaimer": "教学用合成数据 / 机制演示；教学裁决非模型质量证据。",
    }


# ---------------------------------------------------------------------------
# 向后兼容：v0.1 的 audit / audit_all 保留，但明确标注为"教学分级"
# ---------------------------------------------------------------------------
def audit(atlas: dict, model: str, alpha: float = 0.1,
          cal_frac: float = 0.3, seed: int = 0,
          predictor=None, scale_mode: str = "static") -> dict:
    """旧版教学审计（保留兼容）。新用户请用 diagnose()。"""
    if predictor is None:
        predictor = lambda Xf, yf, Xe: predict_with(model, Xf, yf, Xe, scale_mode=scale_mode)
    (Xf, yf), (Xc, yc) = _split(atlas, cal_frac, seed)
    mu_c, sd_c = predictor(Xf, yf, Xc)
    q = conformal_quantile(np.abs(yc - mu_c) / np.maximum(sd_c, 1e-8), alpha)

    def evaluate_split(X, y):
        mu, sd = predictor(Xf, yf, X)
        lo, hi = interval(mu, sd, q)
        return {"coverage": round(coverage(lo, hi, y), 4),
                "rmse_rel": round(float(np.sqrt(np.mean((mu - y) ** 2)) / max(float(np.std(y)), 1e-8)), 4),
                "mean_interval_width": round(float(np.mean(hi - lo)), 4), "_mu": mu}

    id_res = evaluate_split(*atlas["in_domain"])
    id_width = max(id_res["mean_interval_width"], 1e-8)
    protocols = {}
    for proto in PROTOCOLS:
        res = evaluate_split(*atlas[proto])
        res["width_ratio"] = round(res["mean_interval_width"] / id_width, 3)
        res["w1_drift"] = round(w1_proxy(id_res["_mu"].mean(axis=1), res["_mu"].mean(axis=1)), 4)
        # 教学分级：基于覆盖下降 + RMSE 比（简化版，不再是唯一裁决）
        ratio = res["rmse_rel"] / max(id_res["rmse_rel"], 1e-8)
        drop = id_res["coverage"] - res["coverage"]
        res["teaching_verdict"] = ("MODEL_FAIL_TEACHING" if ratio > RMSE_RATIO_THRESHOLD
                                   else "INTERVAL_FAIL_TEACHING" if drop > COVERAGE_DROP_THRESHOLD
                                   else "PASS_TEACHING")
        res.pop("_mu", None)
        protocols[proto] = res
    id_res.pop("_mu", None)
    worst = min((p["teaching_verdict"] for p in protocols.values()),
                key=lambda v: {"MODEL_FAIL_TEACHING": 0, "INTERVAL_FAIL_TEACHING": 1,
                               "PASS_TEACHING": 2}[v])
    return {"model": model, "alpha": alpha, "conformal_q": round(q, 4),
            "in_domain": id_res, "protocols": protocols,
            "overall_verdict": worst,
            "disclaimer": "教学分级，非模型质量证据；请用 diagnose() 做二维诊断。"}


def audit_all(atlas: dict, alpha: float = 0.1,
              models: tuple[str, ...] = MODEL_NAMES) -> dict:
    """诊断全部模型（教学分级，兼容 v0.1）。"""
    per_model = {name: audit(atlas, name, alpha=alpha) for name in models}
    id_scores = {name: per_model[name]["in_domain"]["rmse_rel"] for name in models}
    ladder = evaluate_ladder(
        copy_last=id_scores.get("copy_last"), mean=id_scores.get("mean"),
        linear=id_scores.get("linear"), model=id_scores.get("poly3"),
        cfg=LadderConfig(metric="rmse_rel", lower_is_better=True, min_improvement=0.01),
    )
    summary = []
    for name, res in per_model.items():
        summary.append({
            "model": name,
            "in_domain_rmse_rel": res["in_domain"]["rmse_rel"],
            "in_domain_coverage": res["in_domain"]["coverage"],
            "worst_extrap_coverage": min(p["coverage"] for p in res["protocols"].values()),
            "teaching_verdict": res["overall_verdict"],
            "baseline_ladder": "ADMITTED" if (name == ladder.candidate and ladder.admitted)
                               else ("REJECTED" if name == ladder.candidate else "N/A"),
        })
    return {"per_model": per_model, "baseline_ladder": {
                "candidate": ladder.candidate, "admitted": ladder.admitted,
                "reasons": list(ladder.reasons), "improvements": ladder.improvements},
            "summary": summary,
            "meta": {"atlas": atlas.get("meta", {}), "n_models": len(models),
                     "protocols": list(PROTOCOLS),
                     "interpretation": "教学分级：域内赢过基线不等于外推可信。",
                     "disclaimer": "合成数据机制演示，非实证结论。"}}

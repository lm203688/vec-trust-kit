"""主审计流程：三种外推协议 × 四个基线级别 × conformal 覆盖诊断.

对应 Virtual Embryo Challenge 三个任务：
  unseen_stage          -> T1 时间外推
  unseen_tissue         -> T2 空间-时间外推（组织维度）
  unseen_perturbation   -> T3 敲除效应外推

用法：
    atlas = make_atlas()
    result = audit_all(atlas)
"""
from __future__ import annotations

import numpy as np

from .conformal import conformal_quantile, interval, coverage, w1_proxy, graded_verdict
from .baseline_ladder import LadderConfig, evaluate_ladder, rmse_rel
from .synthetic import MODEL_NAMES, predict_with

PROTOCOLS = ("unseen_stage", "unseen_tissue", "unseen_perturbation")
VERDICT_ORDER = {"REFUTED": 0, "MARGINAL": 1, "PASS_WEAK": 2,
                 "PASS_PARTIAL": 3, "PASS_FULL": 4}


def audit(atlas: dict, model: str, alpha: float = 0.1,
          cal_frac: float = 0.3, seed: int = 0,
          predictor=None) -> dict:
    """对单个模型做完整诊断。

    predictor: 可选的可调用对象 callable(X_fit, y_fit, X_eval) -> (mean, std)。
    不传则用内置基线模型。接自己的模型 / 真实 h5ad 数据时传这个参数。
    """
    if predictor is None:
        predictor = lambda Xf, yf, Xe: predict_with(model, Xf, yf, Xe)
    X_fit_all, y_fit_all = atlas["train"]
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(X_fit_all))
    n_cal = max(10, int(len(perm) * cal_frac))
    idx_cal, idx_fit = perm[:n_cal], perm[n_cal:]
    X_fit, y_fit = X_fit_all[idx_fit], y_fit_all[idx_fit]
    X_cal, y_cal = X_fit_all[idx_cal], y_fit_all[idx_cal]

    mu_cal, sd_cal = predictor(X_fit, y_fit, X_cal)
    cal_scores = np.abs(y_cal - mu_cal) / np.maximum(sd_cal, 1e-8)
    q = conformal_quantile(cal_scores, alpha)

    def evaluate_split(X: np.ndarray, y: np.ndarray) -> dict:
        mu, sd = predictor(X_fit, y_fit, X)
        lo, hi = interval(mu, sd, q)
        cov = coverage(lo, hi, y)
        width = float(np.mean(hi - lo))
        return {"coverage": round(cov, 4), "rmse_rel": round(rmse_rel(mu, y), 4),
                "mean_interval_width": round(width, 4), "_mu": mu}

    id_res = evaluate_split(*atlas["in_domain"])
    id_width = max(id_res["mean_interval_width"], 1e-8)

    protocols: dict[str, dict] = {}
    for proto in PROTOCOLS:
        X, y = atlas[proto]
        res = evaluate_split(X, y)
        res["width_ratio"] = round(res["mean_interval_width"] / id_width, 3)
        res["w1_drift"] = round(w1_proxy(id_res["_mu"].mean(axis=1), res["_mu"].mean(axis=1)), 4)
        verdict, reason = graded_verdict(id_res["coverage"], res["coverage"],
                                         res["width_ratio"], alpha=alpha)
        res["verdict"] = verdict
        res["reason"] = reason
        res.pop("_mu", None)
        protocols[proto] = res
    id_res.pop("_mu", None)

    worst = min((p["verdict"] for p in protocols.values()), key=lambda v: VERDICT_ORDER[v])
    return {
        "model": model,
        "alpha": alpha,
        "conformal_q": round(q, 4),
        "in_domain": id_res,
        "protocols": protocols,
        "overall_verdict": worst,
    }


def audit_all(atlas: dict, alpha: float = 0.1,
              models: tuple[str, ...] = MODEL_NAMES) -> dict:
    """诊断全部模型，并在域内指标上跑基线阶梯。"""
    per_model = {name: audit(atlas, name, alpha=alpha) for name in models}

    # 基线阶梯只看域内 RMSE —— 故意与外推审计分离，暴露两者的冲突
    id_scores = {name: per_model[name]["in_domain"]["rmse_rel"] for name in models}
    ladder = evaluate_ladder(
        copy_last=id_scores.get("copy_last"),
        mean=id_scores.get("mean"),
        linear=id_scores.get("linear"),
        model=id_scores.get("model"),
        cfg=LadderConfig(metric="rmse_rel", lower_is_better=True, min_improvement=0.01),
    )

    summary = []
    for name, res in per_model.items():
        summary.append({
            "model": name,
            "in_domain_rmse_rel": res["in_domain"]["rmse_rel"],
            "in_domain_coverage": res["in_domain"]["coverage"],
            "worst_extrap_coverage": min(p["coverage"] for p in res["protocols"].values()),
            "overall_verdict": res["overall_verdict"],
            "baseline_ladder": "ADMITTED" if (name == ladder.candidate and ladder.admitted)
                               else ("REJECTED" if name == ladder.candidate else "N/A"),
        })

    return {
        "per_model": per_model,
        "baseline_ladder": {
            "candidate": ladder.candidate,
            "admitted": ladder.admitted,
            "reasons": list(ladder.reasons),
            "improvements": ladder.improvements,
        },
        "summary": summary,
        "meta": {
            "atlas": atlas.get("meta", {}),
            "n_models": len(models),
            "protocols": list(PROTOCOLS),
            "interpretation": (
                "基线阶梯只看域内；overall_verdict 看外推覆盖。"
                "两者不一致即'域内赢、外推崩'的典型失效。"
            ),
        },
    }

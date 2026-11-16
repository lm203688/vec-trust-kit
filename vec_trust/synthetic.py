"""可复现的合成"虚拟胚胎图谱"——**教学沙盒，非实证数据**.

> ⚠️ 教学声明：本模块所有数字都是合成机制演示（demo of a mechanism），
> 不是模型评测结论，不可作为"某模型不可信"的实证引用。

设计（相对 v0.1 的关键修正，回应评估需求书 R1/R3）：
    真实表达 = 线性发育趋势 + 扰动/组织效应 + 异方差噪声
    （噪声随发育时间增大）。线性趋势在训练域 stage 0-2 完全可识别，
    因此"正确族 = 线性模型"能安全外推；"错误族 = 三次多项式"会外推爆炸。

    区间尺度的构造方式被显式暴露为第二维度（scale_mode）：
      static   —— 沿用训练残差尺度，不随外推距离增长（漂移下必崩，定理级已知）
      adaptive —— 尺度随外推距离线性放大（模拟异方差/加权 conformal）

    把"模型误差"与"区间构造"两个维度彻底分开，裁决才能区分病因，
    而不是像 v0.1 那样无论换什么模型/区间都恒 REFUTED。
"""
from __future__ import annotations

import numpy as np

STAGES = {"E8.25": 0.0, "E9.0": 0.5, "E9.5": 1.0, "E10.0": 1.5, "E10.5": 2.0}
TRAIN_STAGES = (0.0, 0.5, 1.0, 1.5, 2.0)
TEST_STAGE = 3.5
PERTURBATIONS = ("WT", "KO_A", "KO_B")
TISSUES = ("heart", "embryo")
BASE_NOISE = 0.06
NOISE_GROWTH = 0.35  # 噪声尺度 = BASE_NOISE * (1 + NOISE_GROWTH * stage)


def make_atlas(seed: int = 0, n_per_group: int = 80, n_genes: int = 8) -> dict:
    """生成 dict，含 train / in_domain / 三个外推协议 / 真值参数.

    每个 split 的 X 为 (n, 3) = [stage_time, perturbation_id, tissue_id]，
    y 为 (n, n_genes) 的"基因表达"矩阵。
    """
    rng = np.random.default_rng(seed)
    slope = rng.uniform(0.25, 0.45, n_genes)      # 每基因发育斜率
    intercept = rng.uniform(0.5, 1.5, n_genes)    # 基线表达
    pert_eff = rng.normal(0, 0.15, (len(PERTURBATIONS), n_genes))
    tissue_eff = rng.normal(0, 0.12, (len(TISSUES), n_genes))

    def sample(t: float, p: int, o: int, n: int) -> tuple[np.ndarray, np.ndarray]:
        X = np.column_stack([np.full(n, t), np.full(n, p), np.full(n, o)])
        mu = slope * t + intercept + pert_eff[p] + tissue_eff[o]
        noise_scale = BASE_NOISE * (1 + NOISE_GROWTH * max(t, 0))
        y = np.broadcast_to(mu, (n, n_genes)).copy()
        y += rng.normal(0, noise_scale, y.shape)
        return X, y

    tx, ty = [], []
    for t in TRAIN_STAGES:
        for p in (0, 1):  # 训练只见 WT + KO_A，组织只见 heart
            X, y = sample(t, p, 0, n_per_group)
            tx.append(X); ty.append(y)
    train = (np.vstack(tx), np.vstack(ty))

    return {
        "train": train,
        "in_domain": sample(2.0, 1, 0, n_per_group),                 # 已知 stage/扰动/组织
        "unseen_stage": sample(TEST_STAGE, 0, 0, n_per_group),        # T1 时间外推（主漂移）
        "unseen_perturbation": sample(2.0, 2, 0, n_per_group),        # T3 扰动外推
        "unseen_tissue": sample(2.0, 0, 1, n_per_group),              # T2 组织外推
        "meta": {
            "seed": seed, "n_genes": n_genes, "base_noise": BASE_NOISE,
            "noise_growth": NOISE_GROWTH, "train_stages": list(TRAIN_STAGES),
            "test_stage": TEST_STAGE,
            "true_slope": slope.tolist(), "true_intercept": intercept.tolist(),
            "note": "教学用合成数据。真实机制=线性趋势+异方差噪声；"
                    "正确族(linear)可安全外推，错误族(poly3)外推爆炸。",
        },
    }


def extrap_distance(X_eval: np.ndarray, X_fit: np.ndarray) -> np.ndarray:
    """每个评估点相对训练域的外推距离（0 表示域内）.

    由三部分相加：stage 越界距离 + 未见扰动的类别距离 + 未见组织的类别距离。
    这是 adaptive 区间放大的依据，也是 Rule Guard 思想的简化教学版。
    """
    t = X_fit[:, 0]
    t_lo, t_hi = float(t.min()), float(t.max())
    d = np.maximum(0.0, X_eval[:, 0] - t_hi) + np.maximum(0.0, t_lo - X_eval[:, 0])
    seen_p = set(np.unique(X_fit[:, 1]).tolist())
    seen_o = set(np.unique(X_fit[:, 2]).tolist())
    d = d + np.array([0.0 if int(p) in seen_p else 0.5 for p in X_eval[:, 1]])
    d = d + np.array([0.0 if int(o) in seen_o else 0.5 for o in X_eval[:, 2]])
    return d


def _design(X: np.ndarray, degree: int) -> np.ndarray:
    t, p, o = X[:, 0], X[:, 1], X[:, 2]
    cols = [np.ones(len(t))]
    for d in range(1, degree + 1):
        cols.append(t ** d)
    cols += [p, o]
    return np.column_stack(cols)


def predict_with(name: str, X_fit: np.ndarray, y_fit: np.ndarray,
                 X_eval: np.ndarray, scale_mode: str = "static",
                 atlas: dict | None = None) -> tuple[np.ndarray, np.ndarray]:
    """返回 (mean, std)，形状均为 (n_eval, n_genes).

    name:
      copy_last —— 复制训练末时间点均值（零参数基线）
      mean      —— 训练集全局均值（零参数基线）
      linear    —— 线性模型（**正确族**，真实机制就是线性）
      poly3     —— 三次多项式（**错误族**，域内拟合好但外推爆炸）
      model     —— `poly3` 的向后兼容别名（v0.1 的"招牌模型"）

    scale_mode:
      static    —— std = 训练残差尺度，不随外推距离变化（漂移下必崩，定理已知）
      adaptive  —— std 按 (1 + NOISE_GROWTH * extrap_distance) 放大
                    （模拟异方差/加权 conformal；仅 linear 提供真实自适应尺度）
    """
    if scale_mode not in ("static", "adaptive"):
        raise ValueError("scale_mode 只能是 static / adaptive")
    n_genes = y_fit.shape[1]
    t = X_fit[:, 0]

    if name == "copy_last":
        mask = t == t.max()
        mu = y_fit[mask].mean(axis=0)
        resid_sd = np.maximum(y_fit[mask].std(axis=0, ddof=1), 1e-3)
    elif name == "mean":
        mu = y_fit.mean(axis=0)
        resid_sd = np.maximum(y_fit.std(axis=0, ddof=1), 1e-3)
    elif name in ("linear", "poly3", "model"):
        degree = 3 if name in ("poly3", "model") else 1
        A = _design(X_fit, degree)
        coef, *_ = np.linalg.lstsq(A, y_fit, rcond=None)
        mu = _design(X_eval, degree) @ coef
        resid_sd = np.maximum((y_fit - A @ coef).std(axis=0, ddof=1), 1e-3)
    else:
        raise ValueError(f"未知模型 {name}，可选 copy_last / mean / linear / poly3 / model")

    mu = np.broadcast_to(mu, (len(X_eval), n_genes)).copy()
    if scale_mode == "adaptive":
        d = extrap_distance(X_eval, X_fit)
        sd = resid_sd[None, :] * (1 + NOISE_GROWTH * d[:, None])
    else:
        sd = np.broadcast_to(resid_sd, (len(X_eval), n_genes)).copy()
    return mu, np.maximum(sd, 1e-4)


MODEL_NAMES = ("copy_last", "mean", "linear", "poly3")
CORRECT_MODEL = "linear"   # 负控：正确族，应得到非 REFUTED
WRONG_MODEL = "poly3"      # 正控：错误族，应 REFUTED

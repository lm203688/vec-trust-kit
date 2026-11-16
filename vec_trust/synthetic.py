"""可复现的合成"虚拟胚胎图谱"，用于零依赖演示与自测.

刻意构造一个陷阱：真实表达随发育时间饱和（sigmoid），
而一个高阶多项式模型在训练域内拟合得比线性基线更好（基线阶梯 ADMIT），
但在时间外推区因无法饱和而误差爆炸、预测区间覆盖崩塌（conformal 审计 REFUTED）。

这正是 Community Contribution 想传达的核心教训：
    "域内赢过基线" 不等于 "外推可信"。
"""
from __future__ import annotations

import numpy as np

STAGES = {"E8.25": 0.0, "E9.5": 1.0, "E10.5": 2.0, "E12.5": 4.0}
PERTURBATIONS = ("WT", "KO_A", "KO_B")
TISSUES = ("heart", "embryo")


def _expit(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))


def make_atlas(seed: int = 0, n_per_group: int = 80, n_genes: int = 8) -> dict:
    """生成 dict，含 train / in_domain / unseen_stage / unseen_perturbation / unseen_tissue.

    每个 split 的 X 为 (n, 3) = [stage_time, perturbation_id, tissue_id]，
    y 为 (n, n_genes) 的"基因表达"矩阵。
    """
    rng = np.random.default_rng(seed)
    center = rng.uniform(1.2, 3.0, n_genes)
    scale = rng.uniform(0.45, 1.0, n_genes)
    amp = rng.uniform(0.8, 2.0, n_genes)
    pert_eff = rng.normal(0, 0.18, (len(PERTURBATIONS), n_genes))
    tissue_eff = rng.normal(0, 0.15, (len(TISSUES), n_genes))

    def sample(t: float, p: int, o: int, n: int) -> tuple[np.ndarray, np.ndarray]:
        X = np.column_stack([
            np.full(n, t), np.full(n, p), np.full(n, o),
        ])
        y = amp * _expit((t - center) / scale) + pert_eff[p] + tissue_eff[o]
        y = np.broadcast_to(y, (n, n_genes)).copy()
        y += rng.normal(0, 0.08, y.shape)
        return X, y

    # 训练域：stage 0/1/2，WT + KO_A，heart only
    tx, ty = [], []
    for t in (0.0, 1.0, 2.0):
        for p in (0, 1):
            X, y = sample(t, p, 0, n_per_group)
            tx.append(X); ty.append(y)
    train = (np.vstack(tx), np.vstack(ty))

    return {
        "train": train,
        "in_domain": sample(2.0, 1, 0, n_per_group),          # 已知 stage/扰动/组织
        "unseen_stage": sample(4.0, 0, 0, n_per_group),       # T1 时间外推
        "unseen_perturbation": sample(2.0, 2, 0, n_per_group),  # T3 扰动外推
        "unseen_tissue": sample(2.0, 0, 1, n_per_group),      # T2 组织外推
        "meta": {
            "seed": seed, "n_genes": n_genes, "noise_std": 0.08,
            "train_stages": [0.0, 1.0, 2.0],
            "note": "真实表达为 sigmoid 饱和；高阶多项式在外推区会失控",
        },
    }


# ---------------------------------------------------------------------------
# 四个基线/模型：统一返回 (mean, std)，std 从训练集残差估计，外推时不重新校准
# ---------------------------------------------------------------------------
def _design(X: np.ndarray, degree: int) -> np.ndarray:
    t, p, o = X[:, 0], X[:, 1], X[:, 2]
    cols = [np.ones(len(t))]
    for d in range(1, degree + 1):
        cols.append(t ** d)
    cols += [p, o]
    return np.column_stack(cols)


def predict_with(name: str, X_fit: np.ndarray, y_fit: np.ndarray,
                 X_eval: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """返回 (mean, std)，形状均为 (n_eval, n_genes).

    std 估计刻意**不随外推距离变化**——这正是 conformal 覆盖崩塌的机制：
    区间宽度沿用校准集的分布内尺度，而真实误差在漂移后变大。
    """
    n_genes = y_fit.shape[1]
    if name == "copy_last":
        mask = X_fit[:, 0] == X_fit[:, 0].max()
        mu = y_fit[mask].mean(axis=0)
        std = y_fit[mask].std(axis=0, ddof=1) / np.sqrt(max(mask.sum(), 2))
    elif name == "mean":
        mu = y_fit.mean(axis=0)
        std = y_fit.std(axis=0, ddof=1) / np.sqrt(len(y_fit))
    elif name in ("linear", "model"):
        degree = 1 if name == "linear" else 3
        A = _design(X_fit, degree)
        coef, *_ = np.linalg.lstsq(A, y_fit, rcond=None)
        pred = _design(X_eval, degree) @ coef
        mu = pred
        resid = y_fit - A @ coef
        std = np.maximum(resid.std(axis=0, ddof=1), 1e-3) / np.sqrt(len(y_fit)) * 10
    else:
        raise ValueError(f"未知模型 {name}，可选 copy_last / mean / linear / model")

    mu = np.broadcast_to(mu, (len(X_eval), n_genes)).copy()
    std = np.broadcast_to(std, (len(X_eval), n_genes)).copy()
    return mu, np.maximum(std, 1e-4)


MODEL_NAMES = ("copy_last", "mean", "linear", "model")

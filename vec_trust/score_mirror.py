"""Score Mirror（本地近似打分）——**非官方 scorer，不可当作榜单分数**.

> ⚠️ 诚实声明（回应评估需求书 R2 的关键约束）：
>   本模块依据 2026-11-16 官网公开的指标名称与权重，实现一套**结构相同但实现独立**
>   的本地近似打分。我们没有官方 starter kit 的评测源码，因此：
>     - 不能声称与官方榜差异 <5 分（那需要真值验证集 + 官方代码交叉校准）
>     - 输出只用于"相对比较 / 找最弱项 / 是否过 floor 的粗略自查"
>     - 官方分数以赛事 scorer 为准
>
> 官方刻度（2026-11-16 官网，来源见评估需求书附录 A）：
>   T1 四项：DE 基因回收 25% / 变化方向 25% / 细胞状态分布 30% / 基因共变 20%
>   T2 四项：表达变化 25% / 细胞状态分布 25% / 组织形状与生长尺度 25% / 局部空间组织 25%
>   T3 五项：响应基因回收 30% / 方向 25% / 幅度 25% / 细胞状态分布 20%（官网称五项、列四项）
>   归一化：floor=50、ceiling=100；三任务需合计 >150 才有资格获奖。
"""
from __future__ import annotations

from dataclasses import dataclass

# 官方指标权重（2026-11-16 快照）
T1_WEIGHTS = {"de_recovery": 0.25, "direction": 0.25,
              "state_distribution": 0.30, "gene_covariance": 0.20}
T2_WEIGHTS = {"expression_change": 0.25, "state_distribution": 0.25,
              "shape_growth": 0.25, "local_organization": 0.25}
T3_WEIGHTS = {"response_recovery": 0.30, "direction": 0.25,
              "amplitude": 0.25, "state_distribution": 0.20}
TASK_WEIGHTS = {"T1": T1_WEIGHTS, "T2": T2_WEIGHTS, "T3": T3_WEIGHTS}

FLOOR = 50.0
CEILING = 100.0
FLOOR_TOTAL = 150.0

DISCLAIMER = (
    "本地近似打分（非官方 scorer）：指标名称与权重对齐官网 2026-11-16 快照，"
    "但实现独立、未经官方真值校准。仅供自查与找最弱项，官方分数以赛事 scorer 为准。"
)


@dataclass(frozen=True)
class MirrorResult:
    task: str
    raw_score: float            # 0-1 的加权原始分
    official_scale: float       # 归一化到 50-100
    per_metric: dict[str, float]
    weakest_metric: str
    above_floor: bool
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict:
        return {"task": self.task, "raw_score": round(self.raw_score, 4),
                "official_scale": round(self.official_scale, 2),
                "per_metric": {k: round(v, 4) for k, v in self.per_metric.items()},
                "weakest_metric": self.weakest_metric,
                "above_floor": self.above_floor, "disclaimer": self.disclaimer}


def to_official_scale(raw: float) -> float:
    """把 0-1 原始分线性映射到 floor=50 / ceiling=100 刻度。"""
    raw = min(max(raw, 0.0), 1.0)
    return FLOOR + (CEILING - FLOOR) * raw


# --- 各指标的本地近似实现（纯 numpy，输入为 ndarray）-------------------------
def de_recovery(pred_delta, true_delta, top_k=None):
    """DE 基因回收：预测的差异表达基因里命中真实 DE 的比例（近似 recall）.

    pred_delta / true_delta: (n_genes,) 或 (n_cells, n_genes) 的变化量。
    """
    import numpy as np
    p = np.abs(np.asarray(pred_delta, float)).mean(axis=0).ravel()
    t = np.abs(np.asarray(true_delta, float)).mean(axis=0).ravel()
    k = top_k or max(1, int(0.1 * len(t)))
    true_top = set(np.argsort(-t)[:k].tolist())
    pred_top = np.argsort(-p)[:k].tolist()
    if not true_top:
        return 1.0
    return len(true_top.intersection(pred_top)) / k


def direction_accuracy(pred_delta, true_delta):
    """变化方向一致率：预测与真实变化符号一致的比例。"""
    import numpy as np
    p = np.asarray(pred_delta, float).mean(axis=0).ravel()
    t = np.asarray(true_delta, float).mean(axis=0).ravel()
    mask = np.abs(t) > 1e-8
    if not mask.any():
        return 1.0
    return float(np.mean(np.sign(p[mask]) == np.sign(t[mask])))


def state_distribution_score(pred_cells, true_cells, n_bins=20):
    """细胞状态分布相似度：1 - 总变差距离（一维投影的近似，非官方 ED/MMD）."""
    import numpy as np
    p = np.asarray(pred_cells, float).mean(axis=1).ravel()
    t = np.asarray(true_cells, float).mean(axis=1).ravel()
    lo, hi = float(min(p.min(), t.min())), float(max(p.max(), t.max()))
    if hi - lo < 1e-8:
        return 1.0
    edges = np.linspace(lo, hi, n_bins + 1)
    hp, _ = np.histogram(p, bins=edges, density=True)
    ht, _ = np.histogram(t, bins=edges, density=True)
    hp, ht = hp / max(hp.sum(), 1e-8), ht / max(ht.sum(), 1e-8)
    tvd = 0.5 * np.abs(hp - ht).sum()
    return float(max(0.0, 1.0 - tvd))


def gene_covariance_score(pred_cells, true_cells):
    """基因共变结构相似度：相关矩阵的上三角余弦相似度（近似）."""
    import numpy as np
    p, t = np.asarray(pred_cells, float), np.asarray(true_cells, float)
    if p.shape[1] < 2:
        return 1.0
    # 常数列会让 corrcoef 产生除零警告；先剔除零方差列再算
    keep_p = p.std(axis=0) > 1e-12
    keep_t = t.std(axis=0) > 1e-12
    if keep_p.sum() < 2 or keep_t.sum() < 2:
        return 1.0
    cp = np.corrcoef(p[:, keep_p], rowvar=False)
    ct = np.corrcoef(t[:, keep_t], rowvar=False)
    cp = np.nan_to_num(cp); ct = np.nan_to_num(ct)
    if cp.shape != ct.shape:
        return 0.5  # 有效列数不同，无法对齐比较
    iu = np.triu_indices_from(cp, k=1)
    a, b = cp[iu], ct[iu]
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(max(0.0, np.dot(a, b) / denom)) if denom > 1e-8 else 1.0


def amplitude_score(pred_delta, true_delta):
    """幅度一致性：1 - 相对幅度误差（T3 用）. """
    import numpy as np
    p = np.abs(np.asarray(pred_delta, float)).mean()
    t = np.abs(np.asarray(true_delta, float)).mean()
    if t < 1e-8:
        return 1.0 if p < 1e-8 else 0.0
    return float(max(0.0, 1.0 - abs(p - t) / t))


def mirror_score(task: str, *, pred_delta=None, true_delta=None,
                 pred_cells=None, true_cells=None,
                 shape_pred=None, shape_true=None) -> MirrorResult:
    """计算单任务的本地近似分。

    各任务用得到的指标不同；没有提供的指标按该任务权重重新归一化。
    ⚠️ 缺失指标重归一化会让分数偏乐观——报告里必须标注哪些指标没算。
    """
    import numpy as np
    if task not in TASK_WEIGHTS:
        raise ValueError(f"未知任务 {task}，可选 {list(TASK_WEIGHTS)}")
    weights = TASK_WEIGHTS[task]

    scores: dict[str, float] = {}
    if task == "T1":
        if pred_delta is not None and true_delta is not None:
            scores["de_recovery"] = de_recovery(pred_delta, true_delta)
            scores["direction"] = direction_accuracy(pred_delta, true_delta)
        if pred_cells is not None and true_cells is not None:
            scores["state_distribution"] = state_distribution_score(pred_cells, true_cells)
            scores["gene_covariance"] = gene_covariance_score(pred_cells, true_cells)
    elif task == "T2":
        if pred_delta is not None and true_delta is not None:
            scores["expression_change"] = 1.0 - min(1.0, float(
                np.abs(np.asarray(pred_delta) - np.asarray(true_delta)).mean()))
        if pred_cells is not None and true_cells is not None:
            scores["state_distribution"] = state_distribution_score(pred_cells, true_cells)
            scores["local_organization"] = gene_covariance_score(pred_cells, true_cells)
        if shape_pred is not None and shape_true is not None:
            sp, st = np.asarray(shape_pred, float), np.asarray(shape_true, float)
            scores["shape_growth"] = float(max(0.0, 1.0 - abs(sp.mean() - st.mean())
                                               / max(abs(st.mean()), 1e-8)))
    elif task == "T3":
        if pred_delta is not None and true_delta is not None:
            scores["response_recovery"] = de_recovery(pred_delta, true_delta)
            scores["direction"] = direction_accuracy(pred_delta, true_delta)
            scores["amplitude"] = amplitude_score(pred_delta, true_delta)
        if pred_cells is not None and true_cells is not None:
            scores["state_distribution"] = state_distribution_score(pred_cells, true_cells)

    if not scores:
        raise ValueError("没有提供任何可用于打分的输入")
    # 用已算指标的权重重新归一化（缺失指标偏乐观，需标注）
    used_w = {k: weights[k] for k in scores}
    wsum = sum(used_w.values())
    raw = sum(scores[k] * used_w[k] for k in scores) / wsum
    weakest = min(scores, key=lambda k: scores[k])
    return MirrorResult(task=task, raw_score=raw, official_scale=to_official_scale(raw),
                        per_metric=scores, weakest_metric=weakest,
                        above_floor=raw > 0.0,
                        disclaimer=DISCLAIMER + f" 本任务已算指标：{list(scores)}；"
                        f"缺失指标已重归一化，分数偏乐观。")

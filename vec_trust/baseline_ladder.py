"""基线阶梯：复杂模型必须击败更简单基线才允许被采纳.

来源：SwarmLabs engine/baseline_ladder.py（MIT），迁移时保留准入规则，
把级别命名改为虚拟细胞/胚胎任务语境。

阶梯（简单 -> 复杂）：
  L0 copy_last —— 复制上一时间点/上一观测（零参数）
  L1 mean     —— 训练集全局均值（零参数）
  L2 linear   —— 线性回归（纯数据驱动）
  L3 model    —— 基础模型 / 非线性模型

准入规则：最高级模型必须在预注册指标上严格击败**每一个**更低级基线，
 Improvement < min_improvement 即拒绝。这直接对应 Nature Methods 2025
 基准「部分方法不优于一行线性基线」的教训。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

LEVELS = ("copy_last", "mean", "linear", "model")
LEVEL_RANK = {name: i for i, name in enumerate(LEVELS)}


@dataclass(frozen=True)
class LadderConfig:
    metric: str = "rmse_rel"
    lower_is_better: bool = True
    min_improvement: float = 0.01  # 真实实验建议 0.03-0.05，避免过claim


@dataclass(frozen=True)
class LadderVerdict:
    candidate: str
    admitted: bool
    reasons: tuple[str, ...]
    improvements: dict[str, float] = field(default_factory=dict)
    rejected_by: Optional[str] = None


def _strict_beats(new: float, base: float, cfg: LadderConfig) -> tuple[bool, float]:
    if cfg.lower_is_better:
        improvement = base - new
    else:
        improvement = new - base
    return improvement >= cfg.min_improvement, improvement


def evaluate_ladder(
    copy_last: float,
    mean: Optional[float] = None,
    linear: Optional[float] = None,
    model: Optional[float] = None,
    cfg: Optional[LadderConfig] = None,
) -> LadderVerdict:
    cfg = cfg or LadderConfig()
    levels: dict[str, float] = {"copy_last": copy_last}
    for name, val in (("mean", mean), ("linear", linear), ("model", model)):
        if val is not None:
            levels[name] = float(val)

    candidate = max(levels, key=lambda k: LEVEL_RANK[k])
    cand_val = levels[candidate]
    cand_rank = LEVEL_RANK[candidate]

    improvements: dict[str, float] = {}
    reasons: list[str] = []
    rejected_by = None
    for other, other_val in levels.items():
        if other == candidate or LEVEL_RANK[other] >= cand_rank:
            continue
        beats, improvement = _strict_beats(cand_val, other_val, cfg)
        improvements[other] = round(improvement, 6)
        if not beats:
            rejected_by = other
            reasons.append(
                f"{candidate} ({cand_val:.4f}) 未严格击败 {other} ({other_val:.4f})，"
                f"改善 {improvement:+.4f} < 门槛 {cfg.min_improvement}"
            )

    admitted = rejected_by is None
    if admitted:
        reasons.append(f"{candidate} 击败全部更低级基线，准入")
    return LadderVerdict(candidate, admitted, tuple(reasons), improvements, rejected_by)


def rmse_rel(pred: "object", y_true: "object") -> float:
    """相对 RMSE = RMSE / y_true 的标准差（无量纲，跨基因可比）。"""
    import numpy as np
    p = np.asarray(pred, dtype=float)
    y = np.asarray(y_true, dtype=float)
    denom = max(float(np.std(y)), 1e-8)
    return float(np.sqrt(np.mean((p - y) ** 2)) / denom)

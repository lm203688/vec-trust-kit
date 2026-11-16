"""Split conformal 预测区间与失效分级判定.

来源：SwarmLabs engine/conformal.py 与 outputs/swarmlabs-conformal-audit/scripts/verify.py
（MIT, Copyright 2026 lm203688 / SwarmLabs），为虚拟细胞/胚胎场景改写为模型无关接口。

关键前提：split conformal 的有限样本覆盖保证依赖 exchangeability（校准集与测试集同分布）。
本模块的存在意义就是**暴露这个前提被破坏时的覆盖崩塌**，而不是假装区间永远有效。
"""
from __future__ import annotations

import numpy as np

MARGINAL_FLOOR = 0.7  # 0.7 * nominal coverage 是 PASS_WEAK / REFUTED 的边界
SPURIOUS_WIDTH_RATIO = 10.0  # 覆盖率虚高但区间宽 10x 以上 -> 判定为无效通过


def conformal_quantile(cal_scores: np.ndarray, alpha: float) -> float:
    """有限样本校正的 (1-alpha) 分位数，公式 ceil((n+1)(1-alpha))/n."""
    scores = np.asarray(cal_scores, dtype=float).ravel()
    scores = scores[np.isfinite(scores)]
    if scores.size == 0:
        raise ValueError("校准分数为空或全为 NaN")
    n = scores.size
    level = min(np.ceil((n + 1) * (1.0 - alpha)) / n, 1.0)
    return float(np.quantile(scores, level))


def interval(mean: np.ndarray, std: np.ndarray, q: float) -> tuple[np.ndarray, np.ndarray]:
    """对称区间 mean +/- q*std。std 为模型自身的尺度估计（如 GP 标准差）。"""
    mean = np.asarray(mean, dtype=float)
    std = np.asarray(std, dtype=float)
    return mean - q * std, mean + q * std


def coverage(lo: np.ndarray, hi: np.ndarray, y_true: np.ndarray) -> float:
    """经验覆盖率。多维输入时按所有元素一起计算。"""
    lo, hi, y = np.asarray(lo), np.asarray(hi), np.asarray(y_true)
    return float(np.mean((y >= lo) & (y <= hi)))


def w1_proxy(a: np.ndarray, b: np.ndarray) -> float:
    """一维经验 Wasserstein-1 代理：分位数曲线的平均绝对差。

    不是精确 W1，只用于排序/比较漂移强度，不做统计检验。
    """
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    if a.size == 0 or b.size == 0:
        return float("nan")
    qs = np.linspace(0.02, 0.98, min(len(a), len(b), 100))
    return float(np.mean(np.abs(np.quantile(a, qs) - np.quantile(b, qs))))


def graded_verdict(
    in_domain_cov: float,
    extrap_cov: float,
    width_ratio: float,
    alpha: float = 0.1,
    wet_lab_anchor: bool = False,
) -> tuple[str, str]:
    """分级判定。返回 (等级, 理由)。

    等级：PASS_FULL > PASS_PARTIAL > PASS_WEAK > MARGINAL > REFUTED
    注意 PASS_FULL 需要 wet_lab_anchor=True；纯计算模拟最多 PASS_PARTIAL。
    """
    nominal = 1.0 - alpha
    floor = MARGINAL_FLOOR * nominal

    # 先查"虚假通过"：覆盖率虚高但区间宽得离谱 -> 不是模型好，是区间没信息量。
    # 注意阈值不能写 nominal+0.1：alpha=0.1 时该值为 1.0，永远无法触发。
    if extrap_cov > nominal + 0.05 and width_ratio > SPURIOUS_WIDTH_RATIO:
        return "REFUTED", (
            f"虚假通过：外推覆盖 {extrap_cov:.3f} > 标称 {nominal:.3f} "
            f"但区间宽度比 {width_ratio:.1f}x，区间已失去分辨力"
        )
    if extrap_cov < floor:
        return "REFUTED", (
            f"外推覆盖 {extrap_cov:.3f} < 0.7×标称 {floor:.3f}，"
            f"conformal 保证在漂移下失效（exchangeability 被破坏）"
        )
    if in_domain_cov >= nominal and extrap_cov >= nominal:
        if wet_lab_anchor:
            return "PASS_FULL", f"域内 {in_domain_cov:.3f} / 外推 {extrap_cov:.3f} 均达标且有湿实验锚点"
        return "PASS_PARTIAL", f"域内 {in_domain_cov:.3f} / 外推 {extrap_cov:.3f} 均达标，但无湿实验锚点"
    if in_domain_cov >= nominal and extrap_cov >= floor:
        return "PASS_WEAK", f"域内达标 {in_domain_cov:.3f}，外推降级 {extrap_cov:.3f}（仍在 0.7×标称之上）"
    if in_domain_cov >= floor:
        return "MARGINAL", f"域内覆盖 {in_domain_cov:.3f} 介于 0.7×标称与标称之间，边界情况"
    return "REFUTED", f"域内覆盖 {in_domain_cov:.3f} < 0.7×标称，模型在训练分布内就不可靠"

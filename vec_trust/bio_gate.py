"""Bio Gate（生物学合理性门）——通用 conformal 工具做不出来的差异化.

回应评估需求书 R11。官网 T1 明说考点是"新细胞状态的出现"而非"旧状态的位移"，
T2 的 25% 独立权重给几何。逐元素 RMSE 完全看不到这些。本模块实现五道门：

  G1 组成比例：细胞类型占比与先验的偏差
  G2 marker 程序：关键 marker 基因是否在对应类型中高表达
  G3 空间连续性：3D 邻域内表达的相关性（相邻细胞应相似）
  G4 生长尺度：组织总细胞数/体积的量级一致性
  G5 谱系有序性：分化不能跳级（早期 marker 应先于晚期）

每道门有可复现阈值 + 正负样例（见 tests）。输出"哪道门最弱"。
> ⚠️ 阈值是教学用默认值，真实场景应按先验数据校准。
"""
from __future__ import annotations

from dataclasses import dataclass, field

DISCLAIMER = "Bio Gate 阈值为教学默认值，需按具体组织的先验数据校准；输出为诊断线索，非官方评分。"


@dataclass
class GateResult:
    gate: str
    score: float        # 0-1，越高越好
    passed: bool
    detail: str

    def to_dict(self) -> dict:
        return {"gate": self.gate, "score": round(self.score, 4),
                "passed": self.passed, "detail": self.detail}


@dataclass
class BioReport:
    gates: list[GateResult] = field(default_factory=list)

    @property
    def weakest(self) -> GateResult | None:
        return min(self.gates, key=lambda g: g.score) if self.gates else None

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.gates)

    def to_dict(self) -> dict:
        return {"passed": self.passed,
                "weakest": self.weakest.gate if self.weakest else None,
                "gates": [g.to_dict() for g in self.gates],
                "disclaimer": DISCLAIMER}


def composition_gate(pred_labels, prior: dict, *, tol: float = 0.15) -> GateResult:
    """G1 组成比例：预测类型占比与先验的最大绝对偏差 ≤ tol 则通过。"""
    import numpy as np
    labels = np.asarray(pred_labels).ravel()
    n = len(labels)
    freq = {k: float(np.mean(labels == k)) for k in prior}
    devs = [abs(freq.get(k, 0.0) - prior[k]) for k in prior]
    max_dev = max(devs) if devs else 1.0
    return GateResult("G1_composition", max(0.0, 1 - max_dev / max(tol * 2, 1e-8)),
                      max_dev <= tol, f"最大占比偏差 {max_dev:.3f} > tol {tol}" if max_dev > tol
                      else f"最大占比偏差 {max_dev:.3f} 在容差内")


def marker_gate(expression, labels, marker_genes: dict, *, min_fold: float = 1.3) -> GateResult:
    """G2 marker 程序：每个类型的 marker 基因在该类型中应显著高于其他类型。

    expression: (n_cells, n_genes); labels: (n_cells,); marker_genes: {label: [gene_idx]}
    """
    import numpy as np
    X = np.asarray(expression, float)
    lab = np.asarray(labels).ravel()
    ratios = []
    # 用组内/组间均值差除以全局标准差（对均值为负或接近 0 的表达也稳健），
    # 避免 fold-change 比值在分母趋零或符号相反时爆炸/失真。
    global_sd = float(X.std()) + 1e-8
    effects = []
    for label, genes in marker_genes.items():
        in_mask, out_mask = lab == label, lab != label
        if not in_mask.any() or not out_mask.any() or not genes:
            continue
        for g in genes:
            if g >= X.shape[1]:
                continue
            in_mean = float(X[in_mask, g].mean())
            out_mean = float(X[out_mask, g].mean())
            effects.append((in_mean - out_mean) / global_sd)  # 标准化效应量
    if not effects:
        return GateResult("G2_marker", 0.5, False, "无有效 marker 可检验")
    min_effect = min(effects)
    min_fold_effect = min_fold - 1.0  # fold 1.3 → 效应量阈值 0.3
    score = float(np.clip((min_effect - min_fold_effect + 0.5) / 1.0, 0.0, 1.0))
    return GateResult("G2_marker", score, min_effect >= min_fold_effect,
                      f"最小 marker 标准化效应量 {min_effect:.2f} "
                      f"{'<' if min_effect < min_fold_effect else '>='} {min_fold_effect:.2f}")


def spatial_continuity_gate(expression, coords, *, k: int = 6,
                            min_corr: float = 0.3) -> GateResult:
    """G3 空间连续性：每个细胞与 k 近邻的平均表达相关性应高于阈值.

    coords: (n_cells, 3)。无坐标时返回 SKIP 语义（score=0.5, passed=True）。
    """
    import numpy as np
    X = np.asarray(expression, float)
    C = np.asarray(coords, float)
    if C.ndim != 2 or C.shape[1] < 3 or len(C) != len(X):
        return GateResult("G3_spatial", 0.5, True, "无有效 3D 坐标，跳过")
    n = len(C)
    if n <= k + 1:
        return GateResult("G3_spatial", 0.5, True, "细胞数过少，跳过")
    # 成对距离（n 通常不大；教学用）
    d2 = ((C[:, None, :] - C[None, :, :]) ** 2).sum(axis=-1)
    np.fill_diagonal(d2, np.inf)
    nn = np.argsort(d2, axis=1)[:, :k]
    corrs = []
    for i in range(n):
        a = X[i]
        if np.std(a) < 1e-8:
            continue
        for j in nn[i]:
            b = X[j]
            if np.std(b) < 1e-8:
                continue
            corrs.append(float(np.corrcoef(a, b)[0, 1]))
    corrs = [c for c in corrs if np.isfinite(c)]
    if not corrs:
        return GateResult("G3_spatial", 0.5, True, "无法计算邻域相关性，跳过")
    mean_corr = float(np.mean(corrs))
    return GateResult("G3_spatial", max(0.0, mean_corr),
                      mean_corr >= min_corr,
                      f"k={k} 近邻平均表达相关 {mean_corr:.3f} "
                      f"{'<' if mean_corr < min_corr else '>='} {min_corr}")


def growth_scale_gate(pred_cellcount, prior_count, *, max_ratio: float = 1.5) -> GateResult:
    """G4 生长尺度：预测组织细胞数的量级应与先验一致（比值不超过 max_ratio）. """
    import numpy as np
    ratio = float(pred_cellcount) / max(float(prior_count), 1e-8)
    ok = (1 / max_ratio) <= ratio <= max_ratio
    score = max(0.0, 1 - abs(np.log(max(ratio, 1e-8))) / np.log(max_ratio))
    return GateResult("G4_growth", score, ok,
                      f"细胞数比 {ratio:.2f}，允许 [1/{max_ratio}, {max_ratio}]")


def lineage_order_gate(early_marker_mean, late_marker_mean, *, require_early_higher: bool = True) -> GateResult:
    """G5 谱系有序性：早期 marker 应高于晚期（未分化状态不该提前表达晚期程序）.

    传入标量或数组：早期/晚期 marker 的平均表达。
    """
    import numpy as np
    e = float(np.mean(early_marker_mean)); l = float(np.mean(late_marker_mean))
    ok = (e > l) if require_early_higher else (l > e)
    return GateResult("G5_lineage", 1.0 if ok else 0.0, ok,
                      f"早期 marker {e:.3f} vs 晚期 {l:.3f}，"
                      f"{'满足' if ok else '违反'}分化顺序")


def run_all(*, pred_labels=None, prior=None, expression=None, labels=None,
            marker_genes=None, coords=None, pred_cellcount=None, prior_count=None,
            early=None, late=None) -> BioReport:
    """跑所有提供了输入的门，返回报告（含最弱门）。"""
    gates = []
    if pred_labels is not None and prior is not None:
        gates.append(composition_gate(pred_labels, prior))
    if expression is not None and labels is not None and marker_genes:
        gates.append(marker_gate(expression, labels, marker_genes))
    if expression is not None and coords is not None:
        gates.append(spatial_continuity_gate(expression, coords))
    if pred_cellcount is not None and prior_count is not None:
        gates.append(growth_scale_gate(pred_cellcount, prior_count))
    if early is not None and late is not None:
        gates.append(lineage_order_gate(early, late))
    if not gates:
        gates.append(GateResult("NONE", 0.0, False, "未提供任何门所需的输入"))
    return BioReport(gates=gates)


def render_report(rep: BioReport) -> str:
    lines = ["生物学合理性门（Bio Gate）", f"总判定：{'PASS' if rep.passed else 'FAIL'}", ""]
    for g in rep.gates:
        flag = "✓" if g.passed else "✗"
        lines.append(f"  {flag} {g.gate}: score={g.score:.3f} - {g.detail}")
    if rep.weakest:
        lines += ["", f"最弱门：{rep.weakest.gate} ({rep.weakest.score:.3f})", "", DISCLAIMER]
    return "\n".join(lines)

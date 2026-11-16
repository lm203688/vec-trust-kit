"""Format Precheck（提交格式预检）——本地自查，替代一次上传等待.

回应评估需求书 R10。官方格式检查免费无限次，但只在提交时给结论；
本地预检省一次上传。与官方 format check 一致率无法声称 ≥95%（无官方样例可验证），
本模块按公开格式契约实现，输出为"线索"而非官方结论。

格式契约（来自官网公开信息，见评估需求书）：
  - .X 基因顺序需与参考一致
  - 细胞数在合理范围
  - obsm["spatial_3D"] 存在（T2/T3 需要）
  - 无缺失值 / NaN
  - 文件 ≤ 1200 MB
  - 无标签列（不得夹带 ground truth）

依赖：anndata 可选。装了就验证真实 h5ad；没装则做文件大小/后缀的降级检查并明确提示。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

MAX_FILE_MB = 1200.0
DISCLAIMER = (
    "格式预检为本地自查（按公开格式契约实现），非官方 format check 结论；"
    "最终以赛事提交系统的格式校验为准。"
)


@dataclass
class Check:
    name: str
    status: str   # PASS / FAIL / SKIP / WARN
    detail: str

    def to_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "detail": self.detail}


@dataclass
class FormatReport:
    path: str
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.status != "FAIL" for c in self.checks)

    def to_dict(self) -> dict:
        return {"path": self.path, "passed": self.passed,
                "checks": [c.to_dict() for c in self.checks],
                "disclaimer": DISCLAIMER}


def precheck(path: str | Path, *, task: str = "T1",
             expected_genes: list[str] | None = None) -> FormatReport:
    """对 h5ad 提交文件做格式预检。

    task: T1/T2/T3，决定是否强制检查 spatial_3D
    expected_genes: 参考基因顺序（提供时校验 .var_names 顺序）
    """
    p = Path(path)
    rep = FormatReport(path=str(p))

    # 1) 文件存在 + 后缀
    if not p.exists():
        rep.checks.append(Check("exists", "FAIL", f"文件不存在：{p}"))
        return rep
    rep.checks.append(Check("exists", "PASS", "文件存在"))

    # 2) 文件大小
    mb = p.stat().st_size / (1024 * 1024)
    if mb > MAX_FILE_MB:
        rep.checks.append(Check("size", "FAIL", f"{mb:.1f} MB > {MAX_FILE_MB} MB 上限"))
    else:
        rep.checks.append(Check("size", "PASS", f"{mb:.1f} MB"))

    # 3) 后缀
    if p.suffix.lower() != ".h5ad":
        rep.checks.append(Check("extension", "WARN", f"后缀 {p.suffix} 非 .h5ad"))
    else:
        rep.checks.append(Check("extension", "PASS", ".h5ad"))

    # 4-6) 需要 anndata 的深度检查
    try:
        import anndata as ad  # type: ignore
    except ImportError:
        rep.checks.append(Check("anndata_deep_check", "SKIP",
                                "未安装 anndata，无法检查 .X 顺序/缺失值/spatial_3D/标签列。"
                                "请 pip install anndata 后重跑，或以官方格式校验为准。"))
        return rep

    try:
        a = ad.read_h5ad(p, backed="r")
    except Exception as e:
        rep.checks.append(Check("readable", "FAIL", f"无法读取 h5ad：{e}"))
        return rep
    rep.checks.append(Check("readable", "PASS", "h5ad 可读取"))

    n_cells, n_genes = a.shape
    rep.checks.append(Check("shape", "PASS" if n_cells > 0 and n_genes > 0 else "FAIL",
                            f"细胞数={n_cells}, 基因数={n_genes}"))

    # 基因顺序
    if expected_genes:
        actual = list(a.var_names)
        if actual == list(expected_genes):
            rep.checks.append(Check("gene_order", "PASS", f"{n_genes} 个基因顺序一致"))
        else:
            rep.checks.append(Check("gene_order", "FAIL",
                                    "基因顺序/名称与参考不一致，请按官方 .var_names 重排"))
    else:
        rep.checks.append(Check("gene_order", "SKIP", "未提供参考基因顺序，跳过（提供 expected_genes 可校验）"))

    # 缺失值（抽样检查前若干列，避免全表载入）
    try:
        sample = a.X[: min(2000, n_cells), : min(200, n_genes)]
        import numpy as np
        arr = sample.toarray() if hasattr(sample, "toarray") else np.asarray(sample)
        n_nan = int(np.isnan(np.asarray(arr, dtype=float)).sum())
        rep.checks.append(Check("missing_values", "FAIL" if n_nan else "PASS",
                                f"抽样中发现 {n_nan} 个 NaN/缺失值"))
    except Exception as e:
        rep.checks.append(Check("missing_values", "WARN", f"抽样检查失败：{e}"))

    # spatial_3D
    if task in ("T2", "T3"):
        if "spatial_3D" in a.obsm:
            rep.checks.append(Check("spatial_3D", "PASS", f"obsm['spatial_3D']={a.obsm['spatial_3D'].shape}"))
        else:
            rep.checks.append(Check("spatial_3D", "FAIL",
                                    f"{task} 需要 obsm['spatial_3D']，但未找到"))
    else:
        if "spatial_3D" in a.obsm:
            rep.checks.append(Check("spatial_3D", "PASS", "存在（T1 非必需）"))
        else:
            rep.checks.append(Check("spatial_3D", "SKIP", "T1 不要求"))

    # 标签列（检查 obs 里是否夹带疑似 ground truth）
    suspicious = [c for c in a.obs.columns
                  if any(k in str(c).lower() for k in ("label", "truth", "target", "y_true", "ground"))]
    rep.checks.append(Check("label_leakage",
                            "FAIL" if suspicious else "PASS",
                            f"obs 中疑似标签列：{suspicious}" if suspicious else "未发现标签列"))
    return rep


def render_report(rep: FormatReport) -> str:
    lines = [f"格式预检：{rep.path}", f"总判定：{'PASS' if rep.passed else 'FAIL'}", ""]
    for c in rep.checks:
        lines.append(f"  [{c.status:<4}] {c.name}: {c.detail}")
    lines += ["", DISCLAIMER]
    return "\n".join(lines)

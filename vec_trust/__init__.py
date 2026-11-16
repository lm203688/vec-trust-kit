"""vec-trust-kit: 虚拟细胞/胚胎预测模型的可信度诊断工具包.

零 GPU、零付费 API，仅依赖 numpy（scipy 可选）。
迁移自 SwarmLabs (MIT) 的 conformal 审计内核，面向虚拟胚胎挑战赛三种外推协议。
"""
from .conformal import conformal_quantile, interval, coverage, w1_proxy, graded_verdict
from .baseline_ladder import LadderConfig, evaluate_ladder
from .diagnostics import audit, audit_all
from .licenses import load_license_matrix, query, to_markdown

__version__ = "0.1.0"
__all__ = [
    "conformal_quantile", "interval", "coverage", "w1_proxy", "graded_verdict",
    "LadderConfig", "evaluate_ladder", "audit", "audit_all",
    "load_license_matrix", "query", "to_markdown",
]

"""vec-trust-kit: 虚拟细胞/胚胎预测模型的赛前体检工具包.

零 GPU、零付费 API，仅依赖 numpy（scipy/pandas 可选）。
迁移自 SwarmLabs (MIT) 的 conformal 审计内核，面向虚拟胚胎挑战赛。

⚠️ 教学声明：synthetic 模块的数字是机制演示（demo of a mechanism），
不是模型评测实证结论，不可作为"某模型不可信"的证据引用。
"""
from .conformal import conformal_quantile, interval, coverage, w1_proxy, graded_verdict
from .baseline_ladder import LadderConfig, evaluate_ladder, paired_ladder_test, rmse_rel
from .diagnostics import diagnose, audit, audit_all
from .licenses import load_license_matrix, query, to_markdown
from . import score_mirror, rule_guard, format_check, bio_gate

__version__ = "0.2.0"
__all__ = [
    "conformal_quantile", "interval", "coverage", "w1_proxy", "graded_verdict",
    "LadderConfig", "evaluate_ladder", "paired_ladder_test", "rmse_rel",
    "diagnose", "audit", "audit_all",
    "load_license_matrix", "query", "to_markdown",
    "score_mirror", "rule_guard", "format_check", "bio_gate",
]

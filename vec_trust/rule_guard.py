"""Rule Guard（规则守门）——外部数据是否踩保护窗 + 披露模板.

回应评估需求书 R9。官网明确"未披露即违规，不论是否改变结果"，这是最容易被
取消资格的坑。官方保护窗细节（来自 2026-11-16 官网核对，见评估需求书）：

  T1 保护窗：E9.5 之后至 E13.5；含 "nearness counts" 的中点规则
             （判定数据点在时间轴上是否"接近"被保护阶段）
  T2 插值禁带：时空插值相关的禁区
  T3 基因型禁带：涉及测试基因（如 β-catenin）的基因型限制

> ⚠️ 诚实声明：本模块按上述公开信息实现**保守近似**。
>   官方规则的精确边界（尤其 nearness 的中点取值、各禁带的确切阶段区间）
>   以官网 Rules/Terms 原文为准；本工具的输出是"告警线索"，
>   不是合规裁决。任何边缘样例（如 E9.45 用别的标注伪装）必须人工复核。
"""
from __future__ import annotations

from dataclasses import dataclass, field

# 胚胎发育阶段的可解析时间点（天）
STAGE_DAYS = {
    "E6.75": 6.75, "E7.5": 7.5, "E8.25": 8.25, "E8.5": 8.5,
    "E9.0": 9.0, "E9.5": 9.5, "E10.5": 10.5, "E11.5": 11.5,
    "E12.5": 12.5, "E13.5": 13.5,
}

# T1 保护窗（保守口径）：(9.5, 13.5) 之间算作受保护
T1_WINDOW = (9.5, 13.5)
# nearness 中点半径：距离保护窗边界小于此值的视为"接近"，需告警
NEARNESS_RADIUS = 0.25


@dataclass
class Flag:
    level: str        # VIOLATION / WARNING / OK
    task: str
    detail: str
    field: str = ""

    def to_dict(self) -> dict:
        return {"level": self.level, "task": self.task,
                "field": self.field, "detail": self.detail}


@dataclass
class GuardReport:
    flags: list[Flag] = field(default_factory=list)
    disclosure_rows: list[dict] = field(default_factory=list)

    @property
    def worst(self) -> str:
        order = {"OK": 0, "WARNING": 1, "VIOLATION": 2}
        return max((f.level for f in self.flags), key=lambda x: order[x], default="OK")

    def to_dict(self) -> dict:
        return {"worst": self.worst,
                "flags": [f.to_dict() for f in self.flags],
                "disclosure": self.disclosure_rows,
                "disclaimer": DISCLAIMER}


DISCLAIMER = (
    "规则守门为保守近似（基于官网 2026-11-16 公开信息）。保护窗精确边界以官网 "
    "Rules/Terms 原文为准；VIOLATION/WARNING 均为告警线索，非合规裁决，"
    "边缘样例必须人工复核后再提交。"
)


def parse_stage(value) -> float | None:
    """把 'E9.5' 或 9.5 解析为天数；无法解析返回 None。"""
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().upper()
    if s in STAGE_DAYS:
        return STAGE_DAYS[s]
    if s.startswith("E"):
        try:
            return float(s[1:])
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def check_t1_window(stage, *, label: str = "") -> Flag:
    """T1 保护窗判定：E9.5 之后至 E13.5（含 nearness 中点规则）. """
    day = parse_stage(stage)
    if day is None:
        return Flag("WARNING", "T1",
                    f"阶段 {label or stage!r} 无法解析为时间点，需人工核对是否落入保护窗", "stage")
    lo, hi = T1_WINDOW
    if lo < day < hi:
        return Flag("VIOLATION", "T1",
                    f"{label or stage} ({day}d) 落入 T1 保护窗 ({lo}-{hi}d)，"
                    "作为外部数据使用必须逐项披露并确认许可", "stage")
    if (lo - NEARNESS_RADIUS) <= day <= lo or hi <= day <= (hi + NEARNESS_RADIUS):
        return Flag("WARNING", "T1",
                    f"{label or stage} ({day}d) 接近 T1 保护窗边界 ({lo}/{hi}d)，"
                    "nearness 中点规则可能计入——请按官网原文复核", "stage")
    return Flag("OK", "T1", f"{label or stage} ({day}d) 在 T1 保护窗之外", "stage")


def check_t2_band(stage=None, *, has_3d_coords: bool = False) -> Flag:
    """T2 插值禁带判定（保守近似）. """
    if has_3d_coords:
        return Flag("WARNING", "T2",
                    "外部数据含 3D 坐标：T2 有插值禁带，须核对是否属于禁止的插值区间", "coordinates")
    day = parse_stage(stage) if stage is not None else None
    if day is not None and 9.5 < day < 13.5:
        return Flag("WARNING", "T2",
                    f"阶段 {day}d 与 T2 时空禁带重叠，需按官网核对", "stage")
    return Flag("OK", "T2", "未发现明显 T2 禁带冲突", "stage")


def check_t3_genotype(gene: str | None = None, *, is_knockout: bool = False) -> Flag:
    """T3 基因型禁带判定：测试基因（如 β-catenin）相关基因型受限. """
    if gene and any(g in str(gene).lower() for g in ("ctnnb1", "beta-catenin", "β-catenin", "catenin")):
        return Flag("VIOLATION", "T3",
                    f"外部数据涉及测试基因 {gene!r}，命中 T3 基因型禁带，必须披露并经组委会确认", "gene")
    if is_knockout:
        return Flag("WARNING", "T3", "外部数据为敲除样本，需核对是否命中 T3 基因型禁带", "genotype")
    return Flag("OK", "T3", "未发现明显 T3 基因型冲突", "gene")


def guard(stage=None, *, gene=None, has_3d_coords=False, is_knockout=False,
          dataset_name="external_dataset", stage_label="") -> GuardReport:
    """综合判定外部数据的保护窗风险，并生成官方要求的逐项披露模板。"""
    flags = [
        check_t1_window(stage, label=stage_label or str(stage)),
        check_t2_band(stage, has_3d_coords=has_3d_coords),
        check_t3_genotype(gene, is_knockout=is_knockout),
    ]
    day = parse_stage(stage) if stage is not None else None
    disclosure = [{
        "dataset": dataset_name,
        "stage": str(stage) if stage is not None else "未声明",
        "stage_days": day,
        "gene": gene or "无",
        "has_3d_coords": has_3d_coords,
        "is_knockout": is_knockout,
        "worst_flag": GuardReport(flags=flags).worst,
        "note": "请据实填写数据来源、许可、获取日期；未披露即违规（不论是否改变结果）",
    }]
    return GuardReport(flags=flags, disclosure_rows=disclosure)


def render_disclosure(report: GuardReport) -> str:
    """把披露模板渲染成可直接粘贴到提交表单的 Markdown。"""
    lines = ["### External data disclosure（逐项披露）", "",
             "| 数据集 | 阶段 | 天数 | 基因 | 3D坐标 | 敲除 | 风险 |",
             "|---|---|---|---|---|---|---|"]
    for r in report.disclosure_rows:
        lines.append("| {dataset} | {stage} | {stage_days} | {gene} | {has_3d_coords} | "
                     "{is_knockout} | {worst_flag} |".format(**r))
    lines += ["", "来源 / 许可 / 获取日期：__________", "", DISCLAIMER]
    return "\n".join(lines)

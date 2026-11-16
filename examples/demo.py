#!/usr/bin/env python3
"""端到端演示：生成合成图谱 -> 二维诊断 -> 输出可读报告.

    python examples/demo.py
    python examples/demo.py --json out.json
    python examples/demo.py --mode diagnose --model linear
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vec_trust import audit_all, diagnose
from vec_trust.synthetic import make_atlas

BANNER = (
    "⚠️  教学演示（demo of a mechanism）：以下全部数字来自固定种子的合成数据，\n"
    "    仅为机制展示，不是模型评测实证结论，不可作为'某模型不可信'的证据引用。"
)


def render_diagnose(result: dict) -> str:
    d = result["diagnosis"]
    dims = result["dimensions"]
    p = "unseen_stage"
    lines = [
        "=" * 72, "vec-trust-kit 二维诊断报告", "=" * 72, "",
        BANNER, "",
        f"模型: {result['model']}   区间模式: {result['scale_mode']}   重复划分: {result['n_boot']}",
        "",
        "两个正交维度（time 外推 unseen_stage）：",
        f"  模型维  ΔRMSE  = {dims['model_axis_rmse_ratio'][p]['mean']:.2f}× "
        f"(95% CI {dims['model_axis_rmse_ratio'][p]['ci95']})",
        f"  区间维  Δ覆盖  = {dims['interval_axis_cov_drop'][p]['mean']:.3f} "
        f"(静态覆盖 {dims['coverage_static'][p]['mean']:.3f} → "
        f"自适应 {dims['coverage_adaptive'][p]['mean']:.3f})",
        "",
        f"病因: {d['cause']}",
        f"说明: {d['cause_cn']}",
        f"教学裁决: {d['teaching_verdict']}",
        "",
        "注：教学裁决已降级为机制标签，不再是模型质量证据。",
    ]
    return "\n".join(lines)


def render_legacy(result: dict) -> str:
    lines = [
        "=" * 72, "vec-trust-kit 教学分级报告（v0.1 兼容）", "=" * 72, "",
        BANNER, "",
        f"结论：{result['meta']['interpretation']}",
        "",
        f"{'模型':<12}{'域内RMSE':>11}{'域内覆盖':>11}{'最差外推覆盖':>14}{'教学裁决':>22}{'基线阶梯':>12}",
        "-" * 82,
    ]
    for row in result["summary"]:
        lines.append(
            f"{row['model']:<12}{row['in_domain_rmse_rel']:>11.4f}"
            f"{row['in_domain_coverage']:>11.3f}{row['worst_extrap_coverage']:>14.3f}"
            f"{row['teaching_verdict']:>22}{row['baseline_ladder']:>12}"
        )
    lines += ["", "三种外推协议（覆盖率 / 教学裁决）：", ""]
    for name, res in result["per_model"].items():
        lines.append(f"  [{name}]")
        for proto, p_ in res["protocols"].items():
            lines.append(f"    {proto:<22} cov={p_['coverage']:.3f}  {p_['teaching_verdict']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="diagnose", choices=["diagnose", "legacy"])
    ap.add_argument("--model", default="linear")
    ap.add_argument("--n-boot", type=int, default=10)
    ap.add_argument("--json", default=None)
    ap.add_argument("--alpha", type=float, default=0.1)
    args = ap.parse_args()

    atlas = make_atlas()
    if args.mode == "diagnose":
        result = diagnose(atlas, args.model, n_boot=args.n_boot, alpha=args.alpha)
        print(render_diagnose(result))
    else:
        result = audit_all(atlas, alpha=args.alpha)
        print(render_legacy(result))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"JSON -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

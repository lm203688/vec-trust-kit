#!/usr/bin/env python3
"""端到端演示：生成合成图谱 -> 诊断四模型 -> 输出可读报告.

    python examples/demo.py
    python examples/demo.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vec_trust import audit_all
from vec_trust.synthetic import make_atlas


def render(result: dict) -> str:
    lines = [
        "=" * 72,
        "vec-trust-kit 诊断报告",
        "=" * 72,
        "",
        f"结论：{result['meta']['interpretation']}",
        "",
        f"{'模型':<12}{'域内RMSE':>11}{'域内覆盖':>11}{'最差外推覆盖':>14}{'外推裁决':>16}{'基线阶梯':>12}",
        "-" * 76,
    ]
    for row in result["summary"]:
        lines.append(
            f"{row['model']:<12}{row['in_domain_rmse_rel']:>11.4f}"
            f"{row['in_domain_coverage']:>11.3f}{row['worst_extrap_coverage']:>14.3f}"
            f"{row['overall_verdict']:>16}{row['baseline_ladder']:>12}"
        )

    lines += ["", "三种外推协议明细（覆盖率 / 裁决）：", ""]
    for name, res in result["per_model"].items():
        lines.append(f"  [{name}]")
        for proto, p in res["protocols"].items():
            lines.append(
                f"    {proto:<22} cov={p['coverage']:.3f}  "
                f"width_ratio={p['width_ratio']:.2f}  {p['verdict']}"
            )
            if p["verdict"] == "REFUTED":
                lines.append(f"      -> {p['reason']}")

    ladder = result["baseline_ladder"]
    lines += [
        "",
        f"基线阶梯：候选 = {ladder['candidate']}，准入 = {ladder['admitted']}",
    ]
    for r in ladder["reasons"]:
        lines.append(f"  - {r}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None, help="同时写出完整 JSON")
    ap.add_argument("--alpha", type=float, default=0.1)
    args = ap.parse_args()

    atlas = make_atlas()
    result = audit_all(atlas, alpha=args.alpha)
    print(render(result))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"JSON -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

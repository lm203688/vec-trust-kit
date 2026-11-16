"""vectrust CLI —— 赛前体检的命令行入口.

命令：
  vectrust --help
  vectrust diagnose --model linear|poly3 --json out.json   # 二维诊断
  vectrust score --task T1 --pred pred.h5ad ...            # 本地近似打分（占位）
  vectrust guard --stage E11.5 --gene Ctnnb1               # 保护窗判定
  vectrust format --pred pred.h5ad --task T2               # 格式预检
  vectrust bio --labels ...                                # 生物学门
  vectrust licenses --conflicts                            # 许可图谱
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .diagnostics import diagnose
from .synthetic import make_atlas, MODEL_NAMES
from . import rule_guard, format_check


def _emit(obj: dict, json_path: str | None = None) -> None:
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    if json_path:
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"JSON -> {json_path}")
    else:
        print(text)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="vectrust",
        description="vec-trust-kit：虚拟胚胎挑战赛赛前体检（诊断/打分近似/规则/格式/生物门）",
    )
    ap.add_argument("--version", action="version", version=f"vectrust {__version__}")
    sub = ap.add_subparsers(dest="cmd")

    d = sub.add_parser("diagnose", help="二维诊断（模型维×区间维）")
    d.add_argument("--model", default="linear", choices=list(MODEL_NAMES))
    d.add_argument("--n-boot", type=int, default=10)
    d.add_argument("--scale-mode", default="static", choices=["static", "adaptive"])
    d.add_argument("--json", default=None)

    s = sub.add_parser("score", help="本地近似打分（非官方 scorer）")
    s.add_argument("--task", choices=["T1", "T2", "T3"], required=True)
    s.add_argument("--pred", default=None, help="预测 h5ad（需 anndata，当前为占位入口）")
    s.add_argument("--json", default=None)

    g = sub.add_parser("guard", help="外部数据保护窗判定")
    g.add_argument("--stage", default=None)
    g.add_argument("--gene", default=None)
    g.add_argument("--task3-kb", action="store_true", dest="is_knockout")
    g.add_argument("--coords3d", action="store_true", dest="has_3d_coords")
    g.add_argument("--dataset", default="external_dataset")
    g.add_argument("--json", default=None)

    f = sub.add_parser("format", help="h5ad 提交格式预检")
    f.add_argument("--pred", required=True)
    f.add_argument("--task", default="T1", choices=["T1", "T2", "T3"])

    lic = sub.add_parser("licenses", help="三层许可图谱查询")
    lic.add_argument("--conflicts", action="store_true")
    lic.add_argument("--commercial-only", action="store_true")

    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.cmd is None:
        ap.print_help()
        return 0

    if args.cmd == "diagnose":
        atlas = make_atlas()
        r = diagnose(atlas, args.model, n_boot=args.n_boot, scale_mode=args.scale_mode)
        if args.json:
            _emit(r, args.json)
        else:
            print(f"模型: {r['model']}  病因: {r['diagnosis']['cause']}")
            print(f"说明: {r['diagnosis']['cause_cn']}")
            print(f"声明: {r['disclaimer']}")
        return 0

    if args.cmd == "score":
        from .score_mirror import DISCLAIMER, TASK_WEIGHTS
        # 诚实占位：没有官方真值/评测代码，不能直接对 h5ad 出官方分
        print("score：本地近似打分。指标名称与权重对齐官网 2026-11-16 快照，")
        print(f"  {args.task} 权重 = {TASK_WEIGHTS[args.task]}")
        print(f"  {DISCLAIMER}")
        if args.pred:
            print(f"  注意：直接对 {args.pred} 出分需官方真值验证集；当前仅提供 Python API "
                  "vec_trust.score_mirror.mirror_score(...) 做自查。")
        return 0

    if args.cmd == "guard":
        rep = rule_guard.guard(stage=args.stage, gene=args.gene,
                               is_knockout=args.is_knockout,
                               has_3d_coords=args.has_3d_coords,
                               dataset_name=args.dataset)
        if args.json:
            _emit(rep.to_dict(), args.json)
        else:
            print(rule_guard.render_disclosure(rep))
        return 0

    if args.cmd == "format":
        rep = format_check.precheck(args.pred, task=args.task)
        print(format_check.render_report(rep))
        return 0

    if args.cmd == "licenses":
        from .licenses import query, to_markdown
        rows = query(conflicts_only=args.conflicts,
                     commercial_only=args.commercial_only)
        print(to_markdown(rows))
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

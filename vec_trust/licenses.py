"""三层许可合规图谱的可查询接口.

    from vec_trust.licenses import load_license_matrix, query
    rows = query(commercial_only=True)

    python -m vec_trust.licenses --conflicts
    python -m vec_trust.licenses --category perturbation --markdown
"""
from __future__ import annotations

import csv
import argparse
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "license_matrix.csv"
FIELDS = ("project", "category", "code_license", "weight_license", "data_license",
          "commercial_ok", "key_restriction", "conflict", "source", "checked")


def load_license_matrix(path: Path | None = None) -> list[dict]:
    with open(path or CSV_PATH, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def query(rows: list[dict] | None = None, *, category: str | None = None,
          commercial_only: bool = False, conflicts_only: bool = False,
          keyword: str | None = None) -> list[dict]:
    rows = rows if rows is not None else load_license_matrix()
    out = []
    for r in rows:
        if category and r["category"] != category:
            continue
        if commercial_only and r["commercial_ok"] != "yes":
            continue
        if conflicts_only and r["conflict"] != "yes":
            continue
        if keyword and keyword.lower() not in (
            r["project"] + " " + r["key_restriction"] + " " + r["category"]
        ).lower():
            continue
        out.append(r)
    return out


def to_markdown(rows: list[dict]) -> str:
    cols = ("project", "category", "code_license", "weight_license",
            "data_license", "commercial_ok", "key_restriction", "conflict")
    head = "| " + " | ".join(cols) + " |\n|" + "|".join(["---"] * len(cols)) + "|"
    body = ["| " + " | ".join((r[c] or "-").replace("|", "/") for c in cols) + " |"
            for r in rows]
    return "\n".join([head] + body)


def main() -> int:
    ap = argparse.ArgumentParser(description="查询虚拟细胞生态三层许可图谱")
    ap.add_argument("--category")
    ap.add_argument("--commercial-only", action="store_true")
    ap.add_argument("--conflicts", action="store_true")
    ap.add_argument("--keyword")
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()

    rows = query(category=args.category, commercial_only=args.commercial_only,
                 conflicts_only=args.conflicts, keyword=args.keyword)
    if args.markdown:
        print(to_markdown(rows))
    else:
        for r in rows:
            flag = " [CONFLICT]" if r["conflict"] == "yes" else ""
            print(f"{r['project']}: code={r['code_license']} / weight={r['weight_license']} "
                  f"/ data={r['data_license']} / commercial={r['commercial_ok']}{flag}")
    print(f"\n{len(rows)} rows. 以官方 LICENSE 原文为准（核查日期见 CSV）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

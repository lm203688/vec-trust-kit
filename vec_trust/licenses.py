"""三层许可合规图谱的可查询接口.

    from vec_trust.licenses import load_license_matrix, query, audit_matrix
    rows = query(commercial_only=True)
    report = audit_matrix()   # 检查闭环：unknown / see repo / 死链

    python -m vec_trust.licenses --conflicts
    python -m vec_trust.licenses --audit --check-urls
"""
from __future__ import annotations

import csv
import argparse
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "license_matrix.csv"
FIELDS = ("project", "category", "code_license", "weight_license", "data_license",
          "commercial_ok", "key_restriction", "conflict", "verdict", "evidence",
          "source", "checked")
RESOLVED = {"CONFIRMED", "CONFLICT_RESOLVED", "CLARIFIED"}


def load_license_matrix(path: Path | None = None) -> list[dict]:
    with open(path or CSV_PATH, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def query(rows: list[dict] | None = None, *, category: str | None = None,
          commercial_only: bool = False, conflicts_only: bool = False,
          unresolved_only: bool = False, keyword: str | None = None) -> list[dict]:
    rows = rows if rows is not None else load_license_matrix()
    out = []
    for r in rows:
        if category and r["category"] != category:
            continue
        if commercial_only and r["commercial_ok"] != "yes":
            continue
        if conflicts_only and r["conflict"] != "yes":
            continue
        if unresolved_only and r.get("verdict") != "UNRESOLVED":
            continue
        if keyword and keyword.lower() not in (
            r["project"] + " " + r["key_restriction"] + " " + r["category"]
            + " " + r.get("evidence", "")
        ).lower():
            continue
        out.append(r)
    return out


def audit_matrix(rows: list[dict] | None = None, *, check_urls: bool = False,
                 timeout: float = 8.0) -> dict:
    """许可图谱闭环自检（R5 验收）：unknown / see repo / 冲突裁决 / URL 可用性.

    check_urls=True 时才联网；默认离线只查字段完整性。
    """
    rows = rows if rows is not None else load_license_matrix()
    unknown_commercial = [r["project"] for r in rows if r["commercial_ok"] == "unknown"]
    see_repo = [r["project"] for r in rows
                if "see repo" in (r["code_license"] + r["weight_license"]).lower()]
    conflicts = [r for r in rows if r["conflict"] == "yes"]
    unresolved = [r["project"] for r in conflicts if r.get("verdict") == "UNRESOLVED"]
    no_evidence = [r["project"] for r in conflicts if not r.get("evidence")]

    dead_urls: list[str] = []
    network_unreachable: list[str] = []  # URLError：可能本机代理/网络限制，非确证死链
    if check_urls:
        import urllib.request
        import urllib.error
        from urllib.parse import urlparse
        seen = set()
        for r in rows:
            for u in r["source"].split("|"):
                u = u.strip()
                if not u or u in seen:
                    continue
                seen.add(u)
                # github.com/<owner>/<repo> 用 API 判断（避免 sharecode/重定向干扰）
                host = urlparse(u).netloc
                if host in ("github.com", "www.github.com"):
                    parts = [p for p in urlparse(u).path.split("/") if p]
                    if len(parts) >= 2:
                        api = f"https://api.github.com/repos/{parts[0]}/{parts[1]}"
                        try:
                            req = urllib.request.Request(api, headers={"User-Agent": "vec-trust-audit"})
                            urllib.request.urlopen(req, timeout=timeout)
                            continue
                        except urllib.error.HTTPError as e:
                            # 403 = GitHub 未认证 API 限流，不是死链
                            if e.code == 403:
                                network_unreachable.append(f"{u} (API rate-limited 403)")
                            else:
                                dead_urls.append(f"{u} (HTTP {e.code})")
                            continue
                        except Exception as e:
                            network_unreachable.append(f"{u} ({type(e).__name__})")
                            continue
                try:
                    req = urllib.request.Request(u, headers={"User-Agent": "vec-trust-audit"})
                    urllib.request.urlopen(req, timeout=timeout)
                except urllib.error.HTTPError as e:
                    # 403/429 多为限流或反爬，不等于链接失效；404/410 才是死链
                    if e.code in (403, 429):
                        network_unreachable.append(f"{u} (HTTP {e.code} rate-limited/blocked)")
                    else:
                        dead_urls.append(f"{u} (HTTP {e.code})")
                except Exception as e:
                    # URLError/timeout 多为本地代理或网络限制，不等于链接失效
                    network_unreachable.append(f"{u} ({type(e).__name__})")

    return {
        "total_rows": len(rows),
        "unknown_commercial": unknown_commercial,
        "see_repo": see_repo,
        "conflicts": len(conflicts),
        "resolved_conflicts": len(conflicts) - len(unresolved),
        "unresolved_conflicts": unresolved,
        "conflicts_without_evidence": no_evidence,
        "dead_urls": dead_urls if check_urls else ["<未检查：设置 check_urls=True>"],
        "network_unreachable": network_unreachable,
        "closed": (not unknown_commercial and not see_repo
                   and not no_evidence and (not check_urls or not dead_urls)),
        "note": "UNRESOLVED 表示缺一手 LICENSE 原文，已诚实标注而非强行裁决；"
                "network_unreachable 多为本地代理限制，不等于死链。",
    }


def to_markdown(rows: list[dict]) -> str:
    cols = ("project", "category", "code_license", "weight_license",
            "data_license", "commercial_ok", "conflict", "verdict")
    head = "| " + " | ".join(cols) + " |\n|" + "|".join(["---"] * len(cols)) + "|"
    body = ["| " + " | ".join((r.get(c, "") or "-").replace("|", "/") for c in cols) + " |"
            for r in rows]
    return "\n".join([head] + body)


def main() -> int:
    ap = argparse.ArgumentParser(description="查询虚拟细胞生态三层许可图谱")
    ap.add_argument("--category")
    ap.add_argument("--commercial-only", action="store_true")
    ap.add_argument("--conflicts", action="store_true")
    ap.add_argument("--unresolved", action="store_true")
    ap.add_argument("--keyword")
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--audit", action="store_true", help="闭环自检")
    ap.add_argument("--check-urls", action="store_true", help="自检时联网检查 URL")
    args = ap.parse_args()

    if args.audit:
        import json
        print(json.dumps(audit_matrix(check_urls=args.check_urls), ensure_ascii=False, indent=2))
        return 0

    rows = query(category=args.category, commercial_only=args.commercial_only,
                 conflicts_only=args.conflicts, unresolved_only=args.unresolved,
                 keyword=args.keyword)
    if args.markdown:
        print(to_markdown(rows))
    else:
        for r in rows:
            flag = f" [{r['conflict']}/{r.get('verdict')}]" if r["conflict"] == "yes" else ""
            print(f"{r['project']}: code={r['code_license']} / weight={r['weight_license']} "
                  f"/ data={r['data_license']} / commercial={r['commercial_ok']}{flag}")
    print(f"\n{len(rows)} rows. 以官方 LICENSE 原文为准（核查日期与证据见 CSV）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

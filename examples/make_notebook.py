#!/usr/bin/env python3
"""生成中文教程 notebook（可重复运行，保证内容一致）。"""
from __future__ import annotations

import json
from pathlib import Path


def src(text: str) -> list[str]:
    lines = text.strip("\n").split("\n")
    return [line + "\n" for line in lines[:-1]] + [lines[-1]]


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": src(text)}


def code(text: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": src(text)}


cells = [
    md("""
# 虚拟细胞模型的域内赢 ≠ 外推可信

**vec-trust-kit 中文教程**

这个 notebook 演示一件事：一个模型可以在域内指标上击败所有简单基线，同时在三种外推协议下全部失去预测区间覆盖。排行榜看不到这件事，但做药物筛选的人会为此付出代价。

全程只依赖 numpy，不需要下载数据，不需要 GPU。
"""),
    code("""
import sys
from pathlib import Path
for candidate in (Path.cwd(), Path.cwd().parent):
    if (candidate / "vec_trust").exists():
        sys.path.insert(0, str(candidate))
        break

import numpy as np
from vec_trust import audit, audit_all, query, to_markdown
from vec_trust.synthetic import make_atlas
from vec_trust.licenses import load_license_matrix

print("numpy", np.__version__)
print("工具包已就绪")
"""),
    md("""
## 1. 合成图谱长什么样

真实表达随发育时间**饱和**（sigmoid），这是生命的常态：器官长到一定程度就不再线性长大。我们现在用一个三次多项式模型，它在训练阶段（E8.25–E10.5）会把这条曲线拟合得很好，但到了 E12.5 不会停。

三个外推 split 对应挑战赛三个任务：未见阶段、未见组织、未见扰动。
"""),
    code("""
atlas = make_atlas(seed=0)
print("meta:", atlas["meta"])
for key in ("train", "in_domain", "unseen_stage", "unseen_tissue", "unseen_perturbation"):
    X, y = atlas[key]
    print(f"{key:<22} X={X.shape}  y={y.shape}")
"""),
    md("""
## 2. 域内基线阶梯：谁赢了

阶梯规则来自 SwarmLabs：copy_last → mean → linear → model。最高级模型必须在域内指标上**严格击败每一个**更低级基线，否则不予准入。这一步只看域内，故意不看外推。
"""),
    code("""
result = audit_all(atlas, alpha=0.1)
ladder = result["baseline_ladder"]
print("候选模型:", ladder["candidate"], "准入:", ladder["admitted"])
for reason in ladder["reasons"]:
    print(" -", reason)
print()
print(f"{'模型':<12}{'域内RMSE':>11}{'域内覆盖':>11}")
for row in result["summary"]:
    print(f"{row['model']:<12}{row['in_domain_rmse_rel']:>11.4f}{row['in_domain_coverage']:>11.3f}")
"""),
    md("""
## 3. 赢家真的可信吗

现在看外推。split conformal 区间在训练集上校准到 90% 覆盖率，然后原封不动拿到外推集上用。如果分布漂移了，覆盖率就会掉——掉了就说明这个区间不能用。

注意看 `width_ratio`：区间宽度没变，但真实误差变大了。
"""),
    code("""
m = result["per_model"]["model"]
print("conformal q =", m["conformal_q"], " 域内覆盖 =", m["in_domain"]["coverage"])
print()
print(f"{'协议':<24}{'覆盖':>8}{'宽度比':>9}{'RMSE_rel':>11}  裁决")
for proto, p in m["protocols"].items():
    print(f"{proto:<24}{p['coverage']:>8.3f}{p['width_ratio']:>9.2f}{p['rmse_rel']:>11.4f}  {p['verdict']}")
    if p["verdict"] == "REFUTED":
        print("   ", p["reason"])
print()
print("总裁决:", m["overall_verdict"])
"""),
    md("""
## 4. 把自己模型接进来

`audit()` 接受 `predictor` 参数：`callable(X_fit, y_fit, X_eval) -> (mean, std)`。

真实数据场景下，先用 AnnData 把 h5ad 读成 numpy，按 `[stage, perturbation_id, tissue_id]` 组织特征矩阵，再传给这个接口即可。下面的例子故意做一个过度自信的模型——std 只有真实噪声的十分之一，看看审计会不会抓住它。
"""),
    code("""
def overconfident_predictor(X_fit, y_fit, X_eval):
    # 用域内均值当预测，但把 std 压得极小
    mu = np.broadcast_to(y_fit.mean(axis=0), (len(X_eval), y_fit.shape[1])).copy()
    sd = np.broadcast_to(y_fit.std(axis=0) / 10, mu.shape).copy()
    return mu, np.maximum(sd, 1e-4)

custom = audit(atlas, "my_overconfident_model", predictor=overconfident_predictor)
print("域内覆盖:", custom["in_domain"]["coverage"])
for proto, p in custom["protocols"].items():
    print(f"{proto:<24} cov={p['coverage']:.3f}  width_ratio={p['width_ratio']:.2f}  {p['verdict']}")
print("总裁决:", custom["overall_verdict"])
"""),
    md("""
## 5. 许可图谱：动手前先查这一层

代码开源不等于权重可用，权重可用不等于数据可商用。下面几条是直接筛选出来的高风险项。完整表在 `data/license_matrix.csv`，26 条，带来源 URL 和核查日期。
"""),
    code("""
rows = load_license_matrix()
conflicts = query(rows, conflicts_only=True)
print(to_markdown(conflicts))
print("\\n共", len(rows), "条记录；冲突项", len(conflicts), "条")
print("警告：二手表格只用于筛选，合规决策必须读官方 LICENSE 原文。")
"""),
    md("""
## 6. 结论与提交

这套工具的定位不是取代榜单，而是补上榜单缺的一层：告诉使用者这个分数在什么条件下成立。

**提交到 Community Contribution Award 的步骤**

1. 把仓库推到公开地址（GitHub / Gitee 均可，中文完全合规）
2. 先看官方资源页有没有重复工作：https://virtualembryo.ai/challenge/resources
3. 在 https://virtualembryo.ai/challenge/community 登录并填写链接
4. 有账号就够，不需要注册参赛队伍，不需要提交比赛预测

规则原文：https://virtualembryo.ai/challenge/rules
"""),
]

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.13"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = Path(__file__).resolve().parents[1] / "中文教程_模型可信度诊断.ipynb"
out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("wrote", out)

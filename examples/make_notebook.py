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
# 从"一个分数"到"这个分数在什么条件下成立"

**vec-trust-kit 中文教程 · 赛前体检**

> ⚠️ **教学声明（务必先读）**：本 notebook 全部数字来自 `synthetic.py` 的固定种子**合成数据**，
> 是**机制演示**（demo of a mechanism），不是模型评测实证结论。
> **不可**把下面的数字当成"某模型不可信"的证据引用。

它演示两件事：
1. 一个模型可以在域内赢过基线，同时外推失效——排行榜看不到这件事；
2. 更重要的：把"模型误差"和"区间构造"分开后，同一个正确模型换一种区间就能从"覆盖崩"变"通过"。
   这证明诊断 result 取决于被测对象，而不是被数据生成器写死。

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

合成机制设为：真实表达 = **线性发育趋势 + 随发育时间增大的噪声**（异方差）。
"正确族"是线性模型——它能安全外推；"错误族"是三次多项式 `poly3`，域内拟合很好但外推会爆炸。

三个外推 split 对应挑战赛三个任务：未见阶段、未见组织、未见扰动。注意：这是**协议的名字相似**，
不等于官方指标——官方的真实指标是分布级的（见 README），本 demo 只看逐元素 RMSE 与覆盖。
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
## 3. 一个更重要的实验：同一个模型，两种区间

split conformal 区间在训练集上校准到 90% 覆盖。把**静态区间**（尺度不随外推距离变）
拿到外推集上，覆盖会掉——但这是**定理级已知结果**（漂移破坏 exchangeability），
不能当作"模型不可信"的证据。

关键是区分两件事：静态区间用 `diagnose(..., scale_mode="static")`，
自适应区间用 `scale_mode="adaptive"`（尺度随距离增长）。看同一个正确模型的覆盖能否恢复。
"""),
    code("""
m = result["per_model"]["poly3"]  # 错误族
print("conformal q =", m["conformal_q"], " 域内覆盖 =", m["in_domain"]["coverage"])
print()
print(f"{'协议':<24}{'覆盖':>8}{'宽度比':>9}{'RMSE_rel':>11}  教学裁决")
for proto, p in m["protocols"].items():
    print(f"{proto:<24}{p['coverage']:>8.3f}{p['width_ratio']:>9.2f}{p['rmse_rel']:>11.4f}  {p['teaching_verdict']}")
print()
print("总裁决:", m["overall_verdict"], "（教学标签，非模型质量证据）")
"""),
    md("""
### 二维诊断：裁决真的取决于被测对象

`diagnose()` 输出模型维（ΔRMSE）与区间维（覆盖恢复）两个正交维度，并给出病因。
看正确族 `linear` 与错误族 `poly3` 会落到不同病因——这是 v0.1 恒 REFUTED 做不到的。
"""),
    code("""
from vec_trust import diagnose
for name in ("linear", "poly3"):
    r = diagnose(atlas, name, n_boot=6)
    p = "unseen_stage"
    d = r["diagnosis"]
    print(f"[{name}] ΔRMSE={r['dimensions']['model_axis_rmse_ratio'][p]['mean']:.2f}x "
          f"静态覆盖={r['dimensions']['coverage_static'][p]['mean']:.3f} "
          f"自适应覆盖={r['dimensions']['coverage_adaptive'][p]['mean']:.3f}")
    print(f"   病因: {d['cause']} - {d['cause_cn']}")
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
    print(f"{proto:<24} cov={p['coverage']:.3f}  width_ratio={p['width_ratio']:.2f}  {p['teaching_verdict']}")
print("总裁决:", custom["overall_verdict"], "（教学标签）")
"""),
    md("""
## 5. 接真实数据 + 赛前体检三模块

上面的 predictor 接口可以接你自己的提交。真实场景流程：

```python
import anndata as ad
A = ad.read_h5ad("your_prediction.h5ad")
X = np.column_stack([stage_time, perturbation_id, tissue_id])  # 按官方格式构造
y = A.X.toarray() if hasattr(A.X, "toarray") else np.asarray(A.X)
result = audit(atlas, "my_model", predictor=lambda Xf, yf, Xe: my_predictor(...))
```

但更重要的是：**你真正想知道的是"我离 floor 还有多远、哪一项最弱、有没有踩规则红线"**。
这就是赛前体检三模块（均为保守近似，输出是人工复核线索，非官方裁决）：

- `score_mirror.mirror_score(task="T1", ...)` —— 官方指标分解 + 50–100 刻度（本地近似，非官方 scorer）
- `rule_guard.guard(stage="E11.5", gene="Ctnnb1")` —— 保护窗判定 + 披露模板
- `bio_gate.run_all(...)` —— 组成 / marker / 3D 连续性 / 生长 / 谱系五道门
- `format_check.precheck("pred.h5ad", task="T2")` —— 格式自查（需装 anndata）
"""),
    code("""
from vec_trust import rule_guard, bio_gate, score_mirror
import numpy as np

# 规则守门：E11.5 + β-catenin 应触发告警
rep = rule_guard.guard(stage="E11.5", gene="Ctnnb1", dataset_name="my_external_data")
print("最坏风险:", rep.worst)
print(rule_guard.render_disclosure(rep))

# 生物学门：给出一个"组成比例失衡"的例子
bio = bio_gate.run_all(
    pred_labels=np.array([0]*90 + [1]*10), prior={0: 0.5, 1: 0.5},
    pred_cellcount=1000, prior_count=1000,
    early=1.0, late=0.2,
)
print("最弱门:", bio.weakest.gate)
"""),
    md("""
## 6. 许可图谱：动手前先查这一层

代码开源不等于权重可用，权重可用不等于数据可商用。下面几条是直接筛选出来的高风险项。完整表在 `data/license_matrix.csv`，27 条，带来源 URL、核查日期、裁决与证据；`unknown` 与 `see repo` 均已归零。
"""),
    code("""
rows = load_license_matrix()
conflicts = query(rows, conflicts_only=True)
print(to_markdown(conflicts))
print("\\n共", len(rows), "条记录；冲突项", len(conflicts), "条")
print("警告：二手表格只用于筛选，合规决策必须读官方 LICENSE 原文。")
"""),
    md("""
## 7. 结论与提交

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

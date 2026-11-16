# vec-trust-kit

虚拟细胞 / 虚拟胚胎预测模型的**可信度诊断工具包**。中文，零 GPU，零付费 API，只依赖 numpy。

面向 [NeurIPS 2026 Virtual Embryo Challenge](https://virtualembryo.ai/challenge) 的 Community Contribution Award：不造新模型，帮参赛者判断**什么时候该信模型、什么时候直接用简单基线**。

永久仓库：https://github.com/lm203688/vec-trust-kit
在线展示与下载：https://wbapp-jzwfj5frsi2adm0ahs258b.app.workbuddy.host/?sharecode=RRM6MWPMAO

---

## English summary

**vec-trust-kit** is a Chinese-language, numpy-only *trust diagnostics* toolkit for virtual cell / embryo prediction models. It does not train a model. It helps a competitor decide when a leaderboard number can actually be trusted.

Three reusable assets:

1. **Baseline ladder** — a candidate model is admitted only if it strictly beats `copy_last`, `mean` and `linear` on in-domain error.
2. **Split-conformal extrapolation audit** — empirical coverage is checked under three held-out protocols (unseen developmental stage / unseen tissue / unseen perturbation), returning a graded verdict, plus an explicit check for the failure mode where coverage looks healthy only because the intervals became too wide to discriminate.
3. **Three-layer license matrix** — 26 entries in the virtual-cell ecosystem, annotated separately for code, weights and data, each with source URLs and a verification date.

Also included: a 13-cell Chinese tutorial notebook, 10 passing tests, MIT license, no GPU, no paid API, and no restricted competition data.

**What this is not.** Every number in the demo below comes from a synthetic generator with a fixed seed: it is a mechanism demonstration, not an empirical claim about any real model, and the tool does **not** implement the challenge's official metrics. Please read 「局限与边界」 below before citing anything here.

---

## 一句话说清它解决什么

2025 年 Nature Methods 的 27 方法 × 29 数据集基准给出过一个不好听的结论：跨未见细胞环境时，多数模型明显退化，有些**打不过一行线性基线**。

但比赛排行榜只给一个分数，不会告诉你这个分数是在什么条件下拿到的。本工具做两件榜单不做的事：

1. **基线阶梯**：域内指标上，复杂模型必须严格击败 copy_last / mean / linear 才准入。
2. **外推覆盖诊断**：用 split conformal 区间检查三个外推协议下的实际覆盖率，覆盖崩了就判 REFUTED。

这两件事一起看，才能发现最危险的一类失效——**域内赢过基线，外推全线崩塌**。

---

## 快速开始

```bash
python examples/demo.py                 # 完整诊断报告
python examples/demo.py --json out.json # 同时导出机读结果
python -m pytest tests/ -q              # 10 项自测
python -m vec_trust.licenses --conflicts
python -m vec_trust.licenses --commercial-only --markdown
```

无需下载数据。合成图谱由固定种子生成，任何人跑出的数字都一样。

---

## 合成数据上的输出（机制演示）

> 下表全部来自 `vec_trust/synthetic.py` 的固定种子合成图谱，**不是任何真实模型的实测结果**。它的作用是演示"域内通过、外推崩塌"这一失效模式可以被工具稳定检出，而不是证明某个具体模型不可信。

```
模型               域内RMSE   域内覆盖   最差外推覆盖     外推裁决    基线阶梯
copy_last        0.3530      1.000         0.662       PASS_WEAK        N/A
mean             1.1680      0.758         0.117         REFUTED        N/A
linear           0.2502      0.916         0.144         REFUTED        N/A
model            0.2376      0.891         0.083         REFUTED   ADMITTED
```

`model` 是三次多项式。它在训练域内确实比线性模型好（0.2376 < 0.2502），所以基线阶梯放它进门。但真实表达随发育时间**饱和**，多项式不会饱和，到了未见阶段就一路外冲——时间外推覆盖只剩 0.083。

这就是全部要点：**域内指标通过，不等于模型可以外推。**

---

## 三种外推协议

这三个协议在**设定上**与挑战赛三个任务的划分方式同类，便于参赛者把工具接到自己的划分上；它们是本工具自己的接口，**不是官方指标、也不读官方评测代码**。

| 协议 | 本工具的构造 | 挑战赛中的同类设定 |
|---|---|---|
| `unseen_stage` | 训练到 E10.5，测 E12.5 | T1 时间外推 |
| `unseen_tissue` | 训练在 heart，测 embryo | T2 空间-时间外推 |
| `unseen_perturbation` | 训练 WT + KO_A，测 KO_B | T3 敲除效应外推 |

覆盖判定分级：`PASS_FULL > PASS_PARTIAL > PASS_WEAK > MARGINAL > REFUTED`。
这套分级是本工具**自定义**的，官方规则里没有对应条款。纯计算模拟最高只能到 PASS_PARTIAL；PASS_FULL 需要我们额外拿到真实实验锚点才算。

另外有一项**虚假通过**检查：覆盖率虚高但区间宽度超过域内 10 倍，判 REFUTED。区间宽到没有分辨力，覆盖率再高也没意义。

---

## 三层许可图谱

`data/license_matrix.csv` 收录 26 个虚拟细胞生态常用项目，按**代码 / 权重 / 数据**三层分别标注。这不是可有可无的附录——本次调研里最容易踩坑的就是这里：

| 项目 | 坑 |
|---|---|
| scFoundation | 代码 Apache-2.0，但原始权重限非商业研究 |
| Arc State | 官网记 CC-BY-NC-SA-4.0，另有资料记 Apache 2.0 |
| AlphaFold 3 | 代码 2026-06 起 Apache-2.0，权重仍非商业；Server 输出禁用于 docking / 筛选 / 训练 ML |
| Chai-1 | 两份资料许可记录冲突 |
| VCC 2025 训练集 | 二手数据卡标 CC-BY-4.0，未见一手确认 |

查询接口：

```python
from vec_trust.licenses import load_license_matrix, query, to_markdown

rows = query(conflicts_only=True)   # 只看有冲突的
print(to_markdown(rows))
```

**所有条目核查于 2026-11-16，动手前请读官方仓库 LICENSE 原文。** 二手表格（包括本表）只用于筛选，不用于合规决策。

---

## 参赛路径决策树

给还没决定怎么参与的人：

```
要不要碰 Track 2（Agent Team）？
├─ 想用 AI 助手边聊边看结果边调 → 不要碰。
│  Rules §9 有 configuration lock：运行开始后固定 prompts/harness/预算，
│  人不得读中间分数再指导下一步。我们这种协作方式只能算 Human Team。
└─ 能接受全程锁死配置、提交 trajectory + prompts + harness → 可以。

数据能不能公开展示？
├─ 赛事数据：仅供研究教育，尚未发表。
│  任何发表/公开展示/再分发须经 UCSD Dr. Neil Chi 团队事先批准。
└─ 外部公开数据：允许，但必须逐项披露。未披露即违规，
   不管它有没有真的改变结果。

只想贡献、不想训练模型？
└─ Community Contribution Award。有账号就够，不用注册队伍，
   不用参赛。中文作品完全合规，公开仓库即可，无需合并进官方仓库。
   滚动评审，$200/项，可多次获评，截至 2026-12-11。
```

细节以 [官方 Rules](https://virtualembryo.ai/challenge/rules) 和 [Community Award 页面](https://virtualembryo.ai/challenge/community) 为准。

---

## 数据量与资源

本包不依赖任何受限数据：

- 合成图谱：`vec_trust/synthetic.py`，固定种子，可复现
- 想接真实数据：`predict_with()` 接受任意 `(n, 3)` 特征矩阵和 `(n, genes)` 表达矩阵，用 h5ad / AnnData 读出后转成 numpy 即可
- 推荐的开放数据源：Tahoe-100M（CC0-1.0，可商用可再训练）、CELLxGENE Census、scPerturBench（MIT）

不碰赛事提供的数据，因此本包可以直接公开发布、被任何人复用。

---

## 局限与边界（先读）

| 边界 | 说明 |
|---|---|
| 数据是合成的 | 演示数字来自 `synthetic.py`，用途是演示失效模式可被检出，不能拿来评价任何真实模型 |
| 不实现官方指标 | 官方 T1 是四项加权指标（含细胞状态分布），T2 是八项、T3 是五项，本工具一概没有实现，不能替代官方评测 |
| 未在赛事数据上运行 | 没有碰赛事数据（许可限制）；接真实数据需要自己用 `predict_with()` 适配 |
| 判决规则偏严 | 压力测试显示：把生成器换成参数正确的 sigmoid 族，当前单一阈值仍会判 REFUTED。也就是说方差大的模型可能被误判。v0.2 会把单一裁决拆成 ΔRMSE / Δ覆盖 / Δ区间宽度 三项分别报告 |
| 许可表是二手调研 | 26 条的 source 链接已逐个 HTTP 校验（2026-11-16）：所有 GitHub 与官方网站链接均 200，HuggingFace 与 AlphaFold Server 三处命令行下未取到状态码、未作可达性断言。许可结论以官方 LICENSE 原文为准；4 条冲突标 `conflict=yes` 但未裁决 |

---

## 致谢与许可

conformal 审计内核迁移自 [SwarmLabs](https://github.com/lm203688/swarmlabs-public) 的 `engine/conformal.py` 与 `engine/baseline_ladder.py`（MIT，Copyright 2026 lm203688），改写为模型无关接口，并新增三种外推协议与分级裁决。

包内代码 MIT，Copyright 2026 Li Xing。

提交社区贡献前，请先看 [官方资源页](https://virtualembryo.ai/challenge/resources) 有没有重复工作——官网明确说重叠时**先提交者权重更高**，改进已有作品通常比再造一份更划算。

# vec-trust-kit

虚拟胚胎挑战赛（NeurIPS 2026 Virtual Embryo Challenge）的**赛前体检**工具包。中文，零 GPU，最小依赖只有 numpy。

在你花掉那 2 次不可撤回的 P3 提交之前，它告诉你三件事：你离 floor 还有多远、哪一项加权指标最弱、你声明的外部数据有没有踩保护窗。

> ⚠️ **诚实声明**：内置 demo 使用**合成数据**（`synthetic.py`，固定种子），所有数字是**机制演示**（demo of a mechanism），不是模型评测实证结论，**不可**作为"某模型不可信"的证据引用。官方指标镜像是明确标注的**本地近似**，不是赛事 scorer。

在线展示：https://wbapp-hwixdhi5nwlxgljprmwzzg.app.workbuddy.host/?sharecode=G75FFFHLWF
永久仓库：https://github.com/lm203688/vec-trust-kit

---

## 一句话定位

**不要用一个漂亮的分数，去换一次不可撤回的提交。**

2025 年 Nature Methods 的 27 方法 × 29 数据集基准给出过一个不好听的结论：跨未见细胞环境时，多数模型明显退化，有些**打不过一行线性基线**。排行榜只给一个分数，不告诉你这个分数在什么条件下成立。本工具补上这一层。

---

## 快速开始

```bash
pip install -e .
vectrust --help
vectrust diagnose --model linear --n-boot 10       # 二维诊断（推荐）
vectrust guard --stage E11.5 --gene Ctnnb1          # 保护窗判定
vectrust score --task T1                             # 本地近似打分
python -m pytest tests/ -q                            # 40 项测试
python -m vec_trust.licenses --audit --check-urls   # 许可图谱闭环自检
```

不安装也可直接跑：`python examples/demo.py`。

---

## v0.2 相对 v0.1 的关键修正（回应外部评估）

| v0.1 问题 | v0.2 修正 |
|---|---|
| 裁决恒 `REFUTED`，不可证伪，结论由合成器写死 | `diagnose()` 拆成**模型维（ΔRMSE）× 区间维（Δ覆盖）**；正确模型 + 自适应区间现在**能通过**，错误模型才失败 |
| 把 conformal 在漂移下失效当作模型证据 | 明确标注为定理级已知结果；判据改为"自适应区间能否把覆盖救回" |
| 单种子单划分 | n_boot 次重复 + bootstrap 95% CI；基线阶梯加配对置换检验 |
| "三协议=三个官方任务""9 指标"等自造概念 | 官方面板镜像：T1 25/25/30/20、T2 4×25%、T3 30/25/25/20，归一化到 floor=50/ceiling=100（明确标注本地近似） |
| 不可安装、无 CLI、无 CI | `pip install .`、`vectrust` CLI、GitHub Actions（3 个 Python 版本）、`CITATION.cff` |
| 许可图谱 30% 死链、四成 "see repo" | 3 条死链修正、see repo 归零、9 条冲突各有裁决+证据、`--audit` 闭环检查 |

### 招牌结论：诊断现在能区分病因

| 模型 | 区间 | ΔRMSE | 外推覆盖 | 病因 |
|---|---|---|---|---|
| poly3（错误族） | static | 2.58× | 0.36 | MODEL_ERROR——误差涨 2.6 倍，换区间也救不回 |
| linear（正确族） | static | 1.30× | 0.67 | INTERVAL_NOT_ADAPTIVE——误差稳，但区间没随距离增长 |
| linear（正确族） | adaptive | 1.30× | 0.87 | 覆盖恢复——**证明裁决取决于被测对象，不是生成器写死** |

（以上均为合成机制演示数字。）

---

## 三个赛前体检模块

| 模块 | 解决什么 | 稀缺性来源 |
|---|---|---|
| **Score Mirror** | 近似 50–100 分、四项/八项/五项分解、找最弱项 | P3 每榜仅 2 次提交 |
| **Rule Guard** | 外部数据是否落入保护窗（T1 E9.5–E13.5 含 nearness 中点规则、T2/T3 禁带）+ 披露模板 | "未披露即违规"，边界规则极复杂 |
| **Bio Gate** | 组成比例 / marker / 3D 连续性 / 生长尺度 / 谱系有序性五道门 | 通用 conformal 工具做不出来；对应 T1 的 30% 分布权重与 T2 的 25% 几何权重 |

另有**格式预检**（基因顺序、`spatial_3D`、NaN、≤1200MB、无标签列）与**三层许可图谱**（代码/权重/数据，27 条）。

> Rule Guard 与 Bio Gate 是基于公开信息的**保守近似**，输出是人工复核线索，不是合规裁决，以官网原文为准。

---

## 三层许可图谱

`data/license_matrix.csv` 每条按**代码 / 权重 / 数据**分别标注，27 条、unknown=0、see repo=0。核查中发现并修正的问题：

| 项目 | 原记录问题 | 修正 |
|---|---|---|
| CellVQ | `github.com/CellVQ` 死链 | `A4Bio/CellVQ`（MIT） |
| RF3 | `bakerlab/RF3` 死链 | `RosettaCommons/modelforge`（BSD-3-Clause，可商用） |
| scPerturBench | `theislab/` 死链 + "MIT" 存疑 | `bm2-lab/scPerturBench`（**GPL-3.0**，冲突已裁决） |
| Geneformer V2 | GitHub 仓库已不存在 | HuggingFace `ctheodoris/Geneformer`（Apache-2.0） |
| Protenix | "see repo" | v1 Apache-2.0 可商用；**v2 权重专有** |
| OpenFold3 | 指向 v1 主仓 | `aqlaboratory/openfold-3`（Apache-2.0） |

仍有 4 条标 `UNRESOLVED`（Arc State / scGPT / scFoundation / VCC2025 训练集）——缺一手 LICENSE 原文，**诚实标注而非强行裁决**。动手前请读官方 LICENSE。

```python
from vec_trust.licenses import query, audit_matrix, to_markdown
print(to_markdown(query(conflicts_only=True)))
print(audit_matrix(check_urls=True))
```

---

## 参赛路径

走 **Community Contribution Award**：有账号即可、不用注册队伍、中文作品完全合规、公开仓库即可、$200/项可多次获评、滚动评审到 2026-12-11、先提交权重更高。

提交清单与文案见 `SUBMISSION.md`。提交前先查重：https://virtualembryo.ai/challenge/resources

不建议碰主赛道：无生成模型、无 GPU、起跑晚约 3 个月，主赛道奖金不现实。

---

## 致谢与许可

conformal 审计内核迁移自本地 SwarmLabs 项目（`engine/conformal.py` 等，MIT，Copyright 2026 lm203688）。诚实说明：SwarmLabs 内核目前**没有独立公开仓库**（`lm203688/swarmlabs` 不存在），相关公开描述见 `genetech-14-sites`。

包内代码 MIT，Copyright 2026 Li Xing。

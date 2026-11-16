# 提交清单：Community Contribution Award（v0.2）

## 当前状态

作品已上线、可安装、40 项测试通过。**只差你本人登录官网填表**（我没有你的挑战赛账号）。

| 项 | 状态 |
|---|---|
| 可安装包（`pip install .`）+ `vectrust` CLI | ✅ |
| 40 项 pytest 全通过 / notebook 全格执行 | ✅ |
| 永久仓库（GitHub public） | ✅ https://github.com/lm203688/vec-trust-kit |
| 展示站点 | ✅ https://wbapp-hwixdhi5nwlxgljprmwzzg.app.workbuddy.host/?sharecode=G75FFFHLWF |
| 许可图谱闭环（unknown=0 / see repo=0 / 死链=0） | ✅ |
| 官网提交表单 | ⬜ **需要你登录填写** |

---

## 提交前必做

1. 查重：https://virtualembryo.ai/challenge/resources
2. 提交：https://virtualembryo.ai/challenge/community （右上角登录，不需要注册参赛队伍）
3. 主链接填 GitHub 仓库，备注附展示站点

**截止**：滚动评审，到 2026-12-11 或奖金发完；先提交权重更高。

---

## 按官方五准则组织的推荐文案（中文）

> **Useful（有用）**：赛前体检三模块——Score Mirror 在本地近似官方 50–100 分并分解 T1/T2/T3 加权指标、找最弱项；Rule Guard 判定外部数据是否落入 E9.5–E13.5 保护窗并生成披露模板；Bio Gate 做组成/marker/3D 连续性/生长/谱系五道门。P3 每榜仅 2 次不可撤回提交，这些自查降低"提交即报废"风险。
>
> **Quality（质量）**：二维诊断把"模型误差（ΔRMSE）"与"区间构造（覆盖恢复）"分开——正确模型配自适应区间能通过，错误模型才失败，纠正了 v0.1 恒 REFUTED 的不可证伪缺陷。10 次重复划分 + bootstrap 95% CI + 配对置换检验；40 项测试、GitHub Actions 覆盖 3 个 Python 版本。
>
> **Reach（触达）**：GitHub 公开仓库 + 双语 README（中英）+ 16 格中文教程 notebook，可 `pip install vectrust` 一键安装。
>
> **Openness（开放）**：MIT 许可、CITATION.cff、issue 开放、许可图谱 27 条附证据 URL 与核查日期。
>
> **Impact（影响）**：围绕 2025 官方结论"扰动模型尚未在所有指标上稳定超越朴素基线"构建，不造模型、不碰赛事数据（Terms §14），可直接被任何参赛者复用。

**诚实前提**：内置 demo 全部是固定种子的**合成数据**，为机制演示，非实证结论；指标镜像为**本地近似**，非官方 scorer；Rule Guard/Bio Gate 为保守近似，输出是人工复核线索。文案不得省略这些限定。

---

## English pitch（如表单要求英文）

> **vec-trust-kit — a pre-submission physical for the Virtual Embryo Challenge.**
>
> **Useful**: Before you spend one of your two irrevocable P3 submissions, it tells you how far you are from the `copy_last` floor on the official 50–100 scale, which weighted metric is weakest, and whether your external data crosses a protected developmental window (T1 E9.5–E13.5, nearness midpoint rule). Three modules: Score Mirror, Rule Guard, Bio Gate, plus a format precheck.
>
> **Quality**: A two-axis diagnosis separates model error (ΔRMSE) from interval calibration (coverage recovery) — a correct model + adaptive interval passes, a wrong model fails. 10 repeated splits, bootstrap 95% CIs, paired permutation tests; 40 passing tests, CI on 3 Python versions.
>
> **Reach / Openness**: `pip install vectrust`, `vectrust` CLI, bilingual README, a 16-cell Chinese tutorial, MIT licensed, CITATION.cff, and a 27-entry three-layer licence matrix with evidence URLs.
>
> **Honest scope**: the demo runs on synthetic data (a demo of a mechanism, not empirical evidence); the score mirror is a labelled local approximation, not the official scorer; it trains no model and uses no competition data. Adapted from SwarmLabs (MIT).

---

## 提交前检查

- [ ] GitHub 仓库公开、README（中英）/LICENSE/CITATION.cff 齐全
- [ ] `pip install .` 后 `vectrust --help` 可用；40 tests 通过
- [ ] 文案保留了"合成数据/本地近似/保守近似"三处诚实限定
- [ ] 未把任何赛事数据放进仓库或站点

---

## 可拆成多份独立贡献（官网 $200/项、可多次、无总额上限）

| # | 独立贡献 | 英文一句话 |
|---|---|---|
| 1 | 工具包本体 | "A pre-submission physical for VEC: floor-relative scoring, per-metric breakdown, drift-aware diagnosis. One command, no GPU." |
| 2 | 中文教程 notebook | "A Chinese walkthrough from synthetic mechanism to your first legal submission." |
| 3 | 三层许可图谱 | "Code, weights and data are three separate licences: 27 projects, evidence-backed, 9 documented conflicts." |

每份需独立地址与独立价值，不要把同一份工作拆成多份灌水。合理的预期是 2–3 份被接受。

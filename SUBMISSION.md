# 提交清单：Community Contribution Award

## 当前状态

**公开地址已上线并验证可用，只差你本人登录官网提交。**

本地 git 推送路径不可用（SSH key 未授权、gh CLI 崩溃、无代码托管 Connector），所以我改用自主可控的方式：把整个包做成了公开可访问的展示站点，含源码包 / notebook / CSV 三个下载入口。

| 项 | 状态 |
|---|---|
| 包内容（代码 + 中文教程 + 许可图谱 + 测试） | ✅ 本地完成 |
| 10 项自测 / notebook 全格执行 | ✅ 通过 |
| 公开可访问地址 | ✅ 已部署并验证 HTTP 200 |
| 源码包 / notebook / CSV 下载 | ✅ 全部 HTTP 200，字节数匹配 |
| 官网提交表单 | ⬜ **需要你登录填写（我没有你的挑战赛账号）** |

### 公开地址

**主页**：https://wbapp-jzwfj5frsi2adm0ahs258b.app.workbuddy.host/?sharecode=RRM6MWPMAO

下载入口（页面内也可点）：
- 源码包：`https://wbapp-jzwfj5frsi2adm0ahs258b.app.workbuddy.host/downloads/vec-trust-kit.zip?sharecode=RRM6MWPMAO`
- 中文 notebook：同路径 `/downloads/中文教程_模型可信度诊断.ipynb?sharecode=RRM6MWPMAO`
- 许可图谱：`/downloads/license_matrix.csv?sharecode=RRM6MWPMAO`

> ⚠️ **诚实标注**：这是 WorkBuddy 的托管子域名，不是 GitHub/Gitee 永久仓库。官网只要求"公开地址 + 可公开获取"，未强制指定托管方，但临时域名在长期可引用性上弱于 GitHub。如果你有 GitHub 账号，建议把源码再推一个永久仓库，提交时**两个链接都填**（公开站点做可读展示，GitHub 做永久存档）。这一步我不能代做。

---

## 提交步骤

1. 先看官方资源页确认没有重复工作：
   https://virtualembryo.ai/challenge/resources
2. 打开社区贡献提交页，用右上角按钮登录：
   https://virtualembryo.ai/challenge/community
3. 填入上面的公开主页地址，按下面的文案填写说明。
4. 不需要注册参赛队伍，不需要提交比赛预测文件。
5.（可选但推荐）若有 GitHub，推送源码后把永久仓库链接一并提交。

**截止**：滚动评审，资金发完或 Challenge 结束（2026-12-11）为止。越早提交权重越高——官网原话是早期教程帮到的人更多。

---

## 推荐填写文案（中文）

> vec-trust-kit：虚拟细胞/胚胎模型可信度诊断工具包。中文，零 GPU，仅依赖 numpy。
>
> 包含三件可复用资产：
> 1) 基线阶梯——域内指标上模型必须严格击败 copy_last / mean / linear 才准入；
> 2) conformal 外推覆盖诊断——对应挑战赛三个任务（未见阶段/未见组织/未见扰动），分级判定 PASS_FULL 到 REFUTED，并含"区间虚宽导致的虚假通过"检查；
> 3) 三层许可合规图谱——26 个虚拟细胞生态项目按代码/权重/数据分别标注，4 项冲突已标记，附来源 URL 与核查日期。
>
> 附带 13 格中文教程 notebook 和 10 项自测，全部可复现。合成数据固定种子，不依赖任何受限数据，因此可直接公开发布。
>
> 核心演示：一个三次多项式模型域内 RMSE 0.2376 击败线性基线 0.2502 而获准入，但三种外推覆盖全崩（0.083 / 0.359 / 0.491），总裁决 REFUTED。用于说明"域内赢过基线不等于外推可信"。
>
> 内核迁移自 SwarmLabs（MIT），已按模型无关接口改写并保留署名。

英文短版（如表单要求英文）：

> vec-trust-kit: a Chinese-language, numpy-only trust diagnostics toolkit for virtual cell / embryo models. Provides a baseline ladder (copy_last / mean / linear / model admission), split-conformal coverage audits across the challenge's three extrapolation protocols, a 26-entry three-layer license matrix (code / weights / data), a reproducible Chinese notebook and 10 passing tests. Demonstrates a model that wins in-domain but collapses under all three extrapolation settings. MIT licensed; conformal core adapted from SwarmLabs (MIT).

---

## 提交前检查

- [ ] 仓库是公开的（社区贡献要求作品有公开地址，官网表单收链接不收文件）
- [ ] `README.md`、`LICENSE`、`SUBMISSION.md` 都在仓库根目录
- [ ] `python -m pytest tests/ -q` 仍为 10 passed
- [ ] 许可图谱的冲突项已注明"以官方 LICENSE 原文为准"
- [ ] 没有把任何赛事提供的数据放进仓库（赛事数据仅研究教育用途，公开发布须事先批准）

---

## 为什么走这条而不是 Track 1

| 维度 | Community Contribution | Track 1 正赛 |
|---|---|---|
| 要不要训练生成模型 | 不要 | 要，且需预测表达分布 + 3D 坐标 + 敲除效应 |
| GPU | 不需要 | 主办方有 H100/H200 评测集群，个人从零不现实 |
| 起跑线 | 8-17 才宣布奖项，滚动评审 | starter kit 8-15 已放，别人跑了约 3 个月 |
| 现有资产匹配度 | 直接匹配（评测/诊断/许可） | 不匹配（我们没有时空生成模型） |
| 数据许可风险 | 无，用合成数据 + 公开数据 | 赛事数据公开发表需事先批准 |
| 账号要求 | 有账号即可，不用注册队伍 | 需正式注册队伍 |

如果之后确实想碰 Track 1，可以另起一条线：先注册、拉 starter kit、跑通 `copy_last` baseline 提交一次合法预测，目标是拿一次公开榜单记录，不是冲奖。这和本贡献包互不冲突。

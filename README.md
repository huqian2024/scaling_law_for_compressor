# 压气机二维叶栅 AI4S 数据生成项目

二维压气机叶栅 CFD 数据生成与 scaling-law 研究（研究目标 `E = f(N, P)`）。
当前阶段**只做数据生成前端、几何/QC 流水线与数据集构建**，不做模型训练，也不做 CFD 生产。

> 本文件只是仓库入口与文档索引。
> 权威状态以 `PROJECT_HANDOFF.md` 与 `AGENT_INSTRUCTION.md` §0 为准。

## 当前状态（2026-10-21）

```text
生产规模 / DOE / 参数顺序      FROZEN（2026-10-13）：生产 DOE 仍为 d = 6
                               docs/DESIGN_FREEZE_2026-10-13.md
本地几何流水线 + QC 契约       PASS（legacy 回归 / 生成器 / QC 契约）
几何参数研究（探索性）         DONE：C820 100-case 敏感性 -> C830 57-case 复核
                                    -> C840 几何参数最终裁决 V1
C820 人工工程评审              15 REJECT / 85 ACCEPT（100/100 已判定，2026-10-21）
SS1 / SS2                      3.2 / 0.8 FIXED_BY_REVIEW
其余 11 个几何参数             OPEN（探索性范围，未批准为生产范围）
几何约束方案                   A/B/C 已分析，默认推荐 A（Metal2 ≥ 6.0）；
                               待人工确认，YAML 未修改
FINAL_PRODUCTION_RANGES       PENDING  <- 主要 blocker
NUMECA / CFX / HPC            NOT STARTED
单元测试                      131 passed, 17 subtests passed（2026-10-21 实测）
```

```text
Geometry QC PASS  !=  气动合理  !=  可网格化  !=  CFD 可收敛
探索性参数配置      !=  FINAL_PRODUCTION_RANGES
13 维探索空间       !=  生产 DOE 已冻结为 13 维（生产 DOE 仍为 6 维）
人工 ACCEPT（形状） !=  网格 / CFD / 气动合格
人工评审状态        =  85 ACCEPT / 15 REJECT（100/100 已判定）
```

## 几何参数研究链（Case 号段互不重叠）

| 阶段 | 目录 | Case 号段 | 规模 | 状态 |
|---|---|---|---|---|
| V1 评审（legacy 范围） | `analysis/geometry_review/archive/v1_legacy_review/` | `C800001..C800030` | 30 | 历史阶段 / 已归档 |
| V2 评审（探索边界） | `analysis/geometry_review/senior_review_v2/` | `C810001..C810040` | 40 | 历史阶段 / 评审包已交付 |
| 全参数敏感性 + 边界检验 | [`analysis/geometry_review/parameter_sensitivity_v1_100cases/`](analysis/geometry_review/parameter_sensitivity_v1_100cases/README.md) | `C820001..C820100` | 100 | 探索性 / 未批准（最新敏感性扫描） |
| Ks1/Ks2 专项复核 | [`analysis/geometry_review/ks1_ks2_review_v1/`](analysis/geometry_review/ks1_ks2_review_v1/README.md) | `C830001..C830057` | 57 | 探索性 / 未批准 |
| 几何参数最终裁决 V1 | [`analysis/geometry_review/parameter_final_decision_v1/`](analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md) | `C840001..C840040`（新增） | 40 新增 + 9 复用 | 探索性 FINAL（仅限探索性几何 DOE） |

100-case 实验要点：

```text
目录      analysis/geometry_review/parameter_sensitivity_v1_100cases/
Case      C820001 .. C820100（S1=60, S2=20, S3=20）
总览图    overview_001_050.png / overview_051_100.png
参数表    case_design.csv（100 行）
几何指标  case_metrics.csv（100 行）
结果      生成 100/100，硬性 QC 100/100，冻结 QC 100/100
自动筛选  FIX_CANDIDATE=SS1,SS2 / KEEP_CANDIDATE=10 / REVIEW=Ks2
人工评审  15 REJECT / 85 ACCEPT（human_review_2026-10-21.csv）
```

> 该 100-case 扫描**当时**把 `SS1`（2.4–4.0）、`SS2`（0.5–1.1）作为可变参数；
> `SS1 = 3.2`、`SS2 = 0.8` 是之后的人工评审冻结决定（`FIXED_BY_REVIEW`）。
> 两者不能混写。
>
> 100 个 Case 已全部完成人工形状评审：85 ACCEPT / 15 REJECT（无 UNREVIEWED）。
> ACCEPT 只表示形状合理，不代表网格、CFD 收敛或气动性能合格。
> 15 个被拒 Case 全部通过几何 QC，说明自动 QC 尚不能替代工程评审。
> 分析：`analysis/geometry_review/parameter_sensitivity_v1_100cases/HUMAN_REVIEW_2026-10-21.md`


## 文档入口

```text
PROJECT_HANDOFF.md                              交接总览（当前状态 / 下一步 / 上传清单）
AGENT_INSTRUCTION.md                            本地 Agent 长期项目说明（§0 = 当前权威状态）
docs/DESIGN_FREEZE_2026-10-13.md                生产规模 + DOE 冻结记录
docs/DOE_DECISION.md                            DOE 决策与基准
docs/SCALING_EXPERIMENT_DESIGN.md               scaling-law 实验统计设计
docs/GEOMETRY_GENERATOR_CONTRACT.md             几何生成器契约（FROZEN）
docs/GEOMETRY_QC_CONTRACT.md                    Geometry QC 契约（FROZEN）
docs/NUMECA_BRINGUP_CASE_C900001.md             NUMECA bring-up 记录（C900001 仅 bring-up）
docs/SESSION_DELIVERY_2026-10-11.md             历史 session 记录
docs/SESSION_DELIVERY_2026-10-13.md             生产冻结 session 记录
docs/SESSION_DELIVERY_2026-10-15.md             几何评审 V1/V2 + 40-case 评审包
docs/SESSION_DELIVERY_2026-10-17.md             ★ 100-case 敏感性 + Ks1/Ks2 复核 + 最终裁决
docs/SESSION_DELIVERY_2026-10-21.md             ★ 参数空间核对 + 人工评审补录 + 筛选策略
docs/PARAMETER_SPACE_RECONCILIATION.md          6D 冻结 DOE vs 13 维探索空间对照表
docs/GEOMETRY_SCREENING_STRATEGY_2026-10-21.md  下一阶段筛选策略（宽范围 + 简单约束 + 筛选）
docs/GEOMETRY_CONSTRAINT_ANALYSIS_2026-10-21.md ★ 参数对照 + A/B/C 约束方案（推荐 A）
analysis/geometry_review/README.md              几何评审/研究目录入口
analysis/geometry_review/parameter_sensitivity_v1_100cases/REPORT.md   100-case 分析报告
analysis/geometry_review/parameter_sensitivity_v1_100cases/HUMAN_REVIEW_2026-10-21.md
                                                人工评审记录 + 边界分析
analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md 几何参数最终裁决
```

## 目录结构

```text
code/         生成/QC 流水线与几何核心（geometry_legacy_v1.py 为冻结核心）
config/       运行时范围配置（当前只有 ranges_legacy.yaml）
legacy/       历史生成脚本与冻结 geomTurbo 模板（只读）
geometry/     本地产物目录（bring-up C900001 等，部分按约定不进 Git）
design/       bring-up 设计输入
analysis/     DOE 基准与几何评审/敏感性研究
tools/        研究驱动脚本（敏感性、复核、裁决、绘图）
tests/        回归与契约测试（含 tests/fixtures/）
docs/         冻结记录、契约与 session 交付记录
dataset/ mesh/ cfx/ post/ environment/ logs/   后续阶段目录
```

## 快速验证

```bash
# 环境（全部脚本使用 conda 环境 ai4s）
conda run -n ai4s python -c "import numpy,scipy,matplotlib,yaml;print('env ok')"

# 全量回归
conda run -n ai4s python -m pytest -q
```

## 红线（长期不变）

```text
Do not RUN production design / geometry generation before
FINAL_PRODUCTION_RANGES is frozen.
Do not treat exploratory ranges (V2 / C820 / C830 / C840) as production ranges.
Do not treat the 13-dim exploratory space as a frozen production DOE (it is d = 6).
Do not re-open SS1 = 3.2 / SS2 = 0.8 without an explicit human decision.
Do not read UNREVIEWED as ACCEPT (all 100 C820 cases are now decided: 85 ACCEPT /
15 REJECT), and do not equate human shape ACCEPT or geometry QC PASS with
mesh / CFD / aerodynamic validity.
Do not implement complex joint constraints (JC_XMEAN_KS1_KM) in any sampler
while Xmean upper bound is 0.18.
Do not guess the CFX implementation of Incidence / Mach.
Do not modify legacy files, frozen contracts, existing experiment results or
range values without an explicit human decision.
Do not claim aerodynamic validity or CFD feasibility from Geometry QC PASS.
```

# 压气机二维叶栅 AI4S 数据生成项目

二维压气机叶栅 CFD 数据生成与 scaling-law 研究（研究目标 `E = f(N, P)`）。

当前阶段：**TRANSITION / PLANNING（2026-10-23）**

```text
本地负责   11D Sobol 参数采样 + GeomTurbo 生成 + 几何 QC + 数据管理 + 后续 GPU 训练
师兄负责   CFD 网格 / 边界条件 / 工况 / 求解 / 收敛检查 / 调度（独立服务器）
本地不做   NUMECA/CFX 自动化、CFD 服务器管理、编造求解器设置或物理边界条件
```

> 本文件只是仓库入口与文档索引。
> 当前阶段规划：`docs/PROJECT_TRANSITION_PLAN.md`
> 训练规划：`docs/TRAINING_TRANSITION_PLAN.md`
> 交接状态：`PROJECT_HANDOFF.md` 的 TRANSITION STATUS；长期指令：`AGENT_INSTRUCTION.md` §0
>
> 2026-10-13 / 2026-10-21 的冻结记录保留为历史；其中 **6D 生产 DOE / 单一种子 /
> 200000 默认候选数** 等项目规划约束已标记 `HISTORICAL / SUPERSEDED`。

## 当前状态（2026-10-23）

```text
项目阶段                        TRANSITION / PLANNING
11D 几何参数范围（方案 A）      CURRENT_BASELINE（数值未修改）
SS1 / SS2                       3.2 / 0.8（不变）
本地几何流水线 + QC 契约        VERIFIED PASS（155 passed, 17 subtests, 2026-10-21）
几何生成入口                    PREPARED / NOT EXECUTED；已生成 GeomTurbo = 0
三组 Sobol 生成计划             PROPOSED / NOT EXECUTED（150000 / 15000 / 30000）
目标有效 CFD 数                 PROPOSED（100000 / 10000 / 20000 = 130000）
最低总体有效率                  66.67%（130000 / 195000）
小规模 CFD 成功率               USER-REPORTED ≈75%（未本地复现）
CFD 网格 / 工况 / 求解 / 调度   师兄独立服务器（本地不实现）
AI 训练（GPU HPC + Slurm）      PROPOSED / NOT STARTED
6D 生产 DOE / ONE_6D_POINT_ONE_CASE   HISTORICAL / SUPERSEDED
代码默认候选数 200000           HISTORICAL DEFAULT（不是当前计划数量）
FINAL_PRODUCTION_RANGES         PENDING（CFD 侧）
```

```text
Geometry parameter ranges:
  CURRENT_BASELINE — config/geometry_ranges_frozen_a.yaml（数值未改）
Batch generator implementation:
  PREPARED / NOT EXECUTED
Current production plan (PROPOSED):
  Train 150000 / Validation 15000 / Test 30000 = 195000 候选
  -> 目标有效 100000 / 10000 / 20000 = 130000
Seed values:
  PENDING（三组各自固定，但数值未定）
GeomTurbo files generated:
  0
CFD production:
  师兄独立服务器（本地 NOT EXECUTED）
AI training:
  PROPOSED / NOT STARTED
```

```text
Geometry QC PASS  !=  气动合理  !=  可网格化  !=  CFD 可收敛
探索性参数配置      !=  当前几何生成基线（后者数值已固定，见 frozen_a 配置）
历史 6D DOE        =   HISTORICAL / SUPERSEDED（不再是当前几何生成约束）
当前几何采样        =   11D scrambled Sobol（三组独立种子，PROPOSED）
13 维（11+2）探索空间 =  历史对照口径，不是当前生产 DOE
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
PROJECT_HANDOFF.md                              交接总览（TRANSITION STATUS / 下一步 / 上传清单）
AGENT_INSTRUCTION.md                            本地 Agent 长期项目说明（§0 = 当前权威状态）
docs/PROJECT_TRANSITION_PLAN.md                 ★ 当前阶段主规划（11D 三组生成 / CFD 边界 / 实施顺序）
docs/TRAINING_TRANSITION_PLAN.md                ★ 训练规划（GPU Slurm / 早停 / 测试集 / 防泄漏）
docs/DESIGN_FREEZE_2026-10-13.md                历史冻结记录（HISTORICAL / SUPERSEDED，保留原文）
docs/DOE_DECISION.md                            DOE 方法决策（6D 生产约束已失效）
docs/SCALING_EXPERIMENT_DESIGN.md               scaling-law 统计设计（原则保留，阶梯为候选）
docs/GEOMETRY_GENERATOR_CONTRACT.md             几何生成器契约（FROZEN，不变）
docs/GEOMETRY_QC_CONTRACT.md                    Geometry QC 契约（FROZEN，不变）
docs/NUMECA_BRINGUP_CASE_C900001.md             NUMECA bring-up 记录（C900001 仅 bring-up）
docs/SESSION_DELIVERY_2026-10-11.md             历史 session 记录
docs/SESSION_DELIVERY_2026-10-13.md             历史生产冻结 session 记录
docs/SESSION_DELIVERY_2026-10-15.md             几何评审 V1/V2 + 40-case 评审包
docs/SESSION_DELIVERY_2026-10-17.md             100-case 敏感性 + Ks1/Ks2 复核 + 最终裁决
docs/SESSION_DELIVERY_2026-10-21.md             参数空间核对 + 人工评审补录 + 筛选策略
docs/PARAMETER_SPACE_RECONCILIATION.md          历史维度对照（6D 生产 DOE 已失效）
docs/GEOMETRY_SCREENING_STRATEGY_2026-10-21.md  几何筛选策略（PROPOSED）
docs/GEOMETRY_CONSTRAINT_ANALYSIS_2026-10-21.md 参数对照 + A/B/C 约束方案（历史分析）
docs/GEOMTURBO_PRODUCTION_200K.md               ★ GeomTurbo 生成说明（200000 = 历史默认值）
code/run_geomturbo.py                           ★ 三组生产启动入口（推荐；--group/--N/--seed）
code/generate_geomturbo_production.py           底层生成器（高级用法；显式 --execute）
config/geometry_ranges_frozen_a.yaml            当前几何生成基线（数值未修改）
analysis/geometry_review/README.md              几何评审/研究目录入口
analysis/geometry_review/parameter_sensitivity_v1_100cases/REPORT.md   100-case 分析报告
analysis/geometry_review/parameter_sensitivity_v1_100cases/HUMAN_REVIEW_2026-10-21.md
                                                人工评审记录 + 边界分析
analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md 几何参数最终裁决（历史）
```

## 目录结构

```text
code/         生成/QC 流水线与几何核心（geometry_legacy_v1.py 为冻结核心）
config/       运行时范围配置（ranges_legacy.yaml + geometry_ranges_frozen_a.yaml）
legacy/       历史生成脚本与冻结 geomTurbo 模板（只读）
geometry/     本地产物目录（bring-up C900001 等，部分按约定不进 Git）
design/       bring-up 设计输入
production_geomturbo/   GeomTurbo 生产输出（本地生成，不进 Git）
analysis/     DOE 基准与几何评审/敏感性研究
tools/        研究驱动脚本（敏感性、复核、裁决、绘图）
tests/        回归与契约测试（含 tests/fixtures/）
docs/         规划、冻结记录（含历史）、契约与 session 交付记录
dataset/ mesh/ cfx/ post/ environment/ logs/   后续阶段目录
```

## 快速验证

```bash
# 环境（全部脚本使用 conda 环境 ai4s）
conda run -n ai4s python -c "import numpy,scipy,matplotlib,yaml;print('env ok')"

# 全量回归
conda run -n ai4s python -m pytest -q
```

## GeomTurbo 生成（推荐入口：`code/run_geomturbo.py`）

一条命令即一次明确的生成授权：启动脚本内部调用现有冻结生成器的 `--execute`，
原有安全机制全部保留（配置校验、快照指纹、原子写入、sha256 校验、断点续跑、拒绝混目录）。

```bash
# 0) 只读预览（不创建任何目录 / 文件）
conda run -n ai4s python code/run_geomturbo.py \
    --group train --N 150000 --seed 101 --plan

# 1) 三组正式启动（建议各自在 tmux 窗口中运行；种子仅作示例，启动后必须记录）
#    Train：150000 个候选几何
conda run -n ai4s python code/run_geomturbo.py --group train --N 150000 --seed 101
#    Validation：15000 个候选几何
conda run -n ai4s python code/run_geomturbo.py --group val   --N 15000  --seed 202
#    Test：30000 个候选几何
conda run -n ai4s python code/run_geomturbo.py --group test  --N 30000  --seed 303
```

```bash
# 2) 中断后继续（group / N / seed 必须与首次一致；N 可以增大以延长前缀）
conda run -n ai4s python code/run_geomturbo.py --group train --N 150000 --seed 101 --resume
conda run -n ai4s python code/run_geomturbo.py --group val   --N 15000  --seed 202 --resume
conda run -n ai4s python code/run_geomturbo.py --group test  --N 30000  --seed 303 --resume
```

```text
默认输出目录（每组独立）:
  production_geomturbo/train/
  production_geomturbo/val/
  production_geomturbo/test/
每组各自拥有 manifest.csv、batch_*/manifest.csv、config_snapshot.yaml、
generation_summary.json、group_info.json。
case_id（G0000001…）在每组内重复；全局身份 = group + seed + sobol_index，
case_id 格式不变（G + 7 位数字）。
```

### 查看进度

```text
运行中：
  - 每 2000 个 Case 打印一次 progress: N/total (written=… skipped=… failed=…)
  - 每个 batch 结束打印 batch 000001: cases G0000001..G0005000 written=…
已生成文件数：
  find production_geomturbo/train -name 'G*.geomTurbo' | wc -l
运行摘要：
  cat production_geomturbo/train/generation_summary.json
  （正常结束时写入；Ctrl+C 中断时以 batch manifest 为准，--resume 完成后会重新生成 summary）
```

```bash
# 失败记录统计（status 为第 5 列；只读）
python - <<'PY'
import csv
rows = list(csv.DictReader(open("production_geomturbo/train/manifest.csv")))
print("rows", len(rows),
      "ok", sum(r["status"] == "OK" for r in rows),
      "failed", sum(r["status"] == "FAILED" for r in rows))
for r in rows:
    if r["status"] != "OK":
        print(r["case_id"], r["status"], r["error"])
PY
```

### 安全中断与长任务

```text
安全中断：在运行窗口按一次 Ctrl+C，等待出现
  interrupted after X/N cases ... partial progress was flushed
再关闭窗口。当前批次已完成的 Case 会先写入 batch manifest，--resume 会跳过它们。
不要使用 kill -9 或直接关闭机器：可能丢失最后一个批次尚未落盘的 manifest 记录
（文件本身是原子写，不会出现半截 .geomTurbo；--resume 会以相同参数重算缺失记录）。

tmux 建议：
  tmux new -s gt-train
  conda activate ai4s
  python code/run_geomturbo.py --group train --N 150000 --seed 101
  # 脱离：Ctrl+b 然后 d
  # 重新进入：tmux attach -t gt-train
  # 三组可分别使用 gt-train / gt-val / gt-test 三个 session
  # 同一个 group 不要同时启动两个进程（当前没有进程锁）
```

```text
N = 几何候选数量，不是 CFD 成功数量。
目标有效 CFD 数（Train 100000 / Val 10000 / Test 20000）需要按实测 CFD 成功率
（当前小规模约 75%，USER-REPORTED）由候选数折算，不能把 N 当作可用样本数。

当前计划：Train 150000 / Val 15000 / Test 30000 候选（PROPOSED / NOT EXECUTED）。
200000 只是旧代码默认值（HISTORICAL DEFAULT），不是当前计划。
详细说明：docs/GEOMTURBO_PRODUCTION_200K.md
当前规划：docs/PROJECT_TRANSITION_PLAN.md
高级用法（自行管理 --execute / batch size / 进度间隔）：code/generate_geomturbo_production.py
```

## 红线（长期不变）

```text
Do not treat the 6-D production DOE as the current generation route:
it is HISTORICAL / SUPERSEDED. Current geometry sampling is 11-D
(config/geometry_ranges_frozen_a.yaml), three independent Sobol groups (PROPOSED).
The 11-D GeomTurbo candidate pool may be generated ONLY from
config/geometry_ranges_frozen_a.yaml, and only by the user via
code/run_geomturbo.py (or with an explicit --execute on
code/generate_geomturbo_production.py).
Do not treat exploratory ranges (V2 / C820 / C830 / C840) as production ranges.
Do not treat the 13-dim exploratory space as a frozen production DOE.
Do not re-open SS1 = 3.2 / SS2 = 0.8 without an explicit human decision.
Do not read UNREVIEWED as ACCEPT, and do not equate human shape ACCEPT or
geometry QC PASS with mesh / CFD / aerodynamic validity.
Do not implement complex joint constraints (JC_XMEAN_KS1_KM) in any sampler
while Xmean upper bound is 0.18.
Do not guess the CFX implementation of Incidence / Mach, and do not guess
CFD mesh settings, boundary conditions, solver configuration or result formats.
Do not modify legacy files, frozen contracts, existing experiment results or
frozen range values without an explicit human decision.
Do not add automatic shape filters to the production generator.
Do not let geometry generation start NUMECA / CFX.
Do not start CFD or GPU training from this repository, and do not treat any
PROPOSED plan in docs/ as an approved production or training decision.
```

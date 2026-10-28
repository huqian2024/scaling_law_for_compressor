# PROJECT_HANDOFF

## TRANSITION STATUS（2026-10-23 — 当前权威状态）

```text
项目阶段                  TRANSITION / PLANNING
主规划文档                docs/PROJECT_TRANSITION_PLAN.md
训练规划文档              docs/TRAINING_TRANSITION_PLAN.md
```

```text
当前分工:
  本地    11D Sobol 采样 + GeomTurbo 生成 + 几何 QC + 数据管理 + GPU 训练（后续）
  师兄    CFD 网格 / 边界条件 / 工况 / 求解 / 收敛检查 / 调度（独立服务器）
  本地不做 NUMECA/CFX 自动化、CFD 服务器管理、求解器设置猜测
```

```text
当前几何生产方案（PROPOSED / NOT EXECUTED）:
  Train        150000 候选 -> 目标有效 100000
  Validation    15000 候选 -> 目标有效 10000
  Test          30000 候选 -> 目标有效 20000
  合计         195000 候选 -> 目标有效 130000
  方法         11D scrambled Sobol，三组各用不同固定种子，输出目录相互独立
  种子数值     PENDING
  规模依据     130000 / 195000 = 66.67% 最低总体有效率；
               小规模 CFD 成功率 ≈ 75%（USER-REPORTED，未本地复现）
  已生成文件   0（本仓库未执行任何批量生成）
```

```text
状态语义（本项目统一使用）:
  VERIFIED              已验证事实
  CURRENT_BASELINE      当前实际采用的技术基线
  PROPOSED              待验证的工作设想
  PENDING               尚无决定
  HISTORICAL / SUPERSEDED  历史有效但已不再约束当前工作
  NOT EXECUTED          尚未实际运行
```

```text
本次（2026-10-23）文档整理解除的项目规划约束:
  6D 生产 DOE（d = 6, seed = 1）           -> HISTORICAL / SUPERSEDED
  单一生产序列 / ONE_6D_POINT_ONE_CASE 名称 -> HISTORICAL / SUPERSEDED
  默认 200000 候选数                        -> HISTORICAL DEFAULT
  FINAL_N_TRAIN_MAX / N_TEST / ladder       -> 参考值与候选梯度
  生产规模冻结作为本地几何生成前置条件       -> 不再适用

继续有效的技术冻结（未解除）:
  几何算法 / legacy 回归 / GeomTurbo 格式 / Generator 契约 / QC 契约
  11D 方案 A 参数范围数值（未修改）
  SS1 = 3.2 / SS2 = 0.8
  N = usable training case count 的定义
  训练集 / 验证集 / 测试集分离原则
```

历史记录（保留原文，不改写当时决定）：

```text
docs/DESIGN_FREEZE_2026-10-13.md    HISTORICAL / SUPERSEDED（规划约束）
docs/DOE_DECISION.md                DOE 方法决策保留，6D 生产约束失效
docs/SCALING_EXPERIMENT_DESIGN.md   统计原则保留，训练阶梯降为候选
docs/PARAMETER_SPACE_RECONCILIATION.md  历史维度对照
docs/GEOMTURBO_PRODUCTION_200K.md   生成器说明保留，200000 为历史默认值
```

```text
本轮没有做的事:
  未修改任何 Python 程序 / 测试 / YAML 配置 / GeomTurbo 模板 / 历史数据
  未批量生成 GeomTurbo；未启动 CFD；未启动 GPU 训练
  未创建新的 FINAL / FROZEN 决策
```

## PROJECT

Two-dimensional compressor cascade AI4S CFD data-generation and scaling-law project.

Research target:

```text
E = f(N, P)
```

Current phase: **TRANSITION / PLANNING** — local 11D geometry generation, geometry QC,
data management and (later) GPU training planning. CFD execution is handled by the
senior engineer on a separate server. See `## TRANSITION STATUS` above and
`docs/PROJECT_TRANSITION_PLAN.md`.
No model training in this phase.

## CURRENT_STATUS

```text
Repository baseline             PASS
Legacy preservation             PASS
Legacy audit                    PASS
Environment freeze              PASS
Legacy range freeze             PASS

DOE design review               PASS
DOE benchmark                   PASS
DOE decision                    PASS / 方法决策保留（6D 部分 HISTORICAL）
Scaling statistical design      PASS

FINAL_DOE                       SCRAMBLED_SOBOL — 方法保留
SOBOL_SEED                      1（HISTORICAL DEFAULT；三组种子 PENDING）

Design freeze (2026-10-13)      HISTORICAL / SUPERSEDED（规划约束；原文保留）
N definition                    N = usable training case count        RETAINED
FINAL_N_TRAIN_MAX               100000 usable training cases          参考值
FINAL_N_TEST                    20000 usable test cases (fixed)       参考值
TRAIN_TEST_RATIO                5:1                                   参考值
MIN_USABLE_TRAIN_TEST_CASES     120000                                参考值
FINAL_N_LADDER                  1000..100000                          候选梯度
SOBOL_MASTER_M                  m >= 17（历史下界；不再是当前约束）
GEOMETRY_REUSE                  DISABLED / NOT ACTIVE（默认假设保留）
PRODUCTION_ROUTE                ONE_6D_POINT_ONE_CASE（名称 HISTORICAL）
FINAL_VALIDATION_POLICY         PENDING（验证集将用于 Early Stopping）
FINAL_N_VALIDATION              PENDING（当前计划目标 10000）
FINAL_PRODUCTION_RANGES         PENDING（CFD 侧；本地几何生成不再阻塞）
FINAL_RAW_CFD_ATTEMPTS          PENDING（CFD 侧）
FAILURE_RESERVE_POLICY          PENDING（由实测有效率 66.67% 需求 + 75% 现状替代）

Geometry regression fixtures    PASS
Geometry generator contract     PASS
02_generate_geometry.py         PASS
Geometry QC contract            PASS
03_geometry_qc.py               PASS
Local geometry pipeline         PASS

Geometry Range Review V1        DONE / ARCHIVED  (30 cases, C800001..C800030,
                                legacy ranges; historical stage, FROZEN RECORD)
Geometry Range Review V2        DONE / HISTORICAL (40 cases, C810001..C810040,
                                exploratory ranges, NOT production)
V2 Geometry QC                  40/40 PASS       (geometry_qc_v1_hard)
V2 senior review package        DELIVERED        (no advisor acceptance recorded:
                                human_acceptance / human_comment still empty)

Parameter sensitivity 100 cases DONE / EXPLORATORY (C820001..C820100; 100/100
                                generated, 100/100 hard QC; 13-parameter scan +
                                boundary check; newest sensitivity scan)
Ks1/Ks2 dedicated review 57     DONE / EXPLORATORY (C830001..C830057; 57/57)
Geometry final decision V1      DONE / EXPLORATORY FINAL (C840001..C840040 new +
                                9 reused = 49 rows; 11 geometry dimensions KEEP)
SS1 / SS2                       3.2 / 0.8 FIXED_BY_REVIEW (human decision made
                                AFTER the 100-case scan; that scan DID vary them)
C820 human engineering review   RECORDED 2026-10-21 (85 ACCEPT / 15 REJECT;
                                100/100 decided; per-case reject reasons still missing)
FINAL_PRODUCTION_RANGES         PENDING（CFD 侧；不再是本地几何生成阻塞项）
Production DOE dimension        HISTORICAL / SUPERSEDED: d = 6 (2026-10-13);
                                current geometry sampling is 11-D
                                (config/geometry_ranges_frozen_a.yaml)
Human SHAPE acceptance        85/100 recorded (C820); NO mesh/CFD/aero acceptance
Geometry ranges (11-D)         CURRENT_BASELINE 2026-10-21 (scheme A, values unchanged):
                               Metal2 6.0-32, others unchanged;
                               config/geometry_ranges_frozen_a.yaml
GeomTurbo production entry     code/generate_geomturbo_production.py
                               PREPARED / NOT EXECUTED (d=11)
Default sample count           200000  HISTORICAL DEFAULT (not the current plan)
Current production plan        PROPOSED / NOT EXECUTED: 150000 / 15000 / 30000
                               candidates -> 100000 / 10000 / 20000 usable
Seed values                    PENDING (three independent fixed seeds)
GeomTurbo files generated      0 (no batch run has been executed)
CFD production                 handed to the senior engineer's server (not local)
AI training (GPU HPC / Slurm)  PROPOSED / NOT STARTED
FINAL_PRODUCTION_RANGES        PENDING

01_generate_design.py           PREPARED / NOT EXECUTED / HISTORICAL (6-D path)
generate_geomturbo_batch.py     PREPARED / NOT EXECUTED / HISTORICAL (6-D path)
DO-NOT-RUN (historical)         the 6-D production design path is superseded and is
                                NOT the current generation route. Current route:
                                11-D GeomTurbo from config/geometry_ranges_frozen_a.yaml,
                                started manually by the user with --execute.
NUMECA bring-up C900001         KEPT (bring-up only; never in the
                                production case sequence)
NUMECA / CFX / HPC              NOT STARTED
```

## CONFIRMED FACTS

```text
Conda environment = ai4s
Python = 3.10.20

Legacy DOE:
LatinHypercube
d = 6
optimization = random-cd
seed = 1
historical N = 1891
```

`1891` is the historical experiment size and is **NOT** the target size of the new
project.

Legacy `1891` role (frozen): historical reference / regression / Golden-Case source
only — **NOT** part of the new production Sobol pool.

```text
Geometry = f(Xthick, Tmax, Metal2, Solidity)
OperatingCondition = f(Incidence, Mach)
```

The CFX implementation of `Incidence` / `Mach` is still **TBD**; guessing is
forbidden.

## DOE STATUS（2026-10-23：方法决策保留，6D 生产约束为 HISTORICAL / SUPERSEDED）

```text
FINAL_DOE = SCRAMBLED_SOBOL — DOE 方法决策保留 / 继续沿用
  method   = scipy.stats.qmc.Sobol
  d        = 6            -> HISTORICAL / SUPERSEDED（当前几何采样 d = 11）
  scramble = True         -> 保留
  seed     = 1            -> HISTORICAL DEFAULT（三组独立种子，数值 PENDING）
  ordering = native Sobol sequence order   -> 保留
  nesting  = prefix nesting (同一组内 D_N = first N)  -> 保留

A1 Master LHS + raw prefix
STATUS = BASELINE_ONLY      （历史基准结论不变）

A2 Master LHS + greedy maximin ordering
STATUS = DEPRIORITIZED      （历史基准结论不变）

B Scrambled Sobol
STATUS = FINAL_PRODUCTION_DOE   （当时的方法决策；6D 绑定部分已失效）
```

Legacy:

```text
historical 1891 =
  reference / regression / Golden-Case source only;
  NOT part of the new production Sobol pool
```

Parameter order (recorded for the historical 6-D DOE — `HISTORICAL / SUPERSEDED`):

```text
0 Xthick
1 Tmax
2 Metal2
3 Solidity
4 Incidence
5 Mach
```

```text
当前几何生成参数顺序（11 维，config/geometry_ranges_frozen_a.yaml）:
  Xthick, Tmax, Metal2, Solidity, Metal1, T1, T2, Xmean, K_m, Ks1, Ks2
```

Production principles (staged 2026-10-13; 组内原则保留):

```text
one fixed Sobol sequence per dataset group   （现在是三组，各组一条）
D_N = first N points of that group's sequence
no independent redraw per N
no sorting / reordering
no LHS / Sobol mixing in the same pool
```

References:

- `docs/DOE_DECISION.md`
- `docs/SCALING_EXPERIMENT_DESIGN.md`
- `docs/PROJECT_TRANSITION_PLAN.md`

## PRODUCTION SCALE (2026-10-13 record — HISTORICAL / SUPERSEDED as a constraint)

> 2026-10-23：本节保留为历史记录。`N` 的定义继续有效；
> 规模数值降为参考值，训练阶梯降为候选梯度。
> 当前计划（PROPOSED / NOT EXECUTED）：Train 150000 / Validation 15000 / Test 30000
> 候选，对应目标有效 100000 / 10000 / 20000。见 `docs/PROJECT_TRANSITION_PLAN.md`。

```text
N = usable training case count          （RETAINED，定义不变）
    (test / validation / failed / rejected cases are NOT counted)
```

```text
FINAL_N_TRAIN_MAX           = 100000 usable training cases   参考值
FINAL_N_TEST                = 20000 usable test cases        参考值
TRAIN_TEST_RATIO            = 5:1                            参考值
MIN_USABLE_TRAIN_TEST_CASES = 120000                         参考值
FINAL_N_LADDER              = 1000 2000 5000 10000 20000 35000 50000 70000 100000
                                                             候选梯度（非强制）
```

```text
FINAL_RAW_CFD_ATTEMPTS = PENDING   （CFD 侧；最低总体有效率 66.67% 为当前规划依据）
FAILURE_RESERVE_POLICY = PENDING
```

```text
SCOPE NOTE (2026-10-21, 更新 2026-10-23):
  2026-10-13 的冻结是关于可用 CFD 训练/测试样本数 (N)。
  它不是 GeomTurbo 候选数量。
  代码默认 200000 = HISTORICAL DEFAULT；
  当前候选数计划为 195000（PROPOSED，NOT EXECUTED）。
```

The retired umbrella term `FINAL_NMAX` must no longer be used for current status,
because it conflates training `N_max`, usable total and raw CFD attempts.
Full freeze record (historical): `docs/DESIGN_FREEZE_2026-10-13.md`.

## PREPARED PRODUCTION PIPELINE (2026-10-13 — HISTORICAL 6-D PATH, NOT EXECUTED)

> 2026-10-23：这条 6-D 生产流水线已被 `HISTORICAL / SUPERSEDED` 取代，
> 不是当前几何生成路线。当前路线是 `code/generate_geomturbo_production.py`
> （11 维、三组独立 Sobol，PROPOSED / NOT EXECUTED）。
> 下列代码保留在仓库中，但**不得**当作当前生产入口执行。

One command (historical 6-D entry point; **DO NOT RUN**):

```bash
conda run -n ai4s python code/generate_geomturbo_batch.py \
  --ranges config/ranges_legacy.yaml \
  --n-train 100000 \
  --n-test 20000 \
  --qc-output geometry/geometry_qc_production.csv
```

Pipeline:

```text
Sobol design generation
  -> fixed train/test assignment
  -> master_design.csv
  -> profile generation
  -> .geomTurbo generation
  -> Geometry QC
```

```text
ranges are RUNTIME CONFIGURABLE (--ranges PATH)
legacy ranges are NOT the final production ranges
after the owner confirms the ranges, ONLY this argument changes:

  --ranges config/ranges_production_v1.yaml

(no generator code change required)

production QC output path = geometry/geometry_qc_production.csv
  kept separate from the bring-up report geometry/geometry_qc.csv
```

Bring-up provenance (IMMUTABLE — never part of the production case sequence):

```text
C900001 = bring-up only
design/bringup/                        (tracked)
docs/NUMECA_BRINGUP_CASE_C900001.md    (tracked; records SHA256)
geometry/profiles/C900001.dat          (local artifact, kept)
geometry/geomturbo/C900001.geomTurbo   (local artifact, kept)
geometry/geometry_qc.csv               (local bring-up report, kept)
```

Do not delete or overwrite any of the above.

The three `local artifact` paths above are deliberately **NOT tracked by git**
(the rules are written with comments at the end of `.gitignore`): they stay on
this laptop, and `docs/NUMECA_BRINGUP_CASE_C900001.md` records their SHA256.

## GEOMETRY RANGE REVIEW — V1 (archived) / V2 (historical)

```text
V1  legacy range review     30 cases  C800001..C800030   generation 30/30, QC 30/30 PASS
    archive (FROZEN RECORD, do not edit):
        analysis/geometry_review/archive/v1_legacy_review/
    known gap recorded there: the V1 plotting script was overwritten by the V2
    rewrite while untracked, so it is not recoverable from git; all V1 figures,
    tables, QC report and logs ARE archived.

V2  exploratory range review 40 cases C810001..C810040  generation 40/40, QC 40/40 PASS
    ranges    : analysis/geometry_review/ranges_exploratory_v2.yaml
                (status EXPLORATORY_NOT_APPROVED — never written into config/)
                Xthick 0.10-0.60, Tmax 0.025-0.095, Metal2 0-32 deg,
                Solidity 0.7-2.5, Incidence 0 (fixed), Mach 0.5 (fixed)
    results   : analysis/geometry_review/geometry/            (40 .dat + .geomTurbo)
                analysis/geometry_review/geometry_qc.csv      (40 rows, all PASS)
                analysis/geometry_review/figures/             (6 PNG @200 dpi)
    deliverable: analysis/geometry_review/senior_review_v2/   (40-case review package)
                 analysis/geometry_review/senior_review_v2.zip (local delivery copy only)
    independent facts: min_gap 0.014494..0.072696 m (hard gate > 0, all pass);
                 envelope_clearance negative for 5 cases (diagnostic only, NOT a
                 collision and NOT a QC failure); 25 unique blade outlines
                 (40 cases = 25 blades + 15 pitch-only variants)

Frozen core NOT touched by any of this:
    code/geometry_legacy_v1.py (Metal1 = 53 deg), legacy/, config/ranges_legacy.yaml,
    tests/ + tests/fixtures/, docs/GEOMETRY_GENERATOR_CONTRACT.md, GEOMETRY_QC_CONTRACT.md

WARNING — do not overclaim:
    Geometry QC PASS  !=  aerodynamically reasonable
    Geometry QC PASS  !=  mesh / CFD feasible
    the V2 exploratory ranges are NOT the approved production ranges
    no formal DOE and no CFD production has been executed
```

Full session record: `docs/SESSION_DELIVERY_2026-10-15.md` (V1/V2 stage).

## GEOMETRY PARAMETER RESEARCH (2026-10-17 — EXPLORATORY, NOT PRODUCTION)

```text
Chain (each step has its own disjoint case-number block):

1) 100-case sensitivity + boundary check   analysis/geometry_review/parameter_sensitivity_v1_100cases/
   case_id C820001..C820100
   S1=60 single-factor, S2=20 2x2 coupling, S3=20 adaptive anchor/variant
   100/100 generated, 100/100 hard QC PASS, 100/100 frozen QC PASS
   overview_001_050.png + overview_051_100.png  (two 50-panel overviews)
   case_design.csv (100 rows, parameters) / case_metrics.csv (100 rows, geometry metrics)
   automatic screening (NOT a freeze):
       FIX_CANDIDATE  2  -> SS1, SS2
       KEEP_CANDIDATE 10 -> Xthick Tmax Metal2 Solidity Metal1 T1 T2 Xmean K_m Ks1
       REVIEW         1  -> Ks2
   IMPORTANT: SS1 2.4-4.0 and SS2 0.5-1.1 were VARIABLES in this scan.
              The current freeze (3.2 / 0.8) happened later; do not rewrite
              the historical scan as if SS1/SS2 had always been fixed.

2) 57-case Ks1/Ks2 dedicated review        analysis/geometry_review/ks1_ks2_review_v1/
   case_id C830001..C830057, 57/57 generated + hard QC + frozen QC PASS
   SS1 = 3.2 / SS2 = 0.8 FIXED_BY_REVIEW in every case (human decision)
   Ks1 / Ks2 at that stage: FURTHER_REVIEW

3) Geometry parameter final decision V1    analysis/geometry_review/parameter_final_decision_v1/
   new cases C840001..C840040 (49 design rows incl. 9 reused), 49/49 PASS
   authority: final_geometry_parameters.yaml + FINAL_DECISION.md
   geometry_dimension = 11, operating_dimension = 2, total_candidate_dimension = 13
   KEEP: Xthick 0.10-0.60, Tmax 0.025-0.095, Metal2 0-32 deg, Solidity 0.7-2.5,
         Metal1 48-58 deg, T1 0.010-0.018, T2 0.008-0.016, Xmean 0.06-0.18,
         K_m 0.10-0.35, Ks1 3.0-7.0, Ks2 0.05-0.20
   FIX : SS1 = 3.2, SS2 = 0.8 (FIXED_BY_REVIEW / HUMAN_REVIEW_DECISION)
   joint constraint JC_XMEAN_KS1_KM (K_m >= 0.15 for 0.18 < Xmean <= 0.20)
       recorded but NOT active at the final bound (upper bound stays 0.18)

Current parameter status for further parametric work:
    11 geometry parameters OPEN (ranges above)
    SS1 = 3.2, SS2 = 0.8 FIXED
    Incidence, Mach = operating conditions (fixed 0 deg / 0.5 in these experiments;
    they do not change the blade geometry; CFX implementation still TBD)

Code evidence for the fixed values (verified 2026-10-21):
    code/geometry_legacy_v1.py:44-45                     SS1 = 3.2, SS2 = 0.8
    code/geometry_parametric_exploratory_v1.py:73-74     defaults SS1/SS2 = 3.2/0.8
    tools/geometry_final_decision_v1.py:86               FIXED = {SS1: 3.2, SS2: 0.8}
    tools/geometry_ks1_ks2_review_v1.py:75               FIXED = {SS1: 3.2, SS2: 0.8}

WARNING — do not overclaim:
    "FINAL" above means FINAL ONLY for the EXPLORATORY geometry DOE.
    It is NOT a production range, NOT a CFD certification.
    No NUMECA / CFX run, no formal DOE, no production design has been executed.
    Explicitly still required before production:
        - CFD verification of the high-Xmean / high-Ks1 corner
        - CFD verification of the Ks2 rear-camber control range
        - threshold calibration on the historical 1891-sample population
        - real implementation of the joint constraint inside the DOE sampler
```

Full session record: `docs/SESSION_DELIVERY_2026-10-17.md`.
Regression status at this documentation sync (2026-10-21):
`conda run -n ai4s python -m pytest -q` -> 155 passed, 17 subtests passed
(2026-10-21, including the 24 production-entry tests; earlier same-day count 131).

## PARAMETER SPACE RECONCILIATION (2026-10-21)

Two different stages must not be conflated:

```text
HISTORICAL / SUPERSEDED（2026-10-23）:
Stage A — production DOE (recorded 2026-10-13)
    d = 6 : [Xthick, Tmax, Metal2, Solidity, Incidence, Mach]
    该路线已不再是当前几何生成路线；当前为 11D（frozen_a 配置）
    FINAL_PRODUCTION_RANGES 仍 PENDING（CFD 侧）

Stage B — geometry parameter research (2026-10-17, exploratory)
    11 geometry parameters + 2 operating parameters (SS1/SS2 fixed)
    analysis only: NOT a production DOE, NOT approved ranges
```

```text
The 13-dim space is NOT "the production DOE frozen at 13 dims".
当前也没有“13 维生产 DOE”这个目标；几何采样固定为 11 维。
The 2026-10-13 freeze document is preserved unchanged (historical record).
"13" has two different meanings and must be written explicitly:
    (a) generator PARAM_NAMES = 13 shape parameters (includes SS1/SS2)
    (b) candidate DOF = 11 KEEP geometry + 2 operating = 13 (SS1/SS2 fixed)
```

Full comparison table, physical definitions, independence facts and the Metal1 /
Incidence distinction: `docs/PARAMETER_SPACE_RECONCILIATION.md`.

```text
Metal1      = inlet METAL angle (geometry)   legacy 48 + DeltaBeta(5) = 53 deg
Incidence   = inlet FLOW-angle operating variable; CFX implementation TBD
Verified    : changing only Incidence/Mach gives byte-identical .dat / .geomTurbo
Open        : legacy comment says 49 deg, code uses 53 deg (4 deg, unconfirmed)
```

Joint constraint status:

```text
JC_XMEAN_KS1_KM : K_m >= 0.15 for 0.18 < Xmean <= 0.20
current Xmean upper bound = 0.18  -> the interval is EMPTY -> cannot trigger
active_at_final_bound = false (kept)
=> recorded as a historical / inactive candidate, NOT a production hard constraint,
   NOT implemented in any sampler
```


## C820 HUMAN ENGINEERING REVIEW (2026-10-21)

```text
review file : analysis/geometry_review/parameter_sensitivity_v1_100cases/human_review_2026-10-21.csv
analysis    : analysis/geometry_review/parameter_sensitivity_v1_100cases/HUMAN_REVIEW_2026-10-21.md
rows        : 100 (case_design.csv order; 100 unique IDs)
REJECT      : 15  -> C820033 C820034 C820035 C820036 C820043 C820062
                     C820081 C820082 C820083 C820084
                     C820089 C820090 C820091 C820092 C820100
ACCEPT      : 85  (shape reasonable only; NOT mesh/CFD/aero acceptance)
ACCEPT      : 0
source      : senior engineer review (师兄), transcribed by the owner
comment     : pending (per-case reasons NOT provided; never invented)
```

```text
All 15 rejected cases are hard QC PASS and frozen QC PASS
=> the current automatic QC cannot detect this class of engineering problem.
Field separation: case_metrics.csv = geometry QC; human_review_*.csv = human label.
These labels DO NOT change any C830 / C840 historical decision.
```

Boundary findings (evidence-based, NOT decisions):

```text
supported single-parameter tightening candidates
    K_m upper bound (only at low Xmean ~ 0.08): 0.2012 ACCEPT,
        0.225 / 0.2667 / 0.3083 / 0.35 rejected consecutively -> candidate ~ 0.20
    Metal2 lower bound: Metal2 = 0 rejected; 21.33 / 32 / 15 ACCEPT
        -> lower bound must be > 0, exact value unknown

interaction-driven (do NOT turn into a simple hard bound yet)
    K_m x Xmean : 0.2875 rejected at Xmean 0.09, ACCEPT at 0.15;
                  0.3125 ACCEPT at Xmean 0.164
    S3 groups C820081-084 and C820089-092 : whole group rejected
        (all 4 variants) -> common background, not the varied parameter
    C820100 : only SS2 differs from its anchor C820097 (1.0742 -> 0.59),
        but SS2 = 0.59 is ACCEPT in another background and the S1 SS2
        sweep (0.5 / 0.9 / 1.1) is ACCEPT -> interaction, not a simple bound

insufficient evidence
    exact Metal2 lower bound, Solidity upper bound, SS2 low bound,
    exact K_m threshold, cause of the human rejection
```

```text
No data conflict with C830/C840: the 9 reused C840 cases
(C820027/028/029, C830026/027/028, C830031/032/033) contain none of the 15 rejects
(parameter vectors compared one by one).

But there IS a judgement-scope conflict (recorded, NOT rewritten):
    C830 has 9 cases in the same "low Xmean + high K_m" direction
        (Xmean=0.06, K_m=0.35: C830021-025, C830050-053), all geometry QC PASS,
        but never human-reviewed.
    C840's soft-risk audit located the max RCR 0.2529 at C830050 in that corner
        and kept it as "existing historical morphology", so K_m stayed KEEP
        0.10-0.35 (a numerical substitution result, NOT an engineering review).
    The 2026-10-21 human review rejects that direction at Xmean 0.08-0.09
        (C820033-036, C820062).
=> keep the historical records as they are; K_m upper bound becomes a
   human-decision item (candidate tightening), never an automatic rewrite.
```


## GEOMTURBO PRODUCTION BASELINE — SCHEME A (2026-10-21; values unchanged 2026-10-23)

> 2026-10-23：方案 A 的**数值**继续作为当前生成器基线（`CURRENT_BASELINE`），
> 原冻结记录保留。生产数量不再是"200000 待定"，而是下面的三组计划（`PROPOSED`）。
> 三个种子数值仍为 `PENDING`。

```text
Config (runtime)   : config/geometry_ranges_frozen_a.yaml   status = FROZEN（数值未改）
Decision file      : analysis/geometry_review/parameter_final_decision_v1/
                     final_geometry_parameters.yaml
                     status = FROZEN_FOR_GEOMTURBO_GENERATION
Freeze ID          : geometry_ranges_frozen_a
Freeze scope       : geomturbo_geometry_generation_only
                     (NOT a CFD production-range approval)
FINAL_PRODUCTION_RANGES : PENDING（CFD 侧；不再是本地几何生成阻塞项）
2026-10-13 DOE freeze   : NOT modified（其规划约束已 HISTORICAL / SUPERSEDED）

11 free geometry parameters (order = Sobol dimension order):
  Xthick 0.10-0.60, Tmax 0.025-0.095, Metal2 6.0-32.0, Solidity 0.7-2.5,
  Metal1 48-58, T1 0.010-0.018, T2 0.008-0.016, Xmean 0.06-0.18,
  K_m 0.10-0.35, Ks1 3.0-7.0, Ks2 0.05-0.20
Fixed: SS1 = 3.2, SS2 = 0.8
Only change vs the 2026-10-17 exploratory config: Metal2 lower 0.0 -> 6.0
No joint constraint; JC_XMEAN_KS1_KM stays inactive; no shape filter added
Incidence / Mach are NOT part of this geometry sampling
```

```text
Production entry   : code/run_geomturbo.py（推荐，按 group 启动）
                     code/generate_geomturbo_production.py（底层，需要 --execute）
Status             : PREPARED / NOT EXECUTED（已生成 0 个文件）
Sampling           : Sobol d=11, scramble=True, native order, prefix nesting
                     m = smallest m with 2^m >= count
Seed               : 三组各一个固定种子，数值 PENDING
                     （代码默认 seed=1 保留为默认值，不是三组计划的一部分）
Current plan       : Train 150000 / Validation 15000 / Test 30000
                     -> 目标有效 100000 / 10000 / 20000（PROPOSED / NOT EXECUTED）
Output dirs        : production_geomturbo/train|val|test（尚未创建）
Case IDs           : G + 7 digits，组内各自从 G0000001 开始
                     全局身份 = group + seed + sobol_index
                     （run_geomturbo.py 写入 group_info.json；case_id 格式不变）
Metadata           : config_snapshot.yaml, manifest.csv, generation_summary.json
                     （不含 group / QC 状态；需后续数据管理层补充）
Resume             : --execute --resume; verifies size+sha256, regenerates
                     corrupt/missing files, refuses config/seed/order mismatch
Safety             : no file is written without --execute
Storage estimate   : ~14.2 kB per file; ~2.9 GB at 195000 candidates
                     (--plan default estimate: 15000 B/case)
Tests              : 24 production-entry tests with a STUB renderer (no real
                     GeomTurbo); full suite = 155 passed + 17 subtests (2026-10-21)
Usage guide        : docs/GEOMTURBO_PRODUCTION_200K.md
Current plan doc   : docs/PROJECT_TRANSITION_PLAN.md
```

```text
User must run manually (per group, after fixing seeds and count):
    conda activate ai4s
    python code/generate_geomturbo_production.py --plan \
        --count <N> --seed <SEED> --output-dir production_geomturbo/<group>
    # small real export validation first (e.g. --count 10 in a scratch dir)
    python code/generate_geomturbo_production.py --execute \
        --count <N> --seed <SEED> --output-dir production_geomturbo/<group>
    # or: ... --execute --resume

Current plan (PROPOSED / NOT EXECUTED):
    train      150000 candidates / target 100000 usable
    validation  15000 candidates / target  10000 usable
    test        30000 candidates / target  20000 usable
Seed values are PENDING; each group needs its own output directory.

Not done here: no batch run, no real .geomTurbo, no mesh, no NUMECA/CFX, no training.
200000 is a historical code default, NOT the current plan.
Still to verify only by a real run: actual file size/runtime on this machine,
real sha256 spot checks, and filesystem behaviour at the decided file count.
```

## NEXT-STAGE SCREENING STRATEGY (2026-10-21)

```text
wide-range sampling + few simple hard constraints + automatic geometry screening
+ necessary human review
```

```text
1. SS1 = 3.2, SS2 = 0.8 stay FIXED
2. the other 11 geometry parameters stay variable (ranges still to be confirmed)
3. tighten a single-parameter bound only with clear evidence
4. do NOT prioritize complex multi-parameter joint constraints
5. generate many candidates and screen at geometry level before mesh / CFD
6. record every rejected sample and reason (append-only, never delete)
7. validate automatic QC against human judgement (current QC misses all 15)
8. training set stays nested (D_N prefix); test set fixed and independent
```

```text
NOT implemented this session: no sampler, no constraint filter, no new QC
algorithm, no re-run, no change of any range value.
```

Full strategy: `docs/GEOMETRY_SCREENING_STRATEGY_2026-10-21.md`.
Concrete constraint proposal (A/B/C, scheme A recommended):
`docs/GEOMETRY_CONSTRAINT_ANALYSIS_2026-10-21.md`.

Full session record: `docs/SESSION_DELIVERY_2026-10-21.md`.



## NEXT HUMAN DECISION — HIGHEST PRIORITY

```text
IMMEDIATE (next session, 2026-10-21 close):
  final GeomTurbo sample count N + compute / storage budget
  (200000 is only the code default; PROVISIONAL / NOT FINAL)
  -> then decide when to run a small real export validation and the actual run

THEN (independent, unchanged):
  Before implementing code/01_generate_design.py,
  the project must freeze the six-dimensional production ranges:

1. FINAL_PRODUCTION_RANGES   (owner / advisor confirmation)
```

The advisor input for that decision is now three packages:

```text
1. analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md
   (candidate 13-parameter space, SS1/SS2 fixed, Xmean upper bound 0.18)
2. analysis/geometry_review/parameter_sensitivity_v1_100cases/
   HUMAN_REVIEW_2026-10-21.md  + human_review_2026-10-21.csv
   (85 ACCEPT / 15 REJECT; per-case reject reasons still missing)
3. analysis/geometry_review/senior_review_v2/  (40 real V2 blades, historical stage)
```

Current review coverage (do not overstate it):

```text
C820 (100 cases) : 85 ACCEPT / 15 REJECT -> complete shape review
C830 (57 cases)  : no human review recorded
C840 (49 rows)   : no human review recorded
V2   (40 cases)  : no human review recorded (human_* still empty)
```

Until the advisor has given the missing per-case reasons and answered the CFD /
threshold-calibration items, no production range may be frozen.
`FINAL_PRODUCTION_RANGES` stays PENDING.

Independently still open:

```text
2. production DOE dimension: keep d = 6, or adopt 11 geometry + 2 operating?
3. FINAL_VALIDATION_POLICY / FINAL_N_VALIDATION
4. FINAL_RAW_CFD_ATTEMPTS   (after a real NUMECA/CFX failure-rate stress test)
5. K_m upper bound / Metal2 lower bound tightening (evidence documented,
   values NOT decided; final_geometry_parameters.yaml left unchanged)
   -> current proposal: Metal2 lower bound only; K_m upper bound NOT tightened
6. whether Solidity / Metal1 enter the production DOE
7. which geometry constraint scheme to adopt (A / B / C proposal in
   docs/GEOMETRY_CONSTRAINT_ANALYSIS_2026-10-21.md; scheme A = Metal2 >= 6.0
   recommended; A-min variant Metal2 >= 2.0 has the same 100-sample effect)
```

The exact values MUST NOT be decided by an AI agent.

## NEXT ENGINEERING TASK（2026-10-23 — PROPOSED，未执行）

```text
A) 几何候选池（当前主线；PROPOSED / NOT EXECUTED）
   1. USER DECISION: 三个固定种子 + 组间唯一身份方案 + 去重策略
   2. 每组先 --plan（只读），核对 count / seed / output-dir / 指纹 / 存储估算
   3. 每组做少量真实导出验证（例如 --count 10 到临时目录），确认实际序列化格式
   4. 用户手动 --execute（可 --resume）；三组目录相互独立
   5. 核对文件数 / manifest / sha256
   6. 几何 QC 适配器：production pool（.geomTurbo + manifest）
      -> 冻结 QC 步骤（03_geometry_qc.py 目前期望 design CSV + profile/geomturbo 树，
         适配器仍 PENDING）
   7. 交付清单：group / seed / sobol_index / case_id / 参数向量 / QC 状态 / 去重结果
      -> 交给师兄进行 CFD（交错进行）

B) CFD 侧（不由本地实现）
   网格、边界条件、工况、求解、收敛与有效性检查、任务调度
   本地只接收“有效 / 无效 + 原因”的交接信息（格式 PENDING）

C) 训练侧（PROPOSED / NOT STARTED）
   有效 CFD 结果返回 -> 数据快照 -> 阶段性训练（GPU HPC + Slurm + Early Stopping）
   详见 docs/TRAINING_TRANSITION_PLAN.md
```

```text
历史说明：2026-10-13 的 6-D 生产 DOE 路线（01_generate_design.py /
generate_geomturbo_batch.py）已被 HISTORICAL / SUPERSEDED 取代，
不再是当前工作项，也不得被 Agent 重新激活为“当前必做”。
```

## OPEN HUMAN DECISIONS

Closed / retired:

- FINAL_DOE 方法（scrambled Sobol）—— 方法保留，6D 绑定部分 HISTORICAL / SUPERSEDED
- legacy 1891 future role（historical reference / regression / Golden-Case only）
- production scale（2026-10-13）—— 降为参考值 / 候选梯度，不再强制
- geometry reuse（DISABLED / NOT ACTIVE）—— 作为默认假设继续有效
- ONE_6D_POINT_ONE_CASE —— 名称 HISTORICAL；实际仍是“一个参数点一个 case”
- GeomTurbo generation ranges, scheme A（2026-10-21；Metal2 >= 6.0；
  frozen only for geometry generation, not for CFD production）—— 数值保持不变

Still open (Agent must not decide):

- 三个 Sobol 种子的具体数值
- 去重策略与容差（不同种子不保证无重复参数 / 相同几何）
  （全局样本身份已由 group + seed + sobol_index 解决，见 group_info.json）
- 195000 / 130000 这组规模是否最终采纳（当前为 PROPOSED）
- 每次真实导出验证的执行时间与规模
- adapter from the generated .geomTurbo + manifest pool to the frozen QC step
- CFD 交接文件命名 / 结果容器格式 / 状态码字典（与师兄共同确定）
- CFD 侧运行工况取值（Incidence / Mach 的实际配置）
- per-case reasons for the 15 C820 REJECT cases
- K_m upper bound（只有未来证据支持时才收紧；当前保持 0.35）
- 训练启动阈值、训练阶梯最终档位、验证集规模与早停参数
- 续训 vs 从头训练的正式对照方案
- FINAL_VALIDATION_POLICY / FINAL_N_VALIDATION / FINAL_RAW_CFD_ATTEMPTS
- final `E` definition
- model-size `P` grids
- GPU 平台实际额度 / 分区 / 队列 / 时间上限

## REMAINING DOCUMENTATION NOTES (not errors, do not "fix")

```text
49 vs 50 rows       : C840 case_design.csv / case_metrics.csv hold 49 DATA rows
                      + 1 header = 50 text lines. FINAL_DECISION.md's file table
                      says "50 行" using the text-line convention. Generated report
                      intentionally left unchanged.
provenance git_head : experiment provenance keeps the RUN-TIME head (02e57d1),
                      not the latest commit; cite it as "run-time HEAD".
volume              : 100-case README says ~2.36 MB = provenance.output_size_mb
                      (2.359, output artifacts only); the current directory is
                      ~2.5 MB because it also contains the untracked logs/ dir.
untracked logs      : ks1_ks2_review_v1/logs/ and
                      parameter_sensitivity_v1_100cases/logs/ stay untracked.
                      Verified: tools/ only WRITE logs, never read them, so there is
                      no reproduction dependency; risk is only "logs not in VCS".
test counts         : 111/111 = record of the 2026-10-15 run; latest =
                      155 passed + 17 subtests (2026-10-21, includes the
                      24 production-entry tests; earlier same-day 131).
```


## BLOCKED EXTERNAL INFORMATION

CFD mesh / boundary conditions / solver configuration / result format details belong
to the senior engineer's CFD server and are not confirmed here. GPU HPC quotas,
partitions, queue rules and time limits are also unconfirmed.

## NEW CHAT START HERE

```text
FIRST TASK (2026-10-23):
Read docs/PROJECT_TRANSITION_PLAN.md. The current plan is three independent
11-D Sobol groups (Train 150000 / Validation 15000 / Test 30000 candidates ->
100000 / 10000 / 20000 usable). It is PROPOSED / NOT EXECUTED.
The outstanding decisions are: the three seed values and the
deduplication policy.  The group-qualified sample identity is already
expressed as group + seed + sobol_index (recorded in group_info.json).
Do NOT treat the 6-D production DOE as the current task; it is HISTORICAL / SUPERSEDED.
Do NOT start generation, CFD or training without an explicit user instruction.

SECOND TASK (geometry / QC track):
Implement (only after user approval) the production-pool -> frozen geometry QC
adapter and the delivery manifest (group / seed / sobol_index / QC status / dedup).
Do not change geometry mathematics, the QC contract or any frozen range value.

Read in this order:
  0. docs/PROJECT_TRANSITION_PLAN.md            (current stage plan)
  1. docs/TRAINING_TRANSITION_PLAN.md           (GPU / early stopping / test set)
  2. docs/SESSION_DELIVERY_2026-10-21.md        (parameter-space reconciliation +
                                                 human review + strategy + closeout)
  3. docs/SESSION_DELIVERY_2026-10-17.md        (100-case scan -> 57-case review
                                                 -> final decision, SS1/SS2 freeze)
  4. analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md
  5. analysis/geometry_review/parameter_sensitivity_v1_100cases/README.md
     + REPORT.md                                (100 real blades, C820001..C820100)
  6. analysis/geometry_review/parameter_sensitivity_v1_100cases/HUMAN_REVIEW_2026-10-21.md
     + human_review_2026-10-21.csv              (85 ACCEPT / 15 REJECT)
  7. docs/GEOMTURBO_PRODUCTION_200K.md          (generator usage; 200000 historical)
  8. config/geometry_ranges_frozen_a.yaml       (current geometry baseline, values unchanged)

GeomTurbo status at handoff:
  geometry baseline CURRENT_BASELINE (values unchanged); generator PREPARED /
  NOT EXECUTED; three-group plan PROPOSED / NOT EXECUTED; seed values PENDING;
  files generated 0; CFD on the senior engineer's server; training NOT STARTED;
  FINAL_PRODUCTION_RANGES PENDING (CFD side); AI training PROPOSED.

Do not treat the exploratory candidate ranges as approved production ranges.
Do not equate human shape ACCEPT or geometry QC PASS with mesh/CFD/aero validity.
Do not re-open SS1 = 3.2 / SS2 = 0.8 without an explicit human decision.
Do not rewrite history: the 100-case scan DID vary SS1 (2.4-4.0) and SS2 (0.5-1.1);
they were frozen afterwards.

Historical records (do not treat as current constraints):
  docs/DESIGN_FREEZE_2026-10-13.md    HISTORICAL / SUPERSEDED (planning constraints)
  docs/DOE_DECISION.md                6-D production DOE superseded
  docs/SCALING_EXPERIMENT_DESIGN.md   statistics retained, ladder is a candidate
Geometry review V1/V2 status: docs/SESSION_DELIVERY_2026-10-15.md.
Geometry parameter research status: docs/SESSION_DELIVERY_2026-10-17.md.
```

For a new AI conversation, upload first:

```text
1. PROJECT_HANDOFF.md
2. AGENT_INSTRUCTION.md
3. README.md                              (repository entry point)
4. docs/PROJECT_TRANSITION_PLAN.md        (current stage plan)
5. docs/TRAINING_TRANSITION_PLAN.md       (training plan)
6. docs/GEOMTURBO_PRODUCTION_200K.md      (generator guide; 200000 historical default)
7. config/geometry_ranges_frozen_a.yaml   (current geometry baseline)
8. docs/SCALING_EXPERIMENT_DESIGN.md      (statistical principles)
9. docs/DOE_DECISION.md                   (DOE method; 6-D part superseded)
10. docs/DESIGN_FREEZE_2026-10-13.md      (historical freeze record)
11. docs/SESSION_DELIVERY_2026-10-21.md
12. docs/SESSION_DELIVERY_2026-10-17.md
13. docs/PARAMETER_SPACE_RECONCILIATION.md
14. docs/GEOMETRY_SCREENING_STRATEGY_2026-10-21.md
15. docs/GEOMETRY_CONSTRAINT_ANALYSIS_2026-10-21.md
```

When continuing geometry work, also provide:

```text
16. docs/GEOMETRY_GENERATOR_CONTRACT.md
17. docs/GEOMETRY_QC_CONTRACT.md
18. analysis/geometry_review/README.md                  (review dir entry point)
19. analysis/geometry_review/parameter_sensitivity_v1_100cases/README.md + REPORT.md
20. analysis/geometry_review/parameter_sensitivity_v1_100cases/HUMAN_REVIEW_2026-10-21.md
    + human_review_2026-10-21.csv
21. analysis/geometry_review/parameter_sensitivity_v1_100cases/parameter_decisions.csv
22. analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md
21. analysis/geometry_review/senior_review_v2/README.md (40-case review package)
```

Only when a legacy audit is actually needed, also provide:

```text
legacy/blade_batch_generation.py
legacy/blade_batch_generation_template.geomTurbo
config/ranges_legacy.yaml
```

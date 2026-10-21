# AI4S Compressor CFD Project — Session Delivery
Date: 2026-10-17 (documented / synchronized on 2026-10-21)

> Delivery record for the 2026-10-17 geometry parameter research session.
> It complements, and does not replace, `PROJECT_HANDOFF.md`.
>
> Scope of this session: **13-parameter geometry sensitivity (100 cases) +
> Ks1/Ks2 dedicated review (57 cases) + geometry parameter final decision (40 new cases)
> + repository commit.**
> **No production design, no geometry production run, no mesh, no NUMECA/CFX, no CFD,
> no model training, no modification of the formal DOE or of a production range.**

## 1. Executive Summary

```text
A. 100-case 13-parameter sensitivity + boundary check   DONE / EXPLORATORY
   analysis/geometry_review/parameter_sensitivity_v1_100cases/   C820001..C820100
B. 57-case Ks1/Ks2 dedicated review                     DONE / EXPLORATORY
   analysis/geometry_review/ks1_ks2_review_v1/                   C830001..C830057
C. Geometry parameter final decision V1 (40 new cases)  DONE / EXPLORATORY FINAL
   analysis/geometry_review/parameter_final_decision_v1/          C840001..C840040
   (+ 9 reused historical cases = 49 design rows)
D. Repository commit                                     DONE
   commit 0cc61b8  research(geometry): archive parameter sensitivity and review experiments
E. Document synchronization (2026-10-21)                  DONE (Markdown only)
```

The production blocker is unchanged:

```text
FINAL_PRODUCTION_RANGES is still PENDING (owner / advisor confirmation).
The geometry parameter decision below is FINAL for the EXPLORATORY geometry DOE
only. It is NOT a production-range approval, NOT a CFD certification and NOT a
statement that any blade is aerodynamically acceptable or meshable.
```

## 2. Frozen core (read-only this session, unchanged)

```text
code/geometry_legacy_v1.py                         Metal1 = 53 deg, untouched
legacy/blade_batch_generation_template.geomTurbo   sha256 92c4296f2de27440aebaad9b03b9af4f9e09756fabff2298f4607a87f2c55119
config/ranges_legacy.yaml                          untouched
code/02_generate_geometry.py, code/03_geometry_qc.py  untouched
tests/ + tests/fixtures/                           untouched
docs/GEOMETRY_GENERATOR_CONTRACT.md  docs/GEOMETRY_QC_CONTRACT.md   untouched
```

The frozen generator is **not** modified by the research chain: the 13-parameter
generator used by these experiments is the separate
`code/geometry_parametric_exploratory_v1.py`, whose defaults reproduce the frozen
legacy geometry (`SS1 = 3.2`, `SS2 = 0.8`, `Metal1 = 53`).

## 3. Experiment timeline (case-number blocks are disjoint)

| 阶段 | 目录 | Case 号段 | 规模 | 状态 |
|---|---|---|---|---|
| V1 评审（legacy 范围） | `analysis/geometry_review/archive/v1_legacy_review/` | `C800001..C800030` | 30 | 历史阶段 / 已归档（冻结记录） |
| V2 评审（探索边界） | `analysis/geometry_review/senior_review_v2/` | `C810001..C810040` | 40 | 历史阶段 / 评审包已交付，无师兄评审记录 |
| 全参数敏感性 + 边界检验 | `analysis/geometry_review/parameter_sensitivity_v1_100cases/` | `C820001..C820100` | 100 | 探索性 / 未批准（最新敏感性扫描） |
| Ks1/Ks2 专项复核 | `analysis/geometry_review/ks1_ks2_review_v1/` | `C830001..C830057` | 57 | 探索性 / 未批准 |
| 几何参数最终裁决 V1 | `analysis/geometry_review/parameter_final_decision_v1/` | `C840001..C840040`（新增） | 40 新增 + 9 复用 = 49 行 | 探索性 FINAL（仅限探索性几何 DOE） |

```text
V1 / V2 是历史评审阶段，不代表当前最新进度。
C820（100-case）是全参数敏感性与边界检验的最新一轮扫描。
C830 / C840 是之后的复核与裁决阶段，权重高于 C820 的自动筛选建议。
```

## 4. 100-case sensitivity experiment (C820001..C820100)

```text
directory        analysis/geometry_review/parameter_sensitivity_v1_100cases/
case_id          C820001 .. C820100      (100 cases, unique parameter vectors)
stages           S1 = 60, S2 = 20, S3 = 20
                 S1 单因素扫描, S2 2x2 耦合, S3 自适应锚点 + 单参数变体
random/sobol seed 20261017
generation       100 / 100 succeeded
hard QC          100 / 100 PASS
frozen QC        100 / 100 PASS   (geometry_qc_v1_hard re-check, 0 mismatches)
criteria         parameter_screening_v1_tentative / 1.0.0
                 TENTATIVE_RESEARCH_THRESHOLDS_NOT_CALIBRATED
```

Parameter status **during that scan** (important — do not rewrite history):

```text
13 scanned parameters:
  Xthick  Tmax  Metal2  Solidity  Metal1  T1  T2  Xmean  K_m  Ks1  Ks2  SS1  SS2
SS1 scan range  2.4 .. 4.0      (variable in this experiment)
SS2 scan range  0.5 .. 1.1      (variable in this experiment)
Incidence = 0 deg, Mach = 0.5   (fixed; do NOT change the blade geometry)

automatic screening result (C820, NOT a freeze):
  FIX_CANDIDATE  2  -> SS1, SS2
  KEEP_CANDIDATE 10 -> Xthick Tmax Metal2 Solidity Metal1 T1 T2 Xmean K_m Ks1
  REVIEW         1  -> Ks2
```

So the historical 100-case scan **did vary SS1/SS2**. The `FIX_CANDIDATE` label is
only an automatic screening suggestion; the actual freeze (SS1 = 3.2,
SS2 = 0.8) is the later human review decision recorded in section 6.

Files (entry points):

| 文件 | 内容 |
|---|---|
| `README.md` | 目录入口（状态 / 决策分布 / 文件表 / 复现） |
| `REPORT.md` | 中文分析报告（完整性、13 参数敏感性、耦合、冗余、限制） |
| `overview_001_050.png` | Case C820001–C820050 的真实叶型总览 |
| `overview_051_100.png` | Case C820051–C820100 的真实叶型总览 |
| `case_design.csv` | 100 行：13 参数、归一化水平、阶段、选择理由与证据 |
| `case_metrics.csv` | 100 行：生成状态、硬性 QC、冻结 QC、全部几何指标 |
| `parameter_sensitivity.csv` | 13 行定量敏感性（S_contour / S_LE / S_TE / S_camber / S_thickness / S_cascade / S_comp 等） |
| `parameter_decisions.csv` | 13 行自动筛选建议（KEEP/REVIEW/FIX_CANDIDATE + 规则号） |
| `profiles.npz` | 高精度曲线（按 Case ID） |
| `screening_criteria.yaml` | 预登记判据、阈值、单位、规则 |
| `stage3_selection.json` | 第三阶段候选池与选择依据 |
| `provenance.json` | Git HEAD `02e57d1`、环境、哈希、运行与验收信息 |

Key numbers (from `REPORT.md`, real output on disk):

```text
min_gap                 0.0148856 .. 0.0698073 m   (all > 0)
junction angle jump     LE 7.747 .. 13.324 deg, TE 22.638 .. 24.585 deg
                        (legacy Ncirc=4 structural feature, diagnostic only)
curvature resolution stability 0.066 .. 0.080 (threshold 0.25, all usable)
failed / rejected cases 0
```

## 5. 57-case Ks1/Ks2 review (C830001..C830057)

```text
directory        analysis/geometry_review/ks1_ks2_review_v1/
case_id          C830001 .. C830057     (A=15, B=30, C=12)
generation       57 / 57
hard QC          57 / 57 PASS
frozen QC        57 / 57 PASS
SS1 / SS2        3.2 / 0.8  FIXED_BY_REVIEW in every case
Ks1 suggestion   FURTHER_REVIEW (K1_REVIEW; tendency FIX_IF_HIGH_XMEAN_REGION_EXCLUDED)
Ks2 suggestion   FURTHER_REVIEW (K2_REVIEW; tendency KEEP_IF_METAL2_SUBSTITUTION_REJECTED)
```

This is the stage where SS1/SS2 stop being variables. The 100-case `FIX_CANDIDATE`
suggestion and this human freeze must be described as two different steps.



## 6. Geometry parameter final decision V1 (C840001..C840040)

```text
directory        analysis/geometry_review/parameter_final_decision_v1/
reused pool      157 historical cases (100 sensitivity + 57 Ks1/Ks2 review)
new cases        40  (C840001 .. C840040), 49 design rows in total
generation       49 / 49
hard QC          49 / 49 PASS
frozen QC        49 / 49 PASS
criteria         final_decision_criteria_v1 / 1.0.0 (pre-registered)
status           FINAL for the EXPLORATORY geometry DOE only
```

Decision (authority: `final_geometry_parameters.yaml`, report: `FINAL_DECISION.md`):

| 参数 | 决定 | 范围 / 数值 | 说明 |
|---|---|---|---|
| `Xthick` | KEEP | 0.10 – 0.60 | 几何维 |
| `Tmax` | KEEP | 0.025 – 0.095 | 几何维 |
| `Metal2` | KEEP | 0 – 32 deg | 几何维 |
| `Solidity` | KEEP | 0.7 – 2.5 | 只改栅距 = 0.06 / Solidity |
| `Metal1` | KEEP | 48 – 58 deg | 几何维（legacy 默认 53 deg） |
| `T1` | KEEP | 0.010 – 0.018 | 几何维 |
| `T2` | KEEP | 0.008 – 0.016 | 几何维 |
| `Xmean` | KEEP | 0.06 – 0.18 | 上界未扩展（0.20 对容差敏感，0.22 全部拒绝） |
| `K_m` | KEEP | 0.10 – 0.35 | 几何维 |
| `Ks1` | KEEP | 3.0 – 7.0 | K1_KEEP：7/7 背景不可替代 |
| `Ks2` | KEEP | 0.05 – 0.20 | K2_KEEP：4/4 背景不可替代 |
| `SS1` | **FIX** | **3.2** | `FIXED_BY_REVIEW` / `HUMAN_REVIEW_DECISION` |
| `SS2` | **FIX** | **0.8** | `FIXED_BY_REVIEW` / `HUMAN_REVIEW_DECISION` |

```text
几何维度    = 11
运行条件维  = 2  (Incidence, Mach) — 不改变叶型, 且 CFX 实现仍为 TBD
总候选维度  = 13
```

Code evidence for the fixed values (verified on 2026-10-21):

```text
code/geometry_legacy_v1.py:44        SS1 = 3.2
code/geometry_legacy_v1.py:45        SS2 = 0.8
code/geometry_parametric_exploratory_v1.py:73-74      "SS1": 3.2, "SS2": 0.8
tools/geometry_final_decision_v1.py:86               FIXED = {"SS1": 3.2, "SS2": 0.8, ...}
tools/geometry_ks1_ks2_review_v1.py:75               FIXED = {"SS1": 3.2, "SS2": 0.8, ...}
analysis/geometry_review/parameter_final_decision_v1/final_geometry_parameters.yaml
    fixed_parameters: SS1 = 3.2, SS2 = 0.8, status FIXED_BY_REVIEW
```

Joint constraint recorded but **not active** at the final bound:

```text
JC_XMEAN_KS1_KM:  K_m >= 0.15   applies only to 0.18 < Xmean <= 0.20
active_at_final_bound = false
```

## 7. Explicitly NOT done this session

```text
No NUMECA meshing, no CFX solve, no CFD, no HPC run
No AI / ML training, no dataset construction
No formal DOE run, no production design, no geometry production
No freezing of FINAL_PRODUCTION_RANGES
No advisor engineering acceptance recorded for the V2 / C820 / C830 / C840 shapes
No modification of the frozen legacy generator, template, config or QC contracts
No modification of case parameters, CSV, NPZ, PNG or any experiment result
```

## 8. Document synchronization (2026-10-21, Markdown only)

Corrected the outdated "latest progress" statements, which stopped at the
2026-10-15 V2 review package:

```text
PROJECT_HANDOFF.md          CURRENT_STATUS / geometry research section / next decision /
                            new-chat entry point / upload list
AGENT_INSTRUCTION.md        §0 authoritative status: added the geometry parameter
                            research block and the SS1/SS2 freeze record
README.md (repository root) created as a single entry point with document links
analysis/geometry_review/README.md
                            added the C820 / C830 / C840 blocks and updated next steps
analysis/geometry_review/parameter_sensitivity_v1_100cases/README.md
                            added the experiment's position in the chain, the two
                            overviews, the CSV roles and the later SS1/SS2 freeze
docs/SESSION_DELIVERY_2026-10-17.md
                            this record
```

No code, script, case parameter, CSV, NPZ, PNG or experiment result was modified.
`REPORT.md` files of the experiments are generated artifacts and were left
untouched on purpose.

## 9. Next step (unchanged production blocker)

```text
1. Advisor / owner engineering judgement on the candidate geometry space
   entry: analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md
          + analysis/geometry_review/senior_review_v2/00_all_cases_overview.png
2. CFD verification of the high-Xmean / high-Ks1 corner and the Ks2 rear-camber range
3. Threshold calibration on the historical 1891-sample population
4. Only then: freeze FINAL_PRODUCTION_RANGES (six-dimensional production ranges)
5. Do NOT run 01_generate_design.py / generate_geomturbo_batch.py before step 4
```

`Geometry QC PASS` ≠ 气动合理 ≠ 网格可生成 ≠ CFD 可收敛。

# Geometry Range Review — 叶型参数范围评审 / 敏感性研究

> 本目录是**评审与研究专用**目录：把真实生成的叶型交给师兄做工程合理性判断，
> 并在此完成参数敏感性、冗余与边界检验，为将来的 `FINAL_PRODUCTION_RANGES` 提供依据。
>
> **它不是正式数据集，也不冻结任何生产范围。**
> `range_id` / `sampling_id` / `case_id` 号段与生产号段完全隔离。

```text
V1  legacy range  review   : 30 case  C800001..C800030   -> archive/v1_legacy_review/ (归档，勿改)
V2  exploratory   review   : 40 case  C810001..C810040   -> senior_review_v2/        (历史评审包)
全参数敏感性 + 边界检验    : 100 case C820001..C820100   -> parameter_sensitivity_v1_100cases/  (★ 最新敏感性扫描)
Ks1/Ks2 专项复核           : 57 case  C830001..C830057   -> ks1_ks2_review_v1/
几何参数最终裁决 V1        : 40 case  C840001..C840040   -> parameter_final_decision_v1/ (★ 最新裁决，探索性)
生产 production  号段      : C000001..                    （本目录不产生）
NUMECA bring-up 号段       : C900001                      （在仓库根 geometry/，与本目录无关）
```

```text
时间顺序（越往下越新；历史阶段不代表当前进度）:
V1 (30) -> V2 (40) -> C820 100-case 敏感性/边界 -> C830 57-case 复核 -> C840 最终裁决
```

---

## 1. V2 评审包状态（2026-10-15，历史阶段）

| 阶段 | 含义 | 状态 |
|---|---|---|
| ① 几何生成成功 | `.dat` / `.geomTurbo` 真实存在 | **40 / 40** |
| ② Geometry QC 通过 | 冻结 QC `geometry_qc_v1_hard` 判定 `geometry_ok = 1` | **40 / 40 PASS**（`reason = OK`） |
| ③ 人工判断工程合理 | 师兄的工程判断 | **未填写**（`human_*` 列为空，仓库内无评审记录） |
| ④ 网格 / CFD 可行性 | 能否画网格、能否收敛 | **未验证**（未运行 NUMECA / CFX） |

```text
min_gap                 0.014494 .. 0.072696 m      （硬门 min_gap > 0：40/40 全部通过）
envelope_clearance      5 个 case 为负（诊断量，非失败，非碰撞）
独立单叶轮廓            25 个（40 case = 25 个单叶型 + 15 个不同 Solidity 的栅距变化）
单元测试                111/111 OK（2026-10-15 当次记录）
```

**已冻结、本次未修改**：`Metal1 = 53 deg` 与造型核心 `code/geometry_legacy_v1.py`、
冻结模板 `legacy/blade_batch_generation_template.geomTurbo`
（sha256 `92c4296f...c55119`）、`config/ranges_legacy.yaml`、`tests/fixtures/`。

---

## 1.1 最新进展（2026-10-17，全部探索性 / 未批准）

| 阶段 | 目录 | Case 号段 | 规模 | 结果 | 状态 |
|---|---|---|---|---|---|
| 全参数敏感性 + 边界检验 | `parameter_sensitivity_v1_100cases/` | `C820001..C820100` | 100 | 生成 100/100，硬性 QC 100/100，冻结 QC 100/100 | 探索性 / 未批准 |
| Ks1/Ks2 专项复核 | `ks1_ks2_review_v1/` | `C830001..C830057` | 57 | 生成 57/57，硬性 QC 57/57，冻结 QC 57/57 | 探索性 / 未批准 |
| 几何参数最终裁决 V1 | `parameter_final_decision_v1/` | `C840001..C840040`（新增；共 49 行设计） | 40 新增 + 9 复用 | 49/49 PASS | 探索性 FINAL（仅限探索性几何 DOE） |

```text
100-case 敏感性（C820）:
  入口 = parameter_sensitivity_v1_100cases/README.md + REPORT.md
  两张总览 = overview_001_050.png / overview_051_100.png
  设计参数 = case_design.csv（100 行）
  几何指标 = case_metrics.csv（100 行）
  自动筛选建议 = parameter_decisions.csv
      FIX_CANDIDATE 2（SS1, SS2）/ KEEP_CANDIDATE 10 / REVIEW 1（Ks2）

人工工程评审（2026-10-21，师兄，用户转述）:
  记录 = human_review_2026-10-21.csv（100 行）
  分析 = HUMAN_REVIEW_2026-10-21.md
  ACCEPT 85 / REJECT 15（100/100 已判定，无 UNREVIEWED）
  15 个被拒 Case 全部 hard QC + frozen QC PASS -> 自动 QC 未识别
  逐案不合格原因待补充；ACCEPT 仅代表形状合理

注意（必须区分历史扫描与后续冻结决策）:
  C820 扫描时 SS1 = 2.4-4.0、SS2 = 0.5-1.1 是可变参数；
  SS1 = 3.2 / SS2 = 0.8 的固定是之后的人工决定（FIXED_BY_REVIEW），
  不能把历史 100-case 扫描写成“SS1/SS2 从未变化”。

当前参数状态（仅供探索性几何 DOE）:
  几何 11 维 OPEN：Xthick Tmax Metal2 Solidity Metal1 T1 T2 Xmean K_m Ks1 Ks2
  SS1 = 3.2 FIXED / SS2 = 0.8 FIXED
  Incidence / Mach = 运行条件（不改变叶型；CFX 实现仍 TBD）
  FINAL_PRODUCTION_RANGES 仍为 PENDING

权威记录:
  parameter_final_decision_v1/FINAL_DECISION.md
  parameter_final_decision_v1/final_geometry_parameters.yaml
  docs/SESSION_DELIVERY_2026-10-17.md
  docs/SESSION_DELIVERY_2026-10-21.md
  docs/PARAMETER_SPACE_RECONCILIATION.md
  docs/GEOMETRY_SCREENING_STRATEGY_2026-10-21.md
```

---

## 2. 目录结构

```text
analysis/geometry_review/
├── README.md                     本文件（目录入口）
├── ranges_exploratory_v2.yaml    探索范围定义（status = EXPLORATORY_NOT_APPROVED）
├── make_review_cases.py          40 个 V2 评审 case 的参数表构造脚本（确定性）
├── review_cases.csv              ★ 40 行六维参数（V2 生成器输入）
├── geometry/                     真实流水线产物（40 case）
│   ├── profiles/C8100xx.dat          列 = xp yp xs ys（原始归一化单位）
│   └── geomturbo/C8100xx.geomTurbo   UNITS Meters, periodicity = 0.06 / Solidity
├── geometry_qc.csv               code/03_geometry_qc.py 的真实 QC 报告（40 行全 PASS）
├── figures/                      V2 评审图 6 张（200 dpi）
├── logs/                         V2 运行日志（dry-run / 生成 / QC / 绘图）
├── senior_review_v2/             ★★ 交给师兄的 40 case 评审包（见其 README.md）
│   ├── 00_all_cases_overview.png     40 面板总览（5716 × 3081 px）
│   ├── 00_case_index.csv             40 行索引 + 人工评审空列
│   └── cases/C8100xx/                每个 case：parameters.json + 3 张 PNG + .dat + .geomTurbo
├── senior_review_v2.zip          同一评审包的 ZIP（本地交付文件，**不进 Git**）
├── parameter_sensitivity_v1_100cases/  ★ 100 case 全参数敏感性 + 边界检验
│   ├── README.md / REPORT.md         目录入口 / 中文分析报告
│   ├── overview_001_050.png          C820001–C820050 叶型总览
│   ├── overview_051_100.png          C820051–C820100 叶型总览
│   ├── case_design.csv               100 行 13 参数设计
│   ├── case_metrics.csv              100 行几何指标 + QC
│   ├── parameter_sensitivity.csv / parameter_decisions.csv   13 行敏感性 / 建议
│   ├── screening_criteria.yaml       预登记判据
│   ├── human_review_2026-10-21.csv   100 行人工评审标签（85 ACCEPT / 15 REJECT）
│   ├── HUMAN_REVIEW_2026-10-21.md    人工评审记录与边界分析
│   └── profiles.npz                  高精度曲线
├── ks1_ks2_review_v1/            C830001..C830057（57 case Ks1/Ks2 专项复核）
│   ├── README.md / REPORT.md
│   ├── ks1_xmean_redundancy.csv / ks2_background_sensitivity.csv
│   ├── joint_interaction.csv / parameter_decisions.csv
│   └── profiles.npz
├── parameter_final_decision_v1/  ★ C840001..C840040（几何参数最终裁决 V1）
│   ├── FINAL_DECISION.md             最终报告（决策表 = 唯一权威结论）
│   ├── final_geometry_parameters.yaml 候选参数配置（11 几何维 + 2 运行维）
│   ├── final_decision_criteria.yaml  预登记判据
│   ├── final_decision_evidence.csv / substitution_results.csv
│   ├── xmean_boundary_scan.csv / xmean_hard_qc_scan.csv
│   └── decision_profiles.npz / overview.png / decision_summary.png
└── archive/v1_legacy_review/     V1（30 case，legacy 范围）归档 —— 冻结记录，勿改
```

绘图脚本在仓库约定位置 `tools/plot_geometry_review.py`（V2 图）；
评审包生成脚本 `tools/make_senior_review_v2.py`（只读复用，不重跑几何/QC/CFD）。


---

## 3. V2 探索范围 vs 历史范围

| 参数 | 历史（1891 case / V1） | V2 探索范围 | 性质 |
|---|---|---|---|
| Xthick | 0.15 – 0.45 | **0.10 – 0.60** | 无量纲 |
| Tmax | 0.04 – 0.07 | **0.025 – 0.095** | 无量纲 |
| Metal2 | 6 – 24 deg | **0 – 32 deg** | deg（入口 Metal1 冻结 53 deg） |
| Solidity | 1.0 – 2.0 | **0.7 – 2.5** | 只改栅距 = 0.06 / Solidity |
| Incidence | −4 – 4 deg | 固定 **0 deg** | 工况，不改变叶型 |
| Mach | 0.3 – 0.7 | 固定 **0.5** | 工况，不改变叶型 |

```text
以上 V2 范围 = 探索范围（EXPLORATORY_NOT_APPROVED），不是正式生产范围。
Incidence / Mach 已由 V1 实测证明不改变 legacy 叶型几何，
因此本次固定，只作为追溯记录（详见 senior_review_v2/README.md 第 3 节）。

后续阶段（C820 / C830 / C840）改用 13 参数生成器
code/geometry_parametric_exploratory_v1.py：
  新增 Metal1 / T1 / T2 / Xmean / K_m / Ks1 / Ks2 / SS1 / SS2；
  C820 时 SS1、SS2 仍为变量（2.4-4.0 / 0.5-1.1），
  C830 起 SS1 = 3.2、SS2 = 0.8 固定（FIXED_BY_REVIEW）。
最终候选配置见 parameter_final_decision_v1/final_geometry_parameters.yaml。
```

---

## 4. 如何复现（在仓库根目录执行）

```bash
# 0) 环境（必须 ai4s：含 numpy / scipy / matplotlib / pyyaml）
conda run -n ai4s python -c "import numpy,scipy,matplotlib,yaml;print('env ok')"

# 1) 40 个评审 case 参数表（幂等：已存在则拒绝覆盖，需 --overwrite）
conda run -n ai4s python analysis/geometry_review/make_review_cases.py

# 2) 几何生成（先 dry-run 再正式；输出到评审专用目录，不污染 geometry/）
conda run -n ai4s python code/02_generate_geometry.py \
    --input analysis/geometry_review/review_cases.csv \
    --template legacy/blade_batch_generation_template.geomTurbo \
    --output analysis/geometry_review/geometry --dry-run
conda run -n ai4s python code/02_generate_geometry.py \
    --input analysis/geometry_review/review_cases.csv \
    --template legacy/blade_batch_generation_template.geomTurbo \
    --output analysis/geometry_review/geometry

# 3) Geometry QC（先 dry-run 再正式）
conda run -n ai4s python code/03_geometry_qc.py \
    --input analysis/geometry_review/review_cases.csv \
    --geometry analysis/geometry_review/geometry \
    --output analysis/geometry_review/geometry_qc.csv --dry-run
conda run -n ai4s python code/03_geometry_qc.py \
    --input analysis/geometry_review/review_cases.csv \
    --geometry analysis/geometry_review/geometry \
    --output analysis/geometry_review/geometry_qc.csv

# 4) V2 评审图（6 张，200 dpi，Agg 无 GUI）
conda run -n ai4s python tools/plot_geometry_review.py

# 5) 40 case 师兄评审包 + ZIP（只读复用上面的结果，不重跑几何/QC）
conda run -n ai4s python tools/make_senior_review_v2.py

# 6) 100 case 全参数敏感性 + 边界检验（C820001..C820100）
conda run -n ai4s python tools/geometry_parameter_sensitivity_v1.py all

# 7) Ks1/Ks2 专项复核（C830001..C830057，SS1/SS2 固定 3.2/0.8）
conda run -n ai4s python tools/geometry_ks1_ks2_review_v1.py all

# 8) 几何参数最终裁决 V1（C840001..C840040 + 9 个复用）
conda run -n ai4s python tools/geometry_final_decision_v1.py all

# 9) 全部回归
conda run -n ai4s python -m pytest -q
```

`tools/make_senior_review_v2.py` 的保护：输出目录非空时需显式 `--overwrite`；
`--dpi` 不得低于 `DPI_MIN`；`--no-zip` 可只出目录。构建前后对全部源文件比对 sha256。

---

## 5. 单位约定（最容易读错的地方）

```text
.dat 列 = xp yp xs ys =（压力面 x, 压力面 y, 吸力面 x, 吸力面 y）
.dat 坐标是原始归一化单位，不是 m；绘图时统一缩放到 chord = 0.06 m（冻结 CHORD_TARGET），
所以评审图上的长度才是 m。

来自 .geomTurbo（单位 m）: min_gap, envelope_clearance, periodicity, chord,
                           blade_tangential_extent, 转角(deg), 曲率(1/m)
来自 .dat（归一化单位，不是 m）: min_interior_thickness, max_paired_thickness,
                           le_closure_error, te_closure_error

Xthick / Tmax / Metal2 / Solidity 是无量纲或角度参数，永远不要读成米。
envelope_clearance < 0 只是诊断量（= periodicity − 叶片切向尺寸），不是碰撞、不是 QC 失败。
```

---

## 6. V1 归档说明（`archive/v1_legacy_review/`）

```text
30 case（C800001..C800030，legacy 范围）、30/30 QC PASS、9 张图、全部日志与脚本。
已知缺口：V1 版 tools/plot_geometry_review.py 在被 V2 覆盖前未单独备份，无法从 git 恢复
         （该文件当时未纳入版本管理）；V1 图片本身已完整归档，也可用 V2 脚本加
         --cases / --geometry / --qc 参数重新绘制。
V1 的 30 个 .dat / .geomTurbo 未归档（约 0.5 MB），可由归档 CSV 逐字节复现，
         方法见 archive/v1_legacy_review/PROVENANCE.md。
```

---

## 7. ZIP 与本目录的版本管理约定

```text
纳入 Git：本目录全部内容（含 V1 归档、V2 参数表 / 几何 / QC / 图 / 日志 / 评审包解压目录）
          唯一例外见下。
不进 Git：senior_review_v2.zip —— 它只是 senior_review_v2/ 解压目录的本地打包交付副本，
          内容完全相同；ZIP 保留在本地磁盘用于直接发送/拷贝。
规则写在仓库根 .gitignore（附带注释说明）。
```

---

## 8. 下一步（本阶段之后）

```text
1) 人工工程评审（已部分完成）
   已完成：C820 100-case -> 85 ACCEPT / 15 REJECT（2026-10-21，100/100 已判定）
           入口：parameter_sensitivity_v1_100cases/HUMAN_REVIEW_2026-10-21.md
   待补充：15 个 Case 的逐案不合格原因（部位与判据）
   未覆盖：C830（57）、C840（49 行）、V2（40）仍无人工评审记录
2) 参数空间与 DOE 维度决策（owner / 导师）
   生产 DOE 仍为 d=6；13 维只是探索空间；FINAL_PRODUCTION_RANGES 仍 PENDING
   见 docs/PARAMETER_SPACE_RECONCILIATION.md
3) 单参数边界复核（仅建议，需人工确认）
   K_m 上界（低 Xmean 背景，候选 ≈0.20）、Metal2 下界（> 0）
   证据见 HUMAN_REVIEW_2026-10-21.md 第 2 节
   约束方案 A/B/C 与 100 样本保留情况：
     docs/GEOMETRY_CONSTRAINT_ANALYSIS_2026-10-21.md（默认推荐 A：Metal2 ≥ 6.0）
   复杂联合约束（含 JC_XMEAN_KS1_KM）当前不实现，只作历史候选记录
4) CFD / 工程验证（仓库内尚未进行）
   - Xmean 高端 × Ks1 高端的角点
   - Ks2 后段中弧线控制范围
   - 反向曲率叶瓣的网格敏感性（网格不足会被数值耗散抹平）
5) 用历史 1891 样本校准研究阈值（当前判据为 TENTATIVE，未校准）
   同时验证自动 QC 能否识别人工拒绝的叶型（当前 15/15 未被识别）
6) 依据以上结果冻结 FINAL_PRODUCTION_RANGES（六维生产范围）
   下一阶段筛选策略见 docs/GEOMETRY_SCREENING_STRATEGY_2026-10-21.md
```

```text
Do not re-open SS1 = 3.2 / SS2 = 0.8 without an explicit human decision.
Do not treat human ACCEPT as CFD/mesh/aero validity.
```

**Geometry QC PASS ≠ 气动合理 ≠ 网格/CFD 可行。** 本目录不构成 DOE、不构成 CFD 生产。

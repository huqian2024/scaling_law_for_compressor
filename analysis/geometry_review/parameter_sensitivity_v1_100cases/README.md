# Parameter Sensitivity V1 — 100 Cases（探索性，未批准）

```text
Status            : EXPLORATORY / NOT APPROVED
Case 号段         : C820001 .. C820100
几何生成成功      : 100 / 100
实验硬性 QC 通过  : 100 / 100
冻结 QC 通过      : 100 / 100
人工工程评审      : 85 ACCEPT / 15 REJECT（2026-10-21，100/100 已判定）
本目录体积        : 约 2.36 MB（provenance.output_size_mb = 2.359；输出产物体积，不含未跟踪 logs）
```

```text
几何 QC 字段（case_metrics.csv）与人工评审字段（human_review_2026-10-21.csv）
严格分离；15 个被拒 Case 的 hard/frozen QC 全部 PASS。
ACCEPT 仅表示形状合理，不代表网格 / CFD / 气动合格。
```

本目录只做 13 参数几何敏感性实验与自动筛选，**不包含** NUMECA 网格、CFX 结果、
AI 模型或正式生产 DOE/范围冻结。

## 目录定位（与研究链条的关系）

```text
V1 30 case (C800001..C800030)   历史评审，已归档
V2 40 case (C810001..C810040)   历史评审
C820 100 case（本目录）         ★ 最新一轮全参数敏感性 + 边界检验（13 参数）
C830 57 case (C830001..C830057) 之后：Ks1/Ks2 专项复核（SS1/SS2 已固定）
C840 40 新增 (C840001..C840040) 之后：几何参数最终裁决 V1（探索性 FINAL）

本目录的 KEEP/REVIEW/FIX_CANDIDATE 是**自动筛选建议**；
最终参数状态以 `../parameter_final_decision_v1/FINAL_DECISION.md` 为准。
```

**重要（历史扫描 ≠ 冻结决策）**：本目录扫描时 `SS1 = 2.4–4.0`、`SS2 = 0.5–1.1`
都是**可变参数**，因此 `parameter_decisions.csv` 给出 `FIX_CANDIDATE` 只是
“建议考虑固定”。`SS1 = 3.2`、`SS2 = 0.8` 的固定是之后的人工评审决定
（`FIXED_BY_REVIEW`），不能把本目录的历史扫描写成“SS1/SS2 从未变化”。

```text
后续权威记录（相对仓库根目录）：
  analysis/geometry_review/ks1_ks2_review_v1/README.md + REPORT.md
  analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md
  analysis/geometry_review/parameter_final_decision_v1/final_geometry_parameters.yaml
  docs/SESSION_DELIVERY_2026-10-17.md
  docs/SESSION_DELIVERY_2026-10-21.md
  docs/PARAMETER_SPACE_RECONCILIATION.md
  docs/GEOMETRY_SCREENING_STRATEGY_2026-10-21.md
  docs/GEOMETRY_CONSTRAINT_ANALYSIS_2026-10-21.md
```

## 决策分布（自动建议，不等于冻结）

```text
FIX_CANDIDATE   : 2
KEEP_CANDIDATE  : 10
REVIEW          : 1
```

## 入口文件

| 文件 | 用途 |
|---|---|
| `REPORT.md` | ★ 中文分析报告（结论与复现方式） |
| `overview_001_050.png` / `overview_051_100.png` | 100 个真实叶型总览 |
| `sensitivity_heatmap.png` | 13 参数敏感性热力图 |
| `case_design.csv` | 100 行实验设计与选择理由 |
| `case_metrics.csv` | 100 行 QC + 几何指标 |
| `parameter_sensitivity.csv` | 13 行定量敏感性 |
| `parameter_decisions.csv` | 13 行自动筛选建议 |
| `human_review_2026-10-21.csv` | 100 行人工评审标签（ACCEPT / REJECT + 来源/日期/依据） |
| `HUMAN_REVIEW_2026-10-21.md` | 人工评审记录、15 个 Case 参数对比与边界分析 |
| `profiles.npz` | 生成成功 Case 的高精度曲线（按 Case ID） |
| `stage3_selection.json` | 第三阶段候选池与选择依据 |
| `screening_criteria.yaml` | 判据、阈值、单位、规则（分类前已保存） |
| `provenance.json` | Git/环境/哈希/运行与验收信息 |
| `audit/step0_audit.md` | 执行前代码与公式审计 |

## 复现

```bash
cd /home/qian/compressor_ai4s
conda run -n ai4s python tools/geometry_parameter_sensitivity_v1.py all
```

> `Geometry QC PASS` ≠ 气动合理 ≠ 网格/CFD 可行。
> 所有阈值均为暂定研究阈值，未用历史 1891 样本校准。

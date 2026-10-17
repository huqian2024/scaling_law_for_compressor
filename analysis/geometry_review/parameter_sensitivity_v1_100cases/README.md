# Parameter Sensitivity V1 — 100 Cases（探索性，未批准）

```text
Status            : EXPLORATORY / NOT APPROVED
Case 号段         : C820001 .. C820100
几何生成成功      : 100 / 100
实验硬性 QC 通过  : 100 / 100
冻结 QC 通过      : 100 / 100
本目录体积        : 2.358 MB
```

本目录只做 13 参数几何敏感性实验与自动筛选，**不包含** NUMECA 网格、CFX 结果、
AI 模型或正式生产 DOE/范围冻结。

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

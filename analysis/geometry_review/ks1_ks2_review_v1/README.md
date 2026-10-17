# Ks1 / Ks2 专项几何复核 V1（57 Cases，探索性，未批准）

```text
Status            : EXPLORATORY / NOT APPROVED
Case 号段         : C830001 .. C830057
阶段分布          : A=15, B=30, C=12
几何生成成功      : 57 / 57
实验硬性 QC 通过  : 57 / 57
冻结 QC 复核通过  : 57 / 57
SS1 / SS2         : 3.2 / 0.8（FIXED_BY_REVIEW）
Ks1 建议          : FURTHER_REVIEW（K1_REVIEW）
  Ks1 倾向        : FIX_IF_HIGH_XMEAN_REGION_EXCLUDED
Ks2 建议          : FURTHER_REVIEW（K2_REVIEW）
  Ks2 倾向        : KEEP_IF_METAL2_SUBSTITUTION_REJECTED
本目录体积        : 1.355 MB
```

本轮只做几何研究，**没有** NUMECA / CFX / AI 训练 / 正式 DOE 修改。
Ks1/Ks2 的自动建议不等于最终参数状态；SS1/SS2 为人工决定固定。

## 入口文件

| 文件 | 用途 |
|---|---|
| `REPORT.md` | ★ 中文最终报告（回答 10 个问题） |
| `overview.png` | 57 个真实叶型总览 |
| `ks1_xmean_comparison.png` | Ks1 vs Xmean 余弦/残差/替代曲线 |
| `ks2_background_comparison.png` | Ks2 后段多背景敏感性 |
| `case_design.csv` | 57 行参数、背景、参考 Case、选择规则 |
| `case_metrics.csv` | 57 行 QC + 几何指标 |
| `ks1_xmean_redundancy.csv` | Ks1 多背景余弦/幅值/残差/替代搜索 |
| `ks2_background_sensitivity.csv` | Ks2 后段分量/信噪比/替代搜索 |
| `joint_interaction.csv` | Ks1 × Ks2 三背景 2×2 交互 |
| `parameter_decisions.csv` | Ks1/Ks2 建议 + SS1/SS2 固定状态 |
| `profiles.npz` | 57 个 Case 的高精度曲线 |
| `review_criteria.yaml` | 判据、阈值、单位、规则（分类前保存） |
| `geometry_parameter_candidates_v2.yaml` | 未来探索性候选配置（未批准） |
| `provenance.json` | Git/环境/哈希/验收信息 |
| `audit/` | SHA256 前后快照、运行元数据、验收记录 |

## 复现

```bash
cd /home/qian/compressor_ai4s
conda run -n ai4s python tools/geometry_ks1_ks2_review_v1.py all
```

> `Geometry QC PASS` ≠ 气动合理 ≠ 网格/CFD 可行。
> 所有阈值均为暂定研究阈值。

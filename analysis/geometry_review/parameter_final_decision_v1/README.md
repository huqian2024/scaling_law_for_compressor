# 几何参数最终裁决 V1（Ks1 / Ks2 / Xmean）

```text
状态            : EXPLORATORY / NOT APPROVED（不是 CFD 认证）
                  2026-10-21 起：final_geometry_parameters.yaml 已冻结为
                  GeomTurbo 几何生成参数空间（config/geometry_ranges_frozen_a.yaml）
新增 Case       : 40（复用历史 9）
Ks1             : KEEP（K1_KEEP）
Ks2             : KEEP（K2_KEEP）
Xmean 上界      : 0.18（下限 0.06）
几何维度        : 11
总候选维度      : 13
本目录体积      : 1.056 MB
```

本轮不运行 NUMECA / CFX / AI 训练，不修改正式 DOE 或生产范围。
SS1=3.2、SS2=0.8 保持 FIXED_BY_REVIEW，不重新开放。

## 入口文件

| 文件 | 用途 |
|---|---|
| `FINAL_DECISION.md` | ★ 中文最终报告（含决策表与 5 个回答） |
| `final_geometry_parameters.yaml` | 最终参数配置、联合限制、维度 |
| `final_decision_criteria.yaml` | 预登记判据（含修订记录） |
| `final_decision_evidence.csv` | 长表证据 |
| `case_design.csv` / `case_metrics.csv` | 设计与指标（含复用标记） |
| `substitution_results.csv` | 替代搜索全部结果 |
| `xmean_boundary_scan.csv` | 软风险地图 |
| `xmean_hard_qc_scan.csv` | 边界硬性 QC |
| `decision_profiles.npz` | 新增 Case 高精度曲线 |
| `overview.png` / `decision_summary.png` | 两张总览图 |
| `provenance.json` | Git / 哈希 / 体积 / 回归结果 |
| `protected_assets_before.sha256.json` | 本轮开始前的受保护资产哈希基线 |

## 复现

```bash
cd /home/qian/compressor_ai4s
conda run -n ai4s python tools/geometry_final_decision_v1.py all
conda run -n ai4s python -m pytest -q
```

> `geometry_ok=1` / `hard QC PASS` ≠ 气动合理 ≠ 网格可生成 ≠ CFD 可收敛。

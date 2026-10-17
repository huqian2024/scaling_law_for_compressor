# Step 0 — Ks1/Ks2 专项复核执行前审计

```text
Git HEAD            : 02e57d1d26197d97e65f4b64ef0a23f6d06393b7
Git status (before) : only the previous session's new untracked files
                      (100-case experiment + new generator/metrics/driver/test);
                      no tracked file modified
Audit date          : 2026-10-17
Scope               : geometry only; no NUMECA / CFX / AI training / formal DOE
```

## 1. Ks1 / Ks2 的真实公式与依赖

来源：`legacy/blade_batch_generation.py` 第 73–86 行、
`code/geometry_parametric_exploratory_v1.py` 第 183–195 行（逐字复制）。

```text
Sm1 = tan(Metal1)
Sm2 = tan(Metal2)
Sm0 = tan(Metal1 + (Metal2 - Metal1) * K_m)
SSm1 = Ks1 * (Sm2 - Sm1)
SSm2 = Ks2 * (Sm2 - Sm1)
```

`SSm1`/`SSm2` 只进入中弧线多项式系数：

```text
a1, a2  : 同时含 SSm1 和 SSm2
a3      : = SSm1
a4      : = Sm1
a5, a6  : 同时含 SSm1 和 SSm2
a7      : = -SSm2
a8      : = Sm2
```

结论：

- Ks1/Ks2 不进入厚度多项式 `b1..b10`；
- Ks1/Ks2 不进入前/尾缘圆弧半径 `r1/r2`；
- 因此不能用“厚度/边缘半径”判断它们，必须看中弧线、压力面、吸力面、后段局部曲率；
- Ks1 只控制前段中弧线斜率倍数（`a3` 直接等于 `SSm1`）；
- Ks2 只控制后段中弧线斜率倍数（`a7` 直接等于 `-SSm2`）；
- 二者都依赖 `Sm2 - Sm1`，即 `Metal1`/`Metal2`；在 `Metal2=0/32` 等极端折转背景下作用尺度会改变；
- `Xmean` 是中弧线分段点和 `a1,a2,a5,a6` 的分母，不是 Ks1 的同类“斜率倍数”；
- `K_m` 通过 `Sm0` 控制转弯分配，与 Ks1/Ks2 共享同一组 `a1..a8`，不能假设独立。

## 2. 上一轮（100 Case）的 Ks1/Ks2 结果与局限

来自 `analysis/geometry_review/parameter_sensitivity_v1_100cases/parameter_sensitivity.csv`：

```text
Ks1: S_comp=0.06051, S_camber=0.1154, S_thickness=0,
     redundancy partner Xmean, cosine=0.9944, ratio=0.151,
     decision KEEP_CANDIDATE (R1_KEEP_HIGH)
Ks2: S_comp=0.00526, S_camber=0.01089, S_thickness=0,
     redundancy partner Xmean, cosine=0.6892, ratio=0.0131,
     decision REVIEW (R2_REVIEW_MEDIUM)
```

局限（本轮必须排除）：

1. 上一轮余弦来自 14 维**符号响应签名**（中弧线/厚度/边缘/弦向/间隙）；
   不是按 xc 采样的完整中弧线角度/曲率/压力面/吸力面响应。
2. 上一轮 Ks1/Ks2 只有 3 个水平；本轮 A 阶段用 7 个水平。
3. 上一轮只在全局基准做单因素，B 阶段才提供 6 个不同背景。
4. 上一轮综合分数对全局 RMS 加权，可能低估后 30% 的局部曲率作用。
5. 上一轮没有做“单参数替代”搜索，不能判断高余弦是否等于可替代。
6. 4 位小数序列化可能抹除局部小变化；本轮逐 Case 计算 4 位噪声与 SNR。

## 3. 基准、范围与固定参数

```text
基准：Xthick=0.30, Tmax=0.055, Metal1=53, Metal2=15, Solidity=1.5,
      Xmean=0.08, K_m=0.18, Ks1=5, Ks2=0.10, T1=0.015, T2=0.0125,
      SS1=3.2, SS2=0.8

Ks1 范围 3.0–7.0（7 个非基准水平）
Ks2 范围 0.05–0.20（7 个非基准水平）

SS1 = 3.2  FIXED_BY_REVIEW  （人工决定）
SS2 = 0.8  FIXED_BY_REVIEW  （人工决定）
Incidence = 0.0, Mach = 0.5（工况元数据，不参与几何）
```

SS1/SS2 固定是**人工评审决定**，不是自动判据批准；生成器仍接受这两个参数，
历史几何兼容性保留。正式六维 DOE、V1 生成器、V1/V2 评审、上一轮 100 Case
均未修改。

## 4. 本轮实验设计（57 Case）

```text
A: 1 基准 + Ks1 7 水平 + Ks2 7 水平                      = 15
B: 6 背景 × (1 背景基准 + Ks1 3/7 + Ks2 0.05/0.20)      = 30
C: 3 个由 B 结果自动选择的背景 × Ks1(3,7) × Ks2(0.05,0.20) = 12
合计                                                      = 57
```

背景：

```text
B1 Xmean=0.06, K_m=0.10
B2 Xmean=0.06, K_m=0.35
B3 Xmean=0.18, K_m=0.10
B4 Xmean=0.18, K_m=0.35
B5 Metal1=48, Metal2=0
B6 Metal1=58, Metal2=32
```

Stage C 选择规则：B1–B4 按背景参考叶型的中弧线角范围排序，取最低与最高；
B5/B6 取中弧线角范围更大的一个；实际选择与得分写入 `stage_c_selection.json`。

## 5. 新代码与输出路径

```text
新驱动脚本 : tools/geometry_ks1_ks2_review_v1.py
复用模块   : code/geometry_parametric_exploratory_v1.py
             tools/geometry_sensitivity_metrics_v1.py
输出目录   : analysis/geometry_review/ks1_ks2_review_v1/
```

输出目录内包含：

```text
README.md
experiment_config.yaml
review_criteria.yaml
geometry_parameter_candidates_v2.yaml
case_design.csv
case_metrics.csv
ks1_xmean_redundancy.csv
ks2_background_sensitivity.csv
joint_interaction.csv
parameter_decisions.csv
profiles.npz
overview.png
ks1_xmean_comparison.png
ks2_background_comparison.png
REPORT.md
stage_c_selection.json
provenance.json
audit/
```

## 6. 受保护资产

运行前后检查 SHA256 的文件（见 `audit/sha256_before.txt` / `sha256_after.txt`）：

```text
legacy/blade_batch_generation.py
legacy/blade_batch_generation_template.geomTurbo
code/geometry_legacy_v1.py
code/geometry_parametric_exploratory_v1.py
tools/geometry_sensitivity_metrics_v1.py
tools/geometry_parameter_sensitivity_v1.py
analysis/geometry_review/parameter_sensitivity_v1_100cases/case_design.csv
analysis/geometry_review/parameter_sensitivity_v1_100cases/case_metrics.csv
analysis/geometry_review/parameter_sensitivity_v1_100cases/parameter_sensitivity.csv
analysis/geometry_review/parameter_sensitivity_v1_100cases/parameter_decisions.csv
analysis/geometry_review/parameter_sensitivity_v1_100cases/profiles.npz
analysis/geometry_review/parameter_sensitivity_v1_100cases/screening_criteria.yaml
analysis/geometry_review/senior_review_v2/00_case_index.csv
analysis/geometry_review/geometry_qc.csv
```

本轮没有删除、移动、覆盖任何历史文件；没有提交 Git；没有运行 CFD。

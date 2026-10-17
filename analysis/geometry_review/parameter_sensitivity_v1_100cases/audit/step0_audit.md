# Step 0 — 代码与公式审计（Parameter Sensitivity V1, 100 Cases）

```text
Git HEAD            : 02e57d1d26197d97e65f4b64ef0a23f6d06393b7
Git branch          : master
Git status (start)  : clean (0 modified/untracked files before this session)
Current commit msg  : Complete geometry range review V2 and archive senior review cases
Audit time          : 2026-10-17
```

本文件是 Step 1（代码/公式审计）的追溯记录。所有结论均来自仓库真实实现，
未根据变量名猜测物理意义。

---

## 1. 相关文件与职责

| 文件 | 作用 | 本轮是否修改 |
|---|---|---|
| `legacy/blade_batch_generation.py` | 历史造型脚本（含 13 个几何参数、采样、文件写出） | **否**（只读） |
| `legacy/blade_batch_generation_template.geomTurbo` | 冻结 `.geomTurbo` 模板（754 行） | **否**（只读，sha256 见 `sha256_before.txt`） |
| `code/geometry_legacy_v1.py` | 冻结 V1 纯函数造型核心（只开放 4 参数） | **否**（只读，被新模块 importlib 只读加载） |
| `code/02_generate_geometry.py` | 冻结几何生成 CLI（4 参数 + Solidity） | **否** |
| `code/03_geometry_qc.py` | 冻结 Geometry QC v1（`geometry_qc_v1_hard`） | **否**（只读复用其几何内核） |
| `tests/fixtures/legacy_geometry_v1/` | 13 个冻结回归 fixture（profile + geomTurbo 逐字节） | **否** |
| `analysis/geometry_review/ranges_exploratory_v2.yaml` | V2 40 Case 探索范围定义 | **否**（只读） |
| `analysis/geometry_review/make_review_cases.py` | V2 40 Case 确定性参数表构造 | **否**（只读参考） |
| `code/geometry_parametric_exploratory_v1.py` | **本轮新增** 13 参数实验造型模块 | 新增 |
| `tools/geometry_sensitivity_metrics_v1.py` | **本轮新增** 几何指标 + QC 复用内核 | 新增 |
| `tools/geometry_parameter_sensitivity_v1.py` | **本轮新增** 100 Case 设计/执行/筛选/报告 | 新增 |
| `analysis/geometry_review/parameter_sensitivity_v1_100cases/` | **本轮新增** 全部实验输出（唯一写入目录） | 新增 |

---

## 2. 13 个候选几何参数 → 真实公式映射

来源：`legacy/blade_batch_generation.py` 第 41–60 行（常量）、73–125 行（中弧线/
厚度）、141–227 行（前尾缘圆），与 `code/geometry_legacy_v1.py` 完全一致。

| 参数 | Legacy 默认值 | 实际参与的公式（真实实现） | 类别 |
|---|---|---|---|
| `Xthick` | 实验基准 0.30（legacy 无固定值，由采样给出） | 厚度多项式分段点 `xc <= Xthick`；`St1=(Tmax/2-T1/2)/Xthick`；`St2=(Tmax/2-T2/2)/(1-Xthick)`；`b1..b3,b6,b7` 的分母含 `Xthick`；前尾缘圆 `St1/St2` 也用它 | A 已开放 |
| `Tmax` | 实验基准 0.055（legacy 由采样给出） | 厚度幅值 `Tmax/2` 进入 `St1,St2,b1..b3,b6,b7`；前尾缘 `St1/St2` | A 已开放 |
| `Metal2` | 实验基准 15°（legacy 由采样给出） | `Sm2=tan(Metal2)`；`Sm0=tan(Metal1+(Metal2-Metal1)*K_m)`；`SSm1=Ks1*(Sm2-Sm1)`；`SSm2=Ks2*(Sm2-Sm1)`；`a1..a8` | A 已开放 |
| `Solidity` | 实验基准 1.5（legacy 由采样给出） | **不进入叶片坐标**；只进入 `.geomTurbo` 的 `PERIODICITY = 0.06 / Solidity` | A 已开放（叶栅） |
| `Metal1` | `48 + DeltaBeta = 53°` | `Sm1=tan(Metal1)`；`Sm0`；`SSm1/SSm2`；`a1..a8`。是入口**金属角**，不是 Incidence | B 重点 |
| `T1` | 0.015 | `b5=T1/2`；`St1`；`b1..b3` 的 `term1`；前缘圆 `rr1/r1`（通过 `xp/xs` 端点） | B 重点 |
| `T2` | 0.0125 | `b10=T2/2`；`St2`；`b6,b7` 的 `term2`；尾缘圆 `rr2/r2` | B 重点 |
| `Xmean` | 0.08 | 中弧线分段点 `xc <= Xmean`；`a1,a2,a5,a6` 的分母；`yc` 拼接常数 | B 重点 |
| `K_m` | 0.18 | `Sm0=tan(Metal1+(Metal2-Metal1)*K_m)`；进入 `a1,a2,a5,a6` | B 重点 |
| `Ks1` | 5 | `SSm1=Ks1*(Sm2-Sm1)`；`a1,a2,a3(=SSm1),a5,a6`；`sc` 前段 | C 新增 |
| `Ks2` | 0.10 | `SSm2=Ks2*(Sm2-Sm1)`；`a1,a2,a5,a6,a7(=-SSm2)`；`sc` 后段 | C 新增 |
| `SS1` | 3.2 | `St1=SS1*(Tmax/2-T1/2)/Xthick`；影响 `b1..b4`。**注意**：前缘圆处的 `St1` 被 legacy 重新计算为 `(Tmax/2-T1/2)/Xthick`（不含 SS1） | C 新增 |
| `SS2` | 0.8 | `St2=SS2*(Tmax/2-T2/2)/(1-Xthick)`；影响 `b6,b7,b9`。**注意**：尾缘圆处的 `St2` 同样不含 SS2 | C 新增 |

### 2.1 重要实现事实（必须记录，不能"修正"）

1. `legacy/blade_batch_generation.py` 第 88–91 行用 `SS1/SS2` 计算 `St1/St2` 供厚度
   多项式使用；第 142–143 行在为前尾缘圆计算 `St1/St2` 时**重新赋值且没有乘
   `SS1/SS2`**。这是既有造型算法的一部分，本轮原样保留，并在报告中作为
   "SS1/SS2 不改变前尾缘圆弧半径" 的证据。
2. `Ncirc=4`，但每个圆弧生成 `Ncirc+1=5` 个采样点，仅插入前 `Ncirc` 个（前缘）
   或后 4 个（尾缘），因此圆弧与叶面之间存在一段**弦线**，表现为
   `le_junction_angle_jump_deg` / `te_junction_angle_jump_deg`。本轮将其作为
   几何诊断量记录，不改变算法。
3. `Metal1 = 48 + DeltaBeta = 53°` 与 legacy 注释中的 "零攻角进口气流角 49 度"
   矛盾；冻结契约已声明不解释该矛盾。本轮保持 `Metal1=53°` 默认值，且
   不构造 Incidence ↔ Metal1 换算关系。
4. `.dat` 坐标是**原始归一化单位**（弦长≈1.14），不是米；`.geomTurbo` 缩放为
   弦长 0.06 m（`CHORD_TARGET`）。
5. `T1`/`T2` 是厚度函数的输入参数，不能直接解释为真实前/尾缘半径；本轮同时
   记录解析圆弧半径 `r1/r2` 与从真实轮廓拟合的半径，以区分两者。

---

## 3. 当前 40 Case（V2）的范围与 QC 方法

`analysis/geometry_review/ranges_exploratory_v2.yaml`：

```text
Xthick   0.10 – 0.60
Tmax     0.025 – 0.095
Metal2   0 – 32 deg
Solidity 0.7 – 2.5
Incidence 固定 0 deg，Mach 固定 0.5（不改变 legacy 几何）
Metal1 固定 53 deg（冻结常量，V2 未开放）
```

V2 QC：`code/03_geometry_qc.py`（`qc_policy_id = geometry_qc_v1_hard`，
`calibration_status = UNCALIBRATED`），仅用**无需经验阈值的硬性判据**决定
`geometry_ok`：

```text
artifact exists / profile parse / geomTurbo parse
finite coordinates
LE/TE closure exactly 0 (legacy-v1 structural rule)
no self-intersection of canonical closed polygon
positive interior paired thickness
periodicity finite > 0 / span sections consistent
no adjacent periodic-blade intersection
min_gap finite > 0 / chord finite > 0
no zero-length internal segments / curvature diagnostics finite
```

诊断量（`min_gap`、`envelope_clearance`、曲率等）**不单独判失败**。
V2 结果：40/40 几何生成成功、40/40 QC PASS、25 个独立单叶轮廓
（15 个 case 只改 Solidity/栅距）。

---

## 4. 本轮新建代码与输出路径

```text
新造型模块 : code/geometry_parametric_exploratory_v1.py
新指标模块 : tools/geometry_sensitivity_metrics_v1.py
新实验脚本 : tools/geometry_parameter_sensitivity_v1.py
新回归测试 : tests/test_geometry_parametric_exploratory_v1.py

唯一输出目录:
analysis/geometry_review/parameter_sensitivity_v1_100cases/
    README.md
    experiment_config.yaml
    screening_criteria.yaml
    case_design.csv
    case_metrics.csv
    parameter_sensitivity.csv
    parameter_decisions.csv
    profiles.npz
    provenance.json
    overview_001_050.png
    overview_051_100.png
    sensitivity_heatmap.png
    REPORT.md
    audit/sha256_before.txt
    audit/sha256_after.txt
    logs/...
```

Case 号段：`C820001 .. C820100`（避开 V1 `C8000xx`、V2 `C8100xx`、
生产 `C0000xx`、bring-up `C900001`）。

本轮不进行：NUMECA 网格、CFX 求解、AI 训练、正式 DOE、生产范围冻结。

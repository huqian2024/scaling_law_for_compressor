# Geometry Range Review (2026-10-15) — 叶型参数敏感性评审材料

> **目的**：把 `config/ranges_legacy.yaml` 历史范围内、不同参数组合生成的**真实**叶型
> 展示给师兄，用于人工判断工程合理性，为后续 `FINAL_PRODUCTION_RANGES` 提供依据。
>
> **本目录不是正式数据集**：`range_id = legacy_review`，case_id 使用独立号段
> `C800001..C800030`，与生产号段（`C000001..C120000`）和 NUMECA bring-up 号段
> （`C900001`）完全隔离，绝不混入正式数据集。

---

## 1. 四个阶段必须严格区分（评审时不要混淆）

| 阶段 | 含义 | 本次状态 |
|---|---|---|
| ① 几何生成成功 | `.dat` / `.geomTurbo` 文件真实存在于磁盘 | **30 / 30 成功**（`geometry_generated = 1`） |
| ② Geometry QC 通过 | 冻结 QC（`geometry_qc_v1_hard`）判定 `geometry_ok = 1` | **30 / 30 PASS**，`reason = OK` |
| ③ 人工判断工程合理 | 师兄的工程判断 | **未填写**（`human_*` 列留空） |
| ④ 网格 / CFD 可行性 | 能否画网格、能否收敛 | **未验证**（本次未运行 NUMECA / CFX） |

`review_summary.csv` 中 `geometry_generated` 与 `geometry_qc_status` 是两列，
就是为了防止把①和②混为一谈。

---

## 2. 目录内容

```text
analysis/geometry_review/
├── make_review_cases.py       生成 30 个评审 case 的参数表（评审专用，非生产生成器）
├── review_cases.csv           30 个 case 的六维参数（符合生成器 CSV contract）
├── geometry/                  真实流水线产物
│   ├── profiles/C8000xx.dat             30 个（4 列：xp yp xs ys）
│   └── geomturbo/C8000xx.geomTurbo      30 个
├── geometry_qc.csv            code/03_geometry_qc.py 的真实 QC 报告
├── make_review_summary.py     合并参数表 + QC 报告，追加空白人工评审列
├── review_summary.csv         ★ 交给师兄的评审表
├── figures/                   9 张 PNG（200 dpi）
└── logs/                      终端日志（dry-run / 生成 / QC / 绘图）
tools/plot_geometry_review.py  独立可视化脚本（仓库约定位置）
```

---

## 3. 30 个评审 Case 的设计

| 组 | 数量 | 内容 |
|---|---|---|
| G1 | 1 | 六维参数中点参考 case `C800001`（Xthick=0.30, Tmax=0.055, Metal2=15, Solidity=1.5, Incidence=0, Mach=0.5） |
| G2 | 8 | 单因素 ± 扫描：Xthick / Tmax / Metal2 / Solidity 各自取上下限，其余取中点 |
| G3 | 8 | (Xthick, Tmax, Metal2) 的 2³ 极端角点组合，Solidity=1.5 |
| G4 | 4 | 代表性叶型的 Solidity 变化（1.0 / 2.0） |
| G5 | 8 | 固定随机种子（`default_rng(20261013)`）在 legacy 范围内的补充样本 |
| G6 | 1 | `C800030`：与参考 case 几何相同、仅 Incidence/Mach 取上限（验证攻角不影响叶型） |

参数范围全部来自 `config/ranges_legacy.yaml`（**只读**，未修改）。

---

## 4. 如何复现（在仓库根目录执行）

```bash
# 0) 环境（必须用 ai4s：含 numpy / scipy / matplotlib）
conda run -n ai4s python -c "import numpy,scipy,matplotlib;print('env ok')"

# 1) 生成评审参数表（幂等保护：已存在则拒绝覆盖，需 --overwrite）
conda run -n ai4s python analysis/geometry_review/make_review_cases.py

# 2) 先用现有生成器 dry-run
conda run -n ai4s python code/02_generate_geometry.py \
    --input analysis/geometry_review/review_cases.csv \
    --template legacy/blade_batch_generation_template.geomTurbo \
    --output analysis/geometry_review/geometry --dry-run

# 3) 正式生成叶型（输出到评审专用目录，不污染 geometry/）
conda run -n ai4s python code/02_generate_geometry.py \
    --input analysis/geometry_review/review_cases.csv \
    --template legacy/blade_batch_generation_template.geomTurbo \
    --output analysis/geometry_review/geometry

# 4) Geometry QC（先 dry-run 再正式）
conda run -n ai4s python code/03_geometry_qc.py \
    --input analysis/geometry_review/review_cases.csv \
    --geometry analysis/geometry_review/geometry \
    --output analysis/geometry_review/geometry_qc.csv --dry-run
conda run -n ai4s python code/03_geometry_qc.py \
    --input analysis/geometry_review/review_cases.csv \
    --geometry analysis/geometry_review/geometry \
    --output analysis/geometry_review/geometry_qc.csv

# 5) 评审汇总表
conda run -n ai4s python analysis/geometry_review/make_review_summary.py

# 6) 绘图（PNG，dpi >= 200，无 GUI）
conda run -n ai4s python tools/plot_geometry_review.py
```

**重跑安全**：`02`/`03` 对内容一致的产物返回 `SKIP_MATCH`（跳过）或
`CONFLICT_CONTENT`（不覆盖、报错退出 3），因此重复执行不会破坏已有结果。

---

## 5. 图片清单与看点

| 文件 | 内容 | 评审看点 |
|---|---|---|
| `fig01_reference_blade.png` | 参考叶型 + 中弧线 + 弦线 + 前后缘标记 | 基准外形；图中标注实测中弧线 LE/TE 角度 |
| `fig02a_xthick.png` | Xthick = 0.15 / 0.30 / 0.45 叠加 | 最大厚度位置对叶型的影响 |
| `fig02b_tmax.png` | Tmax = 0.04 / 0.055 / 0.07 叠加 | 最大厚度的影响 |
| `fig02c_metal2.png` | Metal2 = 6 / 15 / 24 叠加 | **出口金属角 → 转角** 的影响（入口角固定） |
| `fig02d_solidity.png` | Solidity = 1.0 / 1.5 / 2.0 叠加 | **叶型完全相同**（Solidity 只改栅距，见 fig04） |
| `fig03_corner_grid.png` | 8 个极端角点 | 边界组合是否仍是合理的压气机叶栅 |
| `fig04_solidity_arrangement.png` | Solidity=1.0/1.5/2.0 各 3 片相邻叶片，沿 +Y 平移 `0.06/Solidity` | 栅距与叶片切向尺寸的关系；Solidity=2.0 时最紧 |
| `fig05_le_te_zoom.png` | 被标记 case 的前缘 / 尾缘放大 | 前尾缘小圆是否光滑、有无尖角/自交 |
| `fig06_qc_diagnostics.png` | QC 状态 + min_gap / envelope_clearance / 曲率 / 转角 | 硬门通过与**诊断异常**的区别 |

绘图约定：

```text
坐标    ：raw profile 按 chord 归一化到 0.06 m（= .geomTurbo 的 CHORD_TARGET）
          Z = 弦向（chordwise），Y = 切向（tangential），与仓库约定一致
单叶对比：等比例坐标轴（equal aspect）+ 组内一致的显示范围
标注    ：每个 case 都标出 case_id、相关参数、QC 状态
无 GUI  ：matplotlib Agg 后端，脚本内不调用 plt.show()
```

> 图内文字使用英文：matplotlib 默认字体没有中文字形，中文会渲染成方框。
> 中文说明统一放在本 README 与 `review_summary.csv` 的列名中。

---

## 6. 本次实际运行结果（真实输出，未做任何手工修改）

```text
生成：selected 30 / CREATE 30 / conflict 0 / ERROR 0
QC  ：selected 30 / pass 30 / fail 0 / missing 0 / parse_failure 0
      reason ∈ {OK}；qc_policy_id = geometry_qc_v1_hard；calibration = UNCALIBRATED
单元测试：conda run -n ai4s python -m unittest discover -s tests → 111/111 OK
```

诊断数值范围（真实 QC 输出）：

```text
min_gap                    0.019361 .. 0.047919 m      （硬门：必须 > 0，全部通过）
chord                      0.0599999 .. 0.0600001 m
min_interior_thickness     0.004610 .. 0.004754 m
max_paired_thickness       0.039979 .. 0.070082 m
envelope_clearance        -0.003948 .. +0.038504 m     ← 出现 1 个负值（见下）
pressure_max_turn_angle    22.84 .. 26.12 deg
pressure_max_curvature     2994 .. 3833 1/m
```

### 可信度交叉验证（与 frozen 回归基线逐字节一致）

评审 case 中有 3 个的几何参数恰好与冻结回归 fixture 相同，输出 SHA256 **完全一致**：

```text
C800001 (Sol=1.5) == LG001   profile 0f0c05c3...4741e   geomTurbo 3976cf33...d6ac
C800020 (Sol=1.0) == LG008   profile 0f0c05c3...4741e   geomTurbo 4d7a3ac5...5f07
C800021 (Sol=2.0) == LG009   profile 0f0c05c3...4741e   geomTurbo 9ecbdaf1...c8d7
```

即本次评审用的叶型与项目冻结的 legacy 回归基线完全同源，
评审图上的形状就是**历史程序真实会生成的形状**。

### Incidence / Mach 不变性的实测证据

```text
C800001 (Incidence=0.0, Mach=0.5) 与 C800030 (Incidence=4.0, Mach=0.7)
   profile  sha256 相同
   geomTurbo sha256 相同
```

即只改 Incidence/Mach 会得到**逐字节相同**的叶型（与上一轮代码审计结论一致）。

### 需要师兄重点看的 1 个诊断异常

```text
C800019   Xthick=0.45  Tmax=0.07  Metal2=24.0  Solidity=2.0
          chord = 0.06 m,  pitch = 0.06/2.0 = 0.030 m
          blade_tangential_extent = 0.033948 m
          envelope_clearance      = -0.003948 m   (负)
          min_gap                 =  0.019361 m   (仍为正 → 硬门 PASS)
```

含义与定性（**不是** QC 失败）：

```text
envelope_clearance = periodicity - blade_tangential_extent
                   = 0.030 - 0.033948 < 0
```

即该叶片的**切向包络宽度超过了栅距**，虽然真实最小间隙 `min_gap` 仍为正、
所有硬门通过。冻结契约第 17 节明确说明 `envelope_clearance` 是**诊断量而非判据**，
并且 frozen baseline 中的 `LG011` 就是同类情况（`envelope_clearance < 0` 而
`min_gap > 0`）。因此 QC 判 PASS 是符合契约的。

但工程上值得判断：**Solidity=2.0 + Metal2=24°（转角 29°）这个角落已经处在
"叶栅通道很挤"的位置**，很可能直接影响网格生成（O 型网格需要足够的通道空间）。
这正是"硬门通过 ≠ 工程可行"的典型例子。

---

## 7. 交给师兄的 3 个问题

1. **入口金属角固定 53°** 的同时扫描 Metal2 ∈ [6,24]（转角 29°–47°），
   这个叶型族是否符合原始设计意图？（背景见上一轮角度审计：
   `legacy/blade_batch_generation.py:46` 注释写"零攻角进口气流角 49 度"，
   而代码实际造出 53°，两者相差 4°，原因仍未确认。）
2. **Solidity=2.0（尤其与 Metal2=24° 组合）** 是否可接受？还是应当在 DOE 中
   增加一条 Solidity–Metal2 的联合约束？
3. **Incidence / Mach 如何进入 CFX inlet BC**？本次用 `C800001` vs `C800030`
   证明：只改 Incidence/Mach 会得到**逐字节相同**的叶型，因此它们只可能在 CFX
   边界条件里生效，而这部分在仓库中尚不存在。

请在 `review_summary.csv` 的 `human_*` 列填写结论：

```text
human_geometry_acceptance       accept / reject / rework
human_engineering_plausibility  yes / no / uncertain
human_mesh_feasibility          默认 not_evaluated（本次未做网格）
human_reviewer / human_review_date / human_comment
```

---

## 8. 本次未做 / 未改（合规声明）

```text
未修改 legacy/ 下任何文件
未修改 code/geometry_legacy_v1.py、code/02_generate_geometry.py、code/03_geometry_qc.py
未修改 docs/GEOMETRY_GENERATOR_CONTRACT.md、docs/GEOMETRY_QC_CONTRACT.md
未修改 tests/fixtures/ 回归基线
未修改 config/ranges_legacy.yaml（只读取）
未实现也未运行 01_generate_design.py / generate_geomturbo_batch.py
未生成生产 Sobol 主序列、master_design.csv 或任何生产 case
未运行 NUMECA / CFX / HPC
未自行冻结任何新的生产参数范围
未提交 Git
```

失败的 case 一律如实保留并记录原因（本次为 0 个失败），未做任何伪造输出或自动删除。

# Geometry Range Review — 叶型参数范围评审（V1 已归档 / V2 当前）

> 本目录是**评审专用**目录：把真实生成的叶型交给师兄做工程合理性判断，
> 为将来的 `FINAL_PRODUCTION_RANGES` 提供依据。
>
> **它不是正式数据集，也不冻结任何范围。**
> `range_id` / `sampling_id` / `case_id` 号段与生产号段完全隔离。

```text
V1  legacy range  review : 30 case  C800001..C800030   ->  archive/v1_legacy_review/ (归档，勿改)
V2  exploratory   review : 40 case  C810001..C810040   ->  senior_review_v2/        (★ 当前评审包)
生产 production  号段     : C000001..                    （本目录不产生）
NUMECA bring-up 号段      : C900001                      （在仓库根 geometry/，与本目录无关）
```

---

## 1. 当前状态（2026-10-15）

| 阶段 | 含义 | 状态 |
|---|---|---|
| ① 几何生成成功 | `.dat` / `.geomTurbo` 真实存在 | **40 / 40** |
| ② Geometry QC 通过 | 冻结 QC `geometry_qc_v1_hard` 判定 `geometry_ok = 1` | **40 / 40 PASS**（`reason = OK`） |
| ③ 人工判断工程合理 | 师兄的工程判断 | **未填写**（`human_*` 列为空） |
| ④ 网格 / CFD 可行性 | 能否画网格、能否收敛 | **未验证**（未运行 NUMECA / CFX） |

```text
min_gap                 0.014494 .. 0.072696 m      （硬门 min_gap > 0：40/40 全部通过）
envelope_clearance      5 个 case 为负（诊断量，非失败，非碰撞）
独立单叶轮廓            25 个（40 case = 25 个单叶型 + 15 个不同 Solidity 的栅距变化）
单元测试                111/111 OK
```

**已冻结、本次未修改**：`Metal1 = 53 deg` 与造型核心 `code/geometry_legacy_v1.py`、
冻结模板 `legacy/blade_batch_generation_template.geomTurbo`
（sha256 `92c4296f...c55119`）、`config/ranges_legacy.yaml`、`tests/fixtures/`。

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
师兄审查 V2 的 40 个真实叶型
  入口：senior_review_v2/00_all_cases_overview.png + senior_review_v2/00_case_index.csv
  评价写在 human_acceptance / human_comment 列（或各 case 的 parameters.json）
  -> 依据反馈确定合理参数空间
  -> 决定是否继续扩边界
  -> 冻结 FINAL_PRODUCTION_RANGES
```

**Geometry QC PASS ≠ 气动合理 ≠ 网格/CFD 可行。** 本目录不构成 DOE、不构成 CFD 生产。

# Geometry Range Review V2 — 40 Case 师兄评审包（叶型几何合理性评审）

> 本目录由 `tools/make_senior_review_v2.py` 生成。**只做评审材料整理与可视化**：
> 没有重新生成几何、没有重跑 Geometry QC、没有修改冻结造型核心、没有运行
> NUMECA / CFX、没有新增参数扫描。
>
> ```text
> range_id    = exploratory_v2_review
> sampling_id = exploratory_v2_deterministic
> case_id     = C810001 .. C810040   (V2 专用号段)
> ```
>
> 号段隔离：V2 评审用 `C81xxxx`，与 V1 评审号段（已归档在
> `analysis/geometry_review/archive/v1_legacy_review/`）、正式生产号段
> `C0000xx..`、NUMECA bring-up 号段 `C900001` 均不重叠，**本包内不含任何
> V1 评审数据**。

---

## 1. 为什么做这次评审

我们准备把研究范围扩展到比历史 1891 Case **更宽**的几何参数空间。
程序无法替师兄判断"这个叶型在工程上是否合理"，因此这里**不做任何程序筛选**，
而是把探索范围内生成的 **全部 40 个 Case** 的真实叶型交给师兄逐一观察，
由师兄按自己的工程标准判断哪些参数范围可用、哪些明显不合理。

本包不是正式数据集，也不冻结任何范围。

---

## 2. 四个阶段必须严格区分（读图时不要混淆）

| 阶段 | 含义 | 本次状态 |
|---|---|---|
| ① 几何生成成功 | `.dat` / `.geomTurbo` 真实存在于磁盘 | **40 / 40 成功** |
| ② Geometry QC 通过 | 冻结 QC（`geometry_qc_v1_hard`）判定 `geometry_ok = 1` | **40 / 40 PASS**，`reason = OK` |
| ③ 人工判断工程合理 | 师兄的工程判断 | **未填写**（索引/JSON 的 `human_*` 列留空） |
| ④ 网格 / CFD 可行性 | 能否画网格、能否收敛 | **未验证**（本次未运行任何 CFD 求解器） |

`00_case_index.csv` 中 `geometry_generated` 与 `geometry_qc_status` 是两列，
正是为了防止把①和②混为一谈。

---

## 3. 探索范围 vs 历史范围

| 参数 | 历史范围（1891 Case） | 本次探索范围 | 说明 |
|---|---|---|---|
| Xthick | 0.15 – 0.45 | 0.10 – 0.60 | 无量纲，最大厚度弦向位置 |
| Tmax | 0.04 – 0.07 | 0.025 – 0.095 | 无量纲，最大厚度比 |
| Metal2 | 6 – 24 deg | 0 – 32 deg | 出口金属角（入口角 Metal1 冻结） |
| Solidity | 1.0 – 2.0 | 0.7 – 2.5 | 只改变栅距 = 0.06 / Solidity |
| Incidence | -4 – 4 deg | 固定 0 deg | 工况，不改变叶型几何 |
| Mach | 0.3 – 0.7 | 固定 0.5 | 工况，不改变叶型几何 |

补充说明：

```text
Metal1 = 53 deg  —— 冻结常量，本次未修改（入口中弧线角）
Incidence / Mach —— 已冻结为 0 deg / 0.5，且不改变叶型几何（V1 已验证）
Solidity —— 只改变 .geomTurbo 的 periodicity = 0.06 / Solidity，不改变单叶型
```

---

## 4. 这 40 个 Case 是怎么挑的

按"边界优先、尽量分散"构造（`make_review_cases.py`，确定性、无随机漂移）：

| 组别 | 数量 | 内容 |
|---|---|---|
| A_single_param | 17 | 单参数新旧边界扫描（Xthick / Tmax / Metal2 / Solidity 各取新旧上下限，其余取历史中点） |
| B_corner | 8 | (Xthick, Tmax, Metal2) 探索范围的 2^3 个极端角点，Solidity = 1.5 |
| C_coupled | 8 | Solidity × Metal2 联合边界（同一单叶型配不同栅距，Solidity = 0.7 / 2.5） |
| C_combined | 3 | 多参数同时取极端（四维极端组合） |
| D_maximin | 4 | 确定性 maximin 分散补充样本（seed 20261015） |
| 合计 | 40 | 全部 Case 一个不漏地进入本评审包 |

**重复单叶型说明（重要）**：

```text
不同的 (Xthick, Tmax, Metal2) 组合数 = 25 个
40 个 Case 中有 15 个是"同一单叶型 + 不同 Solidity"
```

因此本包中 **25 个不同的单叶型** 被展开成 40 个 Case。
相同单叶型的叶子在总览图与索引里有相同的分组 ID（`BLxx`），
**不要误认为产生了新的独立叶型**——它们唯一区别是栅距（pitch）：

```text
BL03: C810003, C810014, C810015, C810016, C810017
BL10: C810010, C810026, C810030
BL11: C810011, C810027, C810031
BL12: C810012, C810028, C810032
BL13: C810013, C810029, C810033
BL15: C810019, C810035
BL19: C810023, C810036
BL20: C810024, C810034
```

---

## 5. 目录结构

```text
senior_review_v2/
├── README.md                     本文件
├── 00_all_cases_overview.png     全部 40 个 Case 总览（5 行 × 8 列，无遗漏）
├── 00_case_index.csv             40 行索引（含参数、分组、QC、重复叶型组、人工评审空列）
└── cases/
    └── C810001/ .. C810040/     每个 Case 一个文件夹
        ├── parameters.json        该 Case 的全部参数 + QC 数值 + 单位说明 + 留空人工列
        ├── blade_profile.png      单叶型（压力面/吸力面/中弧线/前缘/尾缘）
        ├── cascade_3blade.png     按真实 pitch 排列的三叶片叶栅
        ├── edge_details.png       前缘 / 尾缘局部放大
        ├── C810001.dat          原始几何（逐字节复制，未修改）
        └── C810001.geomTurbo    原始几何（逐字节复制，未修改）
```

| 文件 | 说明 |
|---|---|
| `README.md` | 评审说明（目的 / 范围 / 单位 / 声明 / 如何评审） |
| `00_all_cases_overview.png` | 全部 40 个 Case 的总览图 |
| `00_case_index.csv` | 40 行索引，含人工评审空列 |
| `cases/C8100xx/parameters.json` | 该 Case 的六维参数 + 生成/QC 状态 + QC 数值 + 单位说明 + 人工空列 |
| `cases/C8100xx/blade_profile.png` | 单叶型（同一窗口/比例） |
| `cases/C8100xx/cascade_3blade.png` | 三叶片叶栅（真实 pitch） |
| `cases/C8100xx/edge_details.png` | 前缘 / 尾缘局部放大（同一窗口/比例） |
| `cases/C8100xx/C8100xx.dat` | 原始叶型文件（只读副本） |
| `cases/C8100xx/C8100xx.geomTurbo` | 原始几何文件（只读副本） |

**打包与版本管理说明：**

```text
analysis/geometry_review/senior_review_v2.zip
    是本目录（解压后内容）的同一个包的 ZIP 副本，仅作本地交付文件
    （发邮件 / 拷 U 盘 / 直接发给师兄时更方便），内容与本目录完全一致。
    版本管理里跟踪的是本目录（解压后的完整评审材料），ZIP 不进 Git，
    以避免同一份材料重复存储；规则见仓库根 .gitignore（附注释）。
```

---

## 6. 图片说明与单位约定

### 6.1 三张单 Case 图

| 图 | 内容 | 看点 |
|---|---|---|
| `blade_profile.png` | 单叶型全貌：压力面（实线）、吸力面（虚线）、中弧线（点线）、弦线（点划线）、LE/TE 标记、0.01 m 比例尺 | **40 张图使用完全相同的物理坐标窗口与比例**，可直接叠加比较形状差异 |
| `cascade_3blade.png` | 中间为本 Case 叶型，上下相邻叶型按**该 Case 真实栅距**沿 +Y 平移；标出 S、pitch、min_gap、envelope_clearance | 叶栅通道形态；Solidity 越大通道越窄 |
| `edge_details.png` | 前缘、尾缘各一个 0.012 m × 0.012 m 的方形放大窗口（**4× 于 blade_profile 比例**） | 前尾缘小圆是否光滑、有无尖角/自交 |

`00_all_cases_overview.png`：**5 行 × 8 列 = 全部 40 个 Case**，
顺序 = 实验组顺序（A→B→C→D），每个子图给出真实单叶轮廓、Case ID、
Xthick / Tmax / Metal2 / Solidity、QC 状态与重复叶型分组 ID。
所有子图与 `blade_profile.png` 使用同一窗口与比例，因此可以直接横比趋势。

### 6.2 坐标与单位（容易出错，请务必看这一节）

```text
坐标系 : x = Z = 弦向（chordwise），y = Y = 切向（tangential）
         与 .geomTurbo 的 blade section 完全一致（.geomTurbo: UNITS Meters）
缩放   : .dat 是原始归一化 profile 坐标（列顺序 xp yp xs ys）；
         绘图时统一缩放到 chord = 0.06 m（= 冻结的 CHORD_TARGET），
         因此图中所有长度单位都是 m，可以直接量取。
参数   : Xthick / Tmax / Metal2 / Solidity 是无量纲/角度参数，
         永远不要读成米（图注里也标了 [-] 或 [deg]）。
```

**不要把未缩放的厚度数值当成米**：

```text
min_interior_thickness, max_paired_thickness  —— 来自原始 .dat profile，
   单位是"原始归一化单位"，不是 m
（min_gap / envelope_clearance / periodicity / chord / blade_tangential_extent
   来自 .geomTurbo 的物理尺度，单位才是 m）

每个 parameters.json 的 "units" 字段逐项写明了单位与所属坐标系。
```

### 6.3 三张图的坐标一致性约定（避免误读）

```text
blade_profile.png : 全部 40 张 = 同一窗口 + 同一比例（完全可比）
edge_details.png  : 全部 40 张 = 同一 0.012 m 方形窗口 + 同一比例（完全可比）
cascade_3blade.png: 叶片比例与 blade_profile 相同（等比、绝不拉伸），
                    但画布高度随该 Case 的 pitch 变化（pitch 大 → 画布更高），
                    因此各 Case 的"米/像素"不同 —— 请用图中标注的 pitch 数值对比，
                    而不是用像素间距对比叶栅。
```

所有图片都是**由真实坐标数据绘制的二维几何视图**，不是 NUMECA 网格，
也不是 CFD 结果。

---

## 7. 读图前必看的声明

```text
1) 二维几何视图：来自真实 .dat / .geomTurbo 坐标；不是网格、不是 CFD 结果。
2) QC PASS 只代表几何硬门（geometry_qc_v1_hard）通过，
   不代表气动合理，也不代表能画网格 / 能收敛。
3) envelope_clearance < 0 只是诊断量（= periodicity − 叶片切向尺寸），
   不是叶片碰撞。硬门是 min_gap > 0：本次 40/40 全部满足
   （min_gap 范围 0.01449 .. 0.07270 m）。
4) Xthick / Tmax / Metal2 是无量纲参数，从不以米标注。
5) 本包的探索范围未经批准，不是正式生产范围；不冻结任何范围。
```

本次 `envelope_clearance < 0` 的 Case 共 5 个（诊断提示，非失败）：

```text
  C810017: envelope_clearance = -0.0040894 m   (min_gap = 0.0152846 m)
  C810032: envelope_clearance = -0.0099474 m   (min_gap = 0.0148936 m)
  C810033: envelope_clearance = -0.014521 m   (min_gap = 0.0144935 m)
  C810035: envelope_clearance = -0.0145241 m   (min_gap = 0.0151821 m)
  C810038: envelope_clearance = -0.0112428 m   (min_gap = 0.0175675 m)
```

---

## 8. 如何进行人工评审（师兄请看这里）

**建议流程（30–60 分钟）：**

```text
第 1 步  打开 00_all_cases_overview.png
         先看整体趋势：40 个叶型按实验组顺序排列，
         同一窗口、同一比例，形状差异可以直接横比。
第 2 步  打开 00_case_index.csv
         一行一个 Case，含六维参数、实验组、是否超出历史范围、QC 状态、
         重复叶型分组 ID（BLxx）。先扫一遍"超出历史范围"的 Case。
第 3 步  对感兴趣的 Case 打开 cases/C8100xx/ 文件夹
         blade_profile.png 看单叶型；cascade_3blade.png 看叶栅通道；
         edge_details.png 看前尾缘小圆。
第 4 步  填写评价
         在 00_case_index.csv 最后两列填写（不要改动其它列）：
           human_acceptance : 建议取值 accept / accept_with_caution /
                              reject / unsure
           human_comment    : 自由文字（例如"Solidity>2.2 时通道过窄"）
         也可以直接编辑对应 cases/C8100xx/parameters.json 的
         human_acceptance / human_comment 两个字段（当前为 null）。
第 5 步  如果某处需要更细的局部放大，请给出 case_id + 区域
         （例如"C810032 尾缘再放大 4 倍"），我们可以追加出一张放大图。
```

**建议的重点观察点：**

```text
a) Xthick 取 0.10 / 0.60 时，叶型是否还像压气机叶栅（厚度峰位置是否合理）
b) Tmax 取 0.025 / 0.095 时，是否过薄或过厚
c) Metal2 = 0 deg / 32 deg 时，转角是否合理（入口角固定 53 deg 不变）
d) Solidity 0.7 / 2.5（尤其与 Metal2 联合的 C 组）时，叶栅通道是否过宽/过窄
e) 前缘/尾缘小圆是否光滑，有无尖角或明显不光滑
f) 哪些参数组合"明显不可用"，请直接标 reject（这类信息比 accept 更有价值）
```

请注意：**不要**修改 `cases/*/*.dat`、`cases/*/*.geomTurbo` 与任何 PNG；
人工评价只写在索引 CSV 或 `parameters.json` 的 `human_*` 字段里。

---

## 9. 数据来源（只读，本次未修改）

| 源文件 | 说明 |
|---|---|
| `analysis/geometry_review/review_cases.csv` | 40 个 Case 的六维参数（V2 评审专用） |
| `analysis/geometry_review/geometry/profiles/C8100xx.dat` | 真实生成的原始叶型（列 xp yp xs ys） |
| `analysis/geometry_review/geometry/geomturbo/C8100xx.geomTurbo` | 真实生成的几何（UNITS Meters，periodicity = 0.06 / Solidity） |
| `analysis/geometry_review/geometry_qc.csv` | 真实 QC 报告（本次包内全部数值来源） |
| `analysis/geometry_review/ranges_exploratory_v2.yaml` | 探索范围定义（status = EXPLORATORY_NOT_APPROVED） |
| `code/02_generate_geometry.py / code/03_geometry_qc.py` | 生成器与 QC 实现（本次未运行、未修改） |
| `code/geometry_legacy_v1.py` | 冻结造型核心（Metal1 = 53 deg；本次未修改） |
| `legacy/blade_batch_generation_template.geomTurbo` | 冻结模板 sha256 92c4296f...5119（未修改） |
| `tools/plot_geometry_review.py` | V2 绘图脚本；本包复用了它的坐标与比例约定 |

本包的构建是**只读复用**：脚本在开始与结束时对上述源文件逐一比对 sha256，
确认源文件未被修改（见第 10 节自检结果）。每个 `parameters.json` 里也记录了
该 Case 的 `.dat` / `.geomTurbo` 源路径与 sha256。

参考命令（**本次未执行**，仅记录当时的生成方式）：

```bash
# 参数表
conda run -n ai4s python analysis/geometry_review/make_review_cases.py
# 几何（dry-run 后正式）
conda run -n ai4s python code/02_generate_geometry.py \
    --input analysis/geometry_review/review_cases.csv \
    --template legacy/blade_batch_generation_template.geomTurbo \
    --output analysis/geometry_review/geometry
# QC
conda run -n ai4s python code/03_geometry_qc.py \
    --input analysis/geometry_review/review_cases.csv \
    --geometry analysis/geometry_review/geometry \
    --output analysis/geometry_review/geometry_qc.csv
# 本评审包（只读取上面的结果）
conda run -n ai4s python tools/make_senior_review_v2.py
```

---

## 10. 文件清单与自检结果

```text
Case 文件夹            : 40 / 40
parameters.json        : 40 / 40
单 Case PNG            : 120 / 120
总览 PNG               : 1（5716 × 3081 px）
原始 .dat 复制         : 40 / 40
原始 .geomTurbo 复制   : 40 / 40
索引行数               : 40
图片分辨率             : >= 200 dpi
```

自检项：

- [x] Case 文件夹 40/40 存在且命名与 case_id 一致
- [x] parameters.json 40/40 存在，必填字段（参数 / range_id / 生成状态 / QC 状态 / min_gap / envelope_clearance / periodicity / qc_policy_id / human_*）齐全
- [x] 单 Case PNG 120 张（每 Case 3 张）全部存在且可解码
- [x] 总览 PNG 覆盖全部 40 个 Case（5 行 × 8 列，无遗漏）
- [x] 原始 .dat 40 个、.geomTurbo 40 个已复制且 sha256 与源文件一致（逐字节未修改）
- [x] 00_case_index.csv 40 行，case_id 与文件夹 / 图片 / JSON 一一对应
- [x] 索引与 JSON 中的 human_acceptance / human_comment 全部为空（等待师兄填写）
- [x] 只读校验：83 个源文件（评审参数表 / QC 报告 / ranges / 每个 Case 的 .dat 与 .geomTurbo）在打包前后 sha256 未变化
- [x] 包内不含 V1 评审号段（C800xxx）数据，与 V1 归档完全隔离
- [x] 自检结论：全部检查项通过（详见构建终端的 self-check 输出）
- [x] overview PNG 5716x3081 px @ 200 dpi
- [x] overview content check: all 40 panels contain drawn blade geometry

---

## 11. 与 V1 评审包的关系

```text
V1（历史范围 30 Case，C800001..C800030）已归档，未修改：
    analysis/geometry_review/archive/v1_legacy_review/
V2（探索范围 40 Case，C810001..C810040）：
    本目录
两者的 case_id 号段、range_id、sampling_id 完全不同，不会混淆。
```

---

*本包只用于人工几何合理性评审；不构成正式数据集，不冻结生产范围。*

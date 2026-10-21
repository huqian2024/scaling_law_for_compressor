# 航空航天压气机二维叶栅 AI4S 数据生成项目
## 本地 Ubuntu Agent 执行说明 / 项目总指令

> **用途**  
> 本文件是给运行在 Ubuntu 笔记本上的本地 Agent 使用的长期项目说明。  
> Agent 的主要职责是：帮助我完成压气机二维叶栅 AI4S 项目的**数据准备前端、自动化脚本、数据管理、质量检查和最终 canonical dataset 构建**。  
> Agent 必须清楚哪些任务可以在本地完成，哪些任务必须在 Windows/NUMECA/CFX GUI 环境完成，哪些任务必须在学校 HPC 完成，并且**不能越过边界自行假设、伪造或替代 CFD 物理设置**。

---

# 0. 当前权威项目状态（截至 2026-10-21）

> 本节记录**当前已冻结的事实**。若与下文历史描述冲突，**以本节为准**。

```text
FINAL_DOE  = SCRAMBLED_SOBOL          （已获 owner 批准 / FINAL）
SOBOL_SEED = 1                        （来源：analysis/doe_compare_benchmark.py L44，可验证）
             scipy.stats.qmc.Sobol(d=6, scramble=True, seed=1)
ordering   = native Sobol sequence order
nested     = D_N = 前 N 个点（prefix nesting）
参数顺序   = [Xthick, Tmax, Metal2, Solidity, Incidence, Mach]
```

```text
N 定义（FROZEN 2026-10-13）:
N = usable training case count
    （test / validation / failed / rejected 均不计入 N）

FINAL_N_TRAIN_MAX           = 100000 usable training cases
FINAL_N_TEST                = 20000 usable test cases（fixed）
TRAIN_TEST_RATIO            = 5:1
MIN_USABLE_TRAIN_TEST_CASES = 120000
FINAL_N_LADDER              = [1000, 2000, 5000, 10000, 20000, 35000, 50000, 70000, 100000]

GEOMETRY_REUSE              = DISABLED / NOT ACTIVE
PRODUCTION_ROUTE            = ONE_6D_POINT_ONE_CASE

SOBOL_MASTER_M              = m >= 17（下界，非最终长度；FINAL m 仍 PENDING）

FINAL_VALIDATION_POLICY     = PENDING
FINAL_N_VALIDATION          = PENDING
FINAL_PRODUCTION_RANGES     = PENDING    <- 当前最主要 blocker
FINAL_RAW_CFD_ATTEMPTS      = PENDING
FAILURE_RESERVE_POLICY      = PENDING（等真实 CFD failure rate）

（旧的 FINAL_NMAX 一词已退役：不得再用来表示
  training N_max / usable total / raw CFD attempts 中的任何单一概念。）
权威冻结记录: docs/DESIGN_FREEZE_2026-10-13.md
该冻结 session 记录: docs/SESSION_DELIVERY_2026-10-13.md
最新 session 记录: docs/SESSION_DELIVERY_2026-10-17.md（几何参数研究，探索性）
```

```text
Geometry local pipeline = COMPLETE / PASS
  legacy regression fixture       PASS（26/26 exact）
  geometry core exact regression  PASS（26/26）
  geometry generator              PASS（generator contract FROZEN V1.2）
  Geometry QC                     PASS（QC contract FROZEN V1；frozen baseline 13/13 PASS）
```

Geometry 参数研究（2026-10-17，**全部为探索性，未批准生产范围**）：

```text
1) 全参数敏感性 + 边界检验（最新一轮敏感性扫描）
   analysis/geometry_review/parameter_sensitivity_v1_100cases/
   case_id C820001..C820100（100 case；S1=60, S2=20, S3=20）
   生成 100/100，硬性 QC 100/100，冻结 QC 100/100
   总览图：overview_001_050.png / overview_051_100.png
   参数表：case_design.csv；几何指标：case_metrics.csv
   自动筛选：FIX_CANDIDATE=SS1,SS2；KEEP_CANDIDATE=10 个；REVIEW=Ks2
   注意：本轮 SS1（2.4-4.0）与 SS2（0.5-1.1）是可变参数；
         冻结发生在之后的人工评审，不能改写成“一直固定”。

2) Ks1/Ks2 专项复核
   analysis/geometry_review/ks1_ks2_review_v1/  C830001..C830057（57/57 PASS）
   SS1=3.2、SS2=0.8 已在每个 Case 中 FIXED_BY_REVIEW

3) 几何参数最终裁决 V1（仅限探索性几何 DOE）
   analysis/geometry_review/parameter_final_decision_v1/
   新增 C840001..C840040（49 行设计，含 9 个复用；49/49 PASS）
   几何维度 = 11：Xthick Tmax Metal2 Solidity Metal1 T1 T2 Xmean K_m Ks1 Ks2
   开放范围（探索性）：见 final_geometry_parameters.yaml
   SS1 = 3.2 FIXED_BY_REVIEW；SS2 = 0.8 FIXED_BY_REVIEW（人工决定）
   Xmean 探索上界保持 0.18（不扩展到 0.20/0.22）
   运行条件 2 维：Incidence=0 deg、Mach=0.5（不改变叶型；CFX 实现仍 TBD）
```

```text
参数现状（后续参数化研究）:
  SS1 = 3.2  FIXED（code/geometry_legacy_v1.py:44,
                    tools/geometry_final_decision_v1.py:86,
                    final_geometry_parameters.yaml）
  SS2 = 0.8  FIXED（code/geometry_legacy_v1.py:45,
                    tools/geometry_final_decision_v1.py:86,
                    final_geometry_parameters.yaml）
  其余 11 个几何参数 OPEN（探索性范围，不是生产范围）

历史评审阶段（不代表当前进度）:
  V1 = 30 case C800001..C800030（已归档）
  V2 = 40 case C810001..C810040（评审包已交付，无评审记录）

FINAL_PRODUCTION_RANGES 仍为 PENDING：
    上述探索性配置 NOT a production approval / NOT a CFD certification。
权威记录: analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md
          docs/SESSION_DELIVERY_2026-10-17.md
```

2026-10-21 补充（文档核对 + 人工评审补录 + 下一阶段策略）：

```text
C820 人工评审（师兄，用户转述，2026-10-21）
  记录 : analysis/geometry_review/parameter_sensitivity_v1_100cases/
           human_review_2026-10-21.csv  +  HUMAN_REVIEW_2026-10-21.md
  REJECT     : 15 -> C820033 C820034 C820035 C820036 C820043 C820062
                     C820081 C820082 C820083 C820084
                     C820089 C820090 C820091 C820092 C820100
  UNREVIEWED : 0；ACCEPT : 85（形状合理，不代表 CFD/网格/气动合格）
  逐案原因未提供 -> 待补充，不得编造
  15 个全部 hard/frozen QC PASS -> 现有自动 QC 未识别这类工程不合理

DOE 维度（不得混写）
  生产 DOE 仍为 2026-10-13 冻结的 d = 6：
      [Xthick, Tmax, Metal2, Solidity, Incidence, Mach]
  当前 13 维（11 几何 + 2 运行）是探索性研究空间，
  不是“生产 DOE 已冻结为 13 维”
  FINAL_PRODUCTION_RANGES 仍 PENDING
  对照表：docs/PARAMETER_SPACE_RECONCILIATION.md
  Metal1 = 入口金属角（legacy 53 = 48 + DeltaBeta 5）；
  Incidence = 入口气流角工况变量；二者不得混用；CFX 实现仍 TBD

联合约束
  JC_XMEAN_KS1_KM（K_m >= 0.15，0.18 < Xmean <= 0.20）
  在 Xmean <= 0.18 下适用区间为空 -> 无法触发
  保持 active_at_final_bound = false；不写入采样器；不作为生产硬约束

下一阶段策略（PROPOSED / NOT IMPLEMENTED）
  宽范围采样 + 少量简单硬约束 + 自动几何筛选 + 必要人工复核
  SS1/SS2 固定；其余 11 几何参数可变（范围仍需最终确认）
  只收紧证据明确的单参数边界；不优先建立复杂联合约束
  记录全部被拒样本与原因；验证自动 QC 与人工判断的一致性
  文档：docs/GEOMETRY_SCREENING_STRATEGY_2026-10-21.md
  本轮不实现采样器 / 约束过滤器 / 新 QC 算法，不修改任何范围数值

约束方案（ANALYSIS / PROPOSAL，待人工确认）
  docs/GEOMETRY_CONSTRAINT_ANALYSIS_2026-10-21.md
  A  : Metal2 6.0-32，其余 10 参数不变  -> 85/85 ACCEPT，排除 1/15 REJECT（推荐）
  A2 : Metal2 8.0-32                    -> 85/85 ACCEPT，排除 4/15（可选）
  B  : A + K_m <= 0.3125                -> 85/85，排除 6/15，与 C840 K_m 证据冲突
  C  : A + K_m <= 0.2012                -> 83/85（损失 2 ACCEPT），仅对照
  final_geometry_parameters.yaml 未修改
```

已准备的 production 代码：

```text
code/01_generate_design.py        PREPARED / NOT EXECUTED
code/generate_geomturbo_batch.py  PREPARED / NOT EXECUTED

ranges 为 runtime configurable（--ranges PATH）
legacy ranges 不是正式 production ranges
```

一键命令（**当前 DO NOT RUN**）：

```bash
conda run -n ai4s python code/generate_geomturbo_batch.py \
  --ranges config/ranges_legacy.yaml \
  --n-train 100000 \
  --n-test 20000 \
  --qc-output geometry/geometry_qc_production.csv
```

师兄确认范围后 → 只替换：

```text
--ranges config/ranges_production_v1.yaml
```

下一步规则：

```text
Do not RUN any production design / geometry generation until
FINAL_PRODUCTION_RANGES are frozen.

Historical note: the retired term FINAL_NMAX is replaced by the explicit
FINAL_N_TRAIN_MAX / FINAL_N_TEST / MIN_USABLE_TRAIN_TEST_CASES /
FINAL_RAW_CFD_ATTEMPTS terms.
```

NUMECA bring-up provenance（保留，不得删除/覆盖）：

```text
C900001 = bring-up only，永不进入 production case sequence
design/bringup/                        （tracked）
docs/NUMECA_BRINGUP_CASE_C900001.md    （tracked，记录 SHA256）
geometry/profiles/C900001.dat          （本地产物，保留）
geometry/geomturbo/C900001.geomTurbo   （本地产物，保留）
geometry/geometry_qc.csv               （bring-up 报告，保留）
production QC 未来使用独立路径 geometry/geometry_qc_production.csv
```

新会话 Console 必须先：

```text
ask/resolve FINAL_PRODUCTION_RANGES first
before starting any production design generation
```

长期红线（不变）：

```text
do not guess CFX Incidence implementation
do not guess Mach implementation
do not modify legacy files
do not fake-repair failed CFD cases
```

---

# 1. 项目背景

本项目目标是研究：

$$
\text{数据量 }N,\quad \text{模型大小 }P,\quad \text{预测误差 }E
$$

之间是否存在类似 scaling law 的幂律关系，用于指导航空航天压气机二维流场 AI 模型的数据规模和模型规模设计。

现阶段已经使用约 **1891 个二维压气机叶栅流场样本**，验证了项目可行性。

后续计划使用三种模型：

1. PCA + MLP
2. U-Net
3. FNO

但是**当前阶段不做训练**。

当前阶段只做：

> 从参数采样开始，批量生成可靠 CFD 流场，并最终整理成可以直接提供给 PCA+MLP、U-Net、FNO 三套预处理程序的标准原始数据集。

---

# 2. 当前已知的物理/几何结构

整个二维压气机叶栅流场由七个子域组成：

- `domain1`
- `domain3`
- `main_blade_down`
- `main_blade_inlet`
- `main_blade_outlet`
- `main_blade_skin`
- `main_blade_up`

空气总体从左向右流动。

最终每一个 CFD 样本必须能够映射为：

```text
一个 case
│
├── 六个输入参数
│   ├── Xthick
│   ├── Tmax
│   ├── Metal2
│   ├── Solidity
│   ├── Incidence
│   └── Mach
│
├── 七个子域
│   ├── domain1
│   ├── domain3
│   ├── main_blade_down
│   ├── main_blade_inlet
│   ├── main_blade_outlet
│   ├── main_blade_skin
│   └── main_blade_up
│
├── 每个子域的坐标
├── 每个子域的 CFD 物理变量
└── 完整 QC / provenance 信息
```

---

# 3. 当前已有 Python 几何生成程序

已有文件：

```text
blade_batch_generation.py
blade_batch_generation_template.geomTurbo
lhs_samples_train.csv
```

当前 Python 程序做的事情：

```text
六维采样
→ 生成 lhs_samples.csv
→ 生成叶型 profile
→ 生成 .geomTurbo
→ 部分可视化检查
```

当前六维参数范围：

```text
Xthick    = [0.15, 0.45]
Tmax      = [0.04, 0.07]
Metal2    = [6, 24]
Solidity  = [1, 2]
Incidence = [-4, 4]
Mach      = [0.3, 0.7]
```

当前采样方法：

```python
scipy.stats.qmc.LatinHypercube(
    d=6,
    optimization="random-cd",
    seed=1
)
```

当前程序中：

```text
Xthick
Tmax
Metal2
Solidity
```

参与几何/`.geomTurbo` 生成。

而：

```text
Incidence
Mach
```

目前只是被采样和记录，并未直接参与 `.geomTurbo` 几何生成。

因此当前逻辑应理解为：

$$
Geometry=f(Xthick,Tmax,Metal2,Solidity)
$$

而：

$$
OperatingCondition=f(Incidence,Mach)
$$

`Incidence` 和 `Mach` 应在后续 CFX 边界条件中真正生效。

---

# 4. 总体技术路线

整个数据生成流水线定义为：

```text
设计空间定义
→ 参数采样
→ master_design.csv
→ 叶型/profile
→ .geomTurbo
→ Geometry QC
→ NUMECA / AutoGrid 网格
→ Mesh QC
→ CFX-Pre 生成求解输入
→ CFX Solver
→ Solver / Physics QC
→ CFD-Post
→ 七子域导出
→ Raw field dataset
→ Canonical HDF5 dataset
→ Dataset QC
→ 数据准备完成
```

最终必须得到一个**模型无关的 canonical dataset**。

禁止在 CFD-Post 阶段直接把数据变成 U-Net 图像或者 FNO 输入。

三种模型的预处理只能发生在 canonical dataset 之后：

```text
canonical dataset
├── preprocess_pca_mlp.py
├── preprocess_unet.py
└── preprocess_fno.py
```

---

# 5. 三台计算环境的职责边界

## 5.1 Ubuntu RTX4060 笔记本

这是项目的**主要控制中心**。

本地 Agent 主要运行在这里。

允许并建议完成：

```text
Python 开发
参数采样
LHS / Sobol DOE
master_design.csv
.geomTurbo 生成
profile 生成
Geometry QC
参数空间可视化
Git 版本管理
批处理脚本生成
HPC job script 生成
CFX-Pre session 模板生成
CFD-Post session 模板生成
manifest 管理
日志解析
CFD 导出数据收集
CSV → HDF5
canonical dataset 构建
dataset QC
数据统计
抽样可视化
```

RTX4060 在这一阶段不是核心资源。

本地 Python/CPU 足够完成大部分前端工作。

---

## 5.2 Windows 轻薄本

主要用于 GUI 和人工检查。

适合：

```text
NUMECA / AutoGrid GUI 学习与调试
CFX-Pre GUI
CFX Solver Manager GUI
CFD-Post GUI
Golden Case 人工复现
session recording
网格和流场肉眼检查
```

如果 NUMECA / Ansys license 只能在校园网使用，则这些任务等回学校后完成。

Agent 可以：

```text
帮忙生成操作 checklist
帮忙解释 GUI 操作步骤
分析用户导出的 session / script / log
```

但 Agent 不能假设 GUI 已经执行成功。

---

## 5.3 学校 HPC

主要用于高计算量任务。

包括：

```text
NUMECA 批量网格
CFX-Pre batch
CFX Solver 大规模计算
CFD-Post batch
大规模日志收集
```

导师说 HPC 有 H200。

注意：

> H200 对后续 U-Net / FNO / MLP 训练非常有价值，但不能默认 H200 对 CFX 求解就是核心加速资源。

CFX 实际计算速度可能主要取决于：

```text
CPU 节点
MPI
license 并发
I/O
scheduler
Ansys 安装方式
```

Agent 不允许在没有学校实际信息时擅自假设：

```text
Slurm / PBS
CPU 数量
CFX MPI 类型
license 数量
最大并发数
H200 是否参与 CFD
```

这些信息必须回学校后核实。

---

# 6. Agent 的硬边界

本地 Agent 必须遵守以下限制。

## 禁止做的事情

### 6.1 不允许猜 CFX 物理设置

当前未知：

```text
空气模型
Reference Pressure
Total Temperature
Total Pressure
Static Pressure
出口边界
湍流模型
湍流强度
Energy Equation
wall treatment
steady / transient
advection scheme
timescale
收敛条件
最大迭代数
周期边界具体设置
```

这些必须从旧 1891 样本中的成功 CFX case 继承。

Agent 不允许用“常见做法”直接替代。

---

### 6.2 不允许自己定义 Incidence 的换算公式

当前程序存在：

```python
DeltaBeta = 5
Metal1 = 48 + DeltaBeta
```

同时代码注释中出现“零攻角进口气流角”等描述。

这存在需要进一步核实的定义问题。

Agent 不允许自行假设：

```text
inlet_angle = 49 + Incidence
```

或者其他公式。

必须从旧 CFX setup / 师兄脚本 / Golden Case 中确认。

---

### 6.3 不允许自己定义 Mach 的 CFX 设置方式

不能直接假设：

```text
velocity = Mach * speed_of_sound
```

旧项目可能采用：

```text
Total Pressure + Total Temperature + Flow Direction
```

或者其他方式。

必须复用旧 pipeline。

---

### 6.4 不允许直接修改 legacy 文件

以下内容必须保留原始版本：

```text
legacy/blade_batch_generation.py
legacy/blade_batch_generation_template.geomTurbo
legacy/lhs_samples_train.csv
```

新的程序只能在：

```text
code/
config/
```

等目录中创建。

---

### 6.5 不允许删除失败 case

任何失败：

```text
Geometry failure
Mesh failure
CFX-Pre failure
Solver failure
Non-converged
Post failure
Dataset failure
```

都必须被记录。

不允许简单删除。

必须保留：

```text
case_id
failure_stage
failure_reason
```

---

### 6.6 不允许用假的数值修复失败数据

例如禁止：

```text
NaN → 0
缺失 domain → 全零
缺失场变量 → 均值填充
```

失败 case 应：

```text
ml_usable = false
```

---

### 6.7 当前不做模型训练

Agent 此阶段不应主动开展：

```text
PCA training
MLP training
U-Net training
FNO training
scaling-law fitting
```

只需保证最终 canonical dataset 已准备好，可以直接进入三套模型各自的 preprocessing。

---

# 7. 推荐项目目录

Ubuntu 上建议建立：

```text
compressor_ai4s/
│
├── README.md
│
├── AGENT_INSTRUCTION.md
│
├── .git/
│
├── .gitignore
│
├── legacy/
│   ├── blade_batch_generation.py
│   ├── blade_batch_generation_template.geomTurbo
│   └── lhs_samples_train.csv
│
├── code/
│   ├── 01_generate_design.py
│   ├── 02_generate_geometry.py
│   ├── 03_geometry_qc.py
│   ├── 04_generate_cfx_pre.py
│   ├── 05_update_solver_status.py
│   ├── 06_collect_post.py
│   └── 07_dataset_qc.py
│
├── config/
│   ├── ranges_legacy.yaml
│   ├── ranges_core.yaml
│   ├── ranges_expanded_v1.yaml
│   └── project.yaml
│
├── design/
│   ├── master_design.csv
│   └── subsets/
│
├── geometry/
│   ├── profiles/
│   ├── geomturbo/
│   ├── qc_figures/
│   └── geometry_qc.csv
│
├── mesh/
│   ├── cases/
│   └── mesh_qc.csv
│
├── cfx/
│   ├── templates/
│   ├── pre/
│   ├── def/
│   ├── res/
│   └── solver_status.csv
│
├── post/
│   ├── templates/
│   └── raw/
│
├── dataset/
│   └── canonical_v1/
│       ├── samples.h5
│       ├── manifest.csv
│       ├── metadata.yaml
│       ├── rejected_cases.csv
│       └── qc_report.csv
│
└── logs/
```

---

# 8. 本地软件环境

Ubuntu 建议：

```bash
mkdir -p ~/compressor_ai4s
cd ~/compressor_ai4s

python3 -m venv .venv
source .venv/bin/activate

pip install \
    numpy \
    scipy \
    pandas \
    matplotlib \
    h5py \
    pyyaml \
    tqdm \
    scikit-learn
```

建议使用 Git：

```bash
git init
```

大型 CFD 数据不要提交 Git。

`.gitignore` 至少排除：

```text
*.res
*.def
*.cgns
*.igg
*.h5
mesh/cases/
cfx/res/
```

---

# 9. 第一步：冻结 legacy 设计空间

创建：

```text
config/ranges_legacy.yaml
```

内容：

```yaml
dataset_version: legacy

sampling:
  method: lhs
  seed: 1

ranges:
  Xthick: [0.15, 0.45]
  Tmax: [0.04, 0.07]
  Metal2: [6.0, 24.0]
  Solidity: [1.0, 2.0]
  Incidence: [-4.0, 4.0]
  Mach: [0.3, 0.7]
```

不要修改这个文件。

以后新增：

```text
ranges_core.yaml
ranges_expanded_v1.yaml
ranges_expanded_v2.yaml
```

---

# 10. 第二步：建立 Golden Case

回学校后必须从旧 1891 个样本中找一个完整成功样本。

理想的 Golden Case 应包括：

```text
输入六参数
.geomTurbo
NUMECA 网格
CFX setup / .cfx
CFX .def
CFX .res
最终七子域数据
```

定义：

```text
GOLDEN_CASE
```

Golden Case 的用途：

```text
测试新几何生成器
测试 NUMECA 批量流程
测试 CFX-Pre
测试 CFX Solver
测试 CFD-Post
测试七子域导出
测试最终 canonical dataset
```

要求：

```text
相同参数
→ 几何一致
→ 网格类型一致
→ BC 一致
→ CFD 结果相近
→ 七子域结构一致
```

在 Golden Case 成功复现之前：

> 禁止大规模生产新数据。

---

# 11. 第三步：重构参数采样

将旧脚本拆分。

第一个程序：

```text
code/01_generate_design.py
```

只负责：

```text
读取 ranges YAML
→ 生成采样
→ 分配 case_id
→ 写 master_design.csv
```

输出格式：

```csv
case_id,Xthick,Tmax,Metal2,Solidity,Incidence,Mach,range_id,sampling_id
C000001,...
C000002,...
```

case ID 必须固定、唯一、不可重用：

```text
C000001
C000002
...
```

后续所有文件都以该 ID 为主键。

---

# 12. Scaling-law 项目的采样要求

不能以后分别做：

```text
500 个独立 LHS
1000 个独立 LHS
2000 个独立 LHS
```

因为：

$$
D_{500}\not\subset D_{1000}
$$

会使 scaling curve 难以解释。

推荐：

```text
一次生成 master pool
然后从中构造 nested subsets
```

例如：

$$
D_{256}
\subset
D_{512}
\subset
D_{1024}
\subset
D_{2048}
\subset
D_{4096}
\subset
D_{8192}
$$

> 上例只是 2^k 示意。正式 `FINAL_N_LADDER` 已于 2026-10-13 冻结为
> `[1000, 2000, 5000, 10000, 20000, 35000, 50000, 70000, 100000]`
> （含非 2^k 档位；仍使用同一 master sequence 的前 N 个点并保持 nested）。
> 见 `docs/DESIGN_FREEZE_2026-10-13.md`。

如果导师要求继续使用 LHS：

```text
生成一个最大的 LHS
再从 master pool 中进行 deterministic nested subset selection
```

另一种可研究的方案：

```text
scrambled Sobol
```

因为它天然适合：

```text
2^8  = 256
2^9  = 512
2^10 = 1024
...
```

但是：

> 改变 DOE 方法属于实验设计变化，必须先与导师确认。

---

# 13. Core Space 与 Expanded Space 必须区分

现有范围定义为：

$$
\Omega_{core}
$$

将来扩大范围时定义：

$$
\Omega_{expanded}
$$

不要混为一个数据集概念。

纯数据 scaling 应保持：

$$
\Omega=\text{constant}
$$

只改变：

$$
N
$$

否则：

```text
数据更多
```

和：

```text
任务范围更难
```

会混在一起。

master_design.csv 中必须有：

```text
range_id
```

例如：

```text
core
expanded_v1
expanded_v2
```

---

# 14. 第四步：几何生成器

程序：

```text
code/02_generate_geometry.py
```

输入：

```text
master_design.csv
.geomTurbo template
```

输出：

```text
geometry/profiles/C000001.dat
geometry/geomturbo/C000001.geomTurbo
```

必须复用旧程序的核心叶型算法。

当前已知固定设置包括：

```text
Npoint
Ncirc
Metal1
Xmean
K_m
Ks1
Ks2
T1
T2
SS1
SS2
Nscale1
Nscale2
```

除非导师明确要求，否则不要修改。

当前程序会把叶型缩放到约：

$$
c = 0.06\,\mathrm{m}
$$

并使用：

$$
periodicity=\frac{0.06}{Solidity}
$$

还使用约：

$$
h = 0.003\,\mathrm{m}
$$

这些应保持与 legacy 一致。

---

# 15. `.geomTurbo` 模板版本控制

当前程序大量依赖模板固定行号。

因此必须：

```text
冻结模板版本
```

例如：

```text
GT_V1
```

建议计算：

```bash
sha256sum blade_batch_generation_template.geomTurbo
```

将 hash 写入 metadata。

以后模板变化：

```text
GT_V2
```

不能覆盖 V1。

Agent 可以建议后续把固定行号拼接方式升级为占位符模板，例如：

```text
{{INLET_Z}}
{{OUTLET_Z}}
{{PERIODICITY}}
{{SUCTION_SURFACE}}
{{PRESSURE_SURFACE}}
```

但在没有 Golden Case regression test 之前：

> 不允许直接重写模板逻辑并用于生产。

---

# 16. 第五步：Geometry QC

程序：

```text
code/03_geometry_qc.py
```

这是本地必须完成的。

至少检查：

```text
NaN / inf
叶型自交
厚度是否为正
弦长
前缘异常
尾缘异常
periodicity > 0
相邻叶片通道宽度
最小 gap
曲率异常
.geomTurbo 文件是否完整
```

输出：

```text
geometry/geometry_qc.csv
```

示例：

```csv
case_id,geometry_ok,chord,min_gap,self_intersection,reason
C000001,1,0.06001,0.0142,0,OK
C000002,0,0.05999,-0.0012,1,blade_overlap
```

失败 case 不删除。

---

# 17. 几何可视化

旧代码每 5 个 case：

```python
plt.show()
```

正式批量生成时必须禁止。

改为：

```text
每 100~500 个 case 保存一张 QC 图片
```

例如：

```text
geometry/qc_figures/
C000500.png
C001000.png
...
```

使用：

```python
plt.savefig(...)
plt.close()
```

同时必须额外检查：

```text
参数最小值 case
参数最大值 case
随机 case
Geometry QC 边界 case
```

---

# 18. 在校外阶段 Agent 应优先完成的内容

在无法连接校园网/HPC 的情况下，Agent 应将主要精力放在：

```text
项目目录
Git
环境配置
legacy 文件保护
ranges YAML
master_design 生成器
nested subset 逻辑
geometry generator
geometry QC
manifest 结构
模板版本管理
日志格式
未来 HPC 脚本模板
未来 CFX-Pre / CFD-Post 自动化框架
canonical HDF5 schema
dataset QC 框架
```

不要在校外假装运行：

```text
NUMECA
CFX
HPC
```

如果软件/许可证不可用，应明确标注：

```text
BLOCKED_BY_CAMPUS
```

---

# 19. 回学校后的第一个任务：确认 NUMECA 环境

需要确认实际软件：

```text
NUMECA AutoGrid5 / IGG
```

但版本必须实测。

在 HPC/学校终端：

```bash
which igg
igg -help
```

记录：

```text
软件版本
路径
module 名
license
支持的 batch 命令
```

Agent 只能根据真实输出继续生成最终命令。

---

# 20. 获取旧 `.trb` 网格模板

优先向师兄获取：

```text
旧 1891 数据使用的 .trb template
```

它可能隐含：

```text
拓扑
O-grid
网格点数
边界层
前缘/尾缘处理
hub/shroud
周期边界
```

目标是：

> 新数据与旧数据保持尽量一致的 mesh topology 和网格质量。

不要自己从零设计新网格模板，除非导师明确要求。

---

# 21. NUMECA GUI 手工验证

先做 1 个 Golden Case。

在 GUI 中：

```text
加载 .geomTurbo
加载/复用旧 .trb
生成网格
检查网格
```

必须检查：

```text
叶片方向
吸力面 / 压力面
periodic boundary
inlet
outlet
O-grid
网格块
collapsed cells
```

只有 GUI 手工成功后才做 batch。

---

# 22. NUMECA Stress Test

不要直接跑全量。

先选：

```text
中心 case
各参数 min case
各参数 max case
联合极端 case
随机 case
```

总数建议：

```text
20~50
```

目的：

```text
测试 geometry → mesh 鲁棒性
估计失败率
估计平均网格时间
观察极端几何
```

输出：

```text
mesh_qc.csv
```

---

# 23. NUMECA Batch

每个 case 至少保留：

```text
mesh/cases/C000001/
├── mesh file
├── quality report
└── autogrid.log
```

实际 mesh 格式必须复用旧项目。

如果旧项目使用：

```text
CGNS
```

则继续使用 CGNS。

不要为了“统一”擅自改网格格式。

---

# 24. Mesh QC

至少记录：

```text
mesh_ok
n_cells
mesh_runtime
quality_summary
failure_reason
```

不要凭空设定某个通用质量阈值。

优先将：

```text
新网格质量分布
```

与：

```text
旧 1891 个成功网格
```

进行比较。

---

# 25. CFX 前置条件

在进入 CFX 前，必须从旧项目获取至少一个：

```text
.cfx
或
.def
```

最好两者都有。

Agent 必须从旧设置读取：

```text
Material
Domain
Boundary Conditions
Interfaces
Initialisation
Solver Control
Output Control
```

并将其作为 baseline。

---

# 26. CFX Golden Case

在 Windows / 学校工作站 CFX-Pre 中：

```text
导入新 mesh
严格复制旧 CFX 物理设置
替换正确的 Incidence / Mach
写出 .def
```

必须确认：

```text
Incidence 如何进入 inlet BC
Mach 如何进入 inlet BC
```

禁止凭经验猜。

---

# 27. CFX-Pre Session Recording

建议在 CFX-Pre GUI 中录制 session：

```text
Session
→ New Session
→ Start Recording
```

然后完整完成：

```text
Import mesh
建立 domain
设置 inlet
设置 outlet
设置 wall
设置 periodic/interface
设置 Incidence
设置 Mach
Solver Control
Write Solver Input File
```

保存：

```text
build_case.pre
```

以后用于 batch。

---

# 28. 参数化 `.pre` 模板

建议模板中使用：

```text
__CASE_ID__
__MACH__
__INCIDENCE__
__MESH_PATH__
__DEF_PATH__
```

Ubuntu Agent 可以写 Python：

```text
读取 master_design.csv
→ 为每个 case 生成 .pre
```

但是：

> 在没有成功验证 Golden Case 前，不允许批量生成生产级 `.def`。

---

# 29. CFX Solver 小规模验证

运行顺序：

```text
1 case
→ 5 case
→ 50 case
→ 500 case
→ full production
```

不要跳级。

HPC 上实际命令必须基于：

```bash
cfx5solve -help
```

以及学校管理员推荐方式。

Agent 不允许自己猜：

```text
MPI
每 case core 数
partition
memory
并发数量
```

---

# 30. HPC Job Array

如果学校是 Slurm，可以使用 job array 思路。

但具体脚本必须在确认环境后再定。

逻辑：

```text
cases_to_run.csv
→ 每个 array task 读取一个 case_id
→ 找到相应 .def
→ 调用学校推荐 CFX launcher
```

并发限制必须基于：

```text
license
CPU
memory
queue policy
```

不能因为导师说有 H200 就直接开大量 CFD 并发。

---

# 31. Solver QC

`.res` 文件存在不代表成功。

每个 case 必须记录：

```text
solver_exit_code
iterations
residuals
mass_flow_in
mass_flow_out
mass_imbalance
monitor_history
res_exists
res_size
```

状态建议：

```text
SUCCESS
FAILED_PRE
FAILED_SOLVER
NON_CONVERGED
PHYSICALLY_INVALID
POST_FAILED
VALID
```

---

# 32. 数值与物理双重检查

数值检查：

```text
残差
monitor 收敛
solver 正常退出
```

物理检查：

```text
质量守恒
压力范围
温度范围
Mach 范围
无 NaN / inf
无异常爆炸值
整体流动方向合理
```

具体收敛阈值优先复用旧 1891 数据的标准。

---

# 33. CFD-Post Golden Case

CFX 求解后：

```text
C000001.res
```

打开 CFD-Post。

确认七个区域：

```text
domain1
domain3
main_blade_down
main_blade_inlet
main_blade_outlet
main_blade_skin
main_blade_up
```

必须进一步搞清楚这些对象到底是：

```text
domain
boundary
surface
mesh zone
user location
```

不能只根据名称猜。

---

# 34. 冻结输出 CFD 变量

新数据的输出字段必须优先与旧 1891 数据一致。

必须从旧 dataset/后处理脚本中确认：

```text
坐标
Pressure
Temperature
Density
Velocity
Mach
...
```

Agent 不应自行扩大字段列表。

如果需要增加新字段：

```text
生成新的 dataset_version
```

---

# 35. CFD-Post Session Recording

手工成功导出 Golden Case 后：

```text
Session
→ New Session
→ Start Recording
```

依次导出七个区域。

保存：

```text
export_7domains.cse
```

后续用于 batch。

---

# 36. Raw Post 目录格式

每一个成功 case：

```text
post/raw/C000001/
├── domain1.csv
├── domain3.csv
├── main_blade_down.csv
├── main_blade_inlet.csv
├── main_blade_outlet.csv
├── main_blade_skin.csv
└── main_blade_up.csv
```

所有 case 必须保持一致：

```text
文件名
字段名
字段顺序
单位
坐标系
```

---

# 37. 必须检查 mesh point ordering

需要确认：

```text
不同 case 同一个 domain
```

是否满足：

```text
点数一致
topology 一致
point ordering 一致
```

如果 point order 不一致：

> 不能直接 stack 成 tensor。

这件事对：

```text
PCA
U-Net
FNO
```

都非常重要。

---

# 38. 不要过早插值到规则网格

Raw/canonical 阶段保留：

```text
真实 coordinates
真实 CFD fields
真实 topology
zone structure
```

之后：

```text
PCA+MLP
U-Net
FNO
```

再分别做适合自己的 interpolation / flatten / grid mapping。

---

# 39. Canonical Dataset

最终建议使用：

```text
HDF5
```

目录：

```text
dataset/canonical_v1/
├── samples.h5
├── manifest.csv
├── metadata.yaml
├── rejected_cases.csv
└── qc_report.csv
```

HDF5 概念结构：

```text
/C000001
    /input
        parameters
    /domain1
        coords
        fields
    /domain3
        coords
        fields
    /main_blade_down
        coords
        fields
    /main_blade_inlet
        coords
        fields
    /main_blade_outlet
        coords
        fields
    /main_blade_skin
        coords
        fields
    /main_blade_up
        coords
        fields
```

如果 domain 是结构化网格，优先保留：

```text
[Ni, Nj, Channels]
```

不要无必要 flatten。

---

# 40. metadata.yaml

必须至少记录：

```yaml
dataset_version: canonical_v1

geometry:
  chord: 0.06
  span: 0.003
  template_version: GT_V1
  template_sha256: TBD

inputs:
  - Xthick
  - Tmax
  - Metal2
  - Solidity
  - Incidence
  - Mach

zones:
  - domain1
  - domain3
  - main_blade_down
  - main_blade_inlet
  - main_blade_outlet
  - main_blade_skin
  - main_blade_up

fields:
  - TBD

units:
  coordinates: m
  other_fields: TBD

software:
  geometry_generator_version: TBD
  numeca_version: TBD
  ansys_cfx_version: TBD

sampling:
  method: TBD
  seed: TBD
```

---

# 41. Manifest

项目必须维护一个总表。

建议字段：

```text
case_id
Xthick
Tmax
Metal2
Solidity
Incidence
Mach
range_id
sampling_id
geometry_ok
mesh_ok
pre_ok
solver_ok
converged
physics_ok
post_ok
dataset_ok
ml_usable
failure_stage
failure_reason
```

这是整个项目的核心索引。

---

# 42. Dataset QC

程序：

```text
code/07_dataset_qc.py
```

至少检查：

```text
case_id 唯一
参数 finite
七个 domain 全存在
domain 点数合理
字段数量一致
坐标 finite
field finite
单位一致
zone 名一致
field 名一致
无全零 field
无异常巨大值
HDF5 group 完整
```

同时随机抽：

```text
20~50 个 case
```

画：

```text
Mach contour
Pressure contour
Velocity magnitude
```

进行人工检查。

---

# 43. `ml_usable` 的定义

只有同时满足：

```text
Geometry QC PASS
Mesh QC PASS
Solver QC PASS
Physics QC PASS
Post QC PASS
Dataset QC PASS
```

才：

```text
ml_usable = true
```

任何缺失都：

```text
ml_usable = false
```

---

# 44. 数据准备完成的标准

只有当以下文件完整存在时，才算“数据准备结束”：

```text
dataset/canonical_v1/samples.h5
dataset/canonical_v1/manifest.csv
dataset/canonical_v1/metadata.yaml
dataset/canonical_v1/rejected_cases.csv
dataset/canonical_v1/qc_report.csv
```

并且：

```text
ml_usable case 数量已知
失败率已知
失败原因已统计
字段和单位已冻结
七子域一致性已验证
```

此后才能进入三种模型的预处理。

---

# 45. 模型预处理边界

数据准备阶段结束后：

```text
canonical_v1
```

才允许分叉：

## PCA + MLP

可能需要：

```text
固定 ordering
flatten
normalization
PCA
```

## U-Net

可能需要：

```text
规则二维 grid
mask
多 channel field
geometry mask
```

## FNO

可能需要：

```text
fixed grid
operator input channels
coordinate channels
```

但这些内容不属于当前 Agent 的第一阶段任务。

---

# 46. 当前 Agent 的近期执行优先级

在目前“校外、无法直接使用 HPC”的条件下：

## Priority 1

完成：

```text
项目目录
Git
venv
legacy 保护
```

## Priority 2

实现：

```text
ranges YAML
01_generate_design.py
```

## Priority 3

重构：

```text
02_generate_geometry.py
```

要求：

```text
输入 master_design.csv
输出稳定 case_id 文件
```

## Priority 4

实现：

```text
03_geometry_qc.py
```

## Priority 5

设计：

```text
manifest schema
metadata schema
canonical HDF5 schema
```

## Priority 6

只制作 HPC/CFX/NUMECA 的自动化模板框架。

不要执行真实 CFD。

---

# 47. 回学校后必须收集的信息

必须向师兄/管理员确认：

```text
1. 一个完整 Golden Case
2. NUMECA .trb template
3. 旧 .cfx
4. 旧 .def
5. 旧 .res
6. 旧 CFD-Post .cse/.cst 或后处理脚本
7. Incidence 定义
8. Mach 定义
9. NUMECA 版本
10. CFX 版本
11. HPC scheduler：Slurm / PBS
12. CPU 节点配置
13. H200 节点配置
14. NUMECA license
15. CFX license 并发
16. 推荐 CFX MPI
17. 推荐每 case CPU core
18. project storage quota
19. scratch quota
20. 旧 dataset 实际导出的 CFD fields
21. 旧 mesh point / topology 是否固定
22. 七个子域在 CFD-Post 中的真实对象类型
```

这些信息未获得之前：

> Agent 必须保留 `TBD`，不要自行补全。

---

# 48. 版本管理原则

任何会改变数据物理意义或数据格式的修改，都必须创建新版本。

例如：

```text
ranges_expanded_v2
GT_V2
CFX_SETUP_V2
POST_V2
canonical_v2
```

不能直接覆盖。

建议所有配置文件都包含：

```text
created_at
version
git_commit
```

---

# 49. 可复现性原则

每个 case 最终必须能够回答：

```text
它来自哪个参数表？
哪个采样 seed？
哪个范围版本？
哪个 geometry generator commit？
哪个 geomTurbo template？
哪个 mesh template？
哪个 NUMECA 版本？
哪个 CFX setup？
哪个 CFX 版本？
哪个后处理脚本？
为什么被判定 usable / unusable？
```

如果这些问题回答不了，说明 provenance 不完整。

---

# 50. Agent 的工作风格要求

Agent 在协助本项目时应：

1. 优先保证科学可复现性，而不是追求“脚本能跑就行”。
2. 对任何未知 CFD 物理设置明确标记 `TBD`。
3. 不得以通用经验覆盖旧项目已有定义。
4. 大规模运行前必须先做 Golden Case。
5. 大规模运行前必须先做小批 stress test。
6. 所有失败都进入 manifest。
7. 所有自动化脚本必须支持 dry-run。
8. 关键脚本建议支持：
   ```bash
   --config
   --input
   --output
   --dry-run
   --case-id
   --overwrite
   ```
9. 默认禁止 overwrite 已成功 case。
10. 所有 batch 工具必须支持断点续跑。
11. 尽量做到 idempotent：
   ```text
   重复运行不会破坏已有正确结果。
   ```

---

# 51. 建议的 pipeline state machine

每个 case 可以按状态推进：

```text
DESIGNED
↓
GEOMETRY_CREATED
↓
GEOMETRY_VALID
↓
MESH_CREATED
↓
MESH_VALID
↓
CFX_PREPARED
↓
SOLVED
↓
SOLVER_VALID
↓
POSTPROCESSED
↓
DATASET_VALID
↓
ML_USABLE
```

失败时：

```text
FAILED_GEOMETRY
FAILED_MESH
FAILED_PRE
FAILED_SOLVER
FAILED_PHYSICS
FAILED_POST
FAILED_DATASET
```

Agent 应根据 manifest 的当前状态决定下一步，而不是扫描文件名猜状态。

---

# 52. 强烈建议所有 pipeline 支持 dry-run

例如：

```bash
python code/02_generate_geometry.py \
    --input design/master_design.csv \
    --dry-run
```

只输出：

```text
将生成多少 case
输入文件
输出路径
预计覆盖文件
预计失败风险
```

真正执行需要去掉：

```text
--dry-run
```

HPC job 也应该先提供：

```text
submit_preview
```

而不是直接 `sbatch` 全量。

---

# 53. 大规模计算的阶段门控

必须按阶段：

```text
Stage A: 1 Golden Case
Stage B: 5 cases
Stage C: 20~50 stress cases
Stage D: 500 cases
Stage E: Full production
```

每一阶段都必须生成：

```text
success_count
failure_count
failure_rate
failure_reason_distribution
runtime statistics
```

只有上一阶段稳定，才进入下一阶段。

---

# 54. 关于参数范围扩大的要求

目前不要自行决定新的最终范围。

需要与导师讨论：

```text
Xthick
Tmax
Metal2
Solidity
Incidence
Mach
```

各自允许扩展多少。

Agent 可以帮助：

```text
分析旧 1891 参数分布
生成候选 expanded range
做几何可行性扫描
统计 Geometry QC 失败率
```

但最终正式范围需要人工确认。

---

# 55. 未来可以研究的网格/工况复用

因为：

```text
Geometry:
Xthick
Tmax
Metal2
Solidity
```

而：

```text
Operating Condition:
Incidence
Mach
```

理论上可以：

```text
1 个 geometry / mesh
→ 多个 Incidence / Mach 工况
```

例如：

```text
2500 geometry
×
4 operating points
=
10000 flow fields
```

可能显著减少网格生成成本。

但是：

> 这种采样设计会改变现有“六维 LHS 一个 case 一个 geometry”的统计结构。

因此只能作为后续实验设计选项，不能由 Agent 自动启用。

当前权威状态（2026-10-13 冻结）：

```text
GEOMETRY_REUSE   = DISABLED / NOT ACTIVE
PRODUCTION_ROUTE = ONE_6D_POINT_ONE_CASE
```

即当前 production 采样结构保持“一个六维参数点对应一个 CFD case”。

---

# 56. 本项目当前最重要的原则

## 原则 A

先建立稳定数据流水线，再扩大样本。

## 原则 B

先复现旧数据，再生产新数据。

## 原则 C

先 Golden Case，再 batch。

## 原则 D

先保存 canonical raw CFD，再做模型专属预处理。

## 原则 E

所有新数据必须可追溯、可恢复、可验证。

---

# 57. 当前 Agent 启动后的第一批建议任务

Agent 启动本项目后，可以按以下顺序主动推进：

```text
[1] 检查项目目录是否存在
[2] 初始化 Git
[3] 建立 Python venv
[4] 复制 legacy 文件到 legacy/
[5] 计算 legacy template SHA256
[6] 创建 ranges_legacy.yaml
[7] 读取并理解 legacy blade_batch_generation.py
[8] 建立 01_generate_design.py
[9] 建立 master_design.csv schema
[10] 建立 02_generate_geometry.py
[11] 用 legacy 参数生成 5~20 个 test case
[12] 与 legacy 输出做数值/几何回归测试
[13] 建立 03_geometry_qc.py
[14] 建立 manifest.csv
[15] 建立 metadata.yaml skeleton
[16] 建立 canonical HDF5 schema prototype
[17] 建立 HPC TODO checklist
```

如果在执行中发现：

```text
缺文件
定义不明确
物理设置未知
```

必须停止对应分支，并明确请求用户补充。

---

# 58. 当前阶段的完成目标

校外阶段完成后，应至少得到：

```text
一个干净的项目仓库
一个可重复的参数采样器
一个可重复的 geomTurbo generator
一个 geometry QC 系统
一个统一 case_id 系统
一个 manifest 管理系统
一个版本化配置系统
一个 canonical dataset schema
一个 HPC/CFX/NUMECA 待办清单
```

回学校以后只需把真实的：

```text
NUMECA
CFX
HPC
CFD-Post
```

环境接进已有 pipeline。

---

# 59. 绝对不要做的捷径

不要：

```text
直接把 n_samples 改成 10000 就开始跑
```

不要：

```text
没有 Golden Case 就大规模 mesh
```

不要：

```text
没有验证 CFX BC 就大规模 solver
```

不要：

```text
因为 .res 存在就认为收敛
```

不要：

```text
失败 case 直接删掉
```

不要：

```text
将缺失数据补零后送 AI
```

不要：

```text
把 CFD-Post CSV 直接当最终 dataset
```

不要：

```text
为了 U-Net 先把所有原始 CFD 数据插值并丢掉原网格
```

不要：

```text
把训练数据、验证数据、测试数据在 CFD 阶段硬编码
```

这些都应在 canonical dataset 完成后再定义。

---

# 60. 最终目标状态

当项目达到：

```text
dataset/canonical_v1/
├── samples.h5
├── manifest.csv
├── metadata.yaml
├── rejected_cases.csv
└── qc_report.csv
```

并确认：

```text
七个 domain 完整
CFD fields 完整
输入参数完整
mesh/topology 关系明确
QC 完整
provenance 完整
ml_usable 已标记
```

则：

> **数据准备阶段完成。**

之后可以进入：

```text
PCA + MLP preprocessing
U-Net preprocessing
FNO preprocessing
```

以及后续 scaling-law 实验。

---

# 61. 最后给 Agent 的一句话任务定义

> 你的工作不是“帮我随便生成很多 CFD 文件”，而是帮助我构建一个**可复现、可追踪、可批量扩展、支持失败恢复、最终能够为三种 AI 模型提供统一原始数据的压气机二维叶栅 CFD 数据生产系统**。  
> 对未知的 NUMECA/CFX/HPC 细节必须保留边界，不能自行猜测；对本地能够完成的采样、几何生成、QC、manifest、数据格式设计和自动化脚本，则应尽可能工程化、模块化和可验证。


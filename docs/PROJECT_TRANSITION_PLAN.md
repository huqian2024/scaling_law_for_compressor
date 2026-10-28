# 项目阶段规划（TRANSITION → GEOMTURBO PRODUCTION COMPLETED）

日期：2026-10-28（初版 2026-10-23）
当前阶段：**GEOMTURBO PRODUCTION COMPLETED → 几何 QC / 入口工况设计**
范围：**只做文档与状态同步**。本次未修改代码 / 配置 / 测试 / GeomTurbo 模板 / 历史数据，
未重新生成任何几何，未启动 CFD，未启动 GPU 训练。

> 本文件是当前阶段的**主要规划文件**。
> 阶段完成事实与检查结果见 `docs/GEOMTURBO_PRODUCTION_COMPLETION.md`。
>
> 本文件**不构成**新的 `FINAL` / `FROZEN` 决策，也**不构成** CFD 生产或训练的批准。
> 与旧文档冲突时：技术契约（几何算法、QC 契约、GeomTurbo 格式）仍以原冻结文件为准；
> **项目规划类约束**（生产 DOE 维度、样本数量、单一种子单序列路线）以本文件为准，
> 被替代的旧记录保留为 `HISTORICAL / SUPERSEDED`。

## 0. 状态语义与本文件效力

```text
VERIFIED            已经验证的事实（有代码 / 测试 / 实测依据）
CURRENT_BASELINE    当前实际采用的技术基线（可以继续使用）
PROPOSED            待验证的工作设想
PENDING             尚无决定（不由 Agent 决定）
HISTORICAL / SUPERSEDED
                    历史有效、但已不再约束当前工作（记录保留，不抹除）
NOT EXECUTED        尚未实际运行
USER-REPORTED       由用户/师兄口头提供、本仓库未复现的信息
```

```text
当前阶段状态（速览）
  GeomTurbo Production          COMPLETED（195,000 / 195,000）
  File-level Sanity Check       PASSED
  Geometry QC                   NOT YET PERFORMED
  CFD Operating Conditions      PENDING FINAL DESIGN
  CFD Dataset Construction      NOT STARTED

本文件的任务：
  1) 记录已完成 / 已决定 / 暂定 / 待讨论四类状态；
  2) 说明 195,000 是几何候选数，不是有效 CFD 数据数；
  3) 明确本地 / 师兄侧的 CFD 职责边界；
  4) 规划入口工况设计与后续训练路线（训练见配套文档）。

本文件不做的事：
  不冻结新的实验设计；不改任何数值范围；不改代码默认值；
  不批准任何 CFD 生产规模；不宣称任何结果已经被 CFD 验证。
```

## 1. 当前已验证事实（VERIFIED）

### 1.1 环境与本地流水线

```text
Conda 环境          ai4s（项目统一环境）
Python              3.10.20
numpy / scipy       2.2.6 / 1.15.3（已验证版本）
单元测试            173 passed, 17 subtests passed（2026-10-28 实测）
legacy 回归         26/26 exact
几何生成器契约      PASS（generator contract FROZEN V1.2）
Geometry QC 契约    PASS（QC contract FROZEN V1；frozen baseline 13/13 PASS）
```

```text
CURRENT_BASELINE（技术基线，本次未修改）:
  几何数学          code/geometry_parametric_exploratory_v1.py（复用，未改）
  序列化 / 模板     code/geometry_legacy_v1.py + legacy/blade_batch_generation_template.geomTurbo
  几何生成入口      code/run_geomturbo.py（按 group 启动，推荐）
                     code/generate_geomturbo_production.py（底层生成器，高级用法）
  运行配置          config/geometry_ranges_frozen_a.yaml（方案 A）
  几何 QC           geometry_qc_v1_hard（契约冻结，不改）
  SS1 / SS2         3.2 / 0.8（保持不变）
```

### 1.2 几何参数范围（数值保持不变）

11 维方案 A 的既有范围继续作为当前生成器基线，**本次文档调整不修改任何数值**：

| 参数 | 最小值 | 最大值 |
|---|---:|---:|
| `Xthick` | 0.10 | 0.60 |
| `Tmax` | 0.025 | 0.095 |
| `Metal2` | 6.0 | 32.0 |
| `Solidity` | 0.7 | 2.5 |
| `Metal1` | 48.0 | 58.0 |
| `T1` | 0.010 | 0.018 |
| `T2` | 0.008 | 0.016 |
| `Xmean` | 0.06 | 0.18 |
| `K_m` | 0.10 | 0.35 |
| `Ks1` | 3.0 | 7.0 |
| `Ks2` | 0.05 | 0.20 |

```text
固定参数 : SS1 = 3.2, SS2 = 0.8（FIXED_BY_REVIEW，不重新开放）
参数顺序 : Xthick, Tmax, Metal2, Solidity, Metal1, T1, T2, Xmean, K_m, Ks1, Ks2
Incidence / Mach : 不参与本次几何采样（CFD 工况由 CFD 侧决定）
```

### 1.3 已验证的其它事实

```text
C820 人工工程评审   85 ACCEPT / 15 REJECT / 0 UNREVIEWED（2026-10-21）
                    15 个 REJECT 全部 hard QC + frozen QC PASS
                    -> 自动 QC 尚不能替代工程评审
GeomTurbo 生产       COMPLETED 2026-10-28：195000 / 195000 个文件
                    Train 150000/101、Val 15000/202、Test 30000/303
                    39 batches、0 failed、0 missing、≈2.793 GB（磁盘 ≈3.2 GB）
文件级检查          PASSED（数量/大小/manifest/summary/参数/60 文件 SHA256）
几何 QC             NOT YET PERFORMED（文件级检查不能替代）
生成入口安全性      无 --execute 不写文件；--plan 只读；
                    --resume 校验 size + sha256 + 配置指纹
小规模 CFD 成功率   约 75%（USER-REPORTED，本仓库未复现、未统计）
```

```text
不得由这些事实推出的结论：
  “75% 会自动在大规模上成立”   -> 它只是当前可行性依据
  “文件级检查通过 = 几何可用”   -> 只验证了文件与元数据
  “几何 QC PASS 就是气动可用”  -> 四个概念严格分开：
     Geometry QC PASS != 气动合理 != 可网格化 != CFD 可收敛
  “195000 个候选 = 可用样本”   -> 有效数仍为 0，需 CFD 与筛选
```

## 2. 已过时的历史冻结及其新状态

2026-10-13 / 2026-10-21 的冻结记录**原样保留**（不删除、不改写当时的设计决定）。
下表只说明它们**现在是否仍然约束当前工作**。

| 旧记录 | 当时状态 | 新状态 | 是否仍约束当前工作 |
|---|---|---|---|
| 生产 DOE 维度 `d = 6`（`Xthick, Tmax, Metal2, Solidity, Incidence, Mach`） | FROZEN 2026-10-13 | `HISTORICAL / SUPERSEDED` | **否**（不作为当前几何生成路线） |
| `SOBOL_SEED = 1` 单一主序列 | FROZEN 2026-10-13 | `HISTORICAL / SUPERSEDED` | **否**（改为三组独立固定种子） |
| `PRODUCTION_ROUTE = ONE_6D_POINT_ONE_CASE` | FROZEN 2026-10-13 | `HISTORICAL / SUPERSEDED` | **否**（仍是一参数点一 case，但不再绑定 6D 名称） |
| `GEOMETRY_REUSE = DISABLED` | FROZEN 2026-10-13 | `HISTORICAL`（未重新启用） | 作为默认假设继续有效，直到另行决定 |
| `FINAL_N_TRAIN_MAX = 100000` / `FINAL_N_TEST = 20000` / 阶梯 | FROZEN 2026-10-13 | 参考值（`REFERENCE`） | **否**（新计划目标数值相同，但属 PROPOSED，不是冻结值） |
| 默认候选数 `200000` | 代码默认值（PROVISIONAL） | `HISTORICAL` 默认值 | **否**（当前计划 195000，见 §4） |
| `N = usable training case count` | FROZEN 2026-10-13 | **RETAINED（继续有效）** | **是** |
| `FINAL_PRODUCTION_RANGES` / `FINAL_VALIDATION_POLICY` / `FINAL_RAW_CFD_ATTEMPTS` / `FAILURE_RESERVE_POLICY` | PENDING | 仍为 `PENDING`，但**责任方改变**（CFD 侧） | 不再作为本地几何生成的阻塞条件 |
| 几何算法 / 历史回归测试 / GeomTurbo 格式 / 有效 QC 契约 | FROZEN | **不变** | **是（技术约束不解除）** |
| 方案 A 11D 几何范围数值 | FROZEN 2026-10-21（几何生成） | `CURRENT_BASELINE` | **是（数值不动）** |

```text
解除的是“已经失效的项目规划约束”，不是所有技术约束。
凡是几何算法、QC 契约、GeomTurbo 格式、历史回归与历史数据的冻结，一律继续有效。
```

各原文件开头的失效说明与其新状态链接：

```text
docs/DESIGN_FREEZE_2026-10-13.md         -> HISTORICAL / SUPERSEDED（规划约束）
docs/DOE_DECISION.md                     -> DOE 方法决策保留，6D 生产约束失效
docs/SCALING_EXPERIMENT_DESIGN.md        -> 统计原则保留，训练阶梯降为候选
docs/PARAMETER_SPACE_RECONCILIATION.md   -> 阶段对照保留，6D 生产 DOE 失效
docs/GEOMTURBO_PRODUCTION_200K.md        -> 生成器说明保留，200000 为历史默认值
```

## 3. 11D GeomTurbo 生成路线（CURRENT_BASELINE — 已执行完成）

```text
状态        COMPLETED 2026-10-28（195,000 / 195,000 个文件）
三组        Train 150,000（seed 101）/ Validation 15,000（seed 202）/ Test 30,000（seed 303）
批次        30 / 3 / 6 = 39（batch size 5000）
结果        0 failed / 0 missing；文件级 Sanity Check PASSED
数据位置    production_geomturbo/{train,val,test}/（本地，gitignored）
后续        geometry QC adapter -> 入口工况设计 -> CFD 数据集
```

### 3.1 程序与配置

```text
入口        code/generate_geomturbo_production.py
配置        config/geometry_ranges_frozen_a.yaml
采样        11 维 scrambled Sobol（scipy.stats.qmc.Sobol，scramble=True）
顺序        native Sobol 顺序；同一组内 D_N = 前 N 个点（prefix nesting）
固定参数    SS1 = 3.2 / SS2 = 0.8 注入
输出        <output-dir>/batch_XXXXXX/<case_id>.geomTurbo（原子写）
清单        <output-dir>/manifest.csv
            <output-dir>/generation_summary.json
            <output-dir>/config_snapshot.yaml（含配置/模板/生成器哈希与指纹）
case_id     G + 7 位数字（G0000001 …），与 C8xxxxx / C9xxxxx 号段不重叠
batch       默认每 5000 个 case 一个 batch 目录
```

复现 / 扩展命令（生产已于 2026-10-28 由用户执行完成；同 config/seed/N 可逐字节复现，N 可增大以延长前缀）：

```bash
# 只读预览
python code/run_geomturbo.py --group train --N 150000 --seed 101 --plan

# 实际生产参数（已完成；重跑前先确认目录与备份策略）
python code/run_geomturbo.py --group train --N 150000 --seed 101
python code/run_geomturbo.py --group val   --N 15000  --seed 202
python code/run_geomturbo.py --group test  --N 30000  --seed 303

# 中断后继续 / 扩大 N
python code/run_geomturbo.py --group train --N 150000 --seed 101 --resume
```

```text
默认目录：production_geomturbo/train|val|test/
每组独立：manifest.csv, batch_*/manifest.csv, config_snapshot.yaml,
          generation_summary.json, group_info.json
全局身份：group + seed + sobol_index（case_id 在组内重复，格式不变）
N        ：几何候选数，不是 CFD 成功数
```

```text
底层生成器 code/generate_geomturbo_production.py 仍可直接使用（高级用法），
必须显式 --execute；代码默认值未修改（count=200000、seed=1）。
三组生产全部通过命令行参数表达，实际使用 seed 101/202/303。
2026-10-28 本次文档同步没有执行任何生成。
```

### 3.2 已有清单字段与缺口

现有 `manifest.csv` 每行包含：

```text
case_id, sobol_index, batch, path, status, error, sha256, size_bytes,
Xthick, Tmax, Metal2, Solidity, Metal1, T1, T2, Xmean, K_m, Ks1, Ks2, SS1, SS2
```

已经可以追溯 **seed（在 config_snapshot.yaml）+ sobol_index + 参数向量**；
但是：

```text
manifest 不含数据组归属（train / validation / test）
manifest 不含几何 QC 状态
三组分别运行时，各自目录内都会出现 G0000001.. 的相同 case_id
```

```text
2026-10-23 工具更新（已实现）:
  code/run_geomturbo.py 按 --group 分目录启动，并写入 group_info.json
  （group / seed / N_candidates / global_identity），目录本身也携带组归属。
  manifest 的 group / QC 字段仍未加入（不改冻结 manifest schema）；
  跨组全局身份仍以 (group, seed, sobol_index) 表达。
  几何 QC 状态仍需后续数据管理层单独记录（PENDING）。
```

## 4. 三组独立 Sobol 候选数据集（GEOMETRY GENERATION COMPLETED）

### 4.1 规模与实际结果

| 数据集 | Sobol 候选数 | Seed | Batch | 目标有效 CFD 数（仍 PROPOSED） | 生成状态 |
|---|---:|---:|---:|---:|---|
| Train | 150,000 | 101 | 30 | 100,000 | COMPLETED |
| Validation | 15,000 | 202 | 3 | 10,000 | COMPLETED |
| Test | 30,000 | 303 | 6 | 20,000 | COMPLETED |
| **合计** | **195,000** | — | **39** | **130,000** | **COMPLETED** |

```text
已完成：195,000 个候选几何文件（0 failed / 0 missing，39 batches）
仍为 PROPOSED：目标“有效 CFD 数”100000 / 10000 / 20000 = 130000
最低总体有效率 = 130000 / 195000 = 66.67%
当前小规模 CFD 测试成功率 ≈ 75%（USER-REPORTED）
75% 时 195000 候选的期望有效数 ≈ 146250（相对 130000 有约 16250 的余量）
```

```text
这是“生产规模的可行性依据”，不是“大规模计算保证”：
  - 75% 来自小规模测试，未在多批次、长时间、真实队列条件下复现；
  - 失败率可能随参数区域、网格难度、求解器设置变化；
  - 有效数当前为 0（CFD 尚未开始），候选数不能当作可用样本数；
  - 每组仍保留“沿 Sobol 序列继续补充”的能力（N 可增大）。
```

### 4.2 执行记录（已完成）

```text
[1] 采用 11D scrambled Sobol（配置与参数范围不变）
[2] 分别运行三次生产生成程序（code/run_geomturbo.py -> 底层 --execute）
[3] 每次使用不同固定种子；三组输出目录相互独立
[4] 记录 seed / sobol_index / case_id / 参数向量 / 数据集归属（QC 状态尚未产生）
[5] 已完成：195000 个候选文件，0 failed / 0 missing
[6] 后续交由师兄进行 CFD（交错进行），达到目标有效量后停止该组新增提交
[7] 若某组有效样本不足，沿该组 Sobol 序列继续补充（前缀不变，只延长 N）
```

```text
实际目录与参数（已生成）:
  production_geomturbo/train/     count=150000, seed=101, 30 batches
  production_geomturbo/val/       count=15000,  seed=202,  3 batches
  production_geomturbo/test/      count=30000,  seed=303,  6 batches
完成时间（本地）：2026-10-28 14:02–14:10（Val -> Test -> Train）
```

```text
不同种子并不自动保证没有重复参数点或相同几何。
组内参数向量已确认无重复；跨组去重与容差仍未执行（PENDING）。
```

### 4.3 数据集身份与不可迁移原则（COMPLETED / PROPOSED 混合）

```text
[COMPLETED] Train / Validation / Test 三个独立数据集身份，样本不得跨组迁移。
[COMPLETED] 三组各自从自己的 Sobol 序列取前缀；组间不做前缀嵌套。
[COMPLETED] 嵌套只发生在组内；Test 从最开始就与 Train / Validation 分离。
[COMPLETED] 全局身份 = group + seed + sobol_index（group_info.json）。
```

```text
组内前缀与 CFD 失败的处理（PROPOSED，尚未定稿）:
  Sobol 顺序是确定的，但 CFD 是否成功不是。
  因此“前 N 个点”与“前 N 个有效点”不是同一件事。
  当前设想：D_N 按 sobol_index 升序取“前 N 个有效样本”，
  并在元数据中记录该规则与对应的 sobol_index 上界。
  这样可复现，但不等同于原始 prefix nesting 的严格定义，
  必须作为实验条件明确记录，不能混写。
```

### 4.4 入口工况（Incidence / Mach）—— 参考范围，尚未冻结

```text
当前决定（2026-10-28）：暂时沿用项目历史参考范围
  Incidence : −4° ～ +4°
  Mach      : 0.3 ～ 0.7

状态：PROVISIONAL / REFERENCE ONLY
  - 不是 CFD 生产范围，未冻结；
  - 只是下一阶段设计的起点；
  - 最终范围仍需人工确认。

以下全部 PENDING（待讨论）:
  1. Incidence / Mach 的最终范围
  2. 采样方法（是否独立 Sobol、分层或单点）
  3. 两个参数的组合方式
  4. 每个几何对应多少组入口工况（1 个还是多个，尚未决定）
  5. 是否采用独立的工况采样
  6. 入口参数如何转换为 NUMECA/CFX 边界条件（CFD 侧）
  7. 最终 CFD Case Manifest 设计

重要：
  “两个入口参数”（Incidence、Mach）!= “每个几何执行两个工况”。
  每个几何对应一个还是多个 CFD 工况，目前没有决定。
```

## 5. 几何 QC 与 CFD 交付边界（CURRENT_BASELINE + PENDING 接口）

### 5.1 本地职责（本仓库）

```text
1) 11D 参数采样及 GeomTurbo 文件生成
2) 几何 QC（geometry_qc_v1_hard）、明显不合理形状筛除
3) 文件组织、元数据与交付（manifest / 参数向量 / 哈希 / 数据集归属）
4) 接收有效 CFD 结果后的数据管理与版本化快照
5) 后续 AI 模型训练与 Scaling Law 研究
```

```text
几何阶段的效力边界（不变）:
  Geometry QC PASS != 气动合理 != 可网格化 != CFD 可收敛
  文件完整性 / Sanity Check PASS != 几何 QC
  不新增自动形状筛选；不实现复杂联合约束
  JC_XMEAN_KS1_KM 保持“历史候选 / 当前不激活”，不进入采样器
```

```text
已完成（2026-10-28）:
  195000 个 GeomTurbo 候选文件生成 + 文件级 Sanity Check（PASSED）

未完成（PENDING，下一步）:
  - 生产池（.geomTurbo + manifest）到冻结 QC 步骤的适配器
    （03_geometry_qc.py 目前期望 design CSV + profile/geomturbo 树）
  - 几何 QC 结果清单：group / seed / sobol_index / case_id / QC 状态 / 原因
  - 跨组去重结果
```

### 5.2 师兄侧职责（独立服务器）

```text
CFD 网格生成
CFD 边界条件、运行工况配置
CFD 服务器资源设置
求解运行、收敛及结果有效性检查
CFD 计算任务提交与调度
```

```text
本地不做、也不假装做的事:
  NUMECA / CFX 自动化
  CFD 服务器管理、队列管理、许可证管理
  猜测求解器配置、结果格式或具体物理边界条件
```

### 5.3 CFD 数据交接接口的需求（PROPOSED，格式 PENDING）

```text
交付方向 A（本地 -> CFD 侧）: 至少需要能被 CFD 侧唯一识别并回溯
  group(train/validation/test), seed, sobol_index, case_id, 参数向量(11+2 固定值),
  GeomTurbo 文件路径 / sha256, 生成状态, 几何 QC 状态

交付方向 B（CFD 侧 -> 本地）: 至少需要能判定“这个 case 是否可用”
  case 与 group 的唯一标识, CFD 状态(success/fail + reason),
  收敛 / 有效性检查结论, 结果文件路径与格式版本, CFD 运行条件标识,
  完成时间, 失败原因分类

PENDING : 两侧文件命名、结果容器格式（是否沿用历史 .res / 导出场数据）、
          状态码字典、失败原因字典尚未商定。
          信息不完整时不得由 Agent 编造求解器设置、结果格式或物理边界条件。
```

## 6. CFD 数据逐步返回后的训练路线（PROPOSED，摘要）

CFD 耗时长，**不必等全部 CFD 完成再开始训练**。详细可执行规划见
[`docs/TRAINING_TRANSITION_PLAN.md`](TRAINING_TRANSITION_PLAN.md)，本文件只保留主线：

```text
[1] 接收已经完成且通过有效性检查的 CFD 数据
[2] 构建带版本的数据快照（snapshot_vN）
[3] 可用训练样本达到适当规模时，启动阶段性训练
[4] 新样本返回后更新训练数据（新快照，不覆盖旧快照）
[5] 视情况选择 checkpoint 续训或从头训练（必须记录是哪一种）
[6] 记录每一阶段的训练条件与结果（N / P / 数据快照 / 早停规则 / GPU 时间）
[7] 最终基于统一协议整理 Scaling Law 实验
```

```text
训练规模梯度（候选，不强制冻结）:
  1k / 2k / 5k / 10k / 20k / 35k / 50k / 70k / 100k
  （沿用 2026-10-13 记录的数值作为候选，不再作为强制限制）

必须区分的两件事:
  “CFD 已完成的数据数量”        != “最终冻结的数据集组成”
  仅按 CFD 完成速度取样本会引入选择偏差（完成快的样本可能集中在易算区域），
  因此快照必须记录选取规则，而不是简单地“先到先用”。
```

## 7. GPU Slurm 的 Early Stopping 优化（PROPOSED，摘要）

```text
计算平台分工:
  CFD      : 师兄的独立服务器
  AI 训练  : 本人的 GPU HPC 平台（Slurm 调度）

限制:
  GPU HPC 存在任务额度 / 调度优先级限制，额度紧张时可能进入慢速队列。
  -> 训练流程必须优先减少无效 GPU 占用、重复训练与不必要的 Slurm 作业。

优化手段（详见 TRAINING_TRANSITION_PLAN.md §3）:
  定期评估验证集 loss
  保存验证性能最优 checkpoint
  可配置 patience / min_delta
  依据验证指标提前停止
  续训时恢复模型 + 优化器 + 学习率调度状态
  支持 Slurm 时间上限下的安全退出与恢复
  记录训练曲线 / 最优 epoch / 实际优化步数 / GPU 时间
```

```text
不猜测的内容（保持 PENDING）:
  GPU 型号、分区限制、账户额度、具体队列规则、单作业时间上限
```

## 8. 尚未决定的问题（PENDING）

```text
数据与生成（已完成的部分不再列为待决）
  1. 去重策略（完全相同参数向量 / 相同几何）与容差（跨组去重尚未做）
  2. 生产池 -> 冻结 QC 的适配器实现方式
  3. 几何 QC 判定口径、抽样比例与人工复核范围

入口工况（PENDING FINAL DESIGN）
  4. Incidence / Mach 最终范围（当前仅历史参考 −4…+4° / 0.3…0.7）
  5. 采样方法与两参数组合方式
  6. 每个几何对应多少组入口工况（1 个还是多个，未决定）
  7. 是否采用独立 Sobol 工况采样
  8. 入口参数 → NUMECA/CFX 边界条件的实现（CFD 侧）
  9. CFD Case Manifest 设计与交付格式

CFD 交接
 10. 结果容器格式 / 状态码 / 失败原因字典（与师兄共同确定）

训练与 Scaling Law
 11. 阶段性训练的启动阈值（可用样本达到多少时启动）
 12. 续训 vs 从头训练的对外口径（哪些结果可以进入同一张图）
 13. 训练阶梯最终取值（1k…100k 仅候选）
 14. 验证集最终规模与是否需要固定小规模子集起步（10000 为当前计划目标）
 15. 早停 patience / min_delta 的具体数值
 16. 模型规模 P 网格、重复次数、最终 E 的定义
 17. GPU 平台的实际额度、分区与队列规则

已解决（不再 PENDING）:
  三组种子 = 101 / 202 / 303
  三组候选数 = 150000 / 15000 / 30000（已生成 195000 个文件）
  全局身份 = group + seed + sobol_index
  目标有效 CFD 数 100000 / 10000 / 20000 —— 仍是 PROPOSED 目标，不是已完成事实

以上均不由 Agent 单方面决定。
```

## 9. 后续实施顺序（2026-10-28 更新）

```text
已完成:
  Step 1  三组种子与目录（150000/101、15000/202、30000/303）
  Step 2  真实导出验证（生产已全量执行，序列化结果已验证）
  Step 3  --plan / 指纹 / 存储核对
  Step 4  三组生产 + 文件级 Sanity Check（195000 files，PASSED）

下一步:
  Step 5  几何 QC 适配器 + 几何 QC 清单（group / seed / sobol_index / QC 状态）
  Step 6  入口工况设计（Incidence / Mach 范围、采样、组合、每几何工况数）
  Step 7  交付清单 -> 师兄 CFD；接收“有效 / 无效 + 原因”
  Step 8  数据快照 v1 + 阶段性训练（GPU HPC，Early Stopping）
  Step 9  结果汇总，再讨论正式 Scaling Law 实验协议
```

```text
说明:
  Step 6 的数值与组合策略必须由人决定；Agent 不代为冻结。
  “两个入口参数” != “每个几何两个工况”；每几何工况数仍未决定。
  Step 7 之后本地只做数据管理与训练，不实现 CFD。
  2026-10-28 本次文档同步没有执行生成 / QC / CFD / 训练。
```

## 10. 相关文档

```text
docs/GEOMTURBO_PRODUCTION_COMPLETION.md       阶段完成报告（195k / Sanity Check）
docs/TRAINING_TRANSITION_PLAN.md             训练平台 / 早停 / 测试集 / 防泄漏（配套规划）
docs/GEOMTURBO_PRODUCTION_200K.md            生成器使用说明（200000 为历史默认值）
docs/GEOMETRY_QC_CONTRACT.md                 几何 QC 契约（FROZEN，不变）
docs/GEOMETRY_GENERATOR_CONTRACT.md          几何生成器契约（FROZEN，不变）
docs/DESIGN_FREEZE_2026-10-13.md             历史冻结记录（HISTORICAL / SUPERSEDED）
docs/DOE_DECISION.md                         DOE 方法决策（6D 生产约束失效）
docs/SCALING_EXPERIMENT_DESIGN.md            统计设计原则（训练阶梯降为候选）
docs/PARAMETER_SPACE_RECONCILIATION.md       历史维度对照（6D 生产 DOE 失效）
config/geometry_ranges_frozen_a.yaml         当前几何生成基线（数值未改）
production_geomturbo/{train,val,test}/       195000 个已生成文件（本地，gitignored）
```

```text
最后强调：
  几何生产已 COMPLETED，文件级 Sanity Check 已 PASSED；
  几何 QC / NUMECA / 网格 / CFD / 训练仍未执行；
  入口工况仅沿用历史参考范围，未冻结；
  不创建新的 FINAL / FROZEN 决策。
```

# 项目过渡阶段规划（TRANSITION / PLANNING）

日期：2026-10-23
状态：**PROPOSED — 工作设想（未验证、未执行、未冻结）**
范围：**只做文档规划**。未修改代码 / 配置 / 测试 / GeomTurbo 模板 / 历史数据；
未生成任何 GeomTurbo 文件；未启动 CFD；未启动 GPU 训练。

> 本文件是进入 `TRANSITION / PLANNING` 阶段后的**主要规划文件**。
> 它记录“现在要做什么、哪些旧约束已经失效、哪些仍然有效、还有什么没定”。
>
> 本文件**不构成**新的 `FINAL` / `FROZEN` 决策，也**不构成**生产或训练的批准。
> 与旧文档冲突时：技术契约（几何算法、QC 契约、GeomTurbo 格式）仍以原冻结文件为准；
> **项目规划类约束**（生产 DOE 维度、样本数量、单一种子单序列路线）以本文件为准，
> 被替代的旧记录保留为 `HISTORICAL / SUPERSEDED`。

## 0. 状态语义与本文件效力

```text
VERIFIED            已经验证的事实（有代码 / 测试 / 实测依据）
CURRENT_BASELINE    当前实际采用的技术基线（可以继续使用）
PROPOSED            待验证的工作设想（本文件大部分内容）
PENDING             尚无决定（不由 Agent 决定）
HISTORICAL / SUPERSEDED
                    历史有效、但已不再约束当前工作（记录保留，不抹除）
NOT EXECUTED        尚未实际运行
USER-REPORTED       由用户/师兄口头提供、本仓库未复现的信息
```

```text
本文件的任务：
  1) 把已经失效的项目规划约束标清楚，避免旧 6D DOE 被再次当成当前命令；
  2) 记录当前 11D 几何生产方案（三组独立 Sobol）；
  3) 明确本地 / 师兄侧的 CFD 职责边界；
  4) 给出 CFD 数据逐步返回后的训练与 GPU Slurm（Early Stopping）优化路线（见配套文档）。

本文件不做的事：
  不冻结新的实验设计；不改任何数值范围；不改代码默认值；
  不批准任何生产规模；不宣称任何结果已经被验证。
```

## 1. 当前已验证事实（VERIFIED）

### 1.1 环境与本地流水线

```text
Conda 环境          ai4s（项目统一环境）
Python              3.10.20
numpy / scipy       2.2.6 / 1.15.3（已验证版本）
单元测试            155 passed, 17 subtests passed（2026-10-21 实测）
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
已生成 GeomTurbo    0（没有任何批量生成被实际执行）
生成入口安全性      无 --execute 不写文件；--plan 只读；
                    --resume 校验 size + sha256 + 配置指纹
小规模 CFD 成功率   约 75%（USER-REPORTED，本仓库未复现、未统计）
```

```text
不得由这些事实推出的结论：
  “75% 会自动在大规模上成立”   -> 它只是当前可行性依据
  “几何 QC PASS 就是气动可用”  -> 四个概念严格分开：
     Geometry QC PASS != 气动合理 != 可网格化 != CFD 可收敛
  “生成入口已准备好 = 已生成”  -> 代码准备完成 != 执行完成
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

## 3. 现有的 11D GeomTurbo 生成路线（CURRENT_BASELINE）

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

命令行（推荐入口 `code/run_geomturbo.py`；一条命令即一次明确授权）：

```bash
# 只读预览（不创建目录 / 文件）
python code/run_geomturbo.py --group train --N 150000 --seed 101 --plan

# 正式启动三组（每组独立目录；种子仅作示例，启动后必须记录）
python code/run_geomturbo.py --group train --N 150000 --seed 101
python code/run_geomturbo.py --group val   --N 15000  --seed 202
python code/run_geomturbo.py --group test  --N 30000  --seed 303

# 中断后继续（group / seed 不变；N 可增大以延长前缀）
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
必须显式 --execute；本次未修改代码默认值（count=200000、seed=1）。
三组计划全部通过命令行参数表达。
本轮文档/工具任务没有执行任何大规模生成。
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

## 4. 三组独立 Sobol 候选数据集（PROPOSED / NOT EXECUTED）

### 4.1 规模

| 数据集 | Sobol 候选数 | 目标有效 CFD 数 |
|---|---:|---:|
| Train | 150000 | 100000 |
| Validation | 15000 | 10000 |
| Test | 30000 | 20000 |
| 合计 | 195000 | 130000 |

```text
完成目标所需的最低总体有效率 = 130000 / 195000 = 66.67%
当前小规模 CFD 测试成功率 ≈ 75%（USER-REPORTED）
75% 时 195000 候选的期望有效数 ≈ 146250（相对 130000 有约 16250 的余量）
```

```text
这是“生产规模的可行性依据”，不是“大规模计算保证”：
  - 75% 来自小规模测试，未在多批次、长时间、真实队列条件下复现；
  - 失败率可能随参数区域、网格难度、求解器设置变化；
  - 因此每一组都必须保留“沿 Sobol 序列继续补充”的能力。
```

### 4.2 执行设想（三步，独立目录、独立种子）

```text
[1] 采用 11D scrambled Sobol（配置与参数范围不变）
[2] 分别运行三次现有生产生成程序（code/generate_geomturbo_production.py）
[3] 每次使用不同的固定种子；三组输出目录相互独立
[4] 记录 seed / sobol_index / case_id / 参数向量 / 数据集归属 / QC 状态
[5] 交给师兄后，三个数据集交错进行 CFD 计算
[6] 每组达到目标有效样本量后，停止该组新增 CFD 提交
[7] 若某组有效样本不足，沿该组对应的 Sobol 序列继续补充（前缀不变，只延长）
```

```text
建议的目录约定（PROPOSED，尚未创建任何目录）:
  production_geomturbo/train/          count=150000, seed=TRAIN_SEED
  production_geomturbo/val/           count=15000,  seed=VALIDATION_SEED
  production_geomturbo/test/           count=30000,  seed=TEST_SEED
```

```text
三个种子的具体数值：PENDING（本轮不强制确定，也不写死）
注意：不同种子并不自动保证没有重复参数点或相同几何。
      后续数据处理流程必须做去重与可追溯性检查，不能假设“换种子即正交”。
```

### 4.3 数据集身份与不可迁移原则（PROPOSED）

```text
Train / Validation / Test 是三个独立数据集身份，样本不得跨组迁移。
三组各自从自己的 Sobol 序列取前缀；组间不做前缀嵌套（组间彼此独立）。
嵌套只发生在组内：Train 的 D_N 阶梯使用 Train 组内同一序列的前缀。
Test 从最开始就与 Train / Validation 分离。
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
  不新增自动形状筛选；不实现复杂联合约束
  JC_XMEAN_KS1_KM 保持“历史候选 / 当前不激活”，不进入采样器
```

```text
已知待补的本地缺口（PENDING，本轮不实现）:
  - 生产池（.geomTurbo + manifest）到冻结 QC 步骤的适配器
    （03_geometry_qc.py 目前期望 design CSV + profile/geomturbo 树）
  - 数据组归属 / QC 状态 / 去重结果的独立清单
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
数据与生成
  1. 三个种子的具体数值
  2. 三组全局样本身份 —— 已解决：复合键 (group, seed, sobol_index) +
     group_info.json（2026-10-23 工具更新）；去重策略仍 PENDING
  3. 去重策略（完全相同参数向量 / 相同几何）与容差
  4. 生产池 -> 冻结 QC 的适配器实现方式
  5. 195000 / 130000 这组数字是否最终采纳（当前只是 PROPOSED 计划）

CFD 交接
  6. 交付文件命名与结果容器格式
  7. CFD 状态码 / 失败原因字典
  8. CFD 侧运行工况取值（Incidence / Mach 的具体配置）

训练与 Scaling Law
  9. 阶段性训练的启动阈值（可用样本达到多少时启动）
 10. 续训 vs 从头训练的对外口径（哪些结果可以进入同一张图）
 11. 训练阶梯最终取值（1k…100k 仅候选）
 12. 验证集最终规模与是否需要固定小规模子集起步（10000 为当前计划目标）
 13. 早停 patience / min_delta 的具体数值
 14. 模型规模 P 网格、重复次数、最终 E 的定义
 15. GPU 平台的实际额度、分区与队列规则

以上均不由 Agent 单方面决定。
```

## 9. 后续实施顺序（建议，PROPOSED）

```text
Step 0  本文档与训练规划文档评审（人工确认哪些 PROPOSED 项可以进入执行）
Step 1  确定三个种子 + 去重方案（身份已用 group + seed + sobol_index 表达；不改几何算法）
Step 2  小规模真实导出验证（run_geomturbo.py --group ... --N 10 --plan，再在临时目录执行）
Step 3  按组执行 --plan，核对数量 / 指纹 / 存储估算（约 2.9 GB @195000 × 15 kB）
Step 4  用户在 tmux 中按组启动 run_geomturbo.py（自动 --execute；可 --resume），
        核对 manifest / sha256 / 文件数
Step 5  几何 QC 适配器 + 交付清单（含组归属、QC 状态、去重结果）
Step 6  交付 GeomTurbo 给师兄，CFD 交错进行；接收有效结果
Step 7  数据快照 v1 + 阶段性训练（GPU HPC，带 Early Stopping）
Step 8  结果汇总，再讨论正式 Scaling Law 实验协议
```

```text
2026-10-23 工具状态:
  code/run_geomturbo.py 已实现并通过测试（不改变几何数学 / 范围 / 序列化 / QC）。
  同一批次中途 Ctrl+C 时，已完成的 Case 现在会先写入 batch manifest，
  --resume 不再重复渲染这些 Case。
  仍未执行任何大规模生成；Step 4 必须由用户单独启动。
```

## 10. 相关文档

```text
docs/TRAINING_TRANSITION_PLAN.md             训练平台 / 早停 / 测试集 / 防泄漏（配套规划）
docs/GEOMTURBO_PRODUCTION_200K.md            生成器使用说明（200000 为历史默认值）
docs/GEOMETRY_QC_CONTRACT.md                 几何 QC 契约（FROZEN，不变）
docs/GEOMETRY_GENERATOR_CONTRACT.md          几何生成器契约（FROZEN，不变）
docs/DESIGN_FREEZE_2026-10-13.md             历史冻结记录（HISTORICAL / SUPERSEDED）
docs/DOE_DECISION.md                         DOE 方法决策（6D 生产约束失效）
docs/SCALING_EXPERIMENT_DESIGN.md            统计设计原则（训练阶梯降为候选）
docs/PARAMETER_SPACE_RECONCILIATION.md       历史维度对照（6D 生产 DOE 失效）
config/geometry_ranges_frozen_a.yaml         当前几何生成基线（数值未改）
```

```text
最后强调：
  本文件全部新方案为 PROPOSED；
  未生成 GeomTurbo、未运行 CFD、未训练模型；
  不创建新的 FINAL / FROZEN 决策。
```

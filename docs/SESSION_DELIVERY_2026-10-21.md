# AI4S Compressor CFD Project — Session Delivery
Date: 2026-10-21

> **2026-10-23 说明**：本文件是 2026-10-21 的 session 记录（历史）。
> 其中第 9 节“下一次会话从哪里继续”与第 10 节“仍需人工决策”里的
> 6D 生产 DOE / 200000 默认计数等表述已被
> [`docs/PROJECT_TRANSITION_PLAN.md`](PROJECT_TRANSITION_PLAN.md) 取代
> （`HISTORICAL / SUPERSEDED`）；当前计划为三组独立 11D Sobol（PROPOSED）。
> 原始记录保留不改写。

> Delivery record for the 2026-10-21 **documentation reconciliation + human review
> intake + next-stage strategy** session. It complements, and does not replace,
> `PROJECT_HANDOFF.md`.
>
> **No geometry algorithm, sampler, experiment data, CSV/NPZ/PNG, QC contract or CFD
> process was modified. No new experiment was executed.**

## 1. Executive Summary

```text
A. 权威实验记录重新核对（C820 / C830 / C840）          DONE
B. 历史 6D DOE vs 当前 13 维探索空间 对照              DONE
   -> docs/PARAMETER_SPACE_RECONCILIATION.md
C. 联合约束 JC_XMEAN_KS1_KM 状态核实                   DONE（当前不可触发，保持非激活）
D. C820 人工评审结果补录（85 ACCEPT / 15 REJECT）  DONE
   -> analysis/geometry_review/parameter_sensitivity_v1_100cases/
        human_review_2026-10-21.csv
        HUMAN_REVIEW_2026-10-21.md
E. 拒绝 Case 与参数边界分析（仅现有数据）              DONE
F. 下一阶段筛选策略（宽范围 + 简单约束 + 自动筛选 + 人工复核）  DONE
   -> docs/GEOMETRY_SCREENING_STRATEGY_2026-10-21.md
G. 剩余文档一致性项处理                               DONE（见第 6 节）
H. 宽松约束方案 A/B/C 分析（默认推荐 A）              DONE（仅建议，未改 YAML）
   -> docs/GEOMETRY_CONSTRAINT_ANALYSIS_2026-10-21.md
```

```text
FINAL_PRODUCTION_RANGES 仍为 PENDING。
C840 的 "FINAL" 仅指“当时的探索性几何裁决”，不等于 CFD 生产参数获批。
所有范围数值（final_geometry_parameters.yaml）在本轮分析中未修改；
同日后续已按方案 A 正式冻结（见第 7 节）。
```

## 2. 研究演进关系（核对结论）

```text
C820  100 case  C820001..C820100  全参数敏感性与边界扫描
       analysis/geometry_review/parameter_sensitivity_v1_100cases/
         -> 100/100 生成 + 硬性 QC + 冻结 QC PASS
         -> 自动筛选：FIX_CANDIDATE=SS1,SS2 / KEEP=10 / REVIEW=Ks2
         -> 当时 SS1=2.4-4.0、SS2=0.5-1.1 仍是变量

C830   57 case  C830001..C830057  Ks1/Ks2 专项复核
       analysis/geometry_review/ks1_ks2_review_v1/
         -> 57/57 PASS；SS1=3.2 / SS2=0.8 已在每个 Case 固定
         -> Ks1 / Ks2 当时判为 FURTHER_REVIEW

C840   40 new + 9 reused = 49 行  几何参数最终裁决 V1
       analysis/geometry_review/parameter_final_decision_v1/
         -> 49/49 PASS
         -> Ks1 KEEP 3.0-7.0；Ks2 KEEP 0.05-0.20；Xmean 0.06-0.18
         -> 几何 11 维 + 运行 2 维；SS1/SS2 固定
         -> 效力仅限“探索性几何 DOE”

当前   人工工程评审（2026-10-21，师兄，用户转述）
         -> 85 ACCEPT / 15 REJECT（100/100 已判定）
```

```text
与 C830/C840 的关系（核对结论）：
- 无数据冲突：C840 的 9 个复用 Case 与 15 个被拒向量无交集（逐向量比对）。
- 有判断口径冲突：C830 有 9 个 Case 位于 Xmean=0.06 / K_m=0.35 方向
  （C830021-025、C830050-053，几何 QC PASS，未人工评审）；
  C840 在该角点记录最大 RCR 0.2529，但按“历史已存在形态”保留 K_m 0.10-0.35；
  人工评审认为“高 K_m + 低 Xmean”方向不符合工程要求。
- 处理：历史裁决记录不改写；K_m 上界列为待人工决策的候选收紧项。
```

## 3. 人工评审补录

```text
文件      analysis/geometry_review/parameter_sensitivity_v1_100cases/human_review_2026-10-21.csv
行数      100（与 case_design.csv 的 100 个 case_id 一一对应，顺序一致）
REJECT    15（C820033-036, C820043, C820062, C820081-084, C820089-092, C820100）
ACCEPT    85（形状合理；不代表 CFD/网格/气动合格）
UNREVIEWED 0（100/100 已判定）
comment   REJECT 逐案原因待补充（不推测）；ACCEPT 未提供逐例说明
校验      100 行 / 100 唯一 ID / 15 REJECT 无遗漏无重复 / 85 ACCEPT
```

```text
几何 QC 字段（case_metrics.csv）与人工字段（human_review_*.csv）严格分离；
15 个被拒 Case 的 hard_qc_status 与 frozen_qc_status 全部为 PASS，
说明现有自动 QC 无法识别这类工程不合理。
```

## 4. DOE 维度一致性问题（已解释，未决策）

```text
阶段 A（2026-10-13 冻结）：d = 6
    [Xthick, Tmax, Metal2, Solidity, Incidence, Mach]
阶段 B（2026-10-17 探索）：11 几何参数 + 2 运行参数（SS1/SS2 固定）
```

```text
13 维 != 生产 DOE 已冻结为 13 维。
生产 DOE 维度是否变更、FINAL_PRODUCTION_RANGES 如何取，仍待 owner/导师决策。
2026-10-13 冻结记录保持原文，未覆盖。
"13" 的两种含义（生成器 13 个形状参数 vs 11+2 候选自由度）已分别说明。
Metal1（入口金属角）与 Incidence（入口气流角工况）已明确区分：
    Metal1 不是 DOE 变量（legacy 常量 53），Incidence 的 CFX 实现仍 TBD。
```

## 5. 联合约束与筛选策略

```text
JC_XMEAN_KS1_KM : K_m >= 0.15, 适用 0.18 < Xmean <= 0.20
当前 Xmean 上界 = 0.18  -> 适用区间为空 -> 无法触发
active_at_final_bound = false（保持）
记录为“历史候选 / 当前不激活”，不写入采样器，不写成生产硬约束

策略（写入 docs/GEOMETRY_SCREENING_STRATEGY_2026-10-21.md）：
    宽范围采样 + 少量简单硬约束 + 自动几何筛选 + 必要人工复核
    SS1/SS2 固定；11 个几何参数可变（范围待确认）
    只收紧证据明确的单参数边界；不优先复杂联合约束
    记录所有被拒样本与原因；验证自动 QC 与人工判断的一致性
    训练集嵌套 / 测试集固定独立
```

## 6. 剩余一致性项处理

```text
49 vs 50 行         : case_design.csv / case_metrics.csv 为 49 条数据记录 + 1 行表头
                      （文本 50 行）。FINAL_DECISION.md 文件表中的“50 行”是
                      含表头的写法，本轮不改生成报告，仅在交接文档备注。
provenance git_head : 保留运行时刻的 02e57d1，不改为最新提交；引用时注明“运行时刻”。
体积差异            : 100-case README 的 2.358 MB = provenance.output_size_mb（输出产物体积）；
                      当前目录 2.5 MB 含未跟踪 logs。两者口径不同，不强行统一。
C820/C830 logs      : 暂不纳入 Git；已核实 tools/ 只写日志、不读日志，无复现依赖，
                      不影响复现；风险仅为“日志不在版本库”。
历史测试数字        : 111/111（2026-10-15 当次）保留；当次 131 passed + 17 subtests
                      （2026-10-21）；同日追加生产入口测试后为 155 passed + 17 subtests
```

## 7. GeomTurbo 生产冻结与生成入口（同日追加）

```text
Geometry parameter ranges:
  FROZEN_FOR_GEOMTURBO_GENERATION
Batch generator implementation:
  PREPARED / NOT EXECUTED
Default sample count:
  200000  (PROVISIONAL / NOT FINAL)
Actual production count:
  PENDING USER DECISION
GeomTurbo files generated:
  0
CFD production:
  NOT STARTED
FINAL_PRODUCTION_RANGES:
  PENDING
```

```text
方案 A 正式冻结（2026-10-21）:
  config/geometry_ranges_frozen_a.yaml      status = FROZEN
  final_geometry_parameters.yaml            status = FROZEN_FOR_GEOMTURBO_GENERATION
  Metal2 6.0 - 32.0；其余 10 个几何参数不变；SS1=3.2 / SS2=0.8 固定
  K_m 保持 0.10-0.35（不做全局上限）
  无联合约束；无新增形状筛选
  冻结效力仅限 GeomTurbo 几何生成，不是 CFD 生产范围批准

新增生产入口:
  code/generate_geomturbo_production.py     PREPARED / NOT EXECUTED
  config/geometry_ranges_frozen_a.yaml
  tests/test_generate_geomturbo_production.py（24 个测试，全部 STUB，无真实 GeomTurbo）
  docs/GEOMTURBO_PRODUCTION_200K.md

默认: count=200000（仅默认值 / 暂定）, seed=1, d=11, batch_size=5000,
      output=production_geomturbo/
实际数量: PENDING USER DECISION（--count）
安全: 无 --execute 不写文件；--plan 只读；--resume 校验 size+sha256 与指纹

本次未执行:
  没有创建 production_geomturbo/
  没有生成任何实际 .geomTurbo
  没有运行 NUMECA / CFX / CFD
  全量测试 155 passed + 17 subtests
```

## 8. 今日没有开展的工作

```text
1. 没有运行真实 GeomTurbo 生成
2. 没有进行 10-case 真实试生成
3. 没有进行 200000-case 批量生成
4. 没有启动 NUMECA 或 CFX
5. 没有生成 CFD 训练数据集
6. 没有最终决定生产样本量
7. 没有修改此前冻结的历史 DOE 记录
8. 没有开展新的形状筛选算法研究

代码准备完成 != 执行完成。
155 passed + 17 subtests 全部使用 STUB 渲染器；
真实生成器导出结果尚未验证。
```

## 9. 下一次会话从哪里继续

```text
首要任务：
  确认最终生成规模及计算资源预算，然后决定何时进行少量真实 GeomTurbo
  验证和正式生成。

200000 只是代码默认值，不得当作已批准的生产规模；
不要直接把“生成 200000 个”列为下一步已获批操作。

建议顺序：
  1) 用户根据 CFD 时间、算力、磁盘空间、样本有效率、Scaling Law 需求
     确定目标数量 N（例如先用较小 N 试跑）
  2) python code/generate_geomturbo_production.py --plan --count N
  3) 在临时目录做少量真实导出验证（例如 --count 10），检查文件格式/大小
  4) 确认无误后再 --execute --count N（可 --resume）
  5) 生成后核对 manifest / sha256 / 文件数；再讨论 QC 适配器
```

## 10. 仍需人工决策

```text
1. 最终 GeomTurbo 生成数量 N 与计算/存储预算（200000 仅为默认值）
2. 生产 DOE 维度（6 -> ?）与 FINAL_PRODUCTION_RANGES
3. 15 个被拒 Case 的逐案原因（部位与判据）
4. K_m 上界是否收紧（当前保持 0.35）；Metal2 下界已冻结为 6.0
5. Solidity、Metal1 是否进入生产维度
6. Incidence / Mach 的 CFX 实现与 legacy 4 deg 注释差异
7. 若生产维度变更，PRODUCTION_ROUTE 名称中的 “6D” 需重新冻结
```

`Geometry QC PASS` ≠ 气动合理 ≠ 网格可生成 ≠ CFD 可收敛。

# 下一阶段几何参数筛选策略（2026-10-21）

> 状态：**策略说明（PROPOSED / NOT IMPLEMENTED）**。
> 本轮不实现采样器、不实现约束过滤器、不新增工程 QC 算法、不重跑任何实验。
> 所有范围数值保持现状（`final_geometry_parameters.yaml` 数值未修改）。
>
> **2026-10-21 后续（同日）**：方案 A 已正式冻结为 GeomTurbo 几何生成范围
> （`config/geometry_ranges_frozen_a.yaml`，Metal2 下界 0 → 6.0）。
> 本文档其余策略内容保持不变；冻结记录见 `docs/GEOMTURBO_PRODUCTION_200K.md`。

## 1. 总体策略

```text
宽范围采样  +  少量简单硬约束  +  自动几何筛选  +  必要人工复核
```

目标：在进入昂贵的 NUMECA 网格 / CFX 求解之前，用几何层面的廉价筛选把明显
不合理的叶型剔除，同时保留足够宽的参数空间，避免过早收缩导致物理多样性损失。

```text
几何阶段可证明：数学有效、自动诊断正常
几何阶段不能证明：气动合理、可网格化、CFD 收敛
-> 因此筛选只能是“分层过滤”，不是“合格认证”
```

## 2. 研究原则（本轮确认）

```text
1) SS1 = 3.2、SS2 = 0.8 保持固定（FIXED_BY_REVIEW），不重新开放。
2) 其余 11 个几何参数原则上保持可变，但范围仍需最终确认
   （当前 KEEP 范围是探索性候选，不是生产批准）。
3) 仅对“证据明确”的不合理单参数边界提出收紧建议；
   证据不足时保持范围不变并记录待确认。
4) 不优先建立复杂多参数联合限制；
   交互作用先记录为观察，不进入采样器。
5) 尽可能多生成候选几何，在网格与 CFD 之前完成几何筛选。
6) 记录所有被拒绝样本及拒绝原因（含参数向量），避免丢失采样过程信息；
   被拒样本不得删除，只能标记。
7) 后续必须验证自动 QC 能否识别人工认为不合理的几何；
   当前 15 个被人工拒绝的 Case 全部 hard QC PASS，说明现有判据不足。
8) 正式 Scaling Law 数据集仍需满足：训练集嵌套（D_N 前缀）、测试集固定且独立。
```

```text
不做的决策（留给 owner / 导师）：
  生产 DOE 维度、FINAL_PRODUCTION_RANGES、Solidity/Metal1 是否进入生产维度、
  K_m / Metal2 边界是否真正收紧。
```

## 3. 建议的执行链路（下一阶段）

```text
[1] 候选参数采样（宽范围；方法/维度待冻结，本仓库当前不实现）
        |
[2] 生成叶型（现有 13 参数生成器，legacy 数学不变）
        |
[3] 冻结几何 QC（geometry_qc_v1_hard，现有，不改）
        |  不通过 -> 记入 rejection ledger，保留参数向量
[4] 工程几何筛选（待新增判据，本轮不实现）
        |  可疑 -> 记入 rejection ledger（reason_code = ENGINEERING_*）
[5] 必要人工复核（对可疑样本 + 抽样）
        |  人工 REJECT -> 记入 rejection ledger（reason_code = HUMAN_REJECT）
[6] 通过几何筛选的样本进入 NUMECA / CFX（本轮不执行）
```

分层原则：

```text
Layer 0  硬性几何 QC        自动、可复现、已冻结（现有）
Layer 1  工程几何判据      待设计，必须用人工标签校准后才能用于淘汰
Layer 2  人工工程复核      证据来源；不得用 Layer 0 结果替代
```

```text
只有 Layer 0 可以在当前直接用于淘汰；
Layer 1 在完成校准前只能“标记 + 人工复核”，不得静默删除样本。
```

## 4. 单参数边界的收紧判据（证据门槛）

一条“收紧单参数边界”的建议必须同时满足：

```text
A. 同一背景：除目标参数外，其余参数完全相同（或逐位可比）
B. 连续水平：边界方向上有 >= 2 个连续水平被人工拒绝
C. 反向对照：至少 1 个更靠近内部的水平未被拒绝
D. 可追溯：给出 case_id 列表 + 图像来源（overview 编号）
E. 不越权：只作为建议，数值由 owner / 导师确认
```

当前满足 A–D 的候选（**建议，不是决策**）：

```text
K_m 上界（低 Xmean 背景）
    C820032 K_m=0.2012 未被拒
    C820033 0.225 / C820034 0.2667 / C820035 0.3083 / C820036 0.35 连续被拒
    -> 候选上界 ≈ 0.20；0.2012-0.225 之间未采样，真实阈值未知
    -> 仅对 Xmean≈0.08 成立；高 Xmean 存在反例（C820064 / C820086 未被拒）

Metal2 下界
    C820043 Metal2=0 被拒；C820044 21.33、C820045 32、基准 15 ACCEPT
    -> 下界应 > 0；具体数值无法确定（0-21.33 未采样）
```

不满足证据门槛（保持现状，仅记录）：

```text
Solidity 上界      : 被拒 2.005-2.392，未被拒也有 2.381 -> 不可分
SS2 低值边界       : 被拒 0.508-0.590，未被拒 0.590-1.074 -> 重叠
Xmean 上界         : 已有 0.18 的保守结论（C840），本轮无新证据
Ks1 / Ks2 / T1 / T2: 本批无被拒证据
```

```text
禁止事项：
- 不得因为 1 个 Case 被拒就大幅缩小范围
- 不得用 S3 定向样本估算生产合格率
- 不得把“未被拒绝”当作“已接受”
```

## 5. 拒绝记录规范（下一阶段必须实现，本轮不实现）

建议的最小字段（append-only，不覆盖、不删除）：

```text
case_id, design_point_id, param_vector(13), generation_status,
hard_qc_status, qc_reason, engineering_flags,
rejection_stage, reason_code, reason_detail, reviewer, review_date
```

```text
reason_code 建议：GEOMETRY_FAIL / QC_FAIL / ENGINEERING_FLAG /
                  HUMAN_REJECT / CFD_FAIL（后续阶段）
参数向量必须完整保存：否则无法做失败率统计，也无法复现采样分布。
```

## 6. 与 Scaling Law 数据需求的衔接

```text
N = usable training case count（只计可用样本）
不可用样本（几何失败 / QC 失败 / 人工拒绝 / CFD 失败）不计入 N
-> 拒绝率直接影响 FINAL_RAW_CFD_ATTEMPTS 的失败储备
-> 在真实失败率测出之前，失败储备保持 PENDING
训练集仍为 D_N 前缀嵌套；测试集固定且独立；两者不重叠
```

## 7. 本轮明确不做的事

```text
No new sampler / No constraint filter code
No change to final_geometry_parameters.yaml values
(at the time of this analysis; the later 2026-10-21 freeze changed only the
Metal2 lower bound to 6.0 and is recorded in docs/GEOMTURBO_PRODUCTION_200K.md)
No change to frozen QC contract or generator
No new geometry generation / No re-run of C820 / C830 / C840
No NUMECA / CFX / HPC
No new engineered QC algorithm
```

## 8. 相关文档

```text
analysis/geometry_review/parameter_sensitivity_v1_100cases/HUMAN_REVIEW_2026-10-21.md
analysis/geometry_review/parameter_sensitivity_v1_100cases/human_review_2026-10-21.csv
docs/PARAMETER_SPACE_RECONCILIATION.md
docs/GEOMETRY_CONSTRAINT_ANALYSIS_2026-10-21.md   （A/B/C 具体方案，默认推荐 A）
docs/DESIGN_FREEZE_2026-10-13.md
analysis/geometry_review/parameter_final_decision_v1/FINAL_DECISION.md
```


# 几何参数最终裁决 V1（Ks1 / Ks2 / Xmean）

> 状态：**EXPLORATORY / NOT APPROVED**。本轮只做几何生成、几何 QC 与几何替代性数值搜索；
> **没有** NUMECA、**没有** CFX、**没有** AI 训练、**没有** 修改正式 DOE 或正式生产范围。
> 判据：`final_decision_criteria_v1` / `1.0.0`（预登记，正式 Case 生成前冻结；SHA256 见 provenance.json）。
> Case 号段：`C840001..C840040`（新增 40 个）；复用历史 Case 9 个。
> 本报告的结论**不是 CFD 工程认证**，只决定下一阶段探索性几何 DOE 采用哪些参数与范围。

## 0. 执行摘要（最终决策表）

| 参数 | 最终决定 | 固定值或范围 | 核心证据 |
|---|---|---|---|
| `Ks1` | **KEEP** | 3.0 – 7.0 | K1_KEEP：0/7 背景可替代，7/7 背景拒绝；B0 残差 0.07–0.14；B1 残差 0.09–0.15；B2 残差 0.17–1.00 |
| `Ks2` | **KEEP** | 0.05 – 0.20 | K2_KEEP：0/4 背景可替代，4/4 背景拒绝；Metal1/Metal2 固定下 尾部曲率残差 0.87–0.89 |
| `Xmean` | **KEEP** | 0.06 – 0.18 | XMEAN_BOUND_V1：主规则（容差 1.01）给出 0.20，但结论对登记容差敏感（0.85→0.18，1.00→0.18），按预登记保守政策保持 0.18；0.22 在所有容差下均被拒绝；若扩展到 0.20 需联合限制 K_m >= 0.15 |
| `SS1` | **FIX** | 3.2 | 人工决定（FIXED_BY_REVIEW），本轮不重新开放 |
| `SS2` | **FIX** | 0.8 | 人工决定（FIXED_BY_REVIEW），本轮不重新开放 |

```text
最终几何维度      : 11
运行条件维度      : 2 (Incidence, Mach)
总候选维度        : 13
Xmean 探索区间    : 0.06 – 0.18
Ks1               : KEEP  (K1_KEEP)
Ks2               : KEEP  (K2_KEEP)
最终状态          : FINAL（仅限探索性几何 DOE），不存在 FURTHER_REVIEW / PENDING
```

## 1. 实验规模与历史资产复用

| 项目 | 数值 |
|---|---|
| 历史 Case（复用池） | 157（100 敏感性 + 57 Ks1/Ks2 复核） |
| 历史唯一参数向量 | 150 |
| 本轮计划行数 | 49 |
| 其中直接复用历史 Case | 9 |
| 新增正式 Case | 40（限制 ≤ 48） |
| 几何生成成功 | 49/49 |
| 实验硬性 QC 通过 | 49/49 |
| 冻结 QC 复核通过 | 49/49 |
| 内存替代搜索次数 | 60 |
| 软风险地图点数 | 2220（不落盘几何） |
| 硬性 QC 边界扫描点 | 144 |

复用规则：只有当计划参数向量与历史向量**完全一致**（13 参数、1e-9 容差）时才复用；
否则生成新的 `C84xxxx` Case。复用 Case 不重复写入 profiles，只在 NPZ 中记录 ID。

- **D1** Xmean 高端 × Ks1（基准折转）：15 行（新增 12，复用 3）
- **D2** K_m 角点（Xmean 0.18 / 0.22）：12 行（新增 6，复用 6）
- **D3** 大折转 / 小折转 Metal 背景：12 行（新增 12，复用 0）
- **D4** 上界规则角点探针：3 行（新增 3，复用 0）
- **D5** 高 Xmean 下的 Ks2：7 行（新增 7，复用 0）

## 2. 历史资产审计（157 Case 的软风险包络）

在生成任何新 Case 之前，用**同一解析公式**重新计算了 157 个历史 Case 的软风险指标，
用于判断“高端 Xmean 的几何是否为前所未有的新形态”。

| 指标 | 中位 | p90 | 最大 | 最大对应 Case |
|---|---|---|---|---|
| 反向曲率比 RCR | 0.0000 | 0.1166 | **0.2529** | `C830050` (Xmean=0.06, Ks1=3.0, K_m=0.35) |
| 切线角回摆（deg） | — | — | 51.96 | `C830050` (Xmean=0.06, Ks1=3.0, K_m=0.35) |

**关键事实**：反向曲率（中弧线局部斜率回摆）不是高端 Xmean 独有的失效，而是 legacy 分段中弧线
在低 Xmean + 高 K_m 角点就已存在的形态；历史 157 Case 中最大 RCR = 0.2529。
因此本轮**不能**把“出现反向曲率”直接判为几何无效——这正是任务要求的“不得误判既有曲率尖峰”。
同时这也意味着：RCR 只能作为**相对**软风险尺度，用“是否比已接受的形态更极端”来判断。

## 3. 实验一：Xmean 高端与 Ks1 独立性

### 3.1 设计

```text
Xmean  : 0.14 / 0.16 / 0.18 / 0.20 / 0.22
Ks1    : 3 / 5 / 7
K_m    : 0.10 / 0.18 / 0.35
折转背景: M0 (53/15), ML (48/0), MS (58/32)
固定    : Metal1/Metal2（逐背景）、Xthick=0.30、Tmax=0.055、T1=0.015、T2=0.0125、
          Ks2=0.10、SS1=3.2、SS2=0.8
```

### 3.2 替代搜索（Xmean + K_m 联合替代 Ks1）

目标：在保持 Ks1=5 的前提下，仅用 Xmean 与 K_m 复现 Ks1=3 或 Ks1=7 的 95 维响应；
Metal1、Metal2、Tmax、Xthick、T1、T2 全部固定。三个 Xmean 上界（0.18 / 0.20 / 0.22）各做一次，
以便区分“人为边界”与“真实独立作用”。

| 上界 | 背景 | 方向 | 向量残差比例 | 轮廓残差比例 | 最佳 Xmean | 最佳 K_m | 边界命中 | 判定 | 主要未通过项 |
|---|---|---|---|---|---|---|---|---|---|
| 0.18 | B0 | Ks1=3.00 | 0.141 | 0.180 | 0.060 | 0.158 | 是 | 替代失败 | contourrmsabs,anglermsdeg,anglemaxdeg |
| 0.20 | B0 | Ks1=3.00 | 0.141 | 0.180 | 0.060 | 0.158 | 是 | 替代失败 | contourrmsabs,anglermsdeg,anglemaxdeg |
| 0.22 | B0 | Ks1=3.00 | 0.141 | 0.180 | 0.060 | 0.158 | 是 | 替代失败 | contourrmsabs,anglermsdeg,anglemaxdeg |
| 0.18 | B0 | Ks1=7.00 | 0.072 | 0.154 | 0.104 | 0.190 | 否 | 替代失败 | contourrmsabs,rearmeanlinerms,offset:Xmean |
| 0.20 | B0 | Ks1=7.00 | 0.072 | 0.154 | 0.104 | 0.190 | 否 | 替代失败 | contourrmsabs,rearmeanlinerms,offset:Xmean |
| 0.22 | B0 | Ks1=7.00 | 0.072 | 0.154 | 0.104 | 0.190 | 否 | 替代失败 | contourrmsabs,rearmeanlinerms,offset:Xmean |
| 0.18 | B1 | Ks1=3.00 | 0.091 | 0.155 | 0.060 | 0.124 | 是 | 替代失败 | contourrmsabs,rearmeanlinerms,SUBSTITUTEONBOUND |
| 0.20 | B1 | Ks1=3.00 | 0.091 | 0.155 | 0.060 | 0.124 | 是 | 替代失败 | contourrmsabs,rearmeanlinerms,SUBSTITUTEONBOUND |
| 0.22 | B1 | Ks1=3.00 | 0.091 | 0.155 | 0.060 | 0.124 | 是 | 替代失败 | contourrmsabs,rearmeanlinerms,SUBSTITUTEONBOUND |
| 0.18 | B1 | Ks1=7.00 | 0.151 | 0.078 | 0.078 | 0.100 | 是 | 替代失败 | contourrmsabs,rearmeanlinerms,SUBSTITUTEONBOUND |
| 0.20 | B1 | Ks1=7.00 | 0.151 | 0.078 | 0.078 | 0.100 | 是 | 替代失败 | contourrmsabs,rearmeanlinerms,SUBSTITUTEONBOUND |
| 0.22 | B1 | Ks1=7.00 | 0.151 | 0.078 | 0.078 | 0.100 | 是 | 替代失败 | contourrmsabs,rearmeanlinerms,SUBSTITUTEONBOUND |
| 0.18 | B2 | Ks1=3.00 | 1.000 | 1.000 | 0.060 | 0.350 | 是 | 替代失败 | vectorresidualfraction,contourrmsfraction,contourrmsabs |
| 0.20 | B2 | Ks1=3.00 | 1.000 | 1.000 | 0.060 | 0.350 | 是 | 替代失败 | vectorresidualfraction,contourrmsfraction,contourrmsabs |
| 0.22 | B2 | Ks1=3.00 | 1.000 | 1.000 | 0.060 | 0.350 | 是 | 替代失败 | vectorresidualfraction,contourrmsfraction,contourrmsabs |
| 0.18 | B2 | Ks1=7.00 | 0.166 | 0.082 | 0.060 | 0.320 | 是 | 替代失败 | contourrmsabs,anglermsdeg,anglemaxdeg |
| 0.20 | B2 | Ks1=7.00 | 0.166 | 0.082 | 0.060 | 0.320 | 是 | 替代失败 | contourrmsabs,anglermsdeg,anglemaxdeg |
| 0.22 | B2 | Ks1=7.00 | 0.166 | 0.082 | 0.060 | 0.320 | 是 | 替代失败 | contourrmsabs,anglermsdeg,anglemaxdeg |
| 0.18 | B3 | Ks1=3.00 | 0.106 | 0.075 | 0.121 | 0.100 | 是 | 替代失败 | anglemaxdeg,SUBSTITUTEONBOUND,offset:Xmean |
| 0.20 | B3 | Ks1=3.00 | 0.106 | 0.075 | 0.121 | 0.100 | 是 | 替代失败 | anglemaxdeg,SUBSTITUTEONBOUND,offset:Xmean |
| 0.22 | B3 | Ks1=3.00 | 0.106 | 0.075 | 0.121 | 0.100 | 是 | 替代失败 | anglemaxdeg,SUBSTITUTEONBOUND,offset:Xmean |
| 0.18 | B3 | Ks1=7.00 | 1.000 | 1.000 | 0.180 | 0.100 | 是 | 替代失败 | vectorresidualfraction,contourrmsfraction,contourrmsabs |
| 0.20 | B3 | Ks1=7.00 | 0.764 | 0.819 | 0.200 | 0.100 | 是 | 替代失败 | vectorresidualfraction,contourrmsfraction,contourrmsabs |
| 0.22 | B3 | Ks1=7.00 | 0.607 | 0.701 | 0.220 | 0.100 | 是 | 替代失败 | vectorresidualfraction,contourrmsfraction,contourrmsabs |
| 0.18 | B4 | Ks1=3.00 | 0.135 | 0.343 | 0.060 | 0.138 | 是 | 替代失败 | contourrmsfraction,contourrmsabs,anglermsdeg |
| 0.20 | B4 | Ks1=3.00 | 0.135 | 0.343 | 0.060 | 0.138 | 是 | 替代失败 | contourrmsfraction,contourrmsabs,anglermsdeg |
| 0.22 | B4 | Ks1=3.00 | 0.135 | 0.343 | 0.060 | 0.138 | 是 | 替代失败 | contourrmsfraction,contourrmsabs,anglermsdeg |
| 0.18 | B4 | Ks1=7.00 | 0.538 | 0.736 | 0.180 | 0.284 | 是 | 替代失败 | vectorresidualfraction,contourrmsfraction,contourrmsabs |
| 0.20 | B4 | Ks1=7.00 | 0.455 | 0.668 | 0.200 | 0.311 | 是 | 替代失败 | vectorresidualfraction,contourrmsfraction,contourrmsabs |
| 0.22 | B4 | Ks1=7.00 | 0.402 | 0.598 | 0.220 | 0.337 | 是 | 替代失败 | vectorresidualfraction,contourrmsfraction,contourrmsabs |
| 0.18 | ML | Ks1=3.00 | 0.138 | 0.169 | 0.060 | 0.159 | 是 | 替代失败 | contourrmsabs,anglermsdeg,anglemaxdeg |
| 0.20 | ML | Ks1=3.00 | 0.138 | 0.169 | 0.060 | 0.159 | 是 | 替代失败 | contourrmsabs,anglermsdeg,anglemaxdeg |
| 0.22 | ML | Ks1=3.00 | 0.138 | 0.169 | 0.060 | 0.159 | 是 | 替代失败 | contourrmsabs,anglermsdeg,anglemaxdeg |
| 0.18 | ML | Ks1=7.00 | 0.076 | 0.155 | 0.102 | 0.186 | 否 | 替代失败 | contourrmsabs,anglemaxdeg,rearmeanlinerms |
| 0.20 | ML | Ks1=7.00 | 0.076 | 0.155 | 0.102 | 0.186 | 否 | 替代失败 | contourrmsabs,anglemaxdeg,rearmeanlinerms |
| 0.22 | ML | Ks1=7.00 | 0.076 | 0.155 | 0.102 | 0.186 | 否 | 替代失败 | contourrmsabs,anglemaxdeg,rearmeanlinerms |
| 0.18 | MS | Ks1=3.00 | 0.132 | 0.193 | 0.060 | 0.160 | 是 | 替代失败 | contourrmsabs,rearmeanlinerms,SUBSTITUTEONBOUND |
| 0.20 | MS | Ks1=3.00 | 0.132 | 0.193 | 0.060 | 0.160 | 是 | 替代失败 | contourrmsabs,rearmeanlinerms,SUBSTITUTEONBOUND |
| 0.22 | MS | Ks1=3.00 | 0.132 | 0.193 | 0.060 | 0.160 | 是 | 替代失败 | contourrmsabs,rearmeanlinerms,SUBSTITUTEONBOUND |
| 0.18 | MS | Ks1=7.00 | 0.077 | 0.168 | 0.101 | 0.185 | 否 | 替代失败 | contourrmsabs,rearmeanlinerms,offset:Xmean |
| 0.20 | MS | Ks1=7.00 | 0.077 | 0.168 | 0.101 | 0.185 | 否 | 替代失败 | contourrmsabs,rearmeanlinerms,offset:Xmean |
| 0.22 | MS | Ks1=7.00 | 0.077 | 0.168 | 0.101 | 0.185 | 否 | 替代失败 | contourrmsabs,rearmeanlinerms,offset:Xmean |

> `向量残差比例` = ‖v_sub − v_target‖ / ‖v_target − v_ref‖；0 表示完全复现，1 表示与目标变化正交。
> 接受条件为 `final_decision_criteria.yaml` 预登记的 11 项阈值 + 无参数贴边 + 无新异常。

**两种不同的失败模式必须区分**：

1. **中低 Xmean 背景（B0/B1/B2/ML/MS）**：除 `B2 / Ks1=3` 的 1.000 之外，向量残差比例只有 0.072–0.166，
   看起来“几乎可替代”；但绝对残差超限——`contour_rms_abs` 与 `rear_meanline_rms` 均大于 0.002（0.2% 弦长），
   实际尾部中弧线偏差达到 0.31–0.83% 弦长。也就是说：**比例上解释了大部分变化，
   但剩下的部分仍是一个肉眼与网格都能分辨的形状差异**。按预登记规则，这不算替代成功。
2. **高 Xmean 背景（B3/B4）的 Ks1=7 方向**：在最终上界下相对残差为 0.538–1.000；即使放宽到 0.22 也只降到 0.402–0.607，
   且最优解始终贴住 Xmean 上界（B3 还同时贴住 K_m 下界）。说明允许的二维子空间里
   **没有**指向目标的方向——这不是“参数偏移过大”的问题，而是真正的结构性独立。
3. `B2 / Ks1=3` 的残差为 1.000：在 Xmean=0.06、K_m=0.35 的角点，Ks1 的变化与 Xmean/K_m
   方向完全正交，是独立作用最强的证据。

因此 Ks1 的 KEEP 结论并不依赖 `substitute_offset_u_max` 这一条规则：即使完全去掉偏移规则，
除 `B3 / Ks1=3`（角残差 1.04° 仅略微超过 1.0°，但仍有参数贴边）之外，
其余所有背景都至少有一项非偏移类指标明确超限；高端背景则整体失效。
偏移规则只影响“拒绝理由的排序”，不改变结论方向。

### 3.3 边界诊断：高端失败是“边界人为”还是“真实独立”？

把 Xmean 上界从 0.18 放宽到 0.20 / 0.22 后，重新观察同一批高端背景的替代残差：

| 背景 | Ks1 变化 | 上界 0.18 | 上界 0.20 | 上界 0.22 | 结论 |
|---|---|---|---|---|---|
| B0 | Ks1=3.00 | 0.141 | 0.141 | 0.141 | 相对残差可接受，但绝对/局部指标未通过 |
| B0 | Ks1=7.00 | 0.072 | 0.072 | 0.072 | 相对残差可接受，但绝对/局部指标未通过 |
| B1 | Ks1=3.00 | 0.091 | 0.091 | 0.091 | 相对残差可接受，但绝对/局部指标未通过 |
| B1 | Ks1=7.00 | 0.151 | 0.151 | 0.151 | 相对残差可接受，但绝对/局部指标未通过 |
| B2 | Ks1=3.00 | 1.000 | 1.000 | 1.000 | 放宽无改善 → 真实独立作用 |
| B2 | Ks1=7.00 | 0.166 | 0.166 | 0.166 | 相对残差可接受，但绝对/局部指标未通过 |
| B3 | Ks1=3.00 | 0.106 | 0.106 | 0.106 | 相对残差可接受，但绝对/局部指标未通过 |
| B3 | Ks1=7.00 | 1.000 | 0.764 | 0.607 | 放宽后有改善但仍不可替代 |
| B4 | Ks1=3.00 | 0.135 | 0.135 | 0.135 | 相对残差可接受，但绝对/局部指标未通过 |
| B4 | Ks1=7.00 | 0.538 | 0.455 | 0.402 | 放宽后有改善但仍不可替代 |
| ML | Ks1=3.00 | 0.138 | 0.138 | 0.138 | 相对残差可接受，但绝对/局部指标未通过 |
| ML | Ks1=7.00 | 0.076 | 0.076 | 0.076 | 相对残差可接受，但绝对/局部指标未通过 |
| MS | Ks1=3.00 | 0.132 | 0.132 | 0.132 | 相对残差可接受，但绝对/局部指标未通过 |
| MS | Ks1=7.00 | 0.077 | 0.077 | 0.077 | 相对残差可接受，但绝对/局部指标未通过 |

读数规则：残差比例只回答“方向是否一致”，不回答“差异是否可接受”。
表中最后一列按预登记的全部阈值判定：即使 v22 ≤ 0.25，只要绝对残差（0.2% 弦长）、
角残差（0.5°）或曲率残差超限，仍然不算替代成功。
若放宽上界后残差显著下降（B3/B4），说明 0.18 的失败**部分**来自人为边界；
若几乎不变（B0/B1/B2/ML/MS），说明失败与边界无关。

### 3.4 Ks1 的几何作用（中弧线 / 曲率 / 前后段）

| 背景 | 方向 | S_shape | 轮廓变化 | 中弧线曲率变化 | 替代后前段曲率残差 | 替代后后段曲率残差 | 目标 RCR | 替代 RCR |
|---|---|---|---|---|---|---|---|---|
| B0 | Ks1=3.00 | 0.5170 | 0.0330 | 0.2585 | 0.0444 | 0.0060 | 0.043 | 0.028 |
| B0 | Ks1=7.00 | 0.5106 | 0.0327 | 0.2553 | 0.0175 | 0.0033 | 0.000 | 0.000 |
| B1 | Ks1=3.00 | 0.5044 | 0.0339 | 0.2522 | 0.0188 | 0.0020 | 0.000 | 0.000 |
| B1 | Ks1=7.00 | 0.4332 | 0.0336 | 0.2166 | 0.0654 | 0.0034 | 0.000 | 0.000 |
| B2 | Ks1=3.00 | 0.6189 | 0.0408 | 0.3095 | 0.5372 | 0.2343 | 0.253 | 0.243 |
| B2 | Ks1=7.00 | 0.6471 | 0.0411 | 0.3235 | 0.1025 | 0.0181 | 0.229 | 0.230 |
| B3 | Ks1=3.00 | 0.3381 | 0.0152 | 0.1690 | 0.0362 | 0.0042 | 0.000 | 0.065 |
| B3 | Ks1=7.00 | 0.3543 | 0.0151 | 0.1772 | 0.2645 | 0.1832 | 0.238 | 0.163 |
| B4 | Ks1=3.00 | 0.5332 | 0.0178 | 0.2666 | 0.0423 | 0.0066 | 0.000 | 0.000 |
| B4 | Ks1=7.00 | 0.5001 | 0.0176 | 0.2500 | 0.2408 | 0.0104 | 0.000 | 0.000 |
| ML | Ks1=3.00 | 0.6420 | 0.0391 | 0.3210 | 0.0592 | 0.0072 | 0.030 | 0.018 |
| ML | Ks1=7.00 | 0.6301 | 0.0391 | 0.3150 | 0.0236 | 0.0042 | 0.000 | 0.000 |
| MS | Ks1=3.00 | 0.3539 | 0.0226 | 0.1769 | 0.0258 | 0.0027 | 0.034 | 0.022 |
| MS | Ks1=7.00 | 0.3406 | 0.0224 | 0.1703 | 0.0126 | 0.0029 | 0.000 | 0.000 |

说明：Ks1 只进入中弧线系数（SSm1 = Ks1·(Sm2−Sm1)），因此 LE/TE 圆弧半径变化为 0；
它的独立价值只能在中弧线/压力面/吸力面的形状中寻找，不能用户缘半径指标否定。

## 4. 实验二：Ks2 最终裁决

### 4.1 硬约束

本轮规定 **Metal1、Metal2 必须固定**。上一轮曾用 Metal2 替代 Ks2，但 Metal2 直接改变出口金属角，
这种替代不能证明 Ks2 冗余。因此本轮的替代只允许 Xmean、K_m、Ks1，且进出口金属角保持不变。

### 4.2 替代结果（后 30% 弦长为重点）

| 背景 | 方向 | 向量残差比例 | 尾部中弧线残差 | 尾部角残差(deg) | 尾部曲率残差 | 尾部曲率残差比例 | 尾部压力面 | 尾部吸力面 | 判定 |
|---|---|---|---|---|---|---|---|---|---|
| B0 | Ks2=0.05 | 0.848 | 0.0038 | 0.256 | 0.0237 | 0.869 | 0.0039 | 0.0038 | 替代失败 |
| B0 | Ks2=0.20 | 0.850 | 0.0076 | 0.511 | 0.0472 | 0.871 | 0.0076 | 0.0076 | 替代失败 |
| ML | Ks2=0.05 | 0.851 | 0.0041 | 0.293 | 0.0261 | 0.879 | 0.0041 | 0.0041 | 替代失败 |
| ML | Ks2=0.20 | 0.854 | 0.0081 | 0.588 | 0.0523 | 0.881 | 0.0082 | 0.0081 | 替代失败 |
| MS | Ks2=0.05 | 0.856 | 0.0031 | 0.181 | 0.0172 | 0.872 | 0.0031 | 0.0031 | 替代失败 |
| MS | Ks2=0.20 | 0.858 | 0.0060 | 0.359 | 0.0339 | 0.874 | 0.0060 | 0.0060 | 替代失败 |
| X18 | Ks2=0.05 | 0.907 | 0.0011 | 0.217 | 0.0226 | 0.870 | 0.0011 | 0.0011 | 替代失败 |
| X18 | Ks2=0.20 | 0.928 | 0.0026 | 0.447 | 0.0460 | 0.892 | 0.0027 | 0.0026 | 替代失败 |

| 背景 | 方向 | S_rear | 尾部中弧线变化 | 尾部角变化(deg) | 尾部曲率变化 | 信噪比 | 是否可分辨 |
|---|---|---|---|---|---|---|---|
| B0 | Ks2=0.05 | 0.0820 | 0.0030 | 0.289 | 0.0273 | 1132.1 | 是 |
| B0 | Ks2=0.20 | 0.0813 | 0.0059 | 0.575 | 0.0542 | 2167.9 | 是 |
| ML | Ks2=0.05 | 0.0892 | 0.0034 | 0.327 | 0.0297 | 1090.4 | 是 |
| ML | Ks2=0.20 | 0.0891 | 0.0067 | 0.653 | 0.0594 | 2202.6 | 是 |
| MS | Ks2=0.05 | 0.0590 | 0.0023 | 0.203 | 0.0197 | 920.5 | 是 |
| MS | Ks2=0.20 | 0.0582 | 0.0047 | 0.404 | 0.0388 | 1855.2 | 是 |
| X18 | Ks2=0.05 | 0.0781 | 0.0022 | 0.259 | 0.0260 | 1127.3 | 是 |
| X18 | Ks2=0.20 | 0.0774 | 0.0043 | 0.515 | 0.0516 | 2384.2 | 是 |

补充压力测试（Xmean=0.20，**已超出最终采用上界 0.18**，只作参考、不参与裁决）：

| 背景 | 方向 | 向量残差比例 | 尾部曲率残差比例 | 判定 |
|---|---|---|---|---|
| X20 (stress) | Ks2=0.05 | 0.912 | 0.879 | 替代失败 |
| X20 (stress) | Ks2=0.20 | 0.932 | 0.897 | 替代失败 |

压力测试同样失败，说明 Ks2 的尾部控制作用不依赖于 Xmean 是否扩展。

### 4.3 为什么 Metal1/Metal2 固定后 Ks2 不能被替代（解析原因）

```text
后段中弧线: sc(xc) = a5*(1-xc)^3 + a6*(1-xc)^2 + a7*(1-xc) + a8
a7 = -SSm2 = -Ks2*(Sm2-Sm1)      <-- 只有 Ks2 控制这一项
a8 = Sm2                          <-- 由 Metal2 固定
a5,a6                             <-- 由 Xmean/K_m/Ks1/Ks2 共同控制，可部分补偿
```

在 Metal1/Metal2 固定（a8 固定）时，Xmean/K_m/Ks1 可以调整 a5、a6，但无法独立改变 a7；
而 Ks2 的作用恰恰主要是 a7。这是“保持进出口角不变时 Ks2 不可替代”的结构性原因，
与数值搜索的结果一致。上一轮之所以能用 Metal2 得到 10–23% 的轮廓残差，是因为允许了 a8 变化。

注意：Ks2 的失败是**相对残差**失败——替代后仍保留 87%–90% 的尾部曲率变化，
而不是“只差一点绝对量”。因此它不属于阈值边缘情形。

## 5. Xmean 上界裁决

### 5.1 硬性 QC（必要但不充分）

在 Xmean = 0.18 / 0.20 / 0.22 / 0.24 / 0.26 / 0.30，Ks1 = 3/5/6/7，K_m = 0.10/0.35，
三个 Metal 背景下共 144 个角点：硬性 QC 失败 **0** 个。

这说明：**硬性 QC 不能给出上界**。它只排除了自相交、非正厚度、非有限曲率等灾难性几何；
因此本轮明确不以“100% PASS”作为扩大范围的依据，而使用软风险相对尺度。

### 5.2 软风险地图（2200+ 内存几何）

| Xmean 上界 | 最坏 RCR | 最坏点 | 高端(≥0.14)最坏切线回摆(deg) | 拼接曲率跳变 | 对当前 0.18 参考 | 对历史锚点 | 判定 |
|---|---|---|---|---|---|---|---|
| 0.18 | 0.2527 | Xmean=0.060, Ks1=3, K_m=0.35, M0 | 6.96 | 1.81e-09 | 通过 | 通过 | **可接受** |
| 0.20 | 0.2530 | Xmean=0.200, Ks1=7, K_m=0.10, ML | 7.79 | 1.81e-09 | 通过 | 通过 | **可接受** |
| 0.22 | 0.2600 | Xmean=0.220, Ks1=7, K_m=0.10, ML | 8.56 | 1.81e-09 | 不通过 | 不通过 | 拒绝 |

> 全图最坏切线回摆 51.8° 来自低 Xmean 角点（0.06），与上界无关，故表中给出高端（≥0.14 且 ≤ 候选上界）的最坏值。

采用规则：最坏 RCR ≤ 1.01 × 当前 0.18 上界的最坏值
（0.2527）且 ≤ 1.01 × 历史锚点
（0.2529）；切线回摆与拼接跳变不得超过历史最值的 1.25 倍。

- 主规则结果：**0.20**
- 稳健性检查（同一规则在登记容差集上重算）：容差 0.85 → 0.18，容差 1.00 → 0.18
- **结论对容差敏感**：0.20 仅在 1.01 容差下通过（0.2530 vs 0.2527，差 0.13%），
  在 1.00 与 0.85 下都退回 0.18。按预登记政策（敏感性 → 保守分支），
  **最终采用上界 = 0.18（保持 0.18 不变）**。

这不是“扩大范围被 QC 挡住”，而是“0.20 相对 0.18 在软风险上没有任何可测量的改善，
其通过与否只取决于 0.1% 级的数值容差”。在没有 CFD 证据的前提下，不值得为一个
0.1% 级的差异扩大探索范围；0.22 则在所有容差下都被拒绝（+3.4%）。

### 5.3 联合限制

在新增区间 0.18 < Xmean ≤ 0.20 内，RCR 超过 0.2149（= 0.85 × 历史锚点）的点共 22 个（区间总点数 240）。

**拟合出的联合限制：`K_m >= 0.15`（保留新增区间 75%，违例 0 个）。**

等效备选（按保留比例排序）：`Ks1 <= 5.0`（60%）；`Ks1 <= 5.5`（60%）；`Ks1 <= 5.0 AND K_m >= 0.10`（60%）

由于最终上界保持 0.18，该限制在当前配置下**不生效**；
它是为“未来若把 Xmean 扩展到 0.20”准备的准入条件。

为什么需要它：反向曲率叶瓣随 Ks1 增大而增大、随 K_m 增大而减小。
仅限制 Xmean 无法阻止 “Xmean 高端 + Ks1 高端 + K_m 低端”这一角点；
联合限制只排除这一角点，不收缩其余参数空间。

### 5.4 上界附近的几何风险

1. **反向曲率叶瓣**：位置在 xc ≈ Xmean 附近（拼接点之后的第一个小区间），
   物理含义是前段中弧线斜率在拼接点附近先过冲再回摆，形成局部 S 形。
2. **切线角回摆**：高端角点的回摆量为几度量级，远小于 38° 总折转，但会增加前段载荷分布的不确定性。
3. **前段曲率抬升**：Xmean 上移使前段曲率峰值与后段曲率同时增大，
   意味着叶片在前 20% 弦长承担更多弯折，CFD 中可能出现前缘加速/逆压梯度提前。
4. **不存在硬性几何失效**：在 0.30 以内仍未出现自相交或负厚度，
   因此这是一个**工程风险**问题，不是几何可行性问题。

## 6. 最终参数配置

```yaml
config_id: final_geometry_parameters_v1
status: EXPLORATORY_NOT_APPROVED_FOR_PRODUCTION
decision_date: '2026-10-17'
authority: final for the exploratory geometry DOE only; NOT a CFD certification and
  NOT a production-range approval
criteria:
  file: final_decision_criteria.yaml
  criteria_id: final_decision_criteria_v1
  criteria_version: 1.0.0
keep_parameters:
- name: Xthick
  range:
  - 0.1
  - 0.6
  status: KEEP
- name: Tmax
  range:
  - 0.025
  - 0.095
  status: KEEP
- name: Metal2
  range:
  - 0.0
  - 32.0
  status: KEEP
- name: Solidity
  range:
  - 0.7
  - 2.5
  status: KEEP
- name: Metal1
  range:
  - 48.0
  - 58.0
  status: KEEP
- name: T1
  range:
  - 0.01
  - 0.018
  status: KEEP
- name: T2
  range:
  - 0.008
  - 0.016
  status: KEEP
- name: Xmean
  range:
  - 0.06
  - 0.18
  status: KEEP
- name: K_m
  range:
  - 0.1
  - 0.35
  status: KEEP
- name: Ks1
  range:
  - 3.0
  - 7.0
  status: KEEP
- name: Ks2
  range:
  - 0.05
  - 0.2
  status: KEEP
fixed_parameters:
- name: SS1
  value: 3.2
  status: FIXED_BY_REVIEW
  decision_source: HUMAN_REVIEW_DECISION
- name: SS2
  value: 0.8
  status: FIXED_BY_REVIEW
  decision_source: HUMAN_REVIEW_DECISION
xmean:
  lower_bound: 0.06
  upper_bound: 0.18
  previous_upper_bound: 0.18
  movement: 'unchanged (conservative: the extension is not robust to the registered
    threshold sensitivity)'
  decision_rule: XMEAN_BOUND_V1
  primary_rule_result: 0.2
  robust_to_threshold_sensitivity: false
  sensitivity_bounds:
    '0.85': 0.18
    '1.00': 0.18
  worst_rcr_at_bound: 0.2526740157114918
  worst_rcr_at_previous_bound: 0.2526740157114918
  note_on_worst_rcr: identical to the previous bound because the final bound is unchanged
  historical_anchor_rcr: 0.2528590152004063
  joint_constraints:
  - id: JC_XMEAN_KS1_KM
    rule: K_m >= 0.15
    applies_to: 0.18 < Xmean <= 0.20
    active_at_final_bound: false
    rationale: the reverse-curvature lobe grows with Ks1 and shrinks with K_m; the
      flagged corner is excluded without shrinking the rest of the box
    retained_fraction_of_new_region: 0.75
dimensionality:
  geometry_dimension: 11
  operating_dimension: 2
  total_candidate_dimension: 13
  geometry_parameters:
  - Xthick
  - Tmax
  - Metal2
  - Solidity
  - Metal1
  - T1
  - T2
  - Xmean
  - K_m
  - Ks1
  - Ks2
  operating_parameters:
  - Incidence
  - Mach
excluded_from_geometry_space:
  CHORD_TARGET: 0.06
  SPAN: 0.003
  Npoint: 101
  Ncirc: 4
  Nscale1: 1.7
  Nscale2: 1.7
  Rsign: 1.0
  Gridswitch: -1.0
decision_evidence:
  Ks1:
    decision: KEEP
    rule_id: K1_KEEP
    n_resolved: 7
    n_accepted: 0
    n_rejected_resolved: 7
    n_backgrounds: 7
  Ks2:
    decision: KEEP
    rule_id: K2_KEEP
    n_resolved: 4
    n_accepted: 0
    n_rejected_resolved: 4
    n_backgrounds: 4
requires_before_production:
- CFD verification of the high-Xmean / high-Ks1 corner
- CFD verification of the Ks2 rear-camber control range
- mesh independence and convergence check for the reverse-curvature lobe
- calibration of the research thresholds on the 1891-sample population
not_modified:
  formal_doe: true
  production_range: true
  frozen_v1_generator: true
  legacy_files: true
  prior_100_case_experiment: true
  prior_57_case_review: true
```

## 7. 阈值敏感性、噪声与不确定性

### 7.1 阈值敏感性（使用同一批几何，不新增 Case）

| 参数 | 替代残差阈值 | 可替代方向数 | 可替代背景数 | 是否改变裁决 |
|---|---|---|---|---|
| Ks1 | 0.20 | 0/14 | 0/7 | 否 |
| Ks1 | 0.25 | 0/14 | 0/7 | 否 |
| Ks1 | 0.30 | 0/14 | 0/7 | 否 |
| Ks2 | 0.20 | 0/8 | 0/4 | 否 |
| Ks2 | 0.25 | 0/8 | 0/4 | 否 |
| Ks2 | 0.30 | 0/8 | 0/4 | 否 |

| 上界规则容差 | 候选上界 | 最坏 RCR | 是否可接受 |
|---|---|---|---|
| 0.85 | 0.18 | 0.2527 | 否 |
| 0.85 | 0.20 | 0.2530 | 否 |
| 0.85 | 0.22 | 0.2600 | 否 |
| 1.00 | 0.18 | 0.2527 | 是 |
| 1.00 | 0.20 | 0.2530 | 否 |
| 1.00 | 0.22 | 0.2600 | 否 |

> 0.85 容差下连当前 0.18 都不通过，说明该容差过紧（它要求比现有 0.18 上界再降 15%），
> 只作为敏感性下界参考；登记值为 1.01。1.00 与 1.01 的区别只影响 0.20 的边际判定。
### 7.2 数值噪声

所有判定均基于内存 float64；4 位小数序列化只用于测量噪声。
每个 Case 的 `serialization_noise_rms_norm` 见 `case_metrics.csv`；
低于 10 倍噪声的信号一律记为“未分辨”，不会因此删除参数。

### 7.3 不确定性（必须与结论一起阅读）

- Thresholds are research thresholds, not calibrated on the 1891-sample population.
- No CFD, no mesh, no aerodynamic validation.  Geometric feasibility is NOT engineering feasibility.
- The 157-case population is a SCREENING population that passed hard QC; its extremes are tolerated artifacts, not a validated quality envelope.
- The substitution search is a mathematical equivalence test in a 95-D geometric metric; a passing substitute is not proven to be aerodynamically equivalent.
- Only 3 Metal backgrounds; conclusions are not extrapolated to the full Metal1/Metal2 domain.
- All final states are exploratory and reversible; none approves the formal production range.
- 反向曲率指标 RCR 的历史锚点来自一个**低 Xmean 角点**，它代表“过去已接受的最极端形态”，
  不等于“工程上可接受的最极端形态”。因此本轮上界只是**相对**保守，不是绝对安全。
- Ks1 的裁决依赖‘高端背景不可替代’这一事实；如果未来把 Xmean 上界收回到 0.18 以下，
  该证据会减弱，但本轮已按最终上界做出决定，不再安排同类复核。

## 8. 最终回答

**1. Ks1 最终保留还是固定，为什么？**

**KEEP**（K1_KEEP）。在 7 个背景中，Ks1 的几何作用全部可分辨；0 个背景的 Xmean+K_m 替代通过预登记阈值，但 7 个背景明确失败。
失败背景与残差：`B0` 残差 0.072–0.141；`B1` 残差 0.091–0.151；`B2` 残差 0.166–1.000；`B3` 残差 0.106–1.000；`B4` 残差 0.135–0.538；`ML` 残差 0.076–0.138；`MS` 残差 0.077–0.132。
把 Xmean 上界从 0.18 放宽到 0.22 后，高 Xmean 背景（B3/B4）的残差从 1.000/0.538 降到 0.607/0.402——
确有改善，说明 0.18 的失败**部分**来自人为边界；但改善后仍远高于 0.25，且最优解始终贴住边界，
说明 Xmean+K_m 无法表达 Ks1 产生的前段中弧线方向。按预登记的保守规则
（存在未被可靠排除的独立作用即 KEEP），本轮保留 Ks1，范围 3.0–7.0 继续参与几何 DOE。

**2. Ks2 最终保留还是固定，为什么？**

**KEEP**（K2_KEEP）。在 Metal1/Metal2 **固定**的约束下，Ks2 在 4/4 个背景的后 30% 弦长作用可分辨，
而 Xmean+K_m+Ks1 的替代在 4/4 个背景失败。
解析原因是后段中弧线的一次项系数 `a7 = -Ks2·(Sm2−Sm1)` 只由 Ks2 控制；
在进出口金属角固定的前提下，其他中弧线参数无法复现该项。上一轮“可用 Metal2 替代”的结论
是因为允许了出口金属角变化，本轮明确不接受这种替代。因此 Ks2 保留，范围 0.05–0.20。

**3. Xmean 上界最终定为多少，为什么？**

**0.18**（下限 0.06，即**保持 0.18 不变**）。

证据链：

1. 硬性 QC 在 Xmean ≤ 0.30 的 144 个角点上全部通过，因此硬性 QC 完全不能给出上界。
2. 改用软风险相对尺度：0.18 的最坏 RCR = 0.2527，
   0.20 = 0.2530（差 0.13%），0.22 = 0.2600（+2.92%）。
3. 登记规则（容差 1.01）下 0.20 通过、0.22 被拒绝；但稳健性检查显示 0.20 的通过
   完全依赖这 0.13% 的数值容差：容差取 1.00 时退回 0.18。
4. 按预登记政策“阈值敏感 → 取保守分支”，最终保持 0.18。

这不是因为 0.20 的几何“不合格”，而是因为**它相对 0.18 没有任何可测量的软风险改善**，
其结论只由 0.1% 级容差决定；在没有 CFD 证据时，不值得为此扩大探索范围。
0.22 则是所有容差下都拒绝的明确结论。
若未来决定试探性扩展到 0.20，必须同时实施联合限制 `K_m >= 0.15`（保留新增区间 75%）。
该上界是**探索性**上界，不是 CFD 生产边界。

**4. 目前最终候选是多少维？**

几何 11 维 + 运行条件 2 维（Incidence、Mach） = **13 维**。
几何参数为：Xthick, Tmax, Metal2, Solidity, Metal1, T1, T2, Xmean, K_m, Ks1, Ks2。
固定：SS1=3.2、SS2=0.8。

**5. 下一阶段还需要解决哪些工程问题？**

1. **CFD 验证高端角点**：Xmean ≥ 0.19 与 Ks1 ≥ 6 的组合是否存在前缘分离/逆压梯度提前；
   几何上它只是“局部 S 形”，但气动上是否可接受必须由 CFD 回答。
2. **Ks2 的尾部控制是否需要与出口金属角解耦**：本轮证明 Ks2 不可被替代，
   但 Ks2 的工程收益（尾缘载荷、落后角）尚未用 CFD 量化。
3. **反向曲率叶瓣的网格敏感性**：叶瓣位于 xc ≈ Xmean 处，若网格在此处分辨率不足，
   可能被数值耗散抹平，导致“几何有、CFD 看不到”的假象。
4. **阈值校准**：本轮阈值为研究阈值，需用 1891 历史样本校准后再用于生产筛选。
5. **联合限制的实现**：`Xmean > 0.18` 时的联合限制需要在 DOE 采样器中真正实现，
   不能只写在报告里，否则采样会重新产生被排除的角点。
6. **Incidence / Mach 的耦合**：本轮二者固定为 0°/0.5，尚未评估它们与高端 Xmean 的交互。

## 9. 复现与文件清单

```bash
cd /home/qian/compressor_ai4s
conda run -n ai4s python tools/geometry_final_decision_v1.py all
conda run -n ai4s python -m pytest -q
```

| 文件 | 内容 |
|---|---|
| `FINAL_DECISION.md` | 本报告 |
| `final_geometry_parameters.yaml` | 最终参数配置与维度 |
| `final_decision_criteria.yaml` | 预登记判据（含修订记录与 SHA256） |
| `final_decision_evidence.csv` | 长表证据（每条结论对应 Case ID + 数值 + 阈值） |
| `case_design.csv` / `case_metrics.csv` | 本轮 50 行设计/指标（含复用标记） |
| `substitution_results.csv` | 全部替代搜索结果 |
| `xmean_boundary_scan.csv` | 软风险地图（不落盘几何） |
| `xmean_hard_qc_scan.csv` | 边界硬性 QC 扫描 |
| `decision_profiles.npz` | 新增 Case 的高精度曲线（压缩） |
| `overview.png` / `decision_summary.png` | 两张总览图 |
| `provenance.json` | Git/环境/哈希/体积/回归结果 |

> 本轮没有运行 NUMECA / CFX，没有训练模型，没有修改正式 DOE，没有自动提交 Git。

## 10. 最终决策表（速查）

| 参数 | 最终决定 | 固定值或范围 | 核心证据 |
|---|---|---|---|
| Ks1 | KEEP | 3.0 – 7.0 | K1_KEEP，7/7 背景不可替代（B2/Ks1=3 残差 1.000；B3/Ks1=7 残差 1.000；B4/Ks1=7 残差 0.538） |
| Ks2 | KEEP | 0.05 – 0.20 | K2_KEEP，Metal1/Metal2 固定下 4/4 背景不可替代（尾部曲率残差 0.87–0.89） |
| Xmean | KEEP | 0.06 – 0.18 | XMEAN_BOUND_V1；主规则 0.20 对容差敏感（0.12% 级），按保守政策保持 0.18；0.22 在所有容差下拒绝 |
| SS1 | FIX | 3.2 | 人工决定（FIXED_BY_REVIEW） |
| SS2 | FIX | 0.8 | 人工决定（FIXED_BY_REVIEW） |

几何维度 **11** + 运行条件 2（Incidence、Mach） = **13 维**；状态为 FINAL（仅限探索性几何 DOE），不存在 FURTHER_REVIEW / PENDING / UNDECIDED。

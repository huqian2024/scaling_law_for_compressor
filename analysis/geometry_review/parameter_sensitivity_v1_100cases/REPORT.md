# 压气机叶型全参数几何敏感性实验 V1（100 Cases）

> 实验状态：**EXPLORATORY / NOT APPROVED**。
> 本实验只做几何生成、几何 QC 与几何敏感性筛选；**没有** NUMECA 网格生成、**没有** CFX 求解、**没有** AI 训练、**没有** 修改正式 DOE 或冻结正式生产范围。
> 判据：`parameter_screening_v1_tentative` / version `1.0.0`（TENTATIVE_RESEARCH_THRESHOLDS_NOT_CALIBRATED）。
> Case 号段：`C820001..C820100`；git HEAD：`02e57d1d26197d97e65f4b64ef0a23f6d06393b7`。

## A. 实验完整性

```text
预先登记 Case 数        : 100
阶段分布                : S1=60, S2=20, S3=20
第三阶段锚点            : C820081, C820085, C820089, C820093, C820097
第三阶段变体覆盖参数    : K_m, Ks2, Metal1, Metal2, SS1, SS2, T1, T2, Xmean
几何生成成功            : 100/100
实验硬性 QC 通过        : 100/100
冻结 QC (geometry_qc_v1_hard) 通过 : 100/100
实验 QC 与冻结 QC 不一致 : 0
参数向量重复组数        : 0
失败/未通过 Case 数     : 0（全部保留在 case_metrics.csv）
唯一 Case ID 数         : 100
```

未发现参数向量重复；100 个 Case 的参数向量互不相同。

本批 100 个 Case 均几何生成成功且硬性 QC 通过；这不代表工程合理，也不代表 CFD 可收敛。

### A.2 冻结资产与回归检查

```text
冻结文件 SHA256 校验 : PASS
V1 回归测试          : PASS — 50 passed, 2 subtests passed in 5.93s
profiles.npz 回读     : True
总输出体积            : 2.358 MB
```

## B. 全参数几何敏感性

定义：`S = max_levels |feature(level) - feature(baseline)| / |Δu|`，`Δu` 为归一化参数偏移；长度类指标均除以基准弦长，因此 S 无量纲（每整个参数范围）。完整定义、单位、阈值与规则见 `screening_criteria.yaml`。

| 参数 | 扫描范围 | 水平数 | 有效率 | S_contour | S_LE | S_TE | S_camber | S_thickness | S_cascade | S_comp | 主导区域 | 单调性 | 冗余伙伴 (cos) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `Xthick` | 0.1 – 0.6 | 3 | 100% | 0.01008 | 0.04386 | 0.001582 | 0 | 0.01287 | 0.0397 | 0.01375 | 前缘局部 | 不确定 | — |
| `Tmax` | 0.025 – 0.095 | 3 | 100% | 0.01731 | 0.01158 | 0.002229 | 0 | 0.02416 | 0.06443 | 0.01411 | 叶栅通道（栅距/最小间隙） | 单调 | — |
| `Metal2` | 0 – 32 | 3 | 100% | 0.2586 | 0.0003097 | 0.4499 | 0.4644 | 0 | 0.1319 | 0.2446 | 中弧线 | 单调 | Xmean (0.520) |
| `Solidity` | 0.7 – 2.5 | 3 | 100% | 0 | 0 | 0 | 0 | 0 | 3.276 | 0.1638 | 叶栅通道（栅距/最小间隙） | 单调 | — |
| `Metal1` | 48 – 58 | 7 | 100% | 0.029 | 0.003198 | 0.02431 | 0.09636 | 0 | 0.09074 | 0.03664 | 中弧线 | 单调 | K_m (0.625) |
| `T1` | 0.01 – 0.018 | 7 | 100% | 0.001256 | 0.5327 | 0 | 0 | 0.001878 | 0.006631 | 0.0809 | 前缘局部 | 单调 | — |
| `T2` | 0.008 – 0.016 | 7 | 100% | 0.001973 | 5.683e-06 | 0.6399 | 0 | 0.00304 | 0.0006871 | 0.09707 | 尾缘局部 | 单调 | — |
| `Xmean` | 0.06 – 0.18 | 7 | 100% | 0.4601 | 0.0001236 | 0.6994 | 0.712 | 0 | 0.3093 | 0.4008 | 中弧线 | 单调 | Ks1 (0.994) |
| `K_m` | 0.1 – 0.35 | 7 | 100% | 0.3334 | 0.0001108 | 0.5134 | 0.4735 | 0 | 0.2868 | 0.2861 | 尾缘局部 | 单调 | Metal1 (0.625) |
| `Ks1` | 3 – 7 | 3 | 100% | 0.06602 | 0.0002379 | 0.1038 | 0.1154 | 0 | 0.04033 | 0.06051 | 中弧线 | 单调 | Xmean (0.994) |
| `Ks2` | 0.05 – 0.2 | 3 | 100% | 0.005634 | 7.911e-08 | 0.009261 | 0.01089 | 0 | 1.602e-05 | 0.005258 | 中弧线 | 单调 | Xmean (0.689) |
| `SS1` | 2.4 – 4 | 3 | 100% | 0.001055 | 0.0008875 | 0 | 0 | 0.001784 | 6.904e-11 | 0.0007174 | 厚度分布 | 单调 | — |
| `SS2` | 0.5 – 1.1 | 3 | 100% | 0.001373 | 1.51e-05 | 0.0003112 | 0 | 0.001827 | 1.439e-08 | 0.0007348 | 厚度分布 | 单调 | — |

### B.1 逐参数说明

- **`Xthick`**（前缘局部主导，S_comp=0.01375，量级：高；单调性：不确定）。（仅 3 个水平，单调性证据有限） 决策：**KEEP_CANDIDATE**（R1_KEEP_HIGH）。
- **`Tmax`**（叶栅通道（栅距/最小间隙）主导，S_comp=0.01411，量级：高；单调性：单调）。 决策：**KEEP_CANDIDATE**（R1_KEEP_HIGH）。
- **`Metal2`**（中弧线主导，S_comp=0.2446，量级：高；单调性：单调）。 决策：**KEEP_CANDIDATE**（R1_KEEP_HIGH）。
- **`Solidity`**（叶栅通道（栅距/最小间隙）主导，S_comp=0.1638，量级：高；单调性：单调）。 决策：**KEEP_CANDIDATE**（R0_SOLIDITY）。
- **`Metal1`**（中弧线主导，S_comp=0.03664，量级：高；单调性：单调）。 决策：**KEEP_CANDIDATE**（R1_KEEP_HIGH）。
- **`T1`**（前缘局部主导，S_comp=0.0809，量级：高；单调性：单调）。 决策：**KEEP_CANDIDATE**（R1_KEEP_HIGH）。
- **`T2`**（尾缘局部主导，S_comp=0.09707，量级：高；单调性：单调）。 决策：**KEEP_CANDIDATE**（R1_KEEP_HIGH）。
- **`Xmean`**（中弧线主导，S_comp=0.4008，量级：高；单调性：单调）。 决策：**KEEP_CANDIDATE**（R1_KEEP_HIGH）。
- **`K_m`**（尾缘局部主导，S_comp=0.2861，量级：高；单调性：单调）。 决策：**KEEP_CANDIDATE**（R1_KEEP_HIGH）。
- **`Ks1`**（中弧线主导，S_comp=0.06051，量级：高；单调性：单调）。 决策：**KEEP_CANDIDATE**（R1_KEEP_HIGH）。
- **`Ks2`**（中弧线主导，S_comp=0.005258，量级：中等；单调性：单调）。 决策：**REVIEW**（R2_REVIEW_MEDIUM）。
- **`SS1`**（厚度分布主导，S_comp=0.0007174，量级：低；单调性：单调）。 注意：legacy 在前后缘圆处重新计算 St1/St2 且不乘 SS1/SS2，因此本轮的 LE/TE 圆弧半径敏感度为 0（见 B.3）；其低敏感度有一部分来自这一实现事实，不能直接外推为“厚度分布无关”。 决策：**FIX_CANDIDATE**（R3_FIX_LOW）。
- **`SS2`**（厚度分布主导，S_comp=0.0007348，量级：低；单调性：单调）。 注意：legacy 在前后缘圆处重新计算 St1/St2 且不乘 SS1/SS2，因此本轮的 LE/TE 圆弧半径敏感度为 0（见 B.3）；其低敏感度有一部分来自这一实现事实，不能直接外推为“厚度分布无关”。 决策：**FIX_CANDIDATE**（R3_FIX_LOW）。

### B.2 第二阶段（2×2）耦合证据

| 参数对 | 平均交互指数 | 轮廓 RMS | 前缘区域 | 尾缘区域 | 中弧线 | 厚度 | 最小间隙 |
|---|---|---|---|---|---|---|---|
| Xmean × K_m | 4.643 | 7.621 | 4.365 | 7.652 | 7.272 | 0.000 | 0.948 |
| T1 × SS1 | 0.630 | 1.414 | 0.671 | 0.000 | 0.000 | 1.692 | 0.000 |
| T2 × SS2 | 2.029 | 3.044 | 5.332 | 0.481 | 0.000 | 3.318 | 0.000 |
| Metal1 × Metal2 | 1.101 | 0.799 | 4.370 | 0.589 | 0.824 | 0.000 | 0.025 |
| Metal2 × Solidity | 0.011 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.065 |

> 相对交互指数 = |(f_HH - f_LH) - (f_HL - f_LL)| / |f_HH - f_LL|；仅 4 个角点，不能证明整个二维参数域的耦合规律，只能作为局部/探索性证据。指数 > 1 表示两端总变化 f_HH - f_LL 很小（两端效应相互抵消），并不代表计算错误；必须结合四个角点的绝对指标一起解读。

> `Metal2 × Solidity` 的平均交互指数 = 0.011，接近 0：本轮 Solidity 只改栅距，单叶型坐标不变，因此它与 Metal2 的单叶形状效应基本独立；但栅距与 Metal2 的通道匹配仍需工程判断。

### B.3 区域分解（诊断列，不参与 S_comp 加权）

| 参数 | S_LE_radius | S_LE_region | S_TE_radius | S_TE_region | S_camber_meanline | S_camber_angle | S_thick_front | S_thick_mid | S_thick_rear | S_cascade_pitch | S_cascade_gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `Xthick` | 0.04386 | 0.007968 | 0.001582 | 0.0005365 | 0 | 0 | 0.01287 | 0.01166 | 0.005818 | 0 | 0.0397 |
| `Tmax` | 0.01158 | 0.003553 | 0.002229 | 0.0006919 | 0 | 0 | 0.02083 | 0.02416 | 0.00586 | 0 | 0.06443 |
| `Metal2` | 1.955e-15 | 0.0003097 | 8.967e-11 | 0.4499 | 0.2957 | 0.4644 | 0 | 0 | 0 | 0 | 0.1319 |
| `Solidity` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2.571 | 3.276 |
| `Metal1` | 1.454e-14 | 0.003198 | 1.59e-10 | 0.02431 | 0.03648 | 0.09636 | 0 | 0 | 0 | 0 | 0.09074 |
| `T1` | 0.5327 | 0.00319 | 0 | 0 | 0 | 0 | 0.001878 | 0 | 0 | 0 | 0.006631 |
| `T2` | 0 | 5.683e-06 | 0.6399 | 0.003451 | 0 | 0 | 8.205e-05 | 0.001039 | 0.00304 | 0 | 0.0006871 |
| `Xmean` | 1.939e-14 | 0.0001236 | 5.75e-11 | 0.6994 | 0.5216 | 0.712 | 0 | 0 | 0 | 0 | 0.3093 |
| `K_m` | 1.43e-14 | 0.0001108 | 7.321e-11 | 0.5134 | 0.3786 | 0.4735 | 0 | 0 | 0 | 0 | 0.2868 |
| `Ks1` | 4.154e-15 | 0.0002379 | 1.491e-10 | 0.1038 | 0.07989 | 0.1154 | 0 | 0 | 0 | 0 | 0.04033 |
| `Ks2` | 4.846e-15 | 7.911e-08 | 1.406e-10 | 0.009261 | 0.005921 | 0.01089 | 0 | 0 | 0 | 0 | 1.602e-05 |
| `SS1` | 0 | 0.0008875 | 0 | 0 | 0 | 0 | 0.001784 | 0 | 0 | 0 | 6.904e-11 |
| `SS2` | 0 | 1.51e-05 | 0 | 0.0003112 | 0 | 0 | 0.0002179 | 0.001827 | 0.001766 | 0 | 1.439e-08 |

> `S_LE_radius` 是拟合圆弧半径的相对变化；`S_LE_region` 还包含拼接弦与相邻叶面（因此中弧线/厚度变化也会进入该列）。两者必须区分，不能把 `S_LE_region` 直接当作前缘钝度。中弧线 `κmax` 可能由端点控制，因此同时使用 `κRMS` 与 `meanline_curvature_xc{010,050,090}`（见 `case_metrics.csv`）。

### B.4 边缘拼接、曲率可靠性与通道边界

- `min_gap`：14.8856 mm（C820088）– 69.8073 mm（C820046），全部 > 0；本轮没有 `min_gap <= 0.01 m` 的 Case。
- 拼接角跳变：LE 7.747–13.324°，TE 22.638–24.585°。TE 端跳变几乎恒定，是 legacy 只插入 `Ncirc=4` 个圆弧点、留出一段直弦造成的结构特征，不是参数效应。`auto_flags` 因此对所有 Case 标记 `JUNCTION_JUMP_DIAGNOSTIC`，但它不参与硬性 QC，也不参与参数决策。
- 曲率分辨率稳定性：0.066–0.080（阈值 0.25），全部可用；没有把数值振荡误当成真实曲率变化。
- 本轮 100 个 Case 全部通过硬性 QC；这只说明几何在数学上闭合、有限、无自交且通道最小间隙为正，**不说明**工程气动合理或可网格化。

## C. 重点五参数

以下数字全部来自 `case_metrics.csv` 与 `parameter_sensitivity.csv`；引用的 Case ID 可在 `case_design.csv` 中追溯。长度量均除以基准弦长，故以“% 弦长”理解。

### C.1 `Metal1`

- 扫描：48 – 58，共 7 个非基准水平；有效水平 7 个。
- 整体：S_contour=0.029，S_camber=0.09636，S_thickness=0，S_comp=0.03664；主导区域 = 中弧线；单调性 = 单调。
- 极端水平对照（C820002 `Metal1=48` → C820008 `Metal1=58`）：
  - 说明：Metal1 是入口**金属角**；本轮没有把它解释为 Incidence，也没有构造入口气流角换算关系。
  - 中弧线 RMS 偏移：0.01824 → 0.01355；轮廓 RMS：0.0142 → 0.01082。
  - 入口中弧线角（atan(sc)）：48° → 58°；弦向角变化：-0.8925° → 0.0423°。
  - 前/尾缘拟合半径相对变化：LE 6.92e-16 → 6.92e-16，TE -1.56e-11 → -9.23e-12（Metal1 主要改中弧线，不直接改边缘圆弧半径）。
  - 解读：Metal1 改变入口金属角与中弧线，但前/尾缘圆弧半径几乎不变（数值上约 1e-14），与 legacy 圆弧公式一致。
- 冗余：与 `K_m` 的响应余弦 = 0.625；决策：**KEEP_CANDIDATE**（R1_KEEP_HIGH）。

### C.2 `T1`

- 扫描：0.01 – 0.018，共 7 个非基准水平；有效水平 7 个。
- 基准前缘圆弧半径（模型）= 0.3958 mm（按弦长 0.06 m 缩放）；T1 是厚度函数的输入参数，不能直接等同于前缘半径本身。
- 整体：S_contour=0.001256，S_camber=0，S_thickness=0.001878，S_comp=0.0809；主导区域 = 前缘局部；单调性 = 单调。
- 极端水平对照（C820009 `T1=0.01` → C820015 `T1=0.018`）：
  - 前缘拟合半径相对变化：-0.3329 → 0.1996；前缘区域 RMS：0.001975 → 0.001196。
  - 前段厚度 RMS：0.001174 → 0.0007042；整体轮廓 RMS：0.0007811 → 0.000471。
  - 前缘拼接角跳变：10.12° → 10.23°。
  - 解读：T1 确实改变前缘钝度（半径相对变化显著），影响主要集中在前缘与前段厚度，对尾缘几乎无影响。
- 冗余：与其它参数的响应余弦均 < 0.5（无显著冗余）；决策：**KEEP_CANDIDATE**（R1_KEEP_HIGH）。

### C.3 `T2`

- 扫描：0.008 – 0.016，共 7 个非基准水平；有效水平 7 个。
- 基准尾缘圆弧半径（模型）= 0.3293 mm（按弦长 0.06 m 缩放）；T2 是厚度函数的输入参数，不能直接等同于尾缘半径本身。
- 整体：S_contour=0.001973，S_camber=0，S_thickness=0.00304，S_comp=0.09707；主导区域 = 尾缘局部；单调性 = 单调。
- 极端水平对照（C820016 `T2=0.008` → C820022 `T2=0.016`）：
  - 尾缘拟合半径相对变化：-0.3599 → 0.2799；尾缘区域 RMS：0.001939 → 0.00151。
  - 后段厚度 RMS：0.00171 → 0.00133；整体轮廓 RMS：0.001109 → 0.000863。
  - 尾缘拼接角跳变：23.07° → 22.97°。
  - 解读：T2 确实改变尾缘钝度与尾缘区域；拼接角跳变几乎不随 T2 变化，说明该跳变主要由离散圆弧构造（Ncirc）决定，不能归因于 T2。
- 冗余：与其它参数的响应余弦均 < 0.5（无显著冗余）；决策：**KEEP_CANDIDATE**（R1_KEEP_HIGH）。

### C.4 `Xmean`

- 扫描：0.06 – 0.18，共 7 个非基准水平；有效水平 7 个。
- 整体：S_contour=0.4601，S_camber=0.712，S_thickness=0，S_comp=0.4008；主导区域 = 中弧线；单调性 = 单调。
- 极端水平对照（C820023 `Xmean=0.06` → C820029 `Xmean=0.18`）：
  - 中弧线 RMS 偏移：0.08693 → 0.1311；中弧线曲率 RMS 变化：0.3527 → 0.03841。
  - 轮廓 RMS：0.07668 → 0.1163；最大厚度/位置变化：0 / 0 → 0 / 0（Xmean 不进入厚度多项式）。
  - 与 K_m 的 2×2 平均交互指数：4.643（局部证据）。
  - 解读：Xmean 显著改变中弧线分布且不改变厚度；与 K_m 的交互指数 >1 意味着两端效应可相互抵消，不能把两者单因素结果简单相加。
- 冗余：与 `Ks1` 的响应余弦 = 0.994；决策：**KEEP_CANDIDATE**（R1_KEEP_HIGH）。

### C.5 `K_m`

- 扫描：0.1 – 0.35，共 7 个非基准水平；有效水平 7 个。
- 整体：S_contour=0.3334，S_camber=0.4735，S_thickness=0，S_comp=0.2861；主导区域 = 尾缘局部；单调性 = 单调。
- 极端水平对照（C820030 `K_m=0.1` → C820036 `K_m=0.35`）：
  - 中弧线 RMS 偏移：0.1211 → 0.2183；中弧线角范围变化：38° → 63.226°。
  - 轮廓 RMS：0.1067 → 0.2027；中弧线曲率 RMS 变化：0.1062 → 1.207；κmax 变化：0 → 2.731。
  - K_m 只通过 Sm0 进入 meanline 系数，因此它提供的是“转弯在 Xmean 处完成了多少”的独立控制；与 Xmean 同时改变时可能出现非线性局部交互。
  - 解读：K_m 改变转弯分配与中弧线形状；与 Metal1 的响应方向部分重合（cos 见上表），需要联合评审，不能仅凭单因素结果判断独立性。
- 冗余：与 `Metal1` 的响应余弦 = 0.625；决策：**KEEP_CANDIDATE**（R1_KEEP_HIGH）。

## D. 参数冗余与筛选建议

| 参数 | 决策 | 规则 | S_comp | QC 通过率 | 背景数 | 低敏感背景数（含基准） | 冗余伙伴 / cos / 比值 | 下一步复核要求 |
|---|---|---|---|---|---|---|---|---|
| `Xthick` | **KEEP_CANDIDATE** | R1_KEEP_HIGH | 0.01375 | 100% | 0 | 0 | — | continue range exploration; verify engineering limits |
| `Tmax` | **KEEP_CANDIDATE** | R1_KEEP_HIGH | 0.01411 | 100% | 0 | 0 | — | continue range exploration; verify engineering limits |
| `Metal2` | **KEEP_CANDIDATE** | R1_KEEP_HIGH | 0.2446 | 100% | 5 | 0 | Xmean / 0.520 / 0.610 | continue range exploration; verify engineering limits |
| `Solidity` | **KEEP_CANDIDATE** | R0_SOLIDITY | 0.1638 | 100% | 2 | 1 | — | expand pitch range; inspect channel blockage separately |
| `Metal1` | **KEEP_CANDIDATE** | R1_KEEP_HIGH | 0.03664 | 100% | 3 | 0 | K_m / 0.625 / 0.128 | continue range exploration; verify engineering limits |
| `T1` | **KEEP_CANDIDATE** | R1_KEEP_HIGH | 0.0809 | 100% | 3 | 0 | — | continue range exploration; verify engineering limits |
| `T2` | **KEEP_CANDIDATE** | R1_KEEP_HIGH | 0.09707 | 100% | 3 | 1 | — | continue range exploration; verify engineering limits |
| `Xmean` | **KEEP_CANDIDATE** | R1_KEEP_HIGH | 0.4008 | 100% | 4 | 0 | Ks1 / 0.994 / 0.151 | continue range exploration; verify engineering limits |
| `K_m` | **KEEP_CANDIDATE** | R1_KEEP_HIGH | 0.2861 | 100% | 4 | 0 | Metal1 / 0.625 / 0.128 | continue range exploration; verify engineering limits |
| `Ks1` | **KEEP_CANDIDATE** | R1_KEEP_HIGH | 0.06051 | 100% | 0 | 0 | Xmean / 0.994 / 0.151 | continue range exploration; verify engineering limits |
| `Ks2` | **REVIEW** | R2_REVIEW_MEDIUM | 0.005258 | 100% | 2 | 0 | Xmean / 0.689 / 0.013 | local or moderate effect; needs more backgrounds / engineering review |
| `SS1` | **FIX_CANDIDATE** | R3_FIX_LOW | 0.0007174 | 100% | 4 | 5 | — | effect small in >=2 backgrounds; confirm with an independent geometry audit before fixing |
| `SS2` | **FIX_CANDIDATE** | R3_FIX_LOW | 0.0007348 | 100% | 5 | 6 | — | effect small in >=2 backgrounds; confirm with an independent geometry audit before fixing |

**冗余判据**：只比较参数引起的**几何响应向量**（中弧线/厚度/前缘/尾缘/弦向角/弦长/最小间隙/中弧线曲率的符号化响应），不是输入参数相关系数；cos ≥ 0.98 且弱/强敏感度比 ≤ 0.5 才标记为冗余候选。下表只显示 cos ≥ 0.5 的候选；完整余弦值与所有伙伴见 `parameter_sensitivity.csv`。

**证据不足以做删除决定的参数**：`Ks2`。这些参数缺少第二个几何背景的配对复核，只能是 REVIEW，不能判为 FIX_CANDIDATE。

**自动建议 FIX_CANDIDATE 的参数**：`SS1`、`SS2`。这只是自动筛选建议，不等于最终冻结决策。

**值得人工重点评审的冗余候选**：`Xmean` 与 `Ks1` 的响应余弦 = 0.994，`Ks1`/`Xmean` 的敏感度比 = 0.151，即在本轮范围内 Ks1 的中弧线效应大部分被 Xmean 覆盖；但两者 S_comp 都高于 KEEP 阈值，按保存的规则都判 KEEP，不会自动 FIX。下一轮应在 Xmean 的低/中/高三个背景下单独复核 Ks1，再决定是否合并或固定。

## E. 下一轮边界探索建议

- **建议保留并继续探索（KEEP_CANDIDATE）**：`Xthick`、`Tmax`、`Metal2`、`Solidity`、`Metal1`、`T1`、`T2`、`Xmean`、`K_m`、`Ks1`。含义是“在本轮范围内有明确几何影响，值得继续试探上下限”，不是“已批准范围”。扩界应先做小步、单因素试探，其他参数保持基准。
- **建议保留待评审（REVIEW）**：`Ks2`。原因包括局部效应、耦合、数值不稳定或背景证据不足；不能据此删除。
- **建议考虑固定（FIX_CANDIDATE）**：`SS1`、`SS2`。必须经过至少两个几何背景的配对复核；本轮不据此冻结。
- **建议增加联合约束的参数对**：`Xmean × K_m`（平均交互 4.64）、`T1 × SS1`（平均交互 0.63）、`T2 × SS2`（平均交互 2.03）、`Metal1 × Metal2`（平均交互 1.10）。四角点证据只能说明局部交互，不能外推为全域规律。
- **失败边界**：本轮声明范围内没有失败 Case；这不证明范围外安全，也不证明工程合理或可网格化。

### E.1 必须区分的四个阶段

```text
1. 数学几何有效        ：本轮可直接证明（生成器不抛异常、坐标有限、闭合）
2. 自动几何诊断正常    ：本轮可直接证明（硬性 QC + 指标可计算 + 冻结 QC 复核）
3. 工程气动合理        ：本轮未证明，需要人工/工程评审
4. 可网格化 / CFD 收敛 ：本轮未证明，需要 NUMECA + CFX 真实试验
```

本轮结论只能覆盖第 1、2 类；任何“气动可接受”“可用于生产”的说法都超出证据范围。

## F. 数据、复现与限制

### F.1 文件与追溯

| 文件 | 内容 |
|---|---|
| `case_design.csv` | 100 行：13 参数、归一化水平、阶段、来源、选择理由与证据、锚点 Case |
| `case_metrics.csv` | 100 行：生成状态、硬性 QC、冻结 QC 复核、全部几何指标与失败原因 |
| `parameter_sensitivity.csv` | 13 行：S_contour/S_LE/S_TE/S_camber/S_thickness/S_cascade/S_comp、单调性、冗余、背景证据、失败范围 |
| `parameter_decisions.csv` | 13 行：KEEP_CANDIDATE / REVIEW / FIX_CANDIDATE、规则号、判据版本、证据 Case |
| `profiles.npz` | 所有生成成功 Case 的高精度曲线（xp/yp/xs/ys/xc/yc/thick/sc），按 Case ID 映射 |
| `stage3_selection.json` | 候选池统计、锚点打分、每个自适应 Case 的选择依据 |
| `provenance.json` | Git commit、脚本/判据/模板哈希、环境版本、随机种子、运行与验收结果 |
| `overview_001_050.png` / `overview_051_100.png` | 100 个真实叶型总览（统一坐标），标注 Case/组/主要变化参数/QC |
| `sensitivity_heatmap.png` | 13 参数 × 7 指标敏感性热力图（含决策标记） |
| `audit/` | Step 0 审计、冻结资产 SHA256（运行前后）、运行元数据与验收记录 |

### F.2 复现命令

```bash
cd /home/qian/compressor_ai4s
conda run -n ai4s python tools/geometry_parameter_sensitivity_v1.py all
conda run -n ai4s python -m pytest tests/test_geometry_legacy_v1_regression.py tests/test_geometry_parametric_exploratory_v1.py -q
```

单个 Case 的 4 位小数 `.dat` / `.geomTurbo` 可按需从 `profiles.npz` 的高精度坐标 + `code/geometry_parametric_exploratory_v1.py` 重新序列化得到；本轮默认不批量保存这两类文件。

### F.3 指标单位速查

| 指标 | 单位 | 说明 |
|---|---|---|
| contour_rms_dev_norm / contour_max_dev_norm | 基准弦长的比例 | 对称点到折线距离（未配准） |
| contour_rms_dev_aligned_norm | 基准弦长的比例 | 平移/旋转/缩放到基准后的形状差 |
| meanline_rms_dev_norm | 基准弦长的比例 | 同一 xc 网格的中弧线偏移 |
| thickness_*_rms_dev_norm | 基准弦长的比例 | 半厚度差（前/中/后段） |
| le/te_radius_change_rel | 相对值 | 仅当两侧圆弧拟合均有效时给出 |
| le/te_region_rms_dev_norm | 基准弦长的比例 | 边缘 5% 弦长区域（含拼接弦与相邻叶面） |
| min_gap_m / periodicity_m | m | 弦长 0.06 m、pitch = 0.06/Solidity |
| S_* | 无量纲/整个参数范围 | 见 `screening_criteria.yaml` |

### F.4 限制与不确定性

1. 判据阈值是**暂定研究阈值**，没有用历史 1891 样本校准；`criteria_status` 明确标为 `TENTATIVE_RESEARCH_THRESHOLDS_NOT_CALIBRATED`。
2. 只有 100 个 Case，且第三阶段只有 5 个锚点 + 15 个单参数变体；不能据此断言参数的全局无效性。
3. 2×2 耦合只有 4 个角点，只提供局部交互证据；不能外推整个二维参数域。
4. 本轮的“低敏感”只针对**已测试范围与背景**；缺少第二个背景时一律 REVIEW。
5. 前/尾缘圆弧拟合使用 legacy 插入的 7 个真实轮廓点；拼接弦（`Ncirc` 少插一点造成）与相邻叶面被排除在半径拟合之外，但通过 `*_junction_angle_jump_deg` 与 `*_region_rms_dev_norm` 单独记录。
6. 曲率指标使用 B 样条 + 分辨率稳定性检查；不稳定时标记为不可靠，且不参与分类。
7. 本轮没有运行 NUMECA / CFX；`geometry_ok=1` 不代表气动合理、网格可生成或 CFD 可收敛。
8. 未使用 AI/视觉评分来替代数值判据；所有决策均来自 `screening_criteria.yaml` 的保存规则。

### F.5 结论可追溯性

本报告中的每个数字都可用以下方式追溯：

- 参数级数字 → `parameter_sensitivity.csv` / `parameter_decisions.csv`；
- Case 级数字 → `case_metrics.csv`（Case ID 关联）；
- 参数取值与选择理由 → `case_design.csv`；
- 自适应选择 → `stage3_selection.json`；
- 运行环境与哈希 → `provenance.json`；
- 阈值与规则原文 → `screening_criteria.yaml`。


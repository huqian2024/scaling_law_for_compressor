# Ks1 / Ks2 专项几何复核 V1（57 Cases）

> 状态：**EXPLORATORY / NOT APPROVED**。本轮只做几何生成、几何 QC 与参数冗余/替代性分析；**没有** NUMECA、**没有** CFX、**没有** AI 训练、**没有** 修改正式 DOE 或正式生产范围。
> 判据：`ks1_ks2_review_v1_tentative` / `1.0.0`（TENTATIVE_RESEARCH_THRESHOLDS_NOT_CALIBRATED）。
> Case 号段：`C830001..C830057`；Git HEAD：`02e57d1d26197d97e65f4b64ef0a23f6d06393b7`。

## 0. 执行前审计（摘要）

```text
Ks1: SSm1 = Ks1*(Sm2-Sm1) -> a1,a2,a3(=SSm1),a5,a6
Ks2: SSm2 = Ks2*(Sm2-Sm1) -> a1,a2,a5,a6,a7(=-SSm2)
Sm1=tan(Metal1), Sm2=tan(Metal2), Sm0=tan(Metal1+(Metal2-Metal1)*K_m)
Xmean: piecewise break point and denominators of a1,a2,a5,a6
SS1=3.2, SS2=0.8: FIXED_BY_REVIEW in every case
```

上一轮 Ks1 与 Xmean 的 0.994 余弦来自 14 维符号响应签名；本轮改用 95 维、按 xc 采样的中弧线/切线角/曲率/压力面/吸力面响应向量，并加入多背景、残差投影和单参数替代搜索。

## 1. 实验设计

```text
正式 Case 数        : 57
阶段分布            : A=15, B=30, C=12
几何生成成功        : 57/57
实验硬性 QC 通过    : 57/57
冻结 QC 复核通过    : 57/57
参数向量重复组数    : 0
失败 Case 数        : 0（全部保留在 case_metrics.csv）
```

本批 57 个 Case 全部生成成功且硬性 QC 通过；这不代表工程合理或 CFD 可收敛。

### 1.1 背景与 Stage C 选择

| 背景 | 修改参数 |
|---|---|
| B0 | 全局基准 |
| B1 | Xmean=0.06, K_m=0.1 |
| B2 | Xmean=0.06, K_m=0.35 |
| B3 | Xmean=0.18, K_m=0.1 |
| B4 | Xmean=0.18, K_m=0.35 |
| B5 | Metal1=48, Metal2=0 |
| B6 | Metal1=58, Metal2=32 |

Stage C 选择结果：**B4, B2, B5**。规则与得分见 `stage_c_selection.json`：B1–B4 按背景的中弧线角范围排序，取最低与最高；B5/B6 取中弧线角范围更大的一个。

## 2. Ks1 专项复核

| 背景 | 参考 Case | Ks1=7 Case | S_shape | S_local | cos raw | cos block | 残差比例 | 最佳 Xmean | 替代残差比例 | 反向替代残差比例 |
|---|---|---|---|---|---|---|---|---|---|---|
| B0 | C830001 | C830008 | 0.2256 | 0.1038 | 0.9936 | 0.9935 | 0.1128 | 0.0948 | 0.04881 | 0.5929 |
| B1 | C830016 | C830018 | 0.1506 | 0.1072 | 0.9617 | 0.988 | 0.2741 | 0.0768 | 0.01792 | 0.5164 |
| B2 | C830021 | C830023 | 0.5315 | 0.127 | 0.9577 | 0.9873 | 0.2879 | 0.0648 | 0.08543 | 0.8585 |
| B3 | C830026 | C830028 | 0.3731 | 0.05088 | 0.7972 | 0.9506 | 0.6037 | 0.18 | 1 | 0.09343 |
| B4 | C830031 | C830033 | 0.2292 | 0.05799 | 0.7732 | 0.8479 | 0.6341 | 0.18 | 1 | 0.7395 |
| B5 | C830036 | C830038 | 0.2388 | 0.1221 | 0.9923 | 0.9941 | 0.1242 | 0.0954 | 0.04925 | 0.5807 |
| B6 | C830041 | C830043 | 0.1315 | 0.07325 | 0.9926 | 0.9933 | 0.1218 | 0.0954 | 0.04492 | 0.579 |

> `残差比例` = Ks1 响应中不能被 Xmean 方向解释的部分；`替代残差比例` = 最优单 Xmean 替代后的轮廓残差 / 目标变化量。两者接近 0 才说明可替代，接近 1 说明几乎不可替代。

- **Q1. Ks1 在多少个背景下有明显几何作用？** 在 7/7 个背景中达到 `S_shape >= 0.01` 或 `S_local >= 0.02`，且信号超过 4 位小数噪声 10 倍。
- **Q2. Ks1 与 Xmean 的相似度是否稳定？** cos raw 最小/中位/最大 = 0.7732 / 0.9617 / 0.9936；block-weighted 最小/最大 = 0.8479 / 0.9941。**不稳定**：高 Xmean 背景（B3/B4）的余弦明显下降，不能用上一轮单一 0.994 概括全部背景。
- **Q3. 调整 Xmean 能否近似替代 Ks1？** 5/7 个背景的最优单 Xmean 替代残差 ≤ 25%（最小 0.01792，中位数 0.04925），主要发生在 B0/B1/B2/B5/B6；但 B3/B4（Xmean=0.18 边界）替代残差为 1.0，说明高 Xmean 端无法用 Xmean 自己复现 Ks1。因此只能得出“**在中低 Xmean 背景下高度可替代、在高 Xmean 边界不可替代**”，不能宣称全局等价或全局独立。
- **Q4. Ks1 是否值得作为独立变量保留？** 自动判据：**FURTHER_REVIEW**（K1_REVIEW），倾向标记：`FIX_IF_HIGH_XMEAN_REGION_EXCLUDED`。Ks1 effect is resolved in all backgrounds and a single Xmean reproduces it in 5/7 backgrounds, but the high-Xmean backgrounds hit the Xmean range boundary; therefore neither global equivalence nor global independence is proven.
  关键判断：在 Xmean=0.18 的高端，Xmean 已无上移空间，B3/B4 的 Ks1 变化无法被 Xmean 复现（替代残差 1.0），而 Ks1 反而能在 B3 较好复现 Xmean（反向残差约 0.09）；因此 **Ks1 在高 Xmean 端提供了 Xmean 范围外的独立形状**，但在中低 Xmean 端高度冗余。是否保留取决于下一轮是否保留 Xmean 高端。

**Ks1 的局部证据**：Ks1 只进入中弧线系数，不进入 LE/TE 圆弧半径公式，因此前/尾缘半径变化为 0；其独立价值只能在 中弧线/压力面/吸力面 形状中寻找。上表的 `S_local` 与替代残差必须一起看，不能只用余弦判断。

## 3. Ks2 专项复核

| 背景 | Ks2=0.20 Case | S_shape | S_rear | 后段 meanline | 后段 angle | 后段 κ | 后段 pressure | 后段 suction | SNR rear | cos vs K_m | cos vs Metal2 | 替代残差(K_m) | 替代残差(Metal2) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | C830015 | 0.01249 | 0.08202 | 0.01185 | 0.02006 | 0.1084 | 0.01189 | 0.0118 | 2.17e+03 | -0.09517 | 0.5247 | 0.2757 | 0.1601 |
| B1 | C830020 | 0.01039 | 0.08332 | 0.0117 | 0.01973 | 0.11 | 0.01175 | 0.01165 | 2.26e+03 | -0.1627 | 0.4394 | 1 | 0.1448 |
| B2 | C830025 | 0.01492 | 0.0829 | 0.01383 | 0.02168 | 0.1105 | 0.01384 | 0.01381 | 2.01e+03 | -0.2705 | 0.3802 | 0.2659 | 0.1823 |
| B3 | C830030 | 0.01008 | 0.07957 | 0.008291 | 0.01746 | 0.1051 | 0.008341 | 0.008242 | 2.33e+03 | -0.2516 | 0.1427 | 1 | 0.09926 |
| B4 | C830035 | 0.00945 | 0.07695 | 0.009427 | 0.01887 | 0.1017 | 0.009474 | 0.009381 | 2.15e+03 | -0.3396 | 0.4114 | 0.2933 | 0.2316 |
| B5 | C830040 | 0.01373 | 0.08919 | 0.01348 | 0.02281 | 0.1188 | 0.01348 | 0.01347 | 2.2e+03 | -0.06811 | 0.5351 | 0.2956 | 0.1813 |
| B6 | C830045 | 0.007764 | 0.05904 | 0.009308 | 0.01409 | 0.07763 | 0.009364 | 0.009252 | 1.86e+03 | -0.1498 | 0.5137 | 0.2644 | 1 |

> `S_rear` 使用后 30% 弦长（xc>0.70）的 meanline/angle/curvature/pressure/suction 最大值；`SNR rear` 为该变化量相对同 Case 4 位小数序列化噪声的倍数。

- **Q5. Ks2 在什么背景下最敏感？** `B5` 最高，S_rear=0.08919；`B6` 最低，S_rear=0.05904。全部 7 个背景 S_rear 约 0.05904–0.08919（约 1.5 倍差异），不是只在单一极端背景出现。后段曲率分量 0.07763–0.1188，约为后段 meanline/angle 分量的 5–10 倍，说明 Ks2 主要控制**尾段中弧线曲率**，而不是整体平移。
- **Q6. Ks2 的局部几何作用是否达到实际可分辨程度？** 在 7/7 个背景中 `S_rear >= 0.01` 且 SNR ≥ 10；SNR 约 1.86e+03–2.2e+03，远高于 4 位小数序列化噪声，已达到可分辨的后段局部作用。上一轮全局 S_comp=0.0053 明显低估了它：本轮的 S_rear 约 0.059–0.089，是全局值的 11–17 倍，原因是上一轮加权主要看全局轮廓/中弧线 RMS，没有单独加权后 30% 曲率。
- **Q7. Ks2 是否值得保留？** 自动判据：**FURTHER_REVIEW** （K2_REVIEW），倾向标记：`KEEP_IF_METAL2_SUBSTITUTION_REJECTED`。Ks2 has a strong, resolved rear-local effect in 7/7 backgrounds (S_rear about 0.06-0.09 per unit u), but single-parameter K_m/Metal2 substitution reaches <=25% contour residual in 6/7 backgrounds; independent geometry value is therefore not proven even though the effect is clearly resolvable.
  绝对值补充：Ks2=0.20 的轮廓目标变化 RMS 约 0.002553–0.004232 弦长；Metal2 替代后的残差 RMS 约 0.0002534–0.002586 弦长。这属于“轮廓接近但响应方向不同”，是否可接受需要工程判断，不能仅凭余弦或单一残差阈值决定。

**尾缘拼接诊断**：legacy 只插入 Ncirc=4 个圆弧点，TE 拼接角跳变约 23°，本轮把它作为独立诊断量记录；Ks2 的局部作用不能归因于该既有跳变。若 Ks2 的高精度变化存在、但 4 位小数输出大量抹除，报告中会以 SNR 明确标出，不会因此直接删除参数。

## 4. Ks1 × Ks2 联合扫描（Stage C）

| 背景 | 四角 Case | 平均交互指数 | 轮廓 | 中弧线 | 后段 meanline | 后段 angle | 后段 κ |
|---|---|---|---|---|---|---|---|
| B4 | C830046, C830047, C830048, C830049 | 15.77 | 6.532 | 5.975 | 5.995 | 7.061 | 32.03 |
| B2 | C830050, C830051, C830052, C830053 | 4.868 | 5.432 | 5.978 | 5.997 | 5.767 | 4 |
| B5 | C830054, C830055, C830056, C830057 | 10.74 | 6.276 | 5.978 | 5.997 | 5.95 | 0.1305 |

> 交互指数 = |(f_HH - f_LH) - (f_HL - f_LL)| / |f_HH - f_LL|；指数 >1 表示两端总变化 f_HH - f_LL 很小（相互抵消），不代表计算错误；B4/B5 的指数远大于 1 说明四角总变化接近抵消，不能读成“15 倍耦合强度”，应结合四角 Case 的绝对指标解读；仅 3 个背景 × 4 角点，只能作为局部证据。

## 5. 参数决策与证据

| 参数 | 决策 | 倾向 | 规则 | 已分辨背景 | cos 中位/最大 | 替代残差最小/中位 | 替代残差超阈值背景 | 噪声受限背景 |
|---|---|---|---|---|---|---|---|---|
| `Ks1` | **FURTHER_REVIEW** | `FIX_IF_HIGH_XMEAN_REGION_EXCLUDED` | K1_REVIEW | 7/7 | 0.9617 / 0.9936 | 0.01792 / 0.04925 | 2/7 | 0/7 |
| `Ks2` | **FURTHER_REVIEW** | `KEEP_IF_METAL2_SUBSTITUTION_REJECTED` | K2_REVIEW | 7/7 | 0.03729 / 0.5351 | 0.09926 / 0.1813 | 1/7 | 0/7 |

**三个最关键的定量证据（Ks1）**：
1. 最高余弦背景 `B0`：cos=0.9936，但残差比例=0.1128，最佳 Xmean=0.0948，替代残差比例=0.04881（C830008）。
2. 最低替代残差背景 `B1`：替代残差比例=0.01792，说明该背景下 Xmean 可以较好复现 Ks1（C830018）。
3. 最高替代残差背景 `B3`：替代残差比例=1，说明该背景下单一 Xmean 无法复现 Ks1（C830028）。

**三个最关键的定量证据（Ks2）**：
1. 最强后段作用背景 `B5`：S_rear=0.08919，SNR=2.2e+03（C830040）。
2. 最弱后段作用背景 `B6`：S_rear=0.05904，SNR=1.86e+03（C830045）。
3. 最佳可替代背景 `B3`：min(K_m, Metal2) 替代残差比例=0.09926（C830030）。

## 6. SS1 / SS2 固定状态（Q9）

```text
SS1 = 3.2  FIXED_BY_REVIEW  decision_source = HUMAN_REVIEW_DECISION
SS2 = 0.8  FIXED_BY_REVIEW  decision_source = HUMAN_REVIEW_DECISION
```

**Q9 回答：是。** 全部 57 个 Case 的 `SS1`/`SS2` 均分别等于 3.2/0.8；`geometry_parameter_candidates_v2.yaml` 中两者均标记为 `FIXED_BY_REVIEW`，并注明 `decision_source = HUMAN_REVIEW_DECISION`（人工决定，不是自动判据批准）。生成器仍接受这两个参数，历史几何兼容性未被破坏；候选配置没有修改正式六维 DOE 或任何冻结生产配置。

## 7. 异常、失败与限制

本轮声明范围内没有失败 Case；这不证明范围外安全，也不证明工程合理。
- **Q8. 本轮是否发现新的几何异常？** 硬性 QC 失败 0 个；`min_gap` 范围 24.09–32.78 mm（全部 >0）；LE 拼接角跳变 8.634–12.06°，TE 23–23.07°。B2/B3/B4/B5 等背景出现强弯/近 S 形中弧线，但均通过硬性 QC；这是探索范围内的形状，不是新的 QC 异常，工程合理性仍需人工判断。

1. 判据阈值是暂定研究阈值，未用历史 1891 样本校准。
2. 只有 7 个背景、3 个 Stage C 背景和 4 个角点；不能外推到整个参数域。
3. 替代搜索只允许**单一参数**（Xmean 或 Ks1 或 K_m 或 Metal2），不代表两参数/三参数组合不能替代；它只检验“单参数可替代性”。
4. Ks1/Ks2 只影响中弧线系数，不改变厚度分布或 LE/TE 圆弧半径；因此不能用厚度/边缘半径指标判断它们。
5. 4 位小数序列化噪声已逐 Case 计算；若信号低于 10 倍噪声，一律视为未分辨，不会因为文本四舍五入而删除参数。
6. 本轮没有运行 NUMECA / CFX；`geometry_ok=1` 不代表气动合理、网格可生成或 CFD 收敛。
7. 所有自动结论均为建议，不改变正式参数状态。

## 8. 仍需人工审查（Q10）

- **Ks1 最终去留**：当前自动结论 `FURTHER_REVIEW`，倾向 `FIX_IF_HIGH_XMEAN_REGION_EXCLUDED`。关键矛盾是：Xmean 在 B0/B1/B2/B5/B6 可用2–8.5% 轮廓残差复现 Ks1=7，但 B3/B4 的 Xmean 已在 0.18 边界，无法复现；同时 Ks1 可在 B3 较好复现 Xmean（反向残差约 0.09），说明高 Xmean 端Ks1 可能提供超出 Xmean 范围的独立方向。需要人工决定是否保留 Xmean 高端，或将 Ks1 作为高端补充变量。
- **Ks2 最终去留**：当前自动结论 `FURTHER_REVIEW`，倾向 `KEEP_IF_METAL2_SUBSTITUTION_REJECTED`。Ks2 的后段局部作用在所有背景都远超噪声，但 Metal2 单参数替代在 6/7 背景可把轮廓残差压到 10–23%；需要人工确认这种“轮廓接近但方向不同”的替代是否可接受，以及 Ks2 的后段控制是否有独立工程价值。
- 是否用 1891 历史样本校准本轮阈值，尤其是 `keep_rear`、`cosine_independence`、`substitution_max_residual`。
- 是否需要在 Xmean 低/中/高三个背景下加密 Ks1，或用多参数替代搜索复核。
- SS1/SS2 已由人工决定固定；若未来修改生成器的边缘圆 St1/St2 重算逻辑，必须另开几何算法版本并重新评估，不得把算法变化误认为参数效应。

## 9. 复现

```bash
cd /home/qian/compressor_ai4s
conda run -n ai4s python tools/geometry_ks1_ks2_review_v1.py all
conda run -n ai4s python -m pytest -q
```

文件追溯：`case_design.csv`（57 Case 参数/背景/规则）、`case_metrics.csv`（状态/QC/指标）、`ks1_xmean_redundancy.csv`、`ks2_background_sensitivity.csv`、`joint_interaction.csv`、`parameter_decisions.csv`、`profiles.npz`、`review_criteria.yaml`、`provenance.json`。


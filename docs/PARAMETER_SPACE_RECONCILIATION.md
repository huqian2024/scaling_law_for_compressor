# 参数空间与 DOE 维度对照（2026-10-21）

> 目的：消除“历史 6 维冻结 DOE”与“当前 13 维探索性参数空间”之间的**记录性矛盾**。
> 本文档只做**对照与阶段划分**，不冻结任何新维度，也不修改任何历史记录。
>
> **2026-10-21 后续（同日）**：方案 A 已冻结为 GeomTurbo **几何生成**范围
> （`config/geometry_ranges_frozen_a.yaml`，Metal2 6.0–32.0，其余不变）。
> 默认生成量 200000 只是暂定值（PROVISIONAL / NOT FINAL），
> 实际生产数量 PENDING USER DECISION。
> 本文的阶段划分（生产 DOE d=6 vs 探索 11+2）仍然成立；
> 冻结细节见 `docs/GEOMTURBO_PRODUCTION_200K.md`，`FINAL_PRODUCTION_RANGES` 仍 PENDING。

```text
权威边界:
  2026-10-13 生产规模 / DOE 方法 / 参数顺序的冻结记录
      -> docs/DESIGN_FREEZE_2026-10-13.md   （保留，不覆盖）
  FINAL_PRODUCTION_RANGES
      -> 仍为 PENDING
  本文档的结论
      -> 只解释两个阶段各自适用什么，不做最终 DOE 维度决策
```

## 1. 两个阶段

| 项目 | 阶段 A：生产 DOE（2026-10-13 冻结） | 阶段 B：几何参数研究（2026-10-17，探索性） |
|---|---|---|
| 维度 | **6**：`Xthick, Tmax, Metal2, Solidity, Incidence, Mach` | **13 个命名量**：11 个开放几何参数 + 2 个运行参数（`SS1`/`SS2` 固定） |
| 采样方法 | scrambled Sobol，`d=6`，seed=1，prefix nesting | 确定性单因素 / 2×2 耦合 / 自适应锚点（`tools/geometry_*`），不是生产采样器 |
| 范围 | legacy 范围（`config/ranges_legacy.yaml`），**不是**最终生产范围 | 探索范围（`final_geometry_parameters.yaml`），**未批准** |
| 用途 | 未来 100k/20k 生产数据 | 决定哪些几何参数保留、哪些固定、边界是否收紧 |
| 状态 | 方法冻结；`FINAL_PRODUCTION_RANGES = PENDING` | 实验完成；2026-10-21 方案 A 已冻结为**几何生成**范围（仍非 CFD 生产范围） |
| 结论效力 | 可支撑生产，但缺范围 | 不能支撑生产，也不能当作 CFD 认证 |

```text
关键结论 1：13 维是“当前研究空间”，不是“已冻结的生产 DOE”。
关键结论 2：生产 DOE 目前仍记录为 d = 6；是否改成更多维，需要 owner/导师决策，
           本仓库不做该决策，也不修改 2026-10-13 的冻结文件。
关键结论 3：生产路线语义（ONE_6D_POINT_ONE_CASE）本身未变，
           但名称里的 “6D” 绑定在冻结维度上；若生产维度变更，该常量需重新冻结。
```

## 2. “13” 的两种含义（易混淆，必须区分）

```text
(a) 生成器的 13 个形状参数（code/geometry_parametric_exploratory_v1.py PARAM_NAMES）:
    Xthick Tmax Metal2 Solidity Metal1 T1 T2 Xmean K_m Ks1 Ks2 SS1 SS2
    -> 包含 SS1/SS2，不包含 Incidence/Mach

(b) final_geometry_parameters.yaml 的 “13 维候选空间”:
    11 个开放几何参数 + 2 个运行参数 (Incidence, Mach)
    -> SS1/SS2 是固定值，不计入自由度
```

两者数量都是 13，但**集合不同**。引用时必须写清是“生成器参数个数”还是
“候选自由度”。当前探索性结论使用的是 (b)。

## 3. 参数维度对照表

| 参数 | 物理含义（代码事实） | 历史 6D DOE 状态 | 当前探索状态 | 范围来源 | 是否待决策 |
|---|---|---|---|---|---|
| `Xthick` | 厚度多项式断点（`xc <= Xthick` 段），无量纲弦向位置；同时进入 `St1/St2` 分母 | 维度 0，可变 | KEEP 0.10–0.60 | 历史：`ranges_legacy.yaml` 0.15–0.45；当前：`final_geometry_parameters.yaml` | 是（生产范围） |
| `Tmax` | 最大厚度（无量纲，配合 `CHORD_TARGET=0.06` 缩放） | 维度 1，可变 | KEEP 0.025–0.095 | 同上（0.04–0.07） | 是（生产范围） |
| `Metal2` | 出口金属角（deg）；`Sm2 = tan(Metal2)` | 维度 2，可变 | KEEP 0–32 deg | 同上（6–24） | 是（下界建议收紧，见人工评审分析） |
| `Solidity` | 稠度；**只**通过 `periodicity = 0.06 / Solidity` 进入几何，单叶型坐标不变 | 维度 3，可变 | KEEP 0.7–2.5 | 同上（1.0–2.0） | 是（是否保留为生产维度） |
| `Incidence` | 入口气流角工况变量；仓库内**无** CFX 入口边界实现 | 维度 4，可变（−4 – 4 deg） | 固定 0 deg，仅元数据 | 历史：`ranges_legacy.yaml`；当前：`METADATA_FIXED` | 是（CFX 实现仍 TBD） |
| `Mach` | 来流马赫数工况变量 | 维度 5，可变（0.3–0.7） | 固定 0.5，仅元数据 | 同上 | 是（CFX 实现仍 TBD） |
| `Metal1` | **入口金属角**（deg），legacy 为 `48 + DeltaBeta(5) = 53`；不构造入射角关系 | **不是** DOE 变量，legacy 常量（53） | KEEP 48–58 deg | `code/geometry_legacy_v1.py:37`；当前：`final_geometry_parameters.yaml` | 是（是否进入生产维度） |
| `T1` | 前缘厚度（无量纲） | legacy 常量 0.015 | KEEP 0.010–0.018 | 同上 | 是（生产范围） |
| `T2` | 尾缘厚度（无量纲） | legacy 常量 0.0125 | KEEP 0.008–0.016 | 同上 | 是（生产范围） |
| `Xmean` | 中弧线分段断点（弦向比例） | legacy 常量 0.08 | KEEP 0.06–0.18 | 同上（上界不扩展） | 是（上界已记录为保守值） |
| `K_m` | 在 `Xmean` 处已完成折转的比例（`Sm0`） | legacy 常量 0.18 | KEEP 0.10–0.35 | 同上 | 是（高端边界待收紧） |
| `Ks1` | 前段中弧线斜率乘子 | legacy 常量 5.0 | KEEP 3.0–7.0 | 同上 | 是（生产范围） |
| `Ks2` | 后段中弧线斜率乘子 | legacy 常量 0.10 | KEEP 0.05–0.20 | 同上 | 是（生产范围） |
| `SS1` | 前段厚度变化系数（`St1`） | legacy 常量 3.2 | **固定 3.2**（`FIXED_BY_REVIEW`） | `code/geometry_legacy_v1.py:44`；人工评审决定 | 否（除人工重新开启） |
| `SS2` | 后段厚度变化系数（`St2`） | legacy 常量 0.8 | **固定 0.8**（`FIXED_BY_REVIEW`） | `code/geometry_legacy_v1.py:45`；人工评审决定 | 否（除人工重新开启） |

说明：

```text
- 历史 6D DOE 的范围是 legacy 范围，不是最终生产范围（FINAL_PRODUCTION_RANGES 仍 PENDING）。
- 当前 KEEP 范围来自 parameter_final_decision_v1/final_geometry_parameters.yaml，
  仅是探索性候选，不是生产批准。
- SS1/SS2 在 C820（100-case）扫描中仍是变量（2.4-4.0 / 0.5-1.1），
  之后才被人工固定为 3.2 / 0.8；历史记录不得改写。
```

## 4. `Metal1` 与 `Incidence` 的关系（重点核对）

```text
Metal1     = 叶片入口金属角（几何量），legacy = 48 + DeltaBeta(5) = 53 deg
Incidence  = 入口气流角相对金属角的工况变量（气动量）
```

代码事实：

```text
code/geometry_parametric_exploratory_v1.py
  L30  "Metal1 is the inlet *metal* angle. No incidence relation is constructed."
  L41  Incidence / Mach are operating conditions and MUST NOT enter this module
  L91  METADATA_FIXED = {"Incidence": 0.0, "Mach": 0.5}
code/geometry_legacy_v1.py
  L37  Metal1 = 48 + DeltaBeta   (DeltaBeta = 5)
```

已验证事实与未决事项：

```text
已确认：只改 Incidence / Mach，.dat 与 .geomTurbo 逐字节相同
        -> 二者不改变叶型，只能作用在 CFX 入口边界条件
未决 1：CFX 中 Incidence 的实现方式（相对金属角 / 相对轴向）仍未确认，禁止猜测
未决 2：legacy 注释写 “zero-incidence 49 deg”，代码为 Metal1 = 53 deg，
        4 deg 差异原因未确认（docs/SESSION_DELIVERY_2026-10-15.md 第 3 节）
未决 3：Incidence 与 Metal1 是否在正式 DOE 中解耦（即金属角作为设计变量、
        气流角作为工况变量）需要 owner 决策
```

因此：**不得**把 `Metal1` 当作 `Incidence`，也不得用 `Metal1` 的范围去推导
`Incidence` 的范围。二者在 6D DOE 中一个不存在（常量）、一个是工况维度。


## 5. 独立性与实际使用方式（来自 C820 实测，不是假设）

```text
Solidity     : 只改栅距（0.06/S），单叶型坐标完全不变（S_cascade 主导，单叶指标为 0）
Incidence/Mach: 完全不改变几何（只能进 CFX 边界条件）
Xmean / Ks1  : 响应余弦 = 0.994，Ks1/Xmean 敏感度比 = 0.151 -> 高度共线
Metal1 / K_m : 响应余弦 = 0.625 -> 部分重合，需要联合评审
Xmean × K_m  : 2x2 平均交互指数 4.643 -> 明显交互（局部证据）
T1 / T2      : 局部效应（前缘 / 尾缘），对中弧线 S_camber = 0
SS1 / SS2    : 几何敏感度低；但 legacy 在 LE/TE 圆处重算 St1/St2 时不乘 SS1/SS2，
               低敏感度有一部分来自实现事实，不能外推为“厚度分布无关”
```

来源：`analysis/geometry_review/parameter_sensitivity_v1_100cases/REPORT.md`
（B / B.2 / B.3 / D 节）。这些是**几何响应**层面的相关性，不是输入参数相关系数。

## 6. 联合约束 `JC_XMEAN_KS1_KM` 的当前状态

```text
定义      : K_m >= 0.15
适用区间  : 0.18 < Xmean <= 0.20
当前上界  : Xmean <= 0.18（final_geometry_parameters.yaml）
active_at_final_bound : false
来源      : parameter_final_decision_v1/final_decision_criteria.yaml, FINAL_DECISION.md
```

核对结果：

```text
- 当前 Xmean 上界为 0.18，适用区间 (0.18, 0.20] 为空集
  -> 在最终采纳范围下该条件无法触发（不是“已满足”，而是“不存在适用点”）
- 它是 2026-10-17 为“若 Xmean 扩展到 0.20”准备的候选约束，
  随“不扩展上界”的决定而被记录为非激活状态
- 因此：不得写成当前生产必须执行的硬性约束；不得在采样器中实现
```

当前研究决策（2026-10-21）：

```text
尽可能使用简单单参数约束，不优先采用复杂联合约束。
-> 该联合约束保持“历史候选 / 当前不激活”记录，不进入采样器。
-> 历史判据与实验结果不修改。
```

## 7. 待决策清单（不由 Agent 决定）

```text
1. 生产 DOE 维度：维持 6 维，还是改为 11 几何 + 2 运行（并重新冻结 d / 参数顺序）
2. FINAL_PRODUCTION_RANGES（始终 PENDING）
3. Solidity 是否保留为生产维度（当前只影响栅距）
4. Metal1 是否进入生产维度（当前只是 legacy 常量 / 探索参数）
5. Incidence / Mach 的 CFX 实现与 4 deg 注释差异
6. K_m 上界与 Metal2 下界是否收紧（见人工评审分析，仅为建议）
7. 若生产维度改为 13，`PRODUCTION_ROUTE = ONE_6D_POINT_ONE_CASE` 的名称需重新冻结
```

## 8. 核对方式（可复现，只读）

```bash
cd /home/qian/compressor_ai4s
grep -n "PARAM_NAMES" -A 4 code/geometry_parametric_exploratory_v1.py
grep -n "METADATA_FIXED\|Incidence\|Mach" code/geometry_parametric_exploratory_v1.py
grep -n "Metal1\|SS1\|SS2\|Xmean\|K_m\|Ks1\|Ks2\|T1\|T2" code/geometry_legacy_v1.py | head -20
cat config/ranges_legacy.yaml
grep -n "PARAMETER ORDER\|d        = 6\|Parameter order" -A 8 docs/DESIGN_FREEZE_2026-10-13.md
cat analysis/geometry_review/parameter_final_decision_v1/final_geometry_parameters.yaml
```


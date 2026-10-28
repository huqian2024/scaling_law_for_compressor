# GeomTurbo 生产阶段完成报告（195,000 个候选几何）

日期：2026-10-28
阶段状态：**COMPLETED（仅几何文件生成 + 文件级快速检查）**

```text
GEOMTURBO_GENERATION_COMPLETED
SANITY_CHECK_PASSED

Geometry QC                    NOT YET PERFORMED
CFD Operating Conditions        PENDING FINAL DESIGN
CFD Dataset Construction        NOT STARTED
```

> 本报告记录已完成的三组 11D GeomTurbo 候选几何生产及其文件级快速检查。
> 检查只覆盖文件数量/大小、Manifest 与 Summary 一致性、参数合法性、有限哈希抽检；
> **未执行**几何质量 QC、NUMECA 导入、网格生成、CFD 求解或气动有效性检查。
> 不得据此声称“195,000 个几何全部通过几何 QC”或“全部 CFD-ready”。

## 1. 生产配置与脚本入口

```text
运行配置        config/geometry_ranges_frozen_a.yaml
                config_id = geometry_ranges_frozen_a
                status    = FROZEN（几何生成范围，非 CFD 生产范围批准）
                config_sha256 = 0eac51fd33cb6fac0a3f1457118e6609c72fa7fdd2b6144403b5c936cc34242d

采样            11D scrambled Sobol（scipy.stats.qmc.Sobol, scramble=True）
                native 顺序；组内 D_N = 前 N 个点（prefix nesting）
参数顺序        Xthick, Tmax, Metal2, Solidity, Metal1, T1, T2, Xmean, K_m, Ks1, Ks2
固定参数        SS1 = 3.2, SS2 = 0.8
模板            legacy/blade_batch_generation_template.geomTurbo
                sha256 = 92c4296f2de27440aebaad9b03b9af4f9e09756fabff2298f4607a87f2c55119
生成器          code/geometry_parametric_exploratory_v1.py + code/geometry_legacy_v1.py
                （冻结数学与序列化，本次未修改）

启动入口        code/run_geomturbo.py（推荐）
底层生成器      code/generate_geomturbo_production.py（需要显式 --execute）
batch 大小      5000 个 Case / batch
Case ID         G + 7 位数字（G0000001…），组内重复，组间不混淆
全局身份        group + seed + sobol_index（每组 group_info.json 记录）
```

实际启动命令（已完成，保留用于复现或后续扩展）：

```bash
python code/run_geomturbo.py --group train --N 150000 --seed 101
python code/run_geomturbo.py --group val   --N 15000  --seed 202
python code/run_geomturbo.py --group test  --N 30000  --seed 303
```

## 2. 三组规模、种子与批次

| Group | 几何数量 | Sobol Seed | Batch 数量 | 输出目录 |
|---|---:|---:|---:|---|
| Train | 150,000 | 101 | 30 | `production_geomturbo/train/` |
| Validation | 15,000 | 202 | 3 | `production_geomturbo/val/` |
| Test | 30,000 | 303 | 6 | `production_geomturbo/test/` |
| **Total** | **195,000** | — | **39** | — |

```text
Seed 来源     各组 config_snapshot.yaml / group_info.json 实测记录（非推定）
Batch 结构    Train 30 × 5000；Validation 3 × 5000；Test 6 × 5000
Sobol m       Train 18 (2^18 = 262144)；Val 14 (16384)；Test 15 (32768)
指纹          三组 fingerprint 互不相同（seed 不同）
              train 58db9f4d… ; val 6786b851… ; test d243b092…
```

## 3. 生成完成情况

| Group | 请求数量 | 本次写入 | 跳过 | 失败 | completed | 耗时 |
|---|---:|---:|---:|---:|---|---:|
| Train | 150,000 | 150,000 | 0 | 0 | true | 305.1 s |
| Validation | 15,000 | 15,000 | 0 | 0 | true | 27.3 s |
| Test | 30,000 | 30,000 | 0 | 0 | true | 54.6 s |

```text
完成时间（本地，+08:00）
  Validation  2026-10-28 14:02:18
  Test        2026-10-28 14:04:58
  Train       2026-10-28 14:10:23

三组目录各自保留：
  manifest.csv（根级，195,000 行合计）
  batch_XXXXXX/manifest.csv（39 个批次清单）
  config_snapshot.yaml
  generation_summary.json
  group_info.json
```

## 4. 文件级 Sanity Check（已执行）

检查方式：只读取文件系统元数据、`manifest.csv`、`generation_summary.json`、
`group_info.json`、`config_snapshot.yaml`；每组随机抽取 20 个文件比对 SHA256。
未逐个解析 GeomTurbo 内容，未重新计算几何，未执行 QC / CFD。

| 检查项目 | Train | Validation | Test |
|---|---|---|---|
| 实际文件数 / 预期 | 150,000 / 150,000 | 15,000 / 15,000 | 30,000 / 30,000 |
| Manifest 记录数 | 150,000 | 15,000 | 30,000 |
| 生成成功 / 失败 | 150,000 / 0 | 15,000 / 0 | 30,000 / 0 |
| 缺失 / 多余 Case ID | 0 / 0 | 0 / 0 | 0 / 0 |
| 组内重复 Case ID | 0 | 0 | 0 |
| 空文件 | 0 | 0 | 0 |
| 文件大小异常 | 0 | 0 | 0 |
| 参数非法 / 越界 | 0 | 0 | 0 |
| 组内重复参数记录 | 0 | 0 | 0 |
| 批次数量 / batch manifest 异常 | 0 | 0 | 0 |
| 路径缺失 / 字段错位 | 0 / 0 | 0 / 0 | 0 / 0 |
| SHA256 抽检 | 20/20 通过 | 20/20 通过 | 20/20 通过 |
| Summary | `completed=True` 且与文件一致 | 同左 | 同左 |

```text
跨组检查
  种子       101 / 202 / 303，互不相同
  输出目录   三个独立目录，无交叉
  参数序列   三组首个 Case 参数不同（抽样核对），未出现同序列误用

批次检查
  每个 batch 恰好 5000 个 .geomTurbo；batch manifest 行数与文件数逐一相等
  无 .part / 临时文件残留；无意外文件名或额外批次
```

## 5. 文件大小与磁盘占用

| Group | 最小 | 最大 | 平均 | 中位数 | 总体积 |
|---|---:|---:|---:|---:|---:|
| Train | 14,317 B | 14,597 B | 14,322.9 B | 14,321 B | 2.148 GB |
| Validation | 14,317 B | 14,589 B | 14,323.1 B | 14,321 B | 0.215 GB |
| Test | 14,317 B | 14,587 B | 14,322.9 B | 14,321 B | 0.430 GB |
| **合计** | — | — | ≈14.323 KB | — | **2.793 GB** |

```text
实际磁盘分配（st_blocks）   3.195 GB
du -sh production_geomturbo 3.2G
目录表观字节（含 manifest） 2.937 GB
```

## 6. 已知限制

```text
1. 只做了文件级检查，没有解析或验证叶型几何。
2. 没有执行 geometry_qc_v1_hard 或任何几何质量 QC。
3. 没有做 NUMECA 导入测试、网格生成或 CFD 求解。
4. 没有验证可网格化、收敛性或气动性能。
5. SHA256 只抽检每组 20 个文件，未做全量哈希。
6. 未做跨组参数/几何去重（不同 seed 不保证无重复点）。
7. manifest 不含 group 与 QC 状态字段；组归属由目录与 group_info.json 表达。
8. 文件级检查通过 != 几何可用；后续必须补做 QC 与 CFD 侧验证。
```

## 7. 下一阶段任务

```text
A. 几何侧
   1. production pool（.geomTurbo + manifest）→ 冻结 geometry_qc_v1_hard 的适配器
   2. 几何 QC 结果清单（group / seed / sobol_index / QC 状态 / 原因）
   3. 明显不合理形状的筛除与拒绝记录（append-only）

B. 入口工况（Incidence / Mach）—— PENDING FINAL DESIGN
   4. 最终范围（暂沿用历史参考：Incidence −4°…+4°，Mach 0.3…0.7，未冻结）
   5. 采样方法与组合策略
   6. 每个几何对应一个还是多个工况（尚未决定）
   7. 入口参数 → NUMECA/CFX 边界条件的实现（CFD 侧）
   8. CFD Case Manifest 设计

C. CFD 侧（师兄服务器）
   9. 网格、边界条件、求解、收敛与有效性检查
  10. 返回“有效 / 无效 + 原因”的交接信息
```

## 8. 数据保留与可复现性

```text
生产数据位置    production_geomturbo/{train,val,test}/（保留在本地，未移动/删除）
Git 策略        /production_geomturbo/ 已被 .gitignore 忽略；3.2 GB 数据不进入仓库
                （本地打包文件 production_geomturbo.zip 同样不进入仓库）
可复现依据      frozen config + seed + Sobol 参数 + 模板/生成器哈希
                → 同一 config/seed/N 可逐字节复现（组内前缀一致）
```

## 9. 阶段结论

```text
GeomTurbo Production          COMPLETED（195,000 / 195,000）
File-level Sanity Check       PASSED（未发现明显异常）
Geometry QC                   NOT YET PERFORMED
CFD Operating Conditions      PENDING FINAL DESIGN
CFD Dataset Construction      NOT STARTED

本阶段（11D 候选几何生成）到此结束，仓库进入：
  几何 QC 适配 + 入口工况设计 + CFD 数据集构建准备
```

```text
再次强调：
  几何候选数量 195,000 != 有效 CFD 数据数量；
  目标有效数（Train 100000 / Val 10000 / Test 20000）仍为 PROPOSED，
  需要 CFD 成功率与数据筛选结果支撑，不能由本阶段结论推出。
```

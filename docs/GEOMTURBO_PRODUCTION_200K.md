# GeomTurbo 生产几何生成使用说明（默认 200,000 = 历史默认值）

> ## ⚠ 状态更新（2026-10-23）：当前生产计划为三组独立 Sobol（`PROPOSED / NOT EXECUTED`）
>
> 生成器用法、安全机制、manifest 字段与存储估算继续有效（保留原文）。
> **200000 只是代码中的历史默认值，不是当前计划数量。**
> 当前规划见 [`docs/PROJECT_TRANSITION_PLAN.md`](PROJECT_TRANSITION_PLAN.md)。
>
> | 数据集 | Sobol 候选数 | 目标有效 CFD 数 | 建议输出目录（尚未创建） |
> |---|---:|---:|---|
> | Train | 150000 | 100000 | `production_geomturbo/train/` |
> | Validation | 15000 | 10000 | `production_geomturbo/val/` |
> | Test | 30000 | 20000 | `production_geomturbo/test/` |
> | 合计 | 195000 | 130000 | |
>
> ```text
> 执行方式: 同一个生成程序运行三次，每次不同固定种子、不同输出目录
> 种子数值: PENDING（未确定；不使用代码默认 seed=1 作为三组计划的一部分）
> 代码默认值: 本次未修改（count=200000 / seed=1 / production_geomturbo）
> 三组运行会在各自目录内产生相同的 case_id（G0000001..）
>   -> 全局身份 = (group, seed, sobol_index)；`code/run_geomturbo.py` 会写入
>      `group_info.json`（group 目录本身也携带组归属）
>   -> 去重策略仍 PENDING
> 规模依据: 130000 / 195000 = 66.67% 最低总体有效率；
>           小规模 CFD 成功率约 75%（USER-REPORTED）
> ```

> **状态：代码与配置已准备（PREPARED / NOT EXECUTED）。**
> **尚未生成任何实际 GeomTurbo 文件，也未运行任何 CFD。**
> **200000 只是代码中的默认生成数量，是暂定值（PROVISIONAL / NOT FINAL），
> 不是最终决定的生产规模；实际数量由用户决定（`--count`）。**
> 本文档说明如何在本机手动启动生成，不构成“200000 已获批”或“已生成”的声明。

```text
Geometry parameter ranges:
  CURRENT_BASELINE（方案 A，数值未修改；原冻结记录保留）
Batch generator implementation:
  PREPARED / NOT EXECUTED
Default sample count (code default):
  200000  HISTORICAL DEFAULT（不是当前计划数量）
Current production plan (PROPOSED / NOT EXECUTED):
  Train 150000 / Validation 15000 / Test 30000 = 195000 候选
  目标有效 CFD: 100000 / 10000 / 20000 = 130000
Actual production count:
  PENDING（三个种子与最终规模仍需人工确认）
GeomTurbo files generated:
  0
CFD production:
  由师兄在独立服务器执行（本地不实现）
FINAL_PRODUCTION_RANGES:
  PENDING（CFD 侧；不再是本地几何生成阻塞项）
```

## 1. 正式冻结的方案 A

冻结日期 2026-10-21，范围只针对 **GeomTurbo 几何生成参数空间**：

| 参数 | 最小值 | 最大值 |
|---|---:|---:|
| `Xthick` | 0.10 | 0.60 |
| `Tmax` | 0.025 | 0.095 |
| `Metal2` | **6.0** | 32.0 |
| `Solidity` | 0.7 | 2.5 |
| `Metal1` | 48.0 | 58.0 |
| `T1` | 0.010 | 0.018 |
| `T2` | 0.008 | 0.016 |
| `Xmean` | 0.06 | 0.18 |
| `K_m` | 0.10 | 0.35 |
| `Ks1` | 3.0 | 7.0 |
| `Ks2` | 0.05 | 0.20 |

固定参数：`SS1 = 3.2`、`SS2 = 0.8`。

```text
冻结依据：
  C820 人工评审 85 ACCEPT / 15 REJECT；
  方案 A 只收紧 Metal2 下界 0 -> 6.0（C820043 Metal2=0 被拒），
  其余 10 个几何参数保持探索范围；
  K_m 保持 0.10-0.35（不做全局上限）；
  JC_XMEAN_KS1_KM 保持不激活；
  不新增自动形状筛选。
```

```text
本冻结 != CFD 生产范围批准：
  FINAL_PRODUCTION_RANGES 仍为 PENDING；
  2026-10-13 的 DOE 冻结记录未被修改；
  Incidence / Mach 不参与本次几何采样（CFD 工况另行决策）。
```

权威文件：

```text
config/geometry_ranges_frozen_a.yaml                                   运行配置（FROZEN）
analysis/geometry_review/parameter_final_decision_v1/final_geometry_parameters.yaml
                                                                        参数决策（已标记冻结）
docs/GEOMETRY_CONSTRAINT_ANALYSIS_2026-10-21.md                        方案 A 的分析依据
```

## 2. 程序与复用关系

```text
code/generate_geomturbo_production.py        生产入口（新增）
code/geometry_parametric_exploratory_v1.py   13 参数几何数学（复用，未修改）
code/geometry_legacy_v1.py                   冻结的 profile / .geomTurbo 序列化（复用，未修改）
legacy/blade_batch_generation_template.geomTurbo   模板（sha256 校验）
tests/test_generate_geomturbo_production.py  24 个测试（不产生真实 GeomTurbo）
```

```text
没有重新实现叶型公式；生产入口只做：
  采样 -> 参数映射 -> 调用冻结生成器 -> 原子写文件 -> manifest/进度
```

## 3. 环境要求

```text
Conda 环境 : ai4s（项目统一环境）
Python     : 3.10.20
依赖       : numpy, scipy（scipy.stats.qmc.Sobol）, pyyaml
已验证版本 : numpy 2.2.6 / scipy 1.15.3 / pyyaml 6.0.3
```

```bash
conda activate ai4s
python -c "import numpy, scipy, yaml; print(numpy.__version__, scipy.__version__)"
```

## 4. 命令行用法

### 4.0 推荐入口：`code/run_geomturbo.py`（按 group 启动）

```bash
cd /home/qian/compressor_ai4s

# 只读预览（不创建目录 / 文件）
python code/run_geomturbo.py --group train --N 150000 --seed 101 --plan

# 正式启动（一条命令 = 一次明确授权；内部调用生成器的 --execute）
python code/run_geomturbo.py --group train --N 150000 --seed 101
python code/run_geomturbo.py --group val   --N 15000  --seed 202
python code/run_geomturbo.py --group test  --N 30000  --seed 303

# 中断后继续（group / seed 不变；N 可增大以延长 Sobol 前缀）
python code/run_geomturbo.py --group train --N 150000 --seed 101 --resume
```

```text
--group {train,val,test}  必填；默认目录 production_geomturbo/<group>/
--N                       必填；候选几何数量（不是 CFD 成功数）
--seed                    必填；Sobol 种子（续跑时必须一致）
--resume                  继续已有目录（同 config / seed；N 可增大）
--plan                    严格只读
--output-dir              可选，覆盖默认目录
```

```text
每组目录内新增 group_info.json：group / seed / N_candidates / global_identity。
全局身份 = group + seed + sobol_index；case_id 格式不变（G + 7 位数字）。
Ctrl+C 中断时，当前批次已完成的 Case 会先写入 batch manifest，--resume 不会重算它们。
```

以下为底层生成器的直接用法（高级用法 / 等价能力，必须显式 `--execute`）：

```bash
# 1) 只查看计划（只读，不写任何文件）
python code/generate_geomturbo_production.py --plan

# 2) 正式执行（必须显式 --execute）
python code/generate_geomturbo_production.py --execute

# 3) 中断后继续
python code/generate_geomturbo_production.py --execute --resume

# 4) 改变数量（前缀一致）
python code/generate_geomturbo_production.py --plan --count 50000
python code/generate_geomturbo_production.py --execute --count 50000

# 5) 其它参数
python code/generate_geomturbo_production.py --execute \
    --seed 1 --batch-size 5000 --output-dir production_geomturbo
```

| 选项 | 含义 | 默认 |
|---|---|---|
| `--count` | 生成案例数 | 配置文件 `200000`（暂定默认值） |
| `--seed` | Sobol scramble 种子 | `1` |
| `--output-dir` | 输出目录 | `production_geomturbo` |
| `--batch-size` | 每个 batch 目录的案例数 | `5000` |
| `--resume` | 断点续跑 | 关闭 |
| `--plan` | 只显示计划，不生成 | — |
| `--execute` | 明确授权生成 | — |
| `--no-verify-hash` | 续跑时只校验大小（跳过 sha256） | 关闭（默认校验 sha256） |
| `--progress-every` | 每 N 个案例打印进度（0 关闭） | `2000` |
| `--assumed-case-bytes` | 仅用于存储估算 | `15000` |

```text
安全规则：
  不带 --execute 时程序只允许 --plan；
  否则立即以退出码 2 结束，且不会创建输出目录。
  --plan 与 --execute 互斥。
```

### 4.1 三组独立运行（PROPOSED / NOT EXECUTED）

当前计划用同一程序运行三次，三组互不共用输出目录，也不共用种子：

```bash
# Train（目标有效 100000 / 候选 150000）
python code/generate_geomturbo_production.py --plan \
    --count 150000 --seed <TRAIN_SEED> --output-dir production_geomturbo/train
python code/generate_geomturbo_production.py --execute \
    --count 150000 --seed <TRAIN_SEED> --output-dir production_geomturbo/train --resume

# Validation（目标有效 10000 / 候选 15000）
python code/generate_geomturbo_production.py --execute \
    --count 15000 --seed <VALIDATION_SEED> --output-dir production_geomturbo/val --resume

# Test（目标有效 20000 / 候选 30000）
python code/generate_geomturbo_production.py --execute \
    --count 30000 --seed <TEST_SEED> --output-dir production_geomturbo/test --resume
```

```text
说明（不改代码）：
  三个种子数值 PENDING，必须由用户确定并记录；
  每个输出目录各自有 config_snapshot.yaml / manifest.csv / batch_*/，
  因 seed 不同，指纹不同 -> 不能共用一个输出目录续跑；
  三组 case_id 都会从 G0000001 开始；全局身份 = group + seed + sobol_index
  （run_geomturbo.py 写入 group_info.json；去重策略仍 PENDING）；
  上面命令本轮没有执行，且必须由用户显式启动。
```

## 5. 默认数量（历史默认值）与修改方法

```text
默认 count = 200000（来自 config sampling.default_count，不是硬编码逻辑）
200000 = HISTORICAL DEFAULT，不是当前计划数量；
当前计划（PROPOSED / NOT EXECUTED）：150000 / 15000 / 30000 候选
实际数量仍由用户用 --count 指定（种子数值 PENDING），见
docs/PROJECT_TRANSITION_PLAN.md。

200000 不是 2^m，因此（以默认值为例）：
  m = 18（2^18 = 262144）
  master = Sobol(d=11, scramble=True, seed=1).random_base2(18)
  实际使用 master[:count]
调整 --count 不会改变前 N 个参数向量（前缀一致）：
  D_50000 = D_200000 的前 50000 个点
增大数量：--count 300000（m=19，前 200000 个与原来完全一致）
减小数量：只处理到新数量；已生成的多余文件不会被删除
```

## 6. Sobol 采样细节

```text
维度       : 11（顺序 = 配置 geometry_parameters）
顺序       : Xthick, Tmax, Metal2, Solidity, Metal1, T1, T2, Xmean, K_m, Ks1, Ks2
scramble   : True
seed       : 1（可用 --seed 覆盖；覆盖后与旧输出不兼容，续跑会被拒绝）
排列       : native Sobol order（不排序、不打乱）
嵌套       : prefix（D_N = 同一 master block 的前 N 个点）
参数映射   : value = lo + u * (hi - lo)，u ∈ [0,1)
固定参数   : SS1=3.2、SS2=0.8 在映射后自动注入
```

```text
注意：seed / 参数顺序 / 范围 / batch_size / 模板 / 生成器哈希
      任一变化，--resume 会被拒绝（见第 8 节）。
```

## 7. 输出目录与文件命名

```text
production_geomturbo/
├── config_snapshot.yaml          运行配置 + 指纹 + 模板/生成器哈希 + 时间
├── manifest.csv                  全量索引（每 Case 一行；运行开始/结束时重建）
├── generation_summary.json       本次运行统计（成功/失败/写入/跳过/耗时）
├── batch_000001/
│   ├── manifest.csv              该 batch 的权威状态（每个 Case 一行）
│   ├── G0000001.geomTurbo
│   └── ...
├── batch_000002/
└── ...                          （默认 40 个 batch，每个 5000 case）
```

```text
Case ID   : G + 7 位数字（默认 200000 时为 G0000001 .. G0200000）
            与 C8xxxxx（评审）/ C9xxxxx（NUMECA bring-up）不冲突
文件名    : <case_id>.geomTurbo（后缀与现有生成器一致）
batch     : batch_XXXXXX，编号从 1 开始，按 Sobol 顺序连续切分
manifest  : case_id, sobol_index, batch, path, status, error, sha256, size_bytes,
            11 个几何参数, SS1, SS2
status    : OK / FAILED（FAILED 带 error 文本；续跑时自动重试）
```

```text
manifest.csv 与 batch_*/manifest.csv 的关系：
  batch manifest 是权威记录（每批完成后原子重写）；
  root manifest 是聚合视图（运行开始与结束时由 batch manifest 重建）。
  运行中断时 root manifest 可能落后于 batch manifest，--resume 会自动重建。
```

## 8. 断点续跑语义

```bash
# 直接重新执行；程序会跳过已完成且校验通过的 Case
python code/generate_geomturbo_production.py --execute --resume
```

处理规则：

```text
1) status=OK 且文件存在、大小一致、sha256 一致 -> 跳过（不重写）
2) 文件缺失 / 大小为 0 / 大小不符 / sha256 不符 -> 重新生成
3) status=FAILED -> 重新尝试
4) 单个 Case 失败只记录该 Case，不中断整批
5) 写文件使用“同目录临时文件 + os.replace”原子替换
6) 不覆盖历史实验目录（只写入 --output-dir 指定的目录）
```

```text
续跑拒绝条件（退出码 2，不生成任何文件）：
  - 输出目录已有内容但没有 config_snapshot.yaml
  - 未带 --resume 却指向已初始化的目录
  - fingerprint 不一致（config / seed / 参数顺序 / batch_size /
    模板 sha256 / 生成器 sha256 任一变化）
  - --plan 与 --execute 同时给出
```

```text
允许的变化：
  - --count 增大或减小（Sobol 前缀不变；减小不删除已有文件）
  - --progress-every（只影响日志）
  - --no-verify-hash（只放宽完整性校验，不建议长期使用）
```

## 9. 核对实际生成数量

```bash
# 文件数
find production_geomturbo -name 'G*.geomTurbo' | wc -l

# manifest 统计（成功/失败/总数）
python - <<'PY'
import csv
rows = list(csv.DictReader(open("production_geomturbo/manifest.csv")))
print("rows", len(rows),
      "ok", sum(r["status"] == "OK" for r in rows),
      "failed", sum(r["status"] == "FAILED" for r in rows))
PY
```

```text
也可以直接查看 generation_summary.json 的 manifest_rows / manifest_ok /
manifest_failed / completed 字段。
```

## 10. 文件完整性检查

```text
推荐方式：再次执行 --execute --resume
  程序会逐个校验 size + sha256，发现损坏后自动重新生成该 Case，
  并在 summary 中报告 written_this_run。
```

```bash
# 快速抽查（示例：前 3 个文件）
python - <<'PY'
import csv, hashlib, pathlib
root = pathlib.Path("production_geomturbo")
rows = list(csv.DictReader(open(root / "manifest.csv")))[:3]
for r in rows:
    p = root / r["path"]
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    print(r["case_id"], p.stat().st_size == int(r["size_bytes"]), h == r["sha256"])
PY
```

```text
如果只想校验大小（更快，不读文件内容）：
  python code/generate_geomturbo_production.py --execute --resume --no-verify-hash
```

## 11. 存储空间注意事项

```text
实测参考：analysis/geometry_review/geometry/geomturbo/C810001.geomTurbo
          = 14,228 B（同一模板、4 位小数 profile）
估算默认 200,000 个（仅示例）：
  GeomTurbo   : 200000 × ~14.2 kB ≈ 2.85 GB
  manifest    : root + batch ≈ 100-200 MB（每行 ~500 B）
  summary/snapshot : < 1 MB
  合计        : 约 3.0-3.1 GB（--plan 的 15000 B/case 估算为 3.00 GB）
建议预留    : ≥ 5 GB 可用空间（含文件系统开销与临时文件）
inode       : 200,000 个文件 + 40 个 batch 目录
```

```text
避免把 200,000 个文件放在单个目录：
  默认按 batch 分目录（每批 5000 个），便于浏览、校验与增量重跑。
```

## 12. 本次没有做的事

```text
未执行批量生成（没有创建 production_geomturbo/）
未生成任何实际 .geomTurbo 文件
未进行 10-case 真实试生成
未进行 200000-case 批量生成
未运行 NUMECA / CFX / CFD
未生成 CFD 训练数据集
未最终决定生产样本量（200000 只是默认值）
未添加自动形状筛选或新的曲率/厚度阈值
未修改 2026-10-13 的 DOE 冻结记录
未修改冻结生成器与模板
```

```text
因此当前交付是“流程准备完成”，不是“200000 个文件已生成”，
更不是“CFD 已完成”。200000 不是已批准的生产规模。
```

## 13. 需要用户手动运行后验证的内容

```text
以下项目只有真实执行 --execute 才能确认（本轮按规则未执行）：
1) 真实生成器的单案例输出是否与冻结模板格式一致
   （建议先用 --count 10 在临时目录做少量真实导出验证）
2) 按最终决定数量生成后的真实总大小与磁盘占用
   （默认 200000 时估算 ~2.85 GB，仅供参考）
3) 真实运行耗时（估算：几何计算 ~1.6 ms/case，实际受磁盘 I/O 影响，需实测）
4) 真实 sha256 清单与抽查一致性
5) 中断/续跑在真实文件系统上的行为（测试中使用的是 stub 内容）
6) 文件系统对 200,000 个文件的 inode / 目录性能表现
```

## 14. 常见问题

```text
Q: 运行后提示 “refusing to run without --execute”
A: 这是安全设计；先 --plan 查看计划，再显式 --execute。

Q: 提示 “resume refused: ... fingerprint ...”
A: 配置 / seed / 参数顺序 / batch_size / 模板 / 生成器哈希发生了变化。
   用原设置续跑，或换一个新的 --output-dir 重新开始。

Q: 想把数量从 200000 改成 50000？
A: 直接 --execute --count 50000；前 50000 个参数与默认 200000 版本完全一致。

Q: 想删除部分结果重跑？
A: 删除对应 batch 目录下的文件与 manifest 行（或整个 batch 目录），
   再 --resume；不要手工修改 config_snapshot.yaml。

Q: 能否并行？
A: 本轮实现为单进程（冻结生成器含模块级惰性加载，未验证线程安全）。
   后续如需并行，必须逐 Case 保持原子写与 manifest 一致性。
```

## 15. 安全红线

```text
不得在未冻结配置的情况下生成
不得修改 config_snapshot.yaml 以绕过 fingerprint
不得用“重新抽样”替换失败 Case（会破坏 Sobol 索引与参数向量的对应）
不得把生成成功等同于网格/CFD 可用
不得让几何生成程序自动启动 NUMECA / CFX
```


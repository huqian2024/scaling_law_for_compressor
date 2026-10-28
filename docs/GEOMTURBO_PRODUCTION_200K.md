# GeomTurbo 生产几何生成使用说明（200,000 = 历史默认值；实际已完成 195,000）

> ## ✅ 状态更新（2026-10-28）：三组生产已 COMPLETED
>
> | 数据集 | 几何数量 | Seed | Batch | 状态 |
> |---|---:|---:|---:|---|
> | Train | 150,000 | 101 | 30 | COMPLETED |
> | Validation | 15,000 | 202 | 3 | COMPLETED |
> | Test | 30,000 | 303 | 6 | COMPLETED |
> | **合计** | **195,000** | — | **39** | **COMPLETED** |
>
> ```text
> 文件级 Sanity Check   PASSED（0 failed / 0 missing / 60-60 SHA256 抽检）
> 体积                  ≈2.793 GB 文件 / ≈3.2 GB 实际磁盘
> 几何 QC               NOT YET PERFORMED
> 入口工况              PENDING FINAL DESIGN（Incidence/Mach 仅历史参考）
> CFD 数据集            NOT STARTED
> 完成报告              docs/GEOMTURBO_PRODUCTION_COMPLETION.md
> ```
>
> 本文档其余部分保留为生成器使用说明与**复现 / 扩展**指南；
> **200000 只是历史代码默认值，不是本阶段生成数量。**
> 当前规划见 [`docs/PROJECT_TRANSITION_PLAN.md`](PROJECT_TRANSITION_PLAN.md)。

```text
Geometry parameter ranges:
  CURRENT_BASELINE（方案 A，数值未修改；原冻结记录保留）
Batch generator implementation:
  COMPLETED（195000 / 195000 files，0 failed）
Default sample count (code default):
  200000  HISTORICAL DEFAULT（不是本阶段生成数量）
Actual production (COMPLETED):
  Train 150000 / Val 15000 / Test 30000 = 195000 files / 39 batches
Seeds (recorded):
  Train 101 / Validation 202 / Test 303
GeomTurbo files generated:
  195000（production_geomturbo/{train,val,test}/，本地，gitignored）
File-level sanity check:
  PASSED 2026-10-28
CFD production:
  由师兄在独立服务器执行（本地不实现）
FINAL_PRODUCTION_RANGES:
  PENDING（CFD 侧；不是本地几何生成阻塞项）
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

### 4.1 三组独立运行（COMPLETED 2026-10-28）

实际生产用同一程序运行三次，三组互不共用输出目录，也不共用种子（已完成）：

```bash
# Train（150000 个候选；seed 101）
python code/run_geomturbo.py --group train --N 150000 --seed 101

# Validation（15000 个候选；seed 202）
python code/run_geomturbo.py --group val   --N 15000  --seed 202

# Test（30000 个候选；seed 303）
python code/run_geomturbo.py --group test  --N 30000  --seed 303
```

```text
说明（不改代码）：
  实际种子：Train 101 / Validation 202 / Test 303（已在 group_info.json 记录）；
  每个输出目录各自有 config_snapshot.yaml / manifest.csv / batch_*/，
  因 seed 不同，指纹不同 -> 不能共用一个输出目录续跑；
  三组 case_id 都会从 G0000001 开始；全局身份 = group + seed + sobol_index；
  结果：195000 / 195000 文件，39 batches，0 failed；
  本次文档同步没有重新执行生成。
```

## 5. 默认数量（历史默认值）与修改方法

```text
默认 count = 200000（来自 config sampling.default_count，不是硬编码逻辑）
200000 = HISTORICAL DEFAULT，不是本阶段生成数量；
本阶段实际生成：Train 150000 / Val 15000 / Test 30000 = 195000 文件（COMPLETED）
如需扩展，用 --count / --N 指定；同 seed 下前 N 个点不变，见
docs/PROJECT_TRANSITION_PLAN.md 与 docs/GEOMTURBO_PRODUCTION_COMPLETION.md。

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

## 12. 本文档初版时没有做的事（历史）与当前状态

```text
初版（生成器使用说明）时未执行批量生成，也没有实际 .geomTurbo 文件。
该状态已于 2026-10-28 结束：
  195000 个文件已生成（Train 150000 / Val 15000 / Test 30000）
  文件级 Sanity Check PASSED；真实导出、sha256 抽查、批次/断点行为均已实测。
仍未执行（与生成器无关）：
  NUMECA / CFX / CFD、几何 QC、CFD 训练数据集、AI 训练。
```

```text
因此当前状态是“几何候选池已完成”，
不是“几何 QC 已完成”，更不是“CFD 已完成”。
200000 仍只是历史代码默认值，不是本阶段生成数量。
```

## 13. 需要用户手动运行后验证的内容

```text
以下项目已在 2026-10-28 的真实生产中得到验证（保留清单以便复核）：
1) 真实生成器的单案例输出与冻结模板格式一致（已实测）
2) 真实总大小与磁盘占用（≈2.793 GB / ≈3.2 GB）
3) 真实运行耗时（Val 27 s、Test 55 s、Train 305 s）
4) 真实 sha256 清单与抽查一致性（60/60 通过）
5) 中断/续跑在真实文件系统上的行为（单元测试 + 实际批次）
6) 195000 个文件的文件系统表现（扫描约 4.6 s）
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


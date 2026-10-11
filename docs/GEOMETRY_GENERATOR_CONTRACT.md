# Geometry Generator Contract

```text
Status: FROZEN V1 — implementation contract
Baseline commit: 1952186703e32ec60a4e82fb6ffc42e38e6f5d99
Program: code/02_generate_geometry.py
```

This document freezes the **interface** of the future geometry generator. It does
**not** implement, and it does **not** restate the legacy geometry mathematics.

Two contracts are kept strictly separate:

- **production CLI contract** — operates on `C######` production case IDs;
- **legacy regression acceptance contract** — operates on `LG###` fixture IDs
  through a test adapter.

`LG###` fixture IDs are **never** production case IDs.

## 1. Responsibility

`code/02_generate_geometry.py` performs exactly this data flow:

```text
master design row
    ↓
legacy-compatible deterministic geometry calculation
    ↓
profile
    ↓
.geomTurbo
```

### NON-GOALS

```text
NO DOE sampling
NO case_id allocation
NO Incidence/Mach → CFX conversion
NO mesh generation
NO Geometry QC verdict
NO NUMECA
NO CFX
NO CFD-Post
NO model preprocessing
```

Full Geometry QC belongs to `code/03_geometry_qc.py`.

## 2. Production input contract

The CLI input CSV must contain at least these columns:

```text
case_id
Xthick
Tmax
Metal2
Solidity
Incidence
Mach
range_id
sampling_id
```

### case_id

Production IDs must match:

```regex
^C[0-9]{6}$
```

and must be unique. The generator:

```text
does not generate case_id
does not reorder case_id
does not reuse case_id
```

Rows are processed in the **original input CSV row order**.

### numeric columns

`Xthick, Tmax, Metal2, Solidity, Incidence, Mach` must all parse to finite float.
Forbidden: `NaN`, `inf`, `-inf`.

### minimal mathematical preconditions

The generator layer may check:

```text
0 < Xthick < 1
Solidity > 0
```

because the mathematics itself requires these.

But the generator **must not hard-code legacy parameter ranges**, i.e. must NOT
enforce `Xthick ∈ [0.15,0.45]` etc. Design space (`core`, `expanded_v1`,
`expanded_v2`, ...) is owned upstream by DOE/config.

### extra columns

The input CSV may contain additional columns. The generator must not fail because
of unknown extra metadata columns.

## 3. Geometry parameter contract

```text
profile geometry depends on:
    Xthick
    Tmax
    Metal2
```

```text
.geomTurbo additionally depends on:
    Solidity        (via  periodicity = 0.06 / Solidity)
```

```text
Incidence
Mach
```

must be read and validated finite, but:

```text
MUST NOT enter profile generation
MUST NOT alter geomTurbo geometry
```

They belong to a future operating-condition / CFX stage.

Therefore:

```text
Geometry output is invariant under changes in Incidence/Mach
when Xthick/Tmax/Metal2/Solidity are fixed.
```

Behavior already established by the regression fixture:

```text
Changing Solidity alone:
  - profile remains identical
  - geomTurbo changes through PERIODICITY
```

No new physical interpretation is added here.

## 4. CLI v1 contract

```bash
python code/02_generate_geometry.py \
    --input design/master_design.csv \
    --template legacy/blade_batch_generation_template.geomTurbo \
    --output geometry
```

Supported flags:

```text
--input PATH
--template PATH
--output PATH
--case-id CASE_ID
--dry-run
--overwrite
```

### --input
required.

### --template
required. The generator must **not** silently pick an arbitrary template.

### --output
required. Typical value: `geometry`. Internal layout is fixed:

```text
<output>/profiles/<case_id>.dat
<output>/geomturbo/<case_id>.geomTurbo
```

### --case-id
optional, repeatable, e.g.:

```bash
--case-id C000001 --case-id C000010
```

When omitted: process all input rows. If a requested case ID does not exist in the
input: this is an input/CLI error — do **not** silently ignore it.

### --dry-run
Must not produce any persistent project output. It may:

```text
read input
read template
validate schema
run deterministic geometry calculations
produce candidate bytes in memory / a temporary directory
read existing output for comparison
```

On exit: the project tree is unchanged.

### --overwrite
Only permits overwriting existing mismatching / partial output. If the existing
output is already byte-for-byte identical to the freshly generated candidate:

```text
even with --overwrite  →  SKIP_MATCH  (no pointless rewrite)
```

### --config (intentionally absent in v1)

```text
--config is intentionally not part of CLI v1.

The generator receives its required runtime inputs explicitly
through --input, --template and --output.

A future version may add --config if additional versioned
geometry-generator settings are introduced.
```

This does not change the long-term "recommended to support --config" note in
`AGENT_INSTRUCTION.md`.

## 5. Default resume / idempotency semantics

There is **no `--resume` flag**. Resume is part of the default behavior.

For each selected case, the generator first produces a deterministic candidate,
then classifies it into exactly one action of the frozen vocabulary (section 7).

### State A
```text
profile missing
geomTurbo missing
```
action: `CREATE` — both outputs are created.

### State B
```text
both outputs exist and are byte-for-byte identical to the candidate
```
action: `SKIP_MATCH` (exit success). This is the default breakpoint-resume /
idempotency mechanism.

### State C
```text
only one of profile / geomTurbo exists
```
action: `CONFLICT_PARTIAL` (default: FAIL CASE, no write). With an effective
`--overwrite`: `WOULD_OVERWRITE` in dry-run, `OVERWRITE` in a real run.

### State D
```text
both outputs exist but at least one differs from the candidate
```
action: `CONFLICT_CONTENT` (default: FAIL CASE). With an effective `--overwrite`:
`WOULD_OVERWRITE` in dry-run, `OVERWRITE` in a real run.

### Overwrite success semantics (frozen)

existing outputs match candidate + `--overwrite`  =>  `SKIP_MATCH`

only an actual replacement of mismatching / partial output  =>  `OVERWRITE`

`OVERWRITE` must never be reported for already-correct files.

## 6. Atomic-write contract

The implementation phase must satisfy:

1. candidate profile **and** geomTurbo bytes must both be generated successfully
   before any output is finalized;
2. existing output must not be damaged before the candidate is complete;
3. final files use temporary file + atomic rename/replace;
4. if the calculation phase fails, no half-written "looks successful" artifact may
   remain;
5. after a crash that leaves a partial pair, the next run must treat it as a
   partial-output conflict, not as success.

### Pair-level atomicity boundary (frozen)

Single-file writes must use:

```text
temporary file
→ fsync/close as appropriate
→ atomic os.replace / equivalent
```

But v1 does **not** claim that profile + geomTurbo form a cross-file-system
transaction. A crash may therefore leave:

```text
one exists, one missing
```
or
```text
one new, one old
```

The next run must recover through candidate comparison into exactly one action:

```text
CONFLICT_PARTIAL
```
or
```text
CONFLICT_CONTENT
```

By default nothing existing is destroyed; only an explicit `--overwrite` repairs it.
No complex transaction journal is designed.

Not implemented in this round; recorded as contract only.

## 7. Action vocabulary

Frozen per-case action vocabulary — the only allowed code-level tokens:

```text
CREATE
SKIP_MATCH
CONFLICT_PARTIAL
CONFLICT_CONTENT
WOULD_OVERWRITE
OVERWRITE
ERROR
```

Definitions:

- `CREATE` — neither output exists; both outputs are created.
- `SKIP_MATCH` — both outputs exist and match the freshly generated candidate
  byte-for-byte.
- `CONFLICT_PARTIAL` — only one of profile / geomTurbo exists, and no effective
  overwrite is enabled.
- `CONFLICT_CONTENT` — both exist but at least one differs from the candidate, and
  no effective overwrite is enabled.
- `WOULD_OVERWRITE` — only for `--dry-run --overwrite`; the real run would overwrite
  a partial/content conflict.
- `OVERWRITE` — only for a non-dry-run run with `--overwrite`, and only when the
  replacement actually completed.
- `ERROR` — the case generation itself failed.

The only valid conflict tokens are `CONFLICT_PARTIAL` and `CONFLICT_CONTENT`.
Plain-English descriptions may say "partial-output conflict" / "content conflict".

`--dry-run --overwrite` reports `WOULD_OVERWRITE` only; it never actually overwrites.

`OVERWRITE` must never be used for a `SKIP_MATCH` situation (see section 5).

## 8. Console / reporting contract

Each selected case emits at least one machine-readable summary line with the frozen
field concepts:

```text
case_id
action
profile_path
geomturbo_path
reason
```

The final summary freezes at least:

```text
selected_count
create_count
skip_match_count
overwrite_count
conflict_count
error_count
```

where

```text
conflict_count = CONFLICT_PARTIAL + CONFLICT_CONTENT
```

In a dry-run summary, additionally:

```text
would_overwrite_count
```

which is allowed to be `0` in a non-dry-run run.

### Dry-run predicted risk

To align with `AGENT_INSTRUCTION.md`, a dry-run must also report:

```text
predicted_conflict_count
predicted_error_count
```

plus a per-case `reason`. This is this tool's form of "预计覆盖文件 / 预计失败风险".
No probability model or risk score is introduced.

This round does **not** define a central manifest schema. The generator must also
**not** decide:

```text
geometry_ok
ml_usable
```

Those belong to the later QC / manifest pipeline.

## 9. Exit-code contract

### Normal run

```text
0 = all selected cases end as CREATE / SKIP_MATCH / OVERWRITE

2 = CLI / input contract failure

3 = one or more unresolved CONFLICT_PARTIAL / CONFLICT_CONTENT
    and no generation failure occurred

4 = one or more ERROR / geometry-generation failure
```

If a batch contains both an `ERROR` and an unresolved conflict, the overall exit
code is:

```text
4
```

but the summary must still report the per-case status actually reached; do not
pretend everything succeeded.

### Dry-run

```text
clean dry-run (only CREATE / SKIP_MATCH predicted)
    => exit 0

dry-run without --overwrite, with CONFLICT_PARTIAL / CONFLICT_CONTENT present
    => exit 3

dry-run --overwrite: former partial/content conflicts are reported as
WOULD_OVERWRITE; if there is no generation error
    => exit 0

generation error during dry-run (ERROR)
    => exit 4

input / CLI failure
    => exit 2
```

## 10. Determinism contract

For the same:

```text
input row
template bytes
generator version
supported Python/numpy environment
```

the output must be deterministic. It must not contain:

```text
timestamp inside profile
timestamp inside geomTurbo
random UUID
randomized ordering
machine-specific absolute path
```

The output must therefore be suitable for hash regression.

## 11. Template contract

`--template` points to a file that must exist and be readable. The generator never
modifies it. During generation it computes the template SHA256 and reports it in the
CLI summary.

GT_V1 regression uses:

```text
legacy/blade_batch_generation_template.geomTurbo
sha256 = 92c4296f2de27440aebaad9b03b9af4f9e09756fabff2298f4607a87f2c55119
```

But the production generator **must not hard-code this hash as the only allowed
value**. A future GT_V2 must be able to enter a new versioned pipeline through an
explicit `--template`.

## 12. Legacy regression acceptance contract

Before a future implementation is accepted, it must pass the frozen baseline in:

```text
tests/fixtures/legacy_geometry_v1/
```

Acceptance:

```text
13 profiles:  byte-for-byte match
13 geomTurbo: byte-for-byte match
```

i.e. `26/26` exact match. **Not** "approximately equal" and **not** "geometry
visually similar" — it must be an exact byte regression.

It must continue to verify:

```text
LG001 == LG012 == LG013        (profile and geomTurbo)
LG001 profile == LG008 profile == LG009 profile
and the corresponding geomTurbo differ
```

The production CLI `case_id` contract remains `C######`. Fixture `LG###` IDs must be
consumed through a **test adapter / internal test path**. The production case-id
contract must **not** be relaxed in order to run the tests.

## 13. Formatting compatibility

```text
GT_V1 output formatting is part of the regression contract.
```

Including:

```text
numeric formatting
line ordering
template-preserved whitespace
section ordering
newline behavior
```

A future implementation must therefore not merely verify that floating-point
coordinates are close. The legacy-intrinsic whitespace inside the frozen fixtures is
oracle bytes.

## 14. Visualization contract

`code/02_generate_geometry.py`:

```text
MUST NOT call plt.show()
```

No interactive visualization by default. QC figures belong to
`code/03_geometry_qc.py` or dedicated QC tooling.

## 15. Failure behavior

On any selected-case generation failure:

```text
do not fabricate output
do not create an all-zero profile
do not fill a dummy geomTurbo
do not delete an existing conflicting output
explicitly print case_id + failure reason
```

This round does not design a CFD/mesh failure taxonomy. Geometry generation only.

## 16. Implementation architecture guidance (future, not code)

A future implementation should be layered at least as:

```text
CLI / orchestration
    ↓
input validation
    ↓
pure geometry calculation
    ↓
profile serialization
    ↓
geomTurbo serialization
    ↓
filesystem conflict / atomic-write layer
```

The core geometry calculation must not:

```text
read CSV
parse argparse
write files
call plt.show()
```

so that it can be regression-tested directly against the legacy fixtures.

## 17. Cross-document review

A read-only cross-check against `AGENT_INSTRUCTION.md`, `PROJECT_HANDOFF.md`,
`docs/DOE_DECISION.md`, `docs/SCALING_EXPERIMENT_DESIGN.md` and
`tests/fixtures/legacy_geometry_v1/` is recorded in the conversation report.
Any conflict found there is reported only; other documents are not modified here.

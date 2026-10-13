# TEMPORARY — NUMECA bring-up single case

NOT a production master design. This directory holds **one** temporary bring-up
input for NUMECA `.geomTurbo` delivery only.

```text
case_id     = C900001
source      = legacy/lhs_samples_train.csv  (data row 1, read-only source)
range_id    = legacy/core
sampling_id = bringup_v1
```

The original `legacy/lhs_samples_train.csv` is **not modified**.

Frozen contracts honoured:

```text
code/02_generate_geometry.py   FROZEN (docs/GEOMETRY_GENERATOR_CONTRACT.md V1.2)
code/03_geometry_qc.py         FROZEN (docs/GEOMETRY_QC_CONTRACT.md V1)
```

Delete this directory once the production `01_generate_design.py` master design
supersedes it.

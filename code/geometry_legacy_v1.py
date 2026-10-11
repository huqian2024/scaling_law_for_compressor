"""Phase 1: pure legacy-compatible geometry core (LEGACY GT_V1).

This module is a controlled re-implementation of the geometry mathematics in
``legacy/blade_batch_generation.py``. It reuses the same formulas, the same fixed
constants and the same serialization behavior, but performs **no** filesystem
access, no CLI parsing and no plotting.

Boundary (by construction):
    The public API does not accept ``Incidence`` / ``Mach`` / ``case_id`` / any
    path. Operating conditions must never enter the geometry core.

Determinism:
    Fixed ``\\n`` newlines. No timestamps, no UUIDs, no absolute paths. Output is
    suitable for byte-for-byte hash regression.

Note (does not interpret, only records):
    ``Metal1 = 48 + DeltaBeta = 53`` while the legacy comment mentions a 49 degree
    zero-incidence inlet angle. This contradiction is intentionally NOT resolved
    here; the frozen legacy behavior is reproduced verbatim.

See ``docs/GEOMETRY_GENERATOR_CONTRACT.md`` (FROZEN V1).
"""

from __future__ import annotations

import io
import math

import numpy as np

# --- Frozen legacy geometry constants (do not change; LEGACY GT_V1) ---------
Gridswitch = -1.0       # Gridswitch < 0 -> O-grid
Rsign = 1.0             # suction side sign
Npoint = 101            # profile point count
Ncirc = 4               # leading/trailing edge circle points / 2
DeltaBeta = 5           # inlet additional metal angle
Metal1 = 48 + DeltaBeta # inlet metal angle (= 53)
Xmean = 0.08            # meanline break point
K_m = 0.18              # fraction of turning at Xmean
Ks1 = 5                 # leading-edge slope multiplier
Ks2 = 0.10              # trailing-edge slope multiplier
T1 = 0.015              # leading-edge thickness
T2 = 0.0125             # trailing-edge thickness
SS1 = 3.2               # inlet thickness-change coefficient
SS2 = 0.8               # outlet thickness-change coefficient
Nscale1 = 1.7           # meanline front clustering
Nscale2 = 1.7           # meanline rear clustering

# --- Fixed GT_V1 scaling constants ------------------------------------------
CHORD_TARGET = 0.06     # profile chord scaled to 0.06 (legacy)
SPAN = 0.003            # span used for section 2 / channel (legacy)

# --- LEGACY GT_V1 template slices -------------------------------------------
# (skip, count) as used by the legacy script's readline loops; 1-based inclusive.
#   lines 1-14, 17-25, 28-46, 48-77, 247-248, 418-422, 580-581, 739-754
TEMPLATE_SLICES = {
    "header":            (0, 14),
    "channel_shroud":    (16, 9),
    "row_header":        (27, 19),
    "blade_header":      (47, 30),
    "suction_section2":  (246, 2),
    "pressure_header":   (417, 5),
    "pressure_section2": (579, 2),
    "footer":            (738, 16),
}

_MIN_TEMPLATE_LINES = 754


def _check_finite(name, value):
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return v


def _validate_geometry_inputs(Xthick, Tmax, Metal2):
    Xthick = _check_finite("Xthick", Xthick)
    Tmax = _check_finite("Tmax", Tmax)
    Metal2 = _check_finite("Metal2", Metal2)
    # Frozen mathematical precondition (not a production range contract).
    if not (0.0 < Xthick < 1.0):
        raise ValueError(f"Xthick must satisfy 0 < Xthick < 1, got {Xthick!r}")
    return Xthick, Tmax, Metal2


def _validate_solidity(Solidity):
    Solidity = _check_finite("Solidity", Solidity)
    # Frozen mathematical precondition (not a production range contract).
    if Solidity <= 0.0:
        raise ValueError(f"Solidity must be > 0, got {Solidity!r}")
    return Solidity


# ---------------------------------------------------------------------------
# Profile generation
# ---------------------------------------------------------------------------
def generate_profile_text(Xthick, Tmax, Metal2) -> str:
    """Return the legacy-compatible profile text (4 columns, 4-decimal).

    Formatting is part of the GT_V1 regression contract::

        f"{xp1[i]:7.4f} {yp1[i]:7.4f} {xs1[i]:7.4f} {ys1[i]:7.4f}\\n"

    The 4-decimal rounding is intentional and must be preserved: the geomTurbo
    serializer re-parses this rounded text (legacy behavior).
    """
    Xthick, Tmax, Metal2 = _validate_geometry_inputs(Xthick, Tmax, Metal2)

    # --- meanline clustering (verbatim legacy) -----------------------------
    xc00 = np.linspace(0, 1, Npoint)
    xc = np.zeros_like(xc00)

    for i in range(Npoint):
        if xc00[i] <= 0.5:
            xc[i] = (2 * xc00[i]) ** Nscale1 / 2
        else:
            xc[i] = 1 - (2 * (1 - xc00[i])) ** Nscale2 / 2

    # --- meanline coefficients (verbatim legacy) ---------------------------
    Sm1 = np.tan(np.radians(Metal1))
    Sm2 = np.tan(np.radians(Metal2))
    Sm0 = np.tan(np.radians(Metal1 + (Metal2 - Metal1) * K_m))

    SSm1 = Ks1 * (Sm2 - Sm1)
    SSm2 = Ks2 * (Sm2 - Sm1)

    a1 = 1 / 2 * (-SSm1 * Xmean - Xmean ** 3 * SSm2 + Xmean ** 3 * SSm1 + Xmean ** 2 * SSm2 + 3 * Xmean ** 2 * Sm1 - 3 * Xmean ** 2 * Sm2 + Sm0 - Sm1 + 2 * Xmean * Sm0 - 2 * Xmean * Sm1) / (-1 + Xmean) / Xmean ** 3
    a2 = -1 / 2 / Xmean ** 2 * (-Xmean ** 3 * SSm2 + Xmean ** 3 * SSm1 + Xmean ** 2 * SSm2 + 3 * Xmean ** 2 * Sm1 - 3 * Xmean ** 2 * Sm2 + 2 * SSm1 * Xmean ** 2 - 3 * SSm1 * Xmean + 3 * Sm0 - 3 * Sm1) / (-1 + Xmean)
    a3 = SSm1
    a4 = Sm1
    a5 = -1 / 2 * (SSm1 * Xmean - 6 * Xmean * Sm1 - Xmean ** 3 * SSm2 + Xmean ** 3 * SSm1 + 3 * Xmean ** 2 * Sm1 + 3 * Xmean ** 2 * SSm2 + 2 * Xmean * Sm0 - 2 * SSm1 * Xmean ** 2 - 3 * Xmean ** 2 * Sm2 + 4 * Xmean * Sm2 - 2 * SSm2 * Xmean - 3 * Sm0 + 3 * Sm1) / Xmean / (-1 + 3 * Xmean - 3 * Xmean ** 2 + Xmean ** 3)
    a6 = -1 / 2 * (-Xmean ** 3 * SSm2 + Xmean ** 3 * SSm1 + 5 * Xmean ** 2 * SSm2 - 2 * SSm1 * Xmean ** 2 + 3 * Xmean ** 2 * Sm1 - 3 * Xmean ** 2 * Sm2 - 4 * SSm2 * Xmean + SSm1 * Xmean - 6 * Xmean * Sm1 + 6 * Xmean * Sm2 + 3 * Sm1 - 3 * Sm0) / Xmean / (-1 + Xmean) ** 2
    a7 = -SSm2
    a8 = Sm2

    # --- thickness coefficients (verbatim legacy) --------------------------
    St1 = SS1 * (Tmax / 2 - T1 / 2) / Xthick
    St2 = SS2 * (Tmax / 2 - T2 / 2) / (1 - Xthick)

    term1 = (Tmax - T1) * (1 - Xthick) ** 2
    term2 = (Tmax - T2) * Xthick ** 2
    term3 = St1 * Xthick * (1 - Xthick) ** 2
    term4 = St2 * (1 - Xthick) * Xthick ** 2

    b1 = (3 / 2 * term1 - 3 * term2 - term3 + 3 * term4) / ((1 - Xthick) ** 2 * Xthick ** 4)
    b2 = (-4 * term1 + 6 * term2 + 3 * term3 - 6 * term4) / ((1 - Xthick) ** 2 * Xthick ** 3)
    b3 = (3 * term1 - 3 * term2 - 3 * term3 + 3 * term4) / ((1 - Xthick) ** 2 * Xthick ** 2)
    b4 = St1
    b5 = T1 / 2
    b6 = (-3 / 2 * Tmax + 3 / 2 * T2 + 2 * St2 * (1 - Xthick)) / (1 - Xthick) ** 4
    b7 = (2 * Tmax - 2 * T2 - 3 * St2 * (1 - Xthick)) / (1 - Xthick) ** 3
    b8 = 0
    b9 = St2
    b10 = T2 / 2

    # --- meanline / thickness distribution (verbatim legacy) ---------------
    sc = np.zeros(Npoint)
    yc = np.zeros(Npoint)
    thick = np.zeros(Npoint)

    for i in range(Npoint):
        if xc[i] <= Xmean:
            sc[i] = a1 * xc[i] ** 3 + a2 * xc[i] ** 2 + a3 * xc[i] + a4
            yc[i] = 1 / 4 * a1 * xc[i] ** 4 + 1 / 3 * a2 * xc[i] ** 3 + 1 / 2 * a3 * xc[i] ** 2 + a4 * xc[i]
        else:
            sc[i] = a5 * (1 - xc[i]) ** 3 + a6 * (1 - xc[i]) ** 2 + a7 * (1 - xc[i]) + a8
            yc[i] = -1 / 4 * a5 * (1 - xc[i]) ** 4 - 1 / 3 * a6 * (1 - xc[i]) ** 3 - 1 / 2 * a7 * (1 - xc[i]) ** 2 - a8 * (1 - xc[i]) + (1 / 4 * a1 * Xmean ** 4 + 1 / 3 * a2 * Xmean ** 3 + 1 / 2 * a3 * Xmean ** 2 + a4 * Xmean - (-1 / 4 * a5 * (1 - Xmean) ** 4 - 1 / 3 * a6 * (1 - Xmean) ** 3 - 1 / 2 * a7 * (1 - Xmean) ** 2 - a8 * (1 - Xmean)))

        if xc[i] <= Xthick:
            thick[i] = b1 * xc[i] ** 4 + b2 * xc[i] ** 3 + b3 * xc[i] ** 2 + b4 * xc[i] + b5
        else:
            thick[i] = b6 * (1 - xc[i]) ** 4 + b7 * (1 - xc[i]) ** 3 + b8 * (1 - xc[i]) ** 2 + b9 * (1 - xc[i]) + b10

    # --- blade surfaces (verbatim legacy) ----------------------------------
    xs = xc - thick * np.sin(np.arctan(sc))
    ys = yc + thick * np.cos(np.arctan(sc))
    xp = xc + thick * np.sin(np.arctan(sc))
    yp = yc - thick * np.cos(np.arctan(sc))

    # --- leading-edge circle (verbatim legacy) -----------------------------
    St1 = (Tmax / 2 - T1 / 2) / Xthick
    St2 = (Tmax / 2 - T2 / 2) / (1 - Xthick)

    rr1 = (np.sqrt((xc[0] - xp[0]) ** 2 + (yc[0] - yp[0]) ** 2) +
           np.sqrt((xc[0] - xs[0]) ** 2 + (yc[0] - ys[0]) ** 2)) / 2

    delta1 = np.degrees(np.arctan(St1))
    r1 = rr1 / np.cos(np.radians(delta1))

    dxc = rr1 * np.tan(np.radians(delta1))
    xc0 = xc[0] + dxc
    yc0 = (yc[1] - yc[0]) / (xc[1] - xc[0]) * (xc0 - xc[0]) + yc[0]

    if xc0 == xs[0]:
        Theta_start = 90
    elif xs[0] > xc0:
        Theta_start = np.degrees(np.arctan((ys[0] - yc0) / (xs[0] - xc0)))
    else:
        Theta_start = np.degrees(np.arctan((ys[0] - yc0) / (xs[0] - xc0))) + 180

    if xc0 == xp[0]:
        Theta_end = 270
    elif xp[0] > xc0:
        Theta_end = np.degrees(np.arctan((yp[0] - yc0) / (xp[0] - xc0))) + 360
    else:
        Theta_end = np.degrees(np.arctan((yp[0] - yc0) / (xp[0] - xc0))) + 180

    if Gridswitch < 0:  # O-grid
        Theta_p = np.linspace((Theta_start + Theta_end) / 2, Theta_end, Ncirc + 1)
        Theta_s = np.linspace((Theta_start + Theta_end) / 2, Theta_start, Ncirc + 1)
    else:  # H-grid
        Theta_p = np.linspace(180, Theta_end, Ncirc + 1)
        Theta_s = np.linspace(180, Theta_start, Ncirc + 1)

    xple = r1 * np.cos(np.radians(Theta_p)) + xc0
    yple = r1 * np.sin(np.radians(Theta_p)) + yc0

    xsle = r1 * np.cos(np.radians(Theta_s)) + xc0
    ysle = r1 * np.sin(np.radians(Theta_s)) + yc0

    # --- trailing-edge circle (verbatim legacy) ----------------------------
    rr2 = (np.sqrt((xc[-1] - xp[-1]) ** 2 + (yc[-1] - yp[-1]) ** 2) +
           np.sqrt((xc[-1] - xs[-1]) ** 2 + (yc[-1] - ys[-1]) ** 2)) / 2

    delta2 = np.degrees(np.arctan(St2))
    r2 = rr2 / np.cos(np.radians(delta2))

    dxc = rr2 * np.tan(np.radians(delta2))
    xcn = xc[-1] - dxc
    ycn = (yc[-2] - yc[-1]) / (xc[-2] - xc[-1]) * (xcn - xc[-1]) + yc[-1]

    if xcn == xp[-1]:
        Theta_start = -90
    elif xp[-1] > xcn:
        Theta_start = np.degrees(np.arctan((yp[-1] - ycn) / (xp[-1] - xcn)))
    else:
        Theta_start = np.degrees(np.arctan((yp[-1] - ycn) / (xp[-1] - xcn))) - 180

    if xcn == xs[-1]:
        Theta_end = 90
    elif xs[-1] > xcn:
        Theta_end = np.degrees(np.arctan((ys[-1] - ycn) / (xs[-1] - xcn)))
    else:
        Theta_end = np.degrees(np.arctan((ys[-1] - ycn) / (xs[-1] - xcn))) + 180

    if Gridswitch < 0:  # O-grid
        Theta_p = np.linspace(Theta_start, (Theta_start + Theta_end) / 2, Ncirc + 1)
        Theta_s = np.linspace(Theta_end, (Theta_start + Theta_end) / 2, Ncirc + 1)
    else:  # H-grid
        Theta_p = np.linspace(Theta_start, 0, Ncirc + 1)
        Theta_s = np.linspace(Theta_end, 0, Ncirc + 1)

    xpte = r2 * np.cos(np.radians(Theta_p)) + xc[-1]
    ypte = r2 * np.sin(np.radians(Theta_p)) + yc[-1]

    xste = r2 * np.cos(np.radians(Theta_s)) + xc[-1]
    yste = r2 * np.sin(np.radians(Theta_s)) + yc[-1]

    # --- assemble profile with LE/TE circles (verbatim legacy) -------------
    xp1 = np.concatenate([xple[:Ncirc], xp, xpte[1:]])
    yp1 = np.concatenate([yple[:Ncirc], yp, ypte[1:]]) * Rsign

    xs1 = np.concatenate([xsle[:Ncirc], xs, xste[1:]])
    ys1 = np.concatenate([ysle[:Ncirc], ys, yste[1:]]) * Rsign

    chunks = []
    for i in range(len(xp1)):
        chunks.append(f'{xp1[i]:7.4f} {yp1[i]:7.4f} {xs1[i]:7.4f} {ys1[i]:7.4f}\n')
    return "".join(chunks)


# ---------------------------------------------------------------------------
# LEGACY GT_V1 template handling
# ---------------------------------------------------------------------------
def _template_lines(template_text: str):
    """Minimal structural guard for a legacy GT_V1 .geomTurbo template.

    This is NOT a general geomTurbo parser; it only rejects obviously wrong
    templates so that line slicing cannot silently mis-cut. It never modifies the
    template and does not affect GT_V1 output.
    """
    lines = template_text.splitlines(keepends=True)
    if len(lines) < _MIN_TEMPLATE_LINES:
        raise ValueError(
            f"template too short: {len(lines)} lines (< {_MIN_TEMPLATE_LINES}); "
            "not a legacy GT_V1 .geomTurbo template")
    if lines[0].strip() != "GEOMETRY TURBO":
        raise ValueError("template guard: line 1 is not 'GEOMETRY TURBO'")
    if "PERIODICITY" not in lines[46]:
        raise ValueError("template guard: expected PERIODICITY marker at line 47")
    if lines[72].strip() != "suction":
        raise ValueError("template guard: expected 'suction' at line 73")
    if lines[417].strip() != "pressure":
        raise ValueError("template guard: expected 'pressure' at line 418")
    if not lines[738].strip().startswith("NI_END"):
        raise ValueError("template guard: expected NI_END at line 739")
    if lines[753].strip() != "NI_END GEOMETRY":
        raise ValueError("template guard: expected 'NI_END GEOMETRY' at line 754")
    return lines


def generate_geomturbo_text(profile_text: str, Solidity, template_text: str) -> str:
    """Return the legacy-compatible .geomTurbo text (LEGACY GT_V1 serialization).

    Reproduces the legacy pipeline exactly, including the deliberate round-trip
    that re-parses the already-rounded profile text (this is the key to exact
    regression).
    """
    Solidity = _validate_solidity(Solidity)
    lines = _template_lines(template_text)

    # --- re-parse the serialized (rounded) profile, exactly like legacy ----
    coords = [line.split() for line in io.StringIO(profile_text)]
    z1_ori, y1_ori = map(float, coords[0][:2])
    z2_ori, y2_ori = map(float, coords[-1][:2])
    distance = np.sqrt((z2_ori - z1_ori) ** 2 + (y2_ori - y1_ori) ** 2)
    scaling_factor = CHORD_TARGET / distance
    coords_processed = [[float(value) * scaling_factor for value in line] for line in coords]
    line_count = len(coords_processed)

    z1 = coords_processed[0][0]
    z2 = coords_processed[-1][0]
    inlet_z = z1 - (z2 - z1) * 1.5
    outlet_z = z2 + (z2 - z1) * 2

    out = []
    out.extend(lines[0:14])                                    # template lines 1-14
    out.append(f"   {inlet_z:.5f}   0\n")
    out.append(f"   {outlet_z:.5f}   0\n")
    out.extend(lines[16:25])                                   # 17-25
    out.append(f"   {inlet_z:.5f}   0.003\n")
    out.append(f"   {outlet_z:.5f}   0.003\n")
    out.extend(lines[27:46])                                   # 28-46
    periodicity = CHORD_TARGET / Solidity                      # 0.06 / Solidity
    out.append(f"  PERIODICITY\t\t\t{periodicity:.5f}\n")
    out.extend(lines[47:77])                                   # 48-77
    out.append(f"{line_count}\n")
    for line in coords_processed:
        out.append(f"0   {float(line[3]):7.7f}   {float(line[2]):7.7f}\n")
    out.extend(lines[246:248])                                 # 247-248
    out.append(f"{line_count}\n")
    for line in coords_processed:
        out.append(f"0.003   {float(line[3]):7.7f}   {float(line[2]):7.7f}\n")
    out.extend(lines[417:422])                                 # 418-422
    out.append(f"{line_count}\n")
    for line in coords_processed:
        out.append(f"0   {float(line[1]):7.7f}   {float(line[0]):7.7f}\n")
    out.extend(lines[579:581])                                 # 580-581
    out.append(f"{line_count}\n")
    for line in coords_processed:
        out.append(f"0.003   {float(line[1]):7.7f}   {float(line[0]):7.7f}\n")
    out.extend(lines[738:754])                                 # 739-754
    return "".join(out)


def generate_geometry_texts(Xthick, Tmax, Metal2, Solidity, template_text):
    """Convenience pure API -> ``(profile_text, geomturbo_text)``.

    Deliberately does not accept Incidence / Mach / case_id / any path, so that
    operating conditions cannot enter the geometry core.
    """
    profile_text = generate_profile_text(Xthick, Tmax, Metal2)
    geomturbo_text = generate_geomturbo_text(profile_text, Solidity, template_text)
    return profile_text, geomturbo_text

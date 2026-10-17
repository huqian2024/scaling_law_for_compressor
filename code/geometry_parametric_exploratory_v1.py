"""Exploratory 13-parameter blade geometry generator (LEGACY GT_V1 mathematics).

Purpose
-------
Experiment ``analysis/geometry_review/parameter_sensitivity_v1_100cases/`` needs
the **frozen legacy geometry mathematics** with nine former constants exposed as
parameters.  This module is a new, independent file: it does NOT import and does
NOT modify ``code/geometry_legacy_v1.py``.

Frozen behaviour
----------------
The formulas below are copied verbatim from ``legacy/blade_batch_generation.py``
(and its controlled re-implementation ``code/geometry_legacy_v1.py``).
When the nine exploratory parameters are restored to their legacy defaults::

    Metal1 = 53.0      T1 = 0.015     T2 = 0.0125   Xmean = 0.08
    K_m    = 0.18      Ks1 = 5.0      Ks2 = 0.10    SS1 = 3.2   SS2 = 0.8

the 4-decimal profile text and the .geomTurbo text are byte-identical to
``code/geometry_legacy_v1.py`` for the frozen regression fixtures
(see ``tests/test_geometry_parametric_exploratory_v1.py``).

Known legacy quirks that are **preserved deliberately** (not "fixed"):

* the LE/TE circle construction recomputes ``St1``/``St2`` **without** the
  ``SS1``/``SS2`` factors (legacy lines 142-143).  This is intentional legacy
  behaviour; "fixing" it would silently change the blade shape.
* only ``Ncirc`` of ``Ncirc+1`` LE/TE arc samples are inserted, so a short
  straight chord closes each arc (visible as a junction angle jump).
* ``Metal1`` is the inlet *metal* angle.  No incidence relation is constructed.

Scope
-----
Pure mathematics: no filesystem access, no plotting, no CLI, no CFX/NUMECA.
Returned arrays are float64 in the legacy **normalized** coordinate system
(chord is close to 1 but not exactly 1).  Physical (metre) quantities require
the fixed ``CHORD_TARGET`` scaling used by the frozen serializer.

Boundary of the 13-dimensional space
------------------------------------
``Incidence`` and ``Mach`` are operating conditions and MUST NOT enter this
module.  ``CHORD_TARGET``, ``SPAN``, ``Npoint``, ``Ncirc``, ``Nscale1``,
``Nscale2``, ``Rsign`` and ``Gridswitch`` are frozen discretization / direction
constants, not blade-shape design variables.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

# --- 13 explorable parameters and their legacy defaults ---------------------
PARAM_NAMES = (
    "Xthick", "Tmax", "Metal2", "Solidity",
    "Metal1", "T1", "T2", "Xmean", "K_m", "Ks1", "Ks2", "SS1", "SS2",
)

LEGACY_DEFAULTS = {
    "Xthick": 0.30,      # NOT a legacy constant: experimental baseline (V2 mid)
    "Tmax": 0.055,       # NOT a legacy constant: experimental baseline (V2 mid)
    "Metal2": 15.0,      # NOT a legacy constant: experimental baseline (V2 mid)
    "Solidity": 1.5,     # NOT a legacy constant: experimental baseline (V2 mid)
    "Metal1": 48.0 + 5.0,  # legacy: 48 + DeltaBeta, DeltaBeta = 5  -> 53 deg
    "T1": 0.015,
    "T2": 0.0125,
    "Xmean": 0.08,
    "K_m": 0.18,
    "Ks1": 5.0,
    "Ks2": 0.10,
    "SS1": 3.2,
    "SS2": 0.8,
}

# --- Frozen discretization / direction / scaling constants ------------------
FIXED_CONSTANTS = {
    "Gridswitch": -1.0,   # O-grid
    "Rsign": 1.0,         # suction side sign
    "Npoint": 101,        # profile point count
    "Ncirc": 4,           # LE/TE arc samples / 2
    "DeltaBeta": 5.0,     # only used to document Metal1 = 48 + DeltaBeta
    "Nscale1": 1.7,       # meanline front clustering
    "Nscale2": 1.7,       # meanline rear clustering
    "CHORD_TARGET": 0.06, # metres, frozen serializer target
    "SPAN": 0.003,        # metres, frozen geomTurbo span
}

# Operating conditions are metadata only (frozen for this experiment).
METADATA_FIXED = {"Incidence": 0.0, "Mach": 0.5}


class GeometryParameterError(ValueError):
    """Raised when a parameter combination violates a mathematical precondition."""


def default_params() -> dict:
    """Return the 13 experimental baseline parameters (V2 mid point)."""
    return dict(LEGACY_DEFAULTS)


def resolve_params(params=None, **overrides) -> dict:
    """Merge ``params``/``overrides`` onto the defaults and validate them."""
    resolved = default_params()
    if params:
        resolved.update(dict(params))
    resolved.update(overrides)
    unknown = sorted(set(resolved) - set(PARAM_NAMES))
    if unknown:
        raise GeometryParameterError(f"unknown parameter(s): {', '.join(unknown)}")
    out = {}
    for name in PARAM_NAMES:
        value = float(resolved[name])
        if not math.isfinite(value):
            raise GeometryParameterError(f"{name} must be finite, got {value!r}")
        out[name] = value
    if not (0.0 < out["Xthick"] < 1.0):
        raise GeometryParameterError(
            f"Xthick must satisfy 0 < Xthick < 1, got {out['Xthick']!r}")
    if not (0.0 < out["Xmean"] < 1.0):
        raise GeometryParameterError(
            f"Xmean must satisfy 0 < Xmean < 1, got {out['Xmean']!r}")
    if not out["Solidity"] > 0.0:
        raise GeometryParameterError(
            f"Solidity must be > 0, got {out['Solidity']!r}")
    for name in ("Tmax", "T1", "T2"):
        if not out[name] > 0.0:
            raise GeometryParameterError(f"{name} must be > 0, got {out[name]!r}")
    return out


def _turn_deg(a, b, c) -> float:
    """Unsigned turn angle (deg) of the polyline a -> b -> c."""
    u = np.asarray(b, dtype=float) - np.asarray(a, dtype=float)
    v = np.asarray(c, dtype=float) - np.asarray(b, dtype=float)
    nu = float(np.hypot(u[0], u[1]))
    nv = float(np.hypot(v[0], v[1]))
    if nu <= 0.0 or nv <= 0.0:
        return float("nan")
    cosang = float(np.clip((u[0] * v[0] + u[1] * v[1]) / (nu * nv), -1.0, 1.0))
    return float(np.degrees(np.arccos(cosang)))


def compute_geometry(params=None, **overrides) -> dict:
    """Compute the full legacy geometry with 13 exposed parameters.

    Returns high-precision NumPy arrays (float64) plus intermediate variables.
    Raises :class:`GeometryParameterError` when a mathematical precondition is
    violated (non-finite input, ``Xthick``/``Xmean`` outside ``(0, 1)``,
    ``Solidity``/``Tmax``/``T1``/``T2`` non-positive).
    """
    p = resolve_params(params, **overrides)

    Npoint = int(FIXED_CONSTANTS["Npoint"])
    Ncirc = int(FIXED_CONSTANTS["Ncirc"])
    Nscale1 = float(FIXED_CONSTANTS["Nscale1"])
    Nscale2 = float(FIXED_CONSTANTS["Nscale2"])
    Gridswitch = float(FIXED_CONSTANTS["Gridswitch"])
    Rsign = float(FIXED_CONSTANTS["Rsign"])

    Xthick = p["Xthick"]
    Tmax = p["Tmax"]
    Metal2 = p["Metal2"]
    Metal1 = p["Metal1"]
    T1, T2 = p["T1"], p["T2"]
    Xmean, K_m = p["Xmean"], p["K_m"]
    Ks1, Ks2 = p["Ks1"], p["Ks2"]
    SS1, SS2 = p["SS1"], p["SS2"]

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

    # --- LE / TE circle construction (verbatim legacy) ---------------------
    # NOTE: legacy recomputes St1/St2 WITHOUT the SS1/SS2 factors here.
    St1_le = (Tmax / 2 - T1 / 2) / Xthick
    St2_te = (Tmax / 2 - T2 / 2) / (1 - Xthick)

    rr1 = (np.sqrt((xc[0] - xp[0]) ** 2 + (yc[0] - yp[0]) ** 2) +
           np.sqrt((xc[0] - xs[0]) ** 2 + (yc[0] - ys[0]) ** 2)) / 2

    delta1 = np.degrees(np.arctan(St1_le))
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
        Theta_p_le = np.linspace((Theta_start + Theta_end) / 2, Theta_end, Ncirc + 1)
        Theta_s_le = np.linspace((Theta_start + Theta_end) / 2, Theta_start, Ncirc + 1)
    else:  # H-grid (not used here, kept for verbatim parity)
        Theta_p_le = np.linspace(180, Theta_end, Ncirc + 1)
        Theta_s_le = np.linspace(180, Theta_start, Ncirc + 1)

    xple = r1 * np.cos(np.radians(Theta_p_le)) + xc0
    yple = r1 * np.sin(np.radians(Theta_p_le)) + yc0
    xsle = r1 * np.cos(np.radians(Theta_s_le)) + xc0
    ysle = r1 * np.sin(np.radians(Theta_s_le)) + yc0

    rr2 = (np.sqrt((xc[-1] - xp[-1]) ** 2 + (yc[-1] - yp[-1]) ** 2) +
           np.sqrt((xc[-1] - xs[-1]) ** 2 + (yc[-1] - ys[-1]) ** 2)) / 2

    delta2 = np.degrees(np.arctan(St2_te))
    r2 = rr2 / np.cos(np.radians(delta2))

    dxcn = rr2 * np.tan(np.radians(delta2))
    xcn = xc[-1] - dxcn
    ycn = (yc[-2] - yc[-1]) / (xc[-2] - xc[-1]) * (xcn - xc[-1]) + yc[-1]

    if xcn == xp[-1]:
        Theta_start_te = -90
    elif xp[-1] > xcn:
        Theta_start_te = np.degrees(np.arctan((yp[-1] - ycn) / (xp[-1] - xcn)))
    else:
        Theta_start_te = np.degrees(np.arctan((yp[-1] - ycn) / (xp[-1] - xcn))) - 180

    if xcn == xs[-1]:
        Theta_end_te = 90
    elif xs[-1] > xcn:
        Theta_end_te = np.degrees(np.arctan((ys[-1] - ycn) / (xs[-1] - xcn)))
    else:
        Theta_end_te = np.degrees(np.arctan((ys[-1] - ycn) / (xs[-1] - xcn))) + 180

    if Gridswitch < 0:  # O-grid
        Theta_p_te = np.linspace(Theta_start_te, (Theta_start_te + Theta_end_te) / 2, Ncirc + 1)
        Theta_s_te = np.linspace(Theta_end_te, (Theta_start_te + Theta_end_te) / 2, Ncirc + 1)
    else:  # H-grid
        Theta_p_te = np.linspace(Theta_start_te, 0, Ncirc + 1)
        Theta_s_te = np.linspace(Theta_end_te, 0, Ncirc + 1)

    xpte = r2 * np.cos(np.radians(Theta_p_te)) + xc[-1]
    ypte = r2 * np.sin(np.radians(Theta_p_te)) + yc[-1]
    xste = r2 * np.cos(np.radians(Theta_s_te)) + xc[-1]
    yste = r2 * np.sin(np.radians(Theta_s_te)) + yc[-1]

    # --- assemble profile with LE/TE arcs (verbatim legacy) ----------------
    xp1 = np.concatenate([xple[:Ncirc], xp, xpte[1:]])
    yp1 = np.concatenate([yple[:Ncirc], yp, ypte[1:]]) * Rsign
    xs1 = np.concatenate([xsle[:Ncirc], xs, xste[1:]])
    ys1 = np.concatenate([ysle[:Ncirc], ys, yste[1:]]) * Rsign

    chord = float(np.hypot(xp1[-1] - xp1[0], yp1[-1] - yp1[0]))
    chord_angle = float(np.degrees(np.arctan2(yp1[-1] - yp1[0], xp1[-1] - xp1[0])))

    le_jump = max(
        _turn_deg((xple[Ncirc - 1], yple[Ncirc - 1]), (xp[0], yp[0]), (xp[1], yp[1])),
        _turn_deg((xsle[Ncirc - 1], ysle[Ncirc - 1]), (xs[0], ys[0]), (xs[1], ys[1])),
    )
    te_jump = max(
        _turn_deg((xp[-1], yp[-1]), (xpte[1], ypte[1]), (xpte[2], ypte[2])),
        _turn_deg((xs[-1], ys[-1]), (xste[1], yste[1]), (xste[2], yste[2])),
    )

    i_thick = int(np.argmax(thick))

    return {
        "params": p,
        "xc00": xc00, "xc": xc, "sc": sc, "yc": yc, "thick": thick,
        "xp": xp, "yp": yp, "xs": xs, "ys": ys,
        "xp1": xp1, "yp1": yp1, "xs1": xs1, "ys1": ys1,
        "le_arc_pressure": np.column_stack([xple, yple]),
        "le_arc_suction": np.column_stack([xsle, ysle]),
        "te_arc_pressure": np.column_stack([xpte, ypte]),
        "te_arc_suction": np.column_stack([xste, yste]),
        "r1": float(r1), "rr1": float(rr1), "r2": float(r2), "rr2": float(rr2),
        "delta1_deg": float(delta1), "delta2_deg": float(delta2),
        "St1": float(St1), "St2": float(St2),
        "St1_le": float(St1_le), "St2_te": float(St2_te),
        "le_center": (float(xc0), float(yc0)),
        "te_center": (float(xcn), float(ycn)),
        "le_arc_span_deg": float(abs(Theta_end - Theta_start) / 2.0),
        "te_arc_span_deg": float(abs(Theta_start_te - Theta_end_te) / 2.0),
        "le_junction_angle_jump_deg": float(le_jump),
        "te_junction_angle_jump_deg": float(te_jump),
        "chord_norm": chord,
        "chord_angle_deg": chord_angle,
        "thick_min": float(np.min(thick)),
        "thick_max": float(np.max(thick)),
        "thick_max_xc": float(xc[i_thick]),
        "max_thickness_norm": float(2.0 * np.max(thick)),
        "meanline_max_camber_norm": float(np.max(np.abs(yc))),
        "coefficients": {
            "a1": float(a1), "a2": float(a2), "a3": float(a3), "a4": float(a4),
            "a5": float(a5), "a6": float(a6), "a7": float(a7), "a8": float(a8),
            "b1": float(b1), "b2": float(b2), "b3": float(b3), "b4": float(b4),
            "b5": float(b5), "b6": float(b6), "b7": float(b7), "b8": float(b8),
            "b9": float(b9), "b10": float(b10),
        },
    }


# ---------------------------------------------------------------------------
# Serialization (frozen legacy formatting, 4 decimals)
# ---------------------------------------------------------------------------
def serialize_profile(geom: dict) -> str:
    """Return the legacy 4-column, 4-decimal profile text (frozen format)."""
    xp1, yp1 = geom["xp1"], geom["yp1"]
    xs1, ys1 = geom["xs1"], geom["ys1"]
    return "".join(
        f"{xp1[i]:7.4f} {yp1[i]:7.4f} {xs1[i]:7.4f} {ys1[i]:7.4f}\n"
        for i in range(len(xp1))
    )


_LEGACY_MODULE = None


def _load_frozen_legacy_module():
    """Load ``code/geometry_legacy_v1.py`` read-only (never modified)."""
    global _LEGACY_MODULE
    if _LEGACY_MODULE is None:
        import importlib.util
        path = Path(__file__).with_name("geometry_legacy_v1.py")
        spec = importlib.util.spec_from_file_location(
            "_frozen_geometry_legacy_v1", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LEGACY_MODULE = module
    return _LEGACY_MODULE


def generate_geomturbo_text(profile_text: str, Solidity: float,
                            template_text: str) -> str:
    """Delegate .geomTurbo serialization to the frozen V1 serializer.

    Solidity enters the geometry only here (``periodicity = 0.06 / Solidity``).
    """
    return _load_frozen_legacy_module().generate_geomturbo_text(
        profile_text, Solidity, template_text)


def generate_profile_text(params=None, **overrides) -> str:
    """Convenience: 13 parameters -> legacy 4-decimal profile text."""
    return serialize_profile(compute_geometry(params, **overrides))


def generate_geometry_texts(params=None, template_text: str = "",
                            **overrides):
    """Convenience: 13 parameters -> ``(profile_text, geomturbo_text)``."""
    geom = compute_geometry(params, **overrides)
    profile_text = serialize_profile(geom)
    geomturbo_text = generate_geomturbo_text(
        profile_text, geom["params"]["Solidity"], template_text)
    return profile_text, geomturbo_text


def physical_scale(geom: dict) -> float:
    """Metres per normalized unit used by the frozen serializer (0.06 / chord)."""
    return FIXED_CONSTANTS["CHORD_TARGET"] / geom["chord_norm"]


# ---------------------------------------------------------------------------
# Parameter -> formula map (audit record; nothing is evaluated here)
# ---------------------------------------------------------------------------
PARAMETER_FORMULA_MAP = {
    "Xthick": (
        "thickness polynomial break point (xc <= Xthick); St1/St2 denominators; "
        "b1..b3, b6, b7; LE/TE circle St1/St2 (Tmax/2 - T1/2)/Xthick and "
        "(Tmax/2 - T2/2)/(1-Xthick); hence LE/TE arc centres and radii."),
    "Tmax": (
        "thickness amplitudes Tmax/2 in St1, St2, b1..b3, b6, b7 and in the "
        "LE/TE circle St1/St2; changes thickness distribution and both edge radii."),
    "Metal2": (
        "exit metal angle -> Sm2 = tan(Metal2); enters Sm0, SSm1 = Ks1*(Sm2-Sm1), "
        "SSm2 = Ks2*(Sm2-Sm1) and meanline coefficients a1..a8 (camber/turning)."),
    "Solidity": (
        "does NOT enter the blade coordinates. Only .geomTurbo periodicity = "
        "CHORD_TARGET / Solidity (cascade pitch). Single-blade metrics must be "
        "identical for a fixed (Xthick,Tmax,Metal2,Metal1,T1,T2,Xmean,K_m,Ks1,Ks2,SS1,SS2)."),
    "Metal1": (
        "inlet METAL angle -> Sm1 = tan(Metal1); enters Sm0, SSm1, SSm2 and "
        "a1..a8. Not an incidence and not converted to a flow angle."),
    "T1": (
        "b5 = T1/2 (LE half-thickness of the thickness polynomial), St1 "
        "amplitude, and LE circle rr1/r1 through the surface endpoints."),
    "T2": (
        "b10 = T2/2 (TE half-thickness), St2 amplitude, and TE circle rr2/r2 "
        "through the surface endpoints."),
    "Xmean": (
        "meanline piecewise break point (xc <= Xmean) and denominator of "
        "a1, a2, a5, a6; changes camber distribution and the C1 splice location."),
    "K_m": (
        "fraction of turning at Xmean -> Sm0 = tan(Metal1 + (Metal2-Metal1)*K_m); "
        "enters a1, a2, a5, a6."),
    "Ks1": (
        "front meanline slope multiplier -> SSm1 = Ks1*(Sm2-Sm1); affects "
        "a1, a2, a3 (=SSm1) and the front camber slope/curvature."),
    "Ks2": (
        "rear meanline slope multiplier -> SSm2 = Ks2*(Sm2-Sm1); affects "
        "a1, a2, a5, a6, a7 (=-SSm2) and the rear camber slope/curvature."),
    "SS1": (
        "front thickness-change coefficient -> St1 = SS1*(Tmax/2-T1/2)/Xthick; "
        "affects thickness coefficients b1..b4. NOTE legacy recomputes the LE "
        "circle St1 WITHOUT SS1, so SS1 changes the surface slope but not the "
        "LE arc radius."),
    "SS2": (
        "rear thickness-change coefficient -> St2 = SS2*(Tmax/2-T2/2)/(1-Xthick); "
        "affects thickness coefficients b6, b7, b9. NOTE legacy recomputes the "
        "TE circle St2 WITHOUT SS2, so SS2 changes the surface slope but not the "
        "TE arc radius."),
}

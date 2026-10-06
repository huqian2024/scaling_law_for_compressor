# Research benchmark only.
# Not production DOE generation code.
# Results are documented in docs/DOE_DECISION.md.

import numpy as np
from scipy.stats import qmc
from scipy.spatial.distance import cdist

D = 6
NMAX = 1024
NS = [64, 128, 256, 512, 1024]

# ---------- Candidate A1: max optimized LHS, generation order prefix ----------
lhs = qmc.LatinHypercube(d=D, optimization="random-cd", seed=1)
poolA = lhs.random(n=NMAX)                 # (1024, 6) in [0,1)^6
A1 = poolA                                  # ordering = generation order

# ---------- Candidate A2: same pool, deterministic greedy maximin ordering ----------
# Greedy farthest-point (maximin) ordering:
#   start = point closest to space center (ties -> smallest index)
#   next  = unselected point maximizing min-distance to selected set
#           (ties -> smallest original index, via np.argmax first-occurrence)
def greedy_maximin_order(pool):
    n = len(pool)
    center = np.full(D, 0.5)
    d0 = cdist(pool, center.reshape(1, -1)).ravel()
    order = [int(np.argmin(d0))]
    mind = cdist(pool, pool[order[0]].reshape(1, -1)).ravel()
    selected = np.zeros(n, dtype=bool)
    selected[order[0]] = True
    for _ in range(n - 1):
        mind[selected] = -1.0            # exclude selected
        nxt = int(np.argmax(mind))       # deterministic tie-break (first max)
        order.append(nxt)
        selected[nxt] = True
        dnew = cdist(pool, pool[nxt].reshape(1, -1)).ravel()
        mind = np.minimum(mind, dnew)
    return np.array(order)

orderA2 = greedy_maximin_order(poolA)
A2 = poolA[orderA2]

# ---------- Candidate B: scrambled Sobol, balance-preserving base-2 draw ----------
sob = qmc.Sobol(d=D, scramble=True, seed=1)
B = sob.random_base2(10)                    # 2^10 = 1024 balance-preserving points

SCHEMES = {"A1": A1, "A2": A2, "B": B}

def metrics(pts):
    n = len(pts)
    cd = qmc.discrepancy(pts, method="CD")
    dm = cdist(pts, pts)
    np.fill_diagonal(dm, np.inf)
    minpair = float(dm.min())
    nn = dm.min(axis=1)                     # nearest-neighbour distance per point
    return dict(n=n, cd=float(cd), minpair=minpair,
                nn_mean=float(nn.mean()), nn_median=float(np.median(nn)),
                nn_min=float(nn.min()))

def marginal(pts, bins=10):
    out = {}
    empty = 0
    for j in range(D):
        col = pts[:, j]
        h, _ = np.histogram(col, bins=bins, range=(0.0, 1.0))
        empty += int((h == 0).sum())
        out[j] = (float(col.min()), float(col.max()), int(h.min()))
    return out, empty

# ---------- Nested check ----------
def is_prefix_subset(full, sub):
    # sub rows must all appear in full (exact floats, prefix draw => identical)
    s = set(map(tuple, np.round(sub, 12)))
    f = set(map(tuple, np.round(full, 12)))
    return s.issubset(f)

def nested_report(scheme):
    ok = True
    details = []
    for i in range(len(NS) - 1):
        a, b = scheme[:NS[i]], scheme[:NS[i + 1]]
        r = is_prefix_subset(b, a)
        ok = ok and r
        details.append(f"D{NS[i]} in D{NS[i+1]}: {'PASS' if r else 'FAIL'}")
    return ok, details

print("=" * 78)
print(f"scipy {__import__('scipy').__version__} | numpy {np.__version__} | d={D} NMAX={NMAX}")
print("=" * 78)

for name, scheme in SCHEMES.items():
    print(f"\n--- {name} ---")
    for N in NS:
        m = metrics(scheme[:N])
        print(f"N={N:5d}  CD={m['cd']:.6f}  minpair={m['minpair']:.6f}"
              f"  nn_mean={m['nn_mean']:.6f}  nn_median={m['nn_median']:.6f}"
              f"  nn_min={m['nn_min']:.6f}")

print("\n" + "=" * 78)
print("MARGINAL COVERAGE (per-dim min,max and min bin occupancy; empty bins across 6x10)")
print("=" * 78)
for name, scheme in SCHEMES.items():
    for N in NS:
        cov, empty = marginal(scheme[:N])
        rng = " ".join(f"[{cov[j][0]:.3f},{cov[j][1]:.3f}]" for j in range(D))
        minbin = max(cov[j][2] for j in range(D))
        worst = min(cov[j][2] for j in range(D))
        print(f"{name} N={N:5d}  empty_bins={empty:2d}/60  worst_bin_count={worst}  dims_minmax: {rng}")

print("\n" + "=" * 78)
print("NESTED CHECK")
print("=" * 78)
for name, scheme in SCHEMES.items():
    ok, det = nested_report(scheme)
    print(f"{name}: {'PASS' if ok else 'FAIL'}  |  " + " ; ".join(det))

print("\n" + "=" * 78)
print("A2 vs A1 improvement (CD lower better, minpair higher better)")
print("=" * 78)
for N in NS:
    m1 = metrics(A1[:N]); m2 = metrics(A2[:N])
    print(f"N={N:5d}  CD: A1={m1['cd']:.6f} A2={m2['cd']:.6f} "
          f"(x{m1['cd']/m2['cd']:.3f})   minpair: A1={m1['minpair']:.6f} "
          f"A2={m2['minpair']:.6f} (x{m2['minpair']/m1['minpair']:.3f})")

"""Constraint Satisfaction Problem (CSP) for crop-land allocation.

VARIABLES   x_c  = land allocated to crop c, in integer *land units* (1 unit = L / resolution ha)
DOMAINS     D_c  = {min_c, ..., max_c}      ({0} if the crop is blocked by a rotation/belt rule)
CONSTRAINTS C1  min_c <= x_c <= max_c                       (unary: farmer limits)
            C2  sum_c x_c <= total_units                    (land is limited)
            C3  sum_c x_c >= min_total_units                (minimum land utilisation)
            C4  #{c : x_c > 0} <= max_crops                 (optional: at most K crops)
            C5  x_c = 0 for blocked crops                   (rotation / strict KB-belt rule)
SEARCH      backtracking + MRV variable ordering + forward checking (bounds pruning of C2/C3/C4)
The GA (genetic_algorithm.py) uses this CSP to build feasible starting solutions and to
validate the final answer.
"""
from dataclasses import dataclass, field
import random


class InfeasibleError(Exception):
    """Raised when no allocation can satisfy all constraints."""


@dataclass
class AllocationProblem:
    crops: list
    lower: dict                     # min units per crop
    upper: dict                     # max units per crop
    total_units: int
    min_total_units: int = 0
    blocked: set = field(default_factory=set)
    max_crops: int = None
    step_ha: float = 1.0

    # -- domains -------------------------------------------------------------
    def bounds(self, crop):
        if crop in self.blocked:
            return (0, 0) if self.lower[crop] <= 0 else (1, 0)      # (1,0) = empty domain
        return max(self.lower[crop], 0), self.upper[crop]

    def initial_domains(self):
        doms = {}
        for c in self.crops:
            lo, hi = self.bounds(c)
            doms[c] = list(range(lo, hi + 1)) if hi >= lo else []
        return doms

    # -- repair: project any vector back into the feasible region ------------
    def repair(self, x, rng):
        n = len(self.crops)
        lo = [self.bounds(c)[0] for c in self.crops]
        hi = [self.bounds(c)[1] for c in self.crops]
        x = [min(max(int(v), lo[i]), hi[i]) for i, v in enumerate(x)]
        if self.max_crops is not None:                       # C4: drop smallest optional crops
            nz = [i for i in range(n) if x[i] > 0]
            while len(nz) > self.max_crops:
                optional = [i for i in nz if lo[i] == 0]
                if not optional:
                    break
                j = min(optional, key=lambda i: x[i])
                x[j] = 0
                nz.remove(j)
        total = sum(x)
        while total > self.total_units:                      # C2: shrink
            idx = [i for i in range(n) if x[i] > lo[i]]
            if not idx:
                break
            i = rng.choice(idx)
            d = min(total - self.total_units, x[i] - lo[i])
            x[i] -= d
            total -= d
        while total < self.min_total_units:                  # C3: grow
            nz = sum(1 for v in x if v > 0)
            idx = [i for i in range(n) if x[i] < hi[i] and
                   (x[i] > 0 or self.max_crops is None or nz < self.max_crops)]
            if not idx:
                break
            i = rng.choice(idx)
            d = min(self.min_total_units - total, hi[i] - x[i])
            x[i] += d
            total += d
        return x

    def to_hectares(self, x):
        return {c: v * self.step_ha for c, v in zip(self.crops, x)}


class AllocationCSP:
    """Backtracking search with forward checking for an AllocationProblem."""

    def __init__(self, problem: AllocationProblem):
        self.p = problem
        self.stats = {"nodes": 0, "backtracks": 0}

    # -- forward checking: prune values that can no longer be part of a solution
    def _prune(self, doms, assigned_sum, assigned_nonzero):
        p = self.p
        changed = True
        while changed:
            changed = False
            for r in list(doms):
                others = [o for o in doms if o != r]
                min_other = sum(min(doms[o]) for o in others)
                max_other = sum(max(doms[o]) for o in others)
                forced = sum(1 for o in others if 0 not in doms[o])      # others that must be > 0
                new = []
                for v in doms[r]:
                    if assigned_sum + v + min_other > p.total_units:        # C2
                        continue
                    if assigned_sum + v + max_other < p.min_total_units:    # C3
                        continue
                    if p.max_crops is not None and assigned_nonzero + forced + (v > 0) > p.max_crops:   # C4
                        continue
                    new.append(v)
                if not new:
                    return None
                if len(new) < len(doms[r]):
                    doms[r] = new
                    changed = True
        return doms

    def solve(self, rng=None, randomise=True, max_nodes=100000):
        """Return one feasible assignment {crop: units} or None."""
        rng = rng or random.Random(0)
        self.stats = {"nodes": 0, "backtracks": 0}
        doms = self.p.initial_domains()
        if any(len(d) == 0 for d in doms.values()):
            return None
        doms = self._prune(doms, 0, 0)
        if doms is None:
            return None
        return self._backtrack({}, doms, 0, 0, rng, randomise, max_nodes)

    def _backtrack(self, assign, doms, s, nz, rng, randomise, max_nodes):
        if not doms:
            return dict(assign)
        var = min(doms, key=lambda c: (len(doms[c]), c))       # MRV: smallest domain first
        values = list(doms[var])
        if randomise:
            rng.shuffle(values)
        for v in values:
            self.stats["nodes"] += 1
            if self.stats["nodes"] > max_nodes:
                return None
            rest = {c: list(d) for c, d in doms.items() if c != var}
            ns, nnz = s + v, nz + (v > 0)
            if rest:
                rest = self._prune(rest, ns, nnz)
            elif not (self.p.min_total_units <= ns <= self.p.total_units):
                rest = None
            if rest is None:
                self.stats["backtracks"] += 1
                continue
            assign[var] = v
            res = self._backtrack(assign, rest, ns, nnz, rng, randomise, max_nodes)
            if res is not None:
                return res
            del assign[var]
        return None

    def is_feasible(self):
        return self.solve(randomise=False) is not None

    # -- validation of any (e.g. GA) answer -------------------------------------
    def check(self, x):
        """List of {constraint, passed, detail}; x is a list aligned with problem.crops."""
        p, out = self.p, []
        a = dict(zip(p.crops, x))
        tot = sum(x)
        out.append({"constraint": "Total allocated land <= available land", "passed": tot <= p.total_units,
                    "detail": f"{tot * p.step_ha:.2f} ha of {p.total_units * p.step_ha:.2f} ha"})
        out.append({"constraint": "Minimum land utilisation", "passed": tot >= p.min_total_units,
                    "detail": f"{tot * p.step_ha:.2f} ha >= {p.min_total_units * p.step_ha:.2f} ha"})
        for c in p.crops:
            lo, hi = p.bounds(c)
            ok = lo <= a[c] <= hi
            lab = "blocked (rotation/belt) -> 0 ha" if c in p.blocked else f"{lo * p.step_ha:.2f} <= x <= {hi * p.step_ha:.2f} ha"
            out.append({"constraint": f"{c}: allocation within limits", "passed": ok,
                        "detail": f"{a[c] * p.step_ha:.2f} ha; {lab}"})
        out.append({"constraint": "Non-negative allocations", "passed": all(v >= 0 for v in x), "detail": "all x >= 0"})
        if p.max_crops is not None:
            k = sum(1 for v in x if v > 0)
            out.append({"constraint": f"At most {p.max_crops} crops", "passed": k <= p.max_crops, "detail": f"{k} crops used"})
        return out

    def satisfies(self, x):
        return all(r["passed"] for r in self.check(x))

    def diagnose(self):
        """Human-readable reasons why the problem has no solution."""
        p, why = self.p, []
        for c in p.crops:
            lo, hi = p.bounds(c)
            if hi < lo:
                why.append(f"{c} is blocked by a rotation/belt rule but has a minimum allocation > 0.")
        mins = sum(max(p.bounds(c)[0], 0) for c in p.crops if p.bounds(c)[1] >= p.bounds(c)[0])
        maxs = sum(p.bounds(c)[1] for c in p.crops if p.bounds(c)[1] >= p.bounds(c)[0])
        if mins > p.total_units:
            why.append(f"Sum of minimum allocations ({mins * p.step_ha:.2f} ha) exceeds available land ({p.total_units * p.step_ha:.2f} ha).")
        if maxs < p.min_total_units:
            why.append(f"Sum of maximum allocations ({maxs * p.step_ha:.2f} ha) cannot reach the required utilisation ({p.min_total_units * p.step_ha:.2f} ha).")
        if p.max_crops is not None:
            forced = sum(1 for c in p.crops if p.bounds(c)[0] > 0)
            if forced > p.max_crops:
                why.append(f"{forced} crops have a minimum > 0 but at most {p.max_crops} crops are allowed.")
        return why or ["The constraints are jointly unsatisfiable."]

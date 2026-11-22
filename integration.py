"""One integrated pipeline: Historical data + KB  ->  Propositional Logic  ->  CSP  ->  GA  ->  validated plan.

Data flow (see docs/architecture.md):
  1. File 1 gives reference yields / historical area shares per district and crop.
  2. File 3 (KB) is compiled into propositional rules. Planning-relevant outputs of the rule base:
       a. crop-belt facts (e.g. "Cotton belt: ...") -> CSP unary constraint when 'strict belt' is on,
          otherwise a visible warning;
       b. the rice water-use entry fires when the farmer reports low water -> planner warning;
       c. after planning, the rule base returns disease/pest guidance for the chosen crops.
  3. File 2 gives district soil / water context (informational).
  4. CSP builds the feasible region (also seeds the GA and validates the final answer).
  5. GA searches inside that region for the allocation with the best fitness.
"""
import math
import random
import pandas as pd
from algorithms.csp import AllocationProblem, AllocationCSP, InfeasibleError
from algorithms.genetic_algorithm import GeneticAlgorithm
from utils import calculations as calc
from utils.validation import validate_planner_inputs
from evaluation import baseline as bl
from evaluation.metrics import improvement_pct


def district_context(data, district, start, end):
    s = data["soil"]
    sub = s[(s["District"] == district) & (s["Year"].between(start, end))]
    if sub.empty:
        sub = s[s["District"] == district]
    if sub.empty:
        return {}
    return {"soil_type": sub["Soil_Type"].mode().iat[0], "soil_ph": float(sub["Soil_pH"].mean()),
            "water": sub["Water_Availability"].mode().iat[0], "irrigation": sub["Irrigation_Availability"].mode().iat[0],
            "rainfall_mm": float(sub["Rainfall"].mean())}


def build_problem(crops, mins_ha, maxs_ha, land_ha, utilisation, blocked=(), max_crops=None, resolution=100):
    step = land_ha / resolution
    lower = {c: int(math.ceil(mins_ha.get(c, 0) / step - 1e-9)) for c in crops}
    upper = {c: int(math.floor(min(maxs_ha.get(c, land_ha), land_ha) / step + 1e-9)) for c in crops}
    return AllocationProblem(list(crops), lower, upper, resolution, int(math.ceil(utilisation * resolution - 1e-9)),
                             set(blocked), max_crops, step)


def plan_crops(data, rule_base, district, season, land_ha, crops, mins_ha=None, maxs_ha=None,
               start_year=2015, end_year=2024, rotation_blocked=(), utilisation=0.95, alpha=0.5,
               max_crops=None, strict_belt=False, water_level=None, resolution=100, seed=0,
               ga_params=None, min_years=3):
    mins_ha, maxs_ha = dict(mins_ha or {}), dict(maxs_ha or {})
    crops = list(crops)
    errors, warnings = validate_planner_inputs(district, season, land_ha, crops, mins_ha, maxs_ha, data["districts"],
                                               start_year, end_year, utilisation, alpha, max_crops)
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings}
    table = data["table"]
    land_ha = float(land_ha)

    # 1. historical reference yields (crops without enough valid history are dropped, never guessed)
    ref, missing = calc.reference_yields(table, district, crops, start_year, end_year, min_years)
    for c in missing:
        warnings.append(f"{c}: fewer than {min_years} valid historical yield records for {district} "
                        f"({start_year}-{end_year}); excluded from planning.")
    crops = [c for c in crops if c in ref.index]
    if not crops:
        return {"ok": False, "errors": ["None of the selected crops has enough historical yield data for this district and period."], "warnings": warnings}
    pun = calc.punjab_reference_yields(table, crops, start_year, end_year)
    yields = [float(ref.loc[c, "ref_yield"]) for c in crops]
    index = [float(ref.loc[c, "ref_yield"] / pun[c]) if pun.get(c, 0) > 0 else 1.0 for c in crops]
    shares = calc.historical_area_shares(table, district, crops, start_year, end_year)
    if len(yields) > 1 and max(yields) > 5 * sorted(yields)[len(yields) // 2]:
        warnings.append("Some selected crops have much higher tonnage per hectare than others (e.g. sugarcane, vegetables). "
                        "Estimated production in tonnes favours them; lower the 'production weight' to rely more on the "
                        "yield-performance index, and treat tonnes of different crops as non-comparable in value.")

    # 2. knowledge-base derived planning information (propositional logic output -> planner)
    blocked, kb_notes = set(rotation_blocked) & set(crops), []
    for c in crops:
        belt = data["belts"].get(c)
        if belt and district not in belt:
            msg = f"KB crop-belt rule: {c} is listed for {', '.join(sorted(belt))}; {district} is not in that list."
            if strict_belt:
                blocked.add(c)
                msg += " Excluded (strict belt mode)."
            warnings.append(msg)
            kb_notes.append(msg)
    ctx = district_context(data, district, start_year, end_year)
    if water_level in ("Low", "Very Low") and "Rice" in crops:
        ans = rule_base.answer(crop="Rice", categories=["Management"], symptoms="high water use falling water table")
        for m in ans["matches"][:1]:
            warnings.append(f"Water warning (KB rule {m['kb_id']}): {m['cause']} - {m['action']}")
            kb_notes.append(f"Rice water-use rule fired (KB entry {m['kb_id']}).")
    if ctx and ctx["water"] in ("Low", "Very Low") and water_level not in ("Low", "Very Low"):
        warnings.append(f"File 2 lists water availability in {district} as '{ctx['water']}'.")

    # 3. CSP: define the feasible region
    problem = build_problem(crops, mins_ha, maxs_ha, land_ha, utilisation, blocked, max_crops, resolution)
    csp = AllocationCSP(problem)
    if not csp.is_feasible():
        return {"ok": False, "errors": ["No allocation satisfies all constraints: " + " ".join(csp.diagnose())], "warnings": warnings}

    # 4. GA inside the feasible region
    fit = calc.make_fitness(yields, index, problem.step_ha, land_ha, alpha)
    gp = dict(ga_params or {})
    gp.setdefault("seed", seed)
    try:
        ga = GeneticAlgorithm(problem, fit, **gp).run()
    except InfeasibleError as e:
        return {"ok": False, "errors": [str(e)], "warnings": warnings}
    best = ga.best
    if not csp.satisfies(best):                       # safety net: never return an invalid plan
        best = [csp.solve(rng=random.Random(seed))[c] for c in problem.crops]
    validation = csp.check(best)

    # 5. baselines (repaired so that they are feasible too; raw satisfaction also reported)
    eq_raw, hs_raw = bl.equal_allocation_raw(problem), bl.historical_share_raw(problem, shares)
    eq, hs = bl.equal_allocation(problem, seed), bl.historical_share_allocation(problem, shares, seed)
    methods = {"Equal split": eq, "Historical-share": hs, "GA (optimised)": best}
    comp = []
    for name, x in methods.items():
        e = fit.estimate(x)
        comp.append({"Method": name, "Land used (ha)": sum(x) * problem.step_ha, "Est. production (t)": e["production_t"],
                     "Performance index": e["performance_index"], "Fitness": e["fitness"]})
    comp = pd.DataFrame(comp)
    comp["Production vs equal split (%)"] = [improvement_pct(v, comp.loc[0, "Est. production (t)"]) for v in comp["Est. production (t)"]]

    ha = problem.to_hectares(best)
    result = pd.DataFrame({
        "Crop": crops, "Allocation (ha)": [ha[c] for c in crops],
        "Share of land (%)": [100 * ha[c] / land_ha for c in crops],
        "Reference yield (t/ha)": yields, "Performance index": index,
        "Years of data": [int(ref.loc[c, "n_years"]) for c in crops],
        "Est. production (t)": [ha[c] * y for c, y in zip(crops, yields)],
        "Equal split (ha)": [v * problem.step_ha for v in eq], "Historical-share (ha)": [v * problem.step_ha for v in hs],
    })
    est = fit.estimate(best)
    advisories = {}
    for c in crops:
        if ha[c] > 0:
            a = rule_base.answer(crop=c, categories=["Disease", "Pest"], top_k=3)
            advisories[c] = a["matches"]
    return {
        "ok": True, "errors": [], "warnings": warnings, "kb_notes": kb_notes, "table": result, "comparison": comp,
        "validation": validation, "total_allocated_ha": sum(best) * problem.step_ha,
        "remaining_ha": land_ha - sum(best) * problem.step_ha, "land_ha": land_ha, "estimate": est,
        "ga": ga, "csp_stats": dict(csp.stats), "problem": problem, "context": ctx, "advisories": advisories,
        "raw_baseline_satisfaction": {"Equal split": csp.satisfies(eq_raw), "Historical-share": csp.satisfies(hs_raw)},
        "settings": {"district": district, "season": season, "years": f"{start_year}-{end_year}", "alpha": alpha,
                     "resolution": resolution, "seed": seed},
    }

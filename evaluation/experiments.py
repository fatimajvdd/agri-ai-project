"""Runs every experiment of the project and writes tables + charts to results/.

    python -m evaluation.experiments

Design (planner): for every Punjab district x season x test year (2022, 2023, 2024) we plan using ONLY the
9 years before the test year (reference yields), then evaluate the plan with the ACTUAL yields of the test year
(held-out). Crops = 4 largest crops (by mean harvested area) of that district/season with valid data. Land = 50 ha,
every crop between 5% and 60% of the land, >= 95% of land used.
"""
import json
import random
import time
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

from utils.data_loader import load_all
from utils import calculations as calc
from algorithms.csp import AllocationCSP
from algorithms.genetic_algorithm import GeneticAlgorithm
from algorithms.propositional_logic import KnowledgeRuleBase
from integration import build_problem
from evaluation import baseline as bl
from evaluation.metrics import realised_production, constraint_satisfaction_rate
from evaluation.advisory_eval import evaluate_advisor

ROOT = Path(__file__).resolve().parent.parent
OUT, CH = ROOT / "results" / "evaluation_results", ROOT / "results" / "charts"
LAND, MIN_FRAC, MAX_FRAC, UTIL, N_CROPS = 50.0, 0.05, 0.60, 0.95, 4
TEST_YEARS, WINDOW = (2022, 2023, 2024), 9
GREEN, GOLD, GREY, BROWN = "#2e7d32", "#f9a825", "#90a4ae", "#8d6e63"


def scenarios(data):
    t = data["table"]
    for district in data["districts"]:
        for season in calc.SEASONS:
            for ty in TEST_YEARS:
                s0, s1 = ty - WINDOW, ty - 1
                cand = calc.candidate_crops(t, district, season, s0, s1, min_years=5)
                actual = t[(t.District == district) & (t.Year_Start == ty) & t.Valid & ~t.Is_Aggregate].set_index("Crop")["Yield_t_ha"]
                cand = cand[cand["Crop"].isin(actual.index)].head(N_CROPS)
                if len(cand) < N_CROPS:
                    yield {"district": district, "season": season, "test_year": ty, "skip": True}
                    continue
                yield {"district": district, "season": season, "test_year": ty, "skip": False,
                       "crops": list(cand["Crop"]), "start": s0, "end": s1, "actual": actual.to_dict()}


def run_planner_experiments(data):
    t = data["table"]
    rows, curves, csp_ok = [], [], []
    skipped = 0
    for k, sc in enumerate(scenarios(data)):
        if sc["skip"]:
            skipped += 1
            continue
        crops = sc["crops"]
        ref, _ = calc.reference_yields(t, sc["district"], crops, sc["start"], sc["end"], 3)
        if len(ref) < len(crops):
            skipped += 1
            continue
        pun = calc.punjab_reference_yields(t, crops, sc["start"], sc["end"])
        y = [float(ref.loc[c, "ref_yield"]) for c in crops]
        idx = [float(ref.loc[c, "ref_yield"] / pun[c]) for c in crops]
        shares = calc.historical_area_shares(t, sc["district"], crops, sc["start"], sc["end"])
        mins = {c: MIN_FRAC * LAND for c in crops}
        maxs = {c: MAX_FRAC * LAND for c in crops}
        prob = build_problem(crops, mins, maxs, LAND, UTIL)
        csp = AllocationCSP(prob)
        if not csp.is_feasible():
            skipped += 1
            continue
        fit_eval = calc.make_fitness(y, idx, prob.step_ha, LAND, 0.5)       # common yardstick for all methods
        seed = 1000 + k
        eq_raw, hs_raw = bl.equal_allocation_raw(prob), bl.historical_share_raw(prob, shares)
        csp_ok.append({"Equal split (raw)": csp.satisfies(eq_raw), "Historical-share (raw)": csp.satisfies(hs_raw)})
        methods = {
            "Equal split": bl.equal_allocation(prob, seed),
            "Historical-share": bl.historical_share_allocation(prob, shares, seed),
            "CSP only (random feasible)": [csp.solve(rng=random.Random(seed))[c] for c in crops],
        }
        runtime, gens = {}, {}
        for name, alpha in (("GA (alpha=0.5)", 0.5), ("GA (production only, alpha=1)", 1.0), ("GA (index only, alpha=0)", 0.0)):
            f = calc.make_fitness(y, idx, prob.step_ha, LAND, alpha)
            res = GeneticAlgorithm(prob, f, seed=seed).run()
            methods[name], runtime[name], gens[name] = res.best, res.runtime_s, res.generations_run
            if name == "GA (alpha=0.5)":
                curves.append(res.history["best"].to_numpy())
        for name, x in methods.items():
            e = fit_eval.estimate(x)
            rows.append({"district": sc["district"], "season": sc["season"], "test_year": sc["test_year"],
                         "method": name, "crops": "|".join(crops), "est_production_t": e["production_t"],
                         "performance_index": e["performance_index"], "fitness_a05": e["fitness"],
                         "heldout_production_t": realised_production(prob, x, sc["actual"]),
                         "land_used_pct": 100 * sum(x) / prob.total_units, "feasible": csp.satisfies(x),
                         "runtime_s": runtime.get(name, np.nan), "generations": gens.get(name, np.nan),
                         "alloc_ha": json.dumps({c: round(v * prob.step_ha, 2) for c, v in zip(crops, x)})})
    return pd.DataFrame(rows), curves, pd.DataFrame(csp_ok), skipped


def summarise(df, csp_ok):
    key = ["district", "season", "test_year"]
    piv = lambda col: df.pivot_table(index=key, columns="method", values=col)
    est, held = piv("est_production_t"), piv("heldout_production_t")
    fit, perf = piv("fitness_a05"), piv("performance_index")
    methods = list(est.columns)
    order = ["Equal split", "Historical-share", "CSP only (random feasible)", "GA (alpha=0.5)",
             "GA (production only, alpha=1)", "GA (index only, alpha=0)"]
    methods = [m for m in order if m in methods]
    summ = pd.DataFrame({
        "mean_est_production_t": est[methods].mean(), "mean_heldout_production_t": held[methods].mean(),
        "mean_performance_index": perf[methods].mean(), "mean_fitness_a05": fit[methods].mean(),
        "heldout_vs_equal_pct": [100 * (held[m] / held["Equal split"] - 1).mean() for m in methods],
        "heldout_vs_histshare_pct": [100 * (held[m] / held["Historical-share"] - 1).mean() for m in methods],
        "est_vs_histshare_pct": [100 * (est[m] / est["Historical-share"] - 1).mean() for m in methods],
        "feasible_pct": [100 * df[df.method == m]["feasible"].mean() for m in methods],
        "mean_land_used_pct": [df[df.method == m]["land_used_pct"].mean() for m in methods],
    }, index=methods)
    tests = {}
    for m in ("GA (alpha=0.5)", "GA (production only, alpha=1)"):
        for b in ("Equal split", "Historical-share", "CSP only (random feasible)"):
            d = (held[m] - held[b]).dropna()
            w = stats.wilcoxon(d) if (d != 0).any() else None
            tests[f"{m} vs {b} (held-out production)"] = {
                "n": int(len(d)), "mean_diff_t": float(d.mean()), "wins_pct": float(100 * (d > 0).mean()),
                "wilcoxon_p": float(w.pvalue) if w else None}
    ga_t = df[df.method == "GA (alpha=0.5)"]
    extra = {"ga_mean_runtime_s": float(ga_t["runtime_s"].mean()), "ga_max_runtime_s": float(ga_t["runtime_s"].max()),
             "ga_mean_generations": float(ga_t["generations"].mean()), "n_scenarios": int(len(est)),
             "raw_baseline_constraint_satisfaction_pct": {c: float(100 * csp_ok[c].mean()) for c in csp_ok.columns}}
    return summ, tests, extra, held


def make_charts(summ, held, curves, df):
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "font.size": 10})
    show = ["Equal split", "Historical-share", "CSP only (random feasible)", "GA (alpha=0.5)", "GA (production only, alpha=1)"]
    cols = [GREY, BROWN, "#bcaaa4", GREEN, GOLD]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for a, col, title in ((ax[0], "mean_est_production_t", "Estimated production (reference yields)"),
                          (ax[1], "mean_heldout_production_t", "Held-out production (actual yield of test year)")):
        a.bar(range(len(show)), summ.loc[show, col], color=cols)
        a.set_xticks(range(len(show)))
        a.set_xticklabels(["Equal", "Hist.\nshare", "CSP\nonly", "GA\nα=0.5", "GA\nα=1"])
        a.set_title(title); a.set_ylabel("tonnes per 50 ha plan (mean of scenarios)")
    fig.tight_layout(); fig.savefig(CH / "01_production_by_method.png", dpi=150); plt.close(fig)

    L = max(len(c) for c in curves)
    M = np.array([np.pad(c, (0, L - len(c)), mode="edge") for c in curves])
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.plot(range(1, L + 1), M.mean(0), color=GREEN, lw=2, label="mean best fitness")
    ax.fill_between(range(1, L + 1), np.percentile(M, 10, 0), np.percentile(M, 90, 0), color=GREEN, alpha=.2, label="10-90th percentile")
    ax.set_xlabel("generation"); ax.set_ylabel("best fitness (α=0.5)"); ax.set_title("GA convergence across all scenarios"); ax.legend()
    fig.tight_layout(); fig.savefig(CH / "02_ga_convergence.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    data_ = [100 * (held[m] / held["Historical-share"] - 1).dropna() for m in ("GA (alpha=0.5)", "GA (production only, alpha=1)", "Equal split")]
    ax.boxplot(data_, tick_labels=["GA α=0.5", "GA α=1", "Equal split"], showfliers=False, patch_artist=True,
               boxprops=dict(facecolor="#c8e6c9"), medianprops=dict(color="black"))
    ax.axhline(0, color="k", lw=.8); ax.set_ylabel("held-out production vs historical-share (%)")
    ax.set_title("Per-scenario difference to the historical-share baseline")
    fig.tight_layout(); fig.savefig(CH / "03_heldout_vs_baseline.png", dpi=150); plt.close(fig)

    t = df[df.method == "GA (alpha=0.5)"]
    fig, ax = plt.subplots(figsize=(6, 3.8))
    ax.hist(t["runtime_s"] * 1000, bins=25, color=GREEN)
    ax.set_xlabel("GA runtime per plan (ms)"); ax.set_ylabel("scenarios"); ax.set_title("Execution time")
    fig.tight_layout(); fig.savefig(CH / "04_runtime.png", dpi=150); plt.close(fig)


def advisory_chart(summary):
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False})
    names = ["Top-1\naccuracy", "Top-3\naccuracy", "Rule\nactivation", "Supported\ncoverage", "Unsupported\nrejection", "Farmer-style\n(top-3)"]
    vals = [summary[k] for k in ("top1_accuracy_pct", "top3_accuracy_pct", "rule_activation_accuracy_pct",
                                 "supported_coverage_pct", "unsupported_rejection_pct", "hard_top3_pct")]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.bar(names, vals, color=[GREEN] * 5 + [GOLD]); ax.set_ylim(0, 105); ax.set_ylabel("%")
    for i, v in enumerate(vals):
        ax.text(i, v + 1.5, f"{v:.0f}", ha="center")
    ax.set_title("Advisory module evaluation (manual test set)")
    fig.tight_layout(); fig.savefig(CH / "05_advisory_metrics.png", dpi=150); plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True); CH.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    data = load_all()
    rb = KnowledgeRuleBase(data["kb"], data["table"].Crop.unique())
    adv, adv_rows, adv_err = evaluate_advisor(rb)
    pd.DataFrame(adv_rows).to_csv(OUT / "advisory_cases.csv", index=False)
    (OUT / "advisory_summary.json").write_text(json.dumps(adv, indent=2))
    advisory_chart(adv)
    df, curves, csp_ok, skipped = run_planner_experiments(data)
    df.to_csv(OUT / "planner_scenarios.csv", index=False)
    summ, tests, extra, held = summarise(df, csp_ok)
    extra["scenarios_skipped"] = skipped
    summ.round(4).to_csv(OUT / "planner_summary.csv")
    (OUT / "planner_tests.json").write_text(json.dumps({"tests": tests, "extra": extra}, indent=2))
    make_charts(summ, held, curves, df)
    print(summ.round(3).to_string()); print(json.dumps(tests, indent=1)); print(json.dumps(extra, indent=1))
    print("advisory:", json.dumps(adv, indent=1)); print(f"done in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()

"""Plain statistics used by the planner (not AI algorithms)."""
import numpy as np
import pandas as pd

ACRE_TO_HA = 0.40468564224
SEASONS = ("Kharif", "Rabi")


def to_hectares(value: float, unit: str) -> float:
    return value * ACRE_TO_HA if unit.lower().startswith("acre") else value


def valid_rows(table, district=None, crops=None, start=None, end=None):
    m = table["Valid"] & ~table["Is_Aggregate"]
    if district is not None:
        m &= table["District"] == district
    if crops is not None:
        m &= table["Crop"].isin(crops)
    if start is not None:
        m &= table["Year_Start"] >= start
    if end is not None:
        m &= table["Year_Start"] <= end
    return table[m]


def candidate_crops(table, district, season, start, end, min_years=3) -> pd.DataFrame:
    """Crops of the chosen season (plus Annual ones, e.g. sugarcane) with enough valid history."""
    sub = valid_rows(table, district, None, start, end)
    sub = sub[sub["Season"].isin([season, "Annual"])]
    if sub.empty:
        return pd.DataFrame(columns=["Crop", "n_years", "ref_yield", "mean_area_ha"])
    g = sub.groupby("Crop").agg(n_years=("Year_Start", "nunique"), ref_yield=("Yield_t_ha", "median"),
                                mean_area_ha=("Area_Harvested_ha", "mean"))
    return g[g["n_years"] >= min_years].sort_values("mean_area_ha", ascending=False).reset_index()


def reference_yields(table, district, crops, start, end, min_years=3):
    """Median valid district yield per crop over the period. Returns (df, missing_crops)."""
    sub = valid_rows(table, district, crops, start, end)
    g = sub.groupby("Crop").agg(ref_yield=("Yield_t_ha", "median"), n_years=("Year_Start", "nunique"))
    ok = g[g["n_years"] >= min_years]
    missing = [c for c in crops if c not in ok.index]
    return ok, missing


def punjab_reference_yields(table, crops, start, end) -> pd.Series:
    """Median valid yield across all Punjab districts/years: the yardstick for the performance index."""
    sub = valid_rows(table, None, crops, start, end)
    return sub.groupby("Crop")["Yield_t_ha"].median()


def historical_area_shares(table, district, crops, start, end) -> pd.Series:
    """Mean yearly share of each crop's harvested area among the selected crops (historical practice)."""
    sub = valid_rows(table, district, crops, start, end)
    if sub.empty:
        return pd.Series(1.0 / len(crops), index=crops)
    piv = sub.pivot_table(index="Year_Start", columns="Crop", values="Area_Harvested_ha", aggfunc="sum").reindex(columns=crops).fillna(0)
    tot = piv.sum(axis=1).replace(0, np.nan)
    shares = piv.div(tot, axis=0).mean().fillna(0)
    return shares / shares.sum() if shares.sum() > 0 else pd.Series(1.0 / len(crops), index=crops)


def make_fitness(yields, index, step_ha, land_ha, alpha):
    """Fitness of an allocation x (integer land units per crop), in [0, 1].

        production  P(x) = sum_i  x_i * step * y_i                       [tonnes]
        perf. index I(x) = sum_i (x_i*step / L) * (y_i / y_i^Punjab)     [dimensionless]
        fitness     F(x) = alpha * P / P_max + (1 - alpha) * I / I_max

    P_max = L * max(y_i) and I_max = max(index_i) are upper bounds that make the two
    terms comparable (tonnes of sugarcane vs tonnes of cotton are not otherwise comparable).
    """
    y = list(yields)
    idx = list(index)
    p_max = land_ha * max(y) if max(y) > 0 else 1.0
    i_max = max(idx) if max(idx) > 0 else 1.0

    def estimate(x):
        prod = sum(xi * step_ha * yi for xi, yi in zip(x, y))
        perf = sum((xi * step_ha / land_ha) * ii for xi, ii in zip(x, idx))
        return {"production_t": prod, "performance_index": perf,
                "fitness": alpha * prod / p_max + (1 - alpha) * perf / i_max}

    def fitness(x):
        return estimate(x)["fitness"]
    fitness.estimate = estimate
    return fitness

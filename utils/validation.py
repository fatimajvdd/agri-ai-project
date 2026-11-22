"""Input validation for the Crop Planner. Returns messages; never raises on bad user input."""
import math


def _num(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def validate_planner_inputs(district, season, land_ha, crops, mins_ha, maxs_ha, known_districts,
                            start_year=None, end_year=None, utilisation=0.95, alpha=0.5, max_crops=None):
    """Return (errors, warnings). An empty `errors` list means the request may be solved."""
    errors, warnings = [], []
    if district not in set(known_districts):
        errors.append(f"Unknown district '{district}'. Choose a Punjab district from the list.")
    if season not in ("Kharif", "Rabi"):
        errors.append("Season must be Kharif or Rabi.")
    land = _num(land_ha)
    if land is None or land <= 0:
        errors.append("Available land must be a number greater than zero.")
        land = None
    elif land > 100000:
        errors.append("Available land is unrealistically large (> 100,000 ha).")
    if not crops:
        errors.append("Select at least one crop.")
    if len(set(crops)) != len(list(crops)):
        errors.append("The same crop was selected more than once.")
    if start_year is not None and end_year is not None and start_year > end_year:
        errors.append("The historical period start year is after the end year.")
    u = _num(utilisation)
    if u is None or not (0 < u <= 1):
        errors.append("Minimum land utilisation must be between 0 and 100%.")
    a = _num(alpha)
    if a is None or not (0 <= a <= 1):
        errors.append("The production weight must be between 0 and 1.")
    if max_crops is not None and (not isinstance(max_crops, int) or max_crops < 1):
        errors.append("The maximum number of crops must be a whole number >= 1.")
    tot_min, tot_max = 0.0, 0.0
    for c in crops:
        lo, hi = _num(mins_ha.get(c, 0)), _num(maxs_ha.get(c, land if land is not None else 0))
        if lo is None or hi is None:
            errors.append(f"{c}: minimum/maximum allocation must be numbers.")
            continue
        if lo < 0:
            errors.append(f"{c}: minimum allocation cannot be negative.")
        if hi < lo:
            errors.append(f"{c}: maximum allocation ({hi:g} ha) is smaller than its minimum ({lo:g} ha).")
        if land is not None and lo > land:
            errors.append(f"{c}: minimum allocation ({lo:g} ha) exceeds the available land ({land:g} ha).")
        tot_min += max(lo, 0)
        tot_max += min(hi, land) if land else hi
    if land is not None and not errors:
        if tot_min > land + 1e-9:
            errors.append(f"The minimum allocations add up to {tot_min:g} ha, more than the available {land:g} ha.")
        if u is not None and tot_max < u * land - 1e-9:
            errors.append(f"The maximum allocations add up to {tot_max:g} ha, which cannot use {u*100:.0f}% of the land.")
    if len(crops) == 1:
        warnings.append("Only one crop selected: the optimiser has nothing to compare.")
    return errors, warnings

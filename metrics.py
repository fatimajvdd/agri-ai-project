"""Evaluation metrics (all plain formulas, documented in docs/algorithm_explanations.md)."""


def constraint_satisfaction_rate(csp, allocations):
    """Share of allocations that satisfy every CSP constraint, in %."""
    if not allocations:
        return float("nan")
    return 100.0 * sum(csp.satisfies(x) for x in allocations) / len(allocations)


def land_utilisation_pct(problem, x):
    return 100.0 * sum(x) / problem.total_units


def improvement_pct(value, baseline):
    """(value - baseline) / baseline * 100; nan if the baseline is 0."""
    return float("nan") if not baseline else 100.0 * (value - baseline) / baseline


def realised_production(problem, x, actual_yields):
    """Production of allocation x if the *actual* yields of a held-out year had occurred."""
    return sum(v * problem.step_ha * actual_yields[c] for c, v in zip(problem.crops, x))

"""Baseline allocation methods used for comparison with the GA (no AI involved)."""
import random


def equal_allocation_raw(problem):
    """Equal split of the land among selected crops (may violate min/max: used to measure raw satisfaction)."""
    n = len(problem.crops)
    return [problem.total_units // n] * n


def historical_share_raw(problem, shares):
    """Land split in proportion to the crops' historical area shares in the district."""
    return [int(round(shares[c] * problem.total_units)) for c in problem.crops]


def equal_allocation(problem, seed=0):
    return problem.repair(equal_allocation_raw(problem), random.Random(seed))


def historical_share_allocation(problem, shares, seed=0):
    return problem.repair(historical_share_raw(problem, shares), random.Random(seed))

"""Genetic Algorithm (GA) that optimises a crop-land allocation.

CHROMOSOME   list of integers  [x_1 .. x_n]  = land units given to each selected crop
INITIAL POP  feasible solutions produced by the CSP solver (random value ordering)
FITNESS      supplied by the caller (see utils.calculations.make_fitness)
SELECTION    tournament selection (size k)
CROSSOVER    uniform or arithmetic crossover (50/50), then repair
MUTATION     "transfer" mutation: move d units from one crop to another (keeps the total),
             or reset one gene to a random value inside its domain; then repair
REPAIR       problem.repair() clamps to the CSP bounds and fixes the land total
ELITISM      best `elitism` individuals survive unchanged
TERMINATION  max generations, or no improvement for `patience` generations
"""
import random
import time
from dataclasses import dataclass
import pandas as pd
from algorithms.csp import AllocationCSP, AllocationProblem, InfeasibleError


@dataclass
class GAResult:
    best: list
    best_fitness: float
    history: pd.DataFrame          # generation, best, mean, worst
    generations_run: int
    evaluations: int
    runtime_s: float


class GeneticAlgorithm:
    def __init__(self, problem: AllocationProblem, fitness_fn, pop_size=80, generations=150,
                 crossover_rate=0.9, mutation_rate=0.35, tournament_size=3, elitism=2,
                 patience=30, seed=0):
        self.p, self.f = problem, fitness_fn
        self.pop_size, self.generations = pop_size, generations
        self.cx, self.mut = crossover_rate, mutation_rate
        self.k, self.elitism, self.patience = tournament_size, elitism, patience
        self.seed = seed

    def _initial_population(self, rng):
        csp = AllocationCSP(self.p)
        pop = []
        for _ in range(self.pop_size):
            sol = csp.solve(rng=rng, randomise=True)
            if sol is None:
                raise InfeasibleError("CSP found no feasible allocation to seed the GA.")
            pop.append([sol[c] for c in self.p.crops])
        return pop

    def _select(self, pop, fit, rng):
        group = rng.sample(range(len(pop)), min(self.k, len(pop)))
        return pop[max(group, key=lambda i: fit[i])]

    def _crossover(self, a, b, rng):
        if rng.random() > self.cx:
            return list(a)
        if rng.random() < 0.5:                                   # uniform
            child = [x if rng.random() < 0.5 else y for x, y in zip(a, b)]
        else:                                                    # arithmetic blend
            w = rng.random()
            child = [round(w * x + (1 - w) * y) for x, y in zip(a, b)]
        return self.p.repair(child, rng)

    def _mutate(self, x, rng):
        if rng.random() > self.mut:
            return x
        x = list(x)
        n = len(x)
        if n >= 2 and rng.random() < 0.8:                        # transfer land between two crops
            i, j = rng.sample(range(n), 2)
            d = rng.randint(1, max(1, self.p.total_units // 10))
            d = min(d, x[i])
            x[i] -= d
            x[j] += d
        else:                                                    # random reset inside the domain
            i = rng.randrange(n)
            lo, hi = self.p.bounds(self.p.crops[i])
            x[i] = rng.randint(lo, hi)
        return self.p.repair(x, rng)

    def run(self) -> GAResult:
        t0 = time.perf_counter()
        rng = random.Random(self.seed)
        pop = self._initial_population(rng)
        fit = [self.f(x) for x in pop]
        evals = len(pop)
        rows, best_ever, stall = [], max(fit), 0
        gen = 0
        for gen in range(1, self.generations + 1):
            order = sorted(range(len(pop)), key=lambda i: fit[i], reverse=True)
            new = [list(pop[i]) for i in order[:self.elitism]]
            while len(new) < self.pop_size:
                child = self._crossover(self._select(pop, fit, rng), self._select(pop, fit, rng), rng)
                new.append(self._mutate(child, rng))
            pop = new
            fit = [self.f(x) for x in pop]
            evals += len(pop)
            rows.append({"generation": gen, "best": max(fit), "mean": sum(fit) / len(fit), "worst": min(fit)})
            if max(fit) > best_ever + 1e-9:
                best_ever, stall = max(fit), 0
            else:
                stall += 1
                if stall >= self.patience:
                    break
        b = max(range(len(pop)), key=lambda i: fit[i])
        return GAResult(pop[b], fit[b], pd.DataFrame(rows), gen, evals, time.perf_counter() - t0)

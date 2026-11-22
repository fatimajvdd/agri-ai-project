"""Quantitative evaluation of the propositional-logic advisor on the manual test set."""
from evaluation.advisory_testset import SUPPORTED, BROWSE, UNSUPPORTED, HARD


def evaluate_advisor(rb):
    rows, errors = [], []
    top1 = top3 = fired = answered = 0
    for q, crop, exp in SUPPORTED:
        a = rb.answer(question=q, crop=crop)
        ids = [m["kb_id"] for m in a["matches"]]
        r = {"type": "supported", "question": q, "crop": crop, "expected": exp, "returned": ids[:5],
             "top1": bool(ids and ids[0] == exp), "top3": exp in ids[:3], "rule_fired": exp in ids, "answered": bool(ids)}
        top1 += r["top1"]; top3 += r["top3"]; fired += r["rule_fired"]; answered += r["answered"]
        rows.append(r)
        if not r["top1"]:
            errors.append(r)
    b_hits = b_recall = 0.0
    for q, crop, cat, exp in BROWSE:
        a = rb.answer(question=q, crop=crop, categories=[cat], top_k=20)
        ids = {m["kb_id"] for m in a["matches"]}
        rec = len(exp & ids) / len(exp)
        rows.append({"type": "browse", "question": q, "crop": crop, "expected": sorted(exp), "returned": sorted(ids),
                     "recall": rec, "extra": sorted(ids - exp)})
        b_recall += rec
        b_hits += exp <= ids
    rejected = 0
    for q, crop in UNSUPPORTED:
        a = rb.answer(question=q, crop=crop)
        ok = not a["supported"]
        rejected += ok
        rows.append({"type": "unsupported", "question": q, "crop": crop, "rejected": ok,
                     "returned": [m["kb_id"] for m in a["matches"]]})
        if not ok:
            errors.append(rows[-1])
    hard_hits = 0
    for q, crop, acc in HARD:
        ids = [m["kb_id"] for m in rb.answer(question=q, crop=crop)["matches"]]
        ok = bool(acc & set(ids[:3]))
        hard_hits += ok
        rows.append({"type": "hard", "question": q, "crop": crop, "expected": sorted(acc), "returned": ids[:5], "top3": ok})
        if not ok:
            errors.append(rows[-1])
    ns, nb, nu, nh = len(SUPPORTED), len(BROWSE), len(UNSUPPORTED), len(HARD)
    summary = {
        "n_supported": ns, "n_browse": nb, "n_unsupported": nu,
        "top1_accuracy_pct": 100 * top1 / ns, "top3_accuracy_pct": 100 * top3 / ns,
        "rule_activation_accuracy_pct": 100 * fired / ns, "supported_coverage_pct": 100 * answered / ns,
        "browse_mean_recall_pct": 100 * b_recall / nb, "browse_complete_pct": 100 * b_hits / nb,
        "unsupported_rejection_pct": 100 * rejected / nu,
        "n_hard": nh, "hard_top3_pct": 100 * hard_hits / nh,
    }
    return summary, rows, errors

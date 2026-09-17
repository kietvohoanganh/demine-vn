"""Spatially separated folds and tie-aware area-budget evaluation.

Extends the supplied spatial_cv.py design with a buffer and task exclusion.
"""
import numpy as np
from scipy.spatial import cKDTree


def spatial_folds(xy, cell_tasks, buffer_m=600):
    xy = np.asarray(xy, float)
    midpoint = (xy.min(axis=0) + xy.max(axis=0)) / 2
    fold = (xy[:, 0] >= midpoint[0]).astype(int) + 2*(xy[:, 1] >= midpoint[1]).astype(int)
    for k in range(4):
        test = fold == k
        if not test.any():
            raise ValueError('Empty spatial quadrant')
        distance = cKDTree(xy[test]).query(xy, k=1)[0]
        test_tasks = set().union(*(cell_tasks[i] for i in np.flatnonzero(test)))
        shares_task = np.array([bool(tasks & test_tasks) for tasks in cell_tasks])
        train = ~test & (distance > buffer_m) & ~shares_task
        yield k, train, test


def budget_selection(scores, fraction):
    """Fractional inclusion at cutoff ties avoids location/order tie bias."""
    scores = np.asarray(scores, float)
    if not len(scores) or not np.isfinite(scores).all() or not 0 < fraction <= 1:
        raise ValueError('Invalid scores or area fraction')
    budget = len(scores) * fraction
    threshold = np.sort(scores)[-max(1, int(np.ceil(budget)))]
    selected = (scores > threshold).astype(float)
    tied = scores == threshold
    selected[tied] = (budget-selected.sum()) / tied.sum()
    return selected


def coverage(scores, observed, fraction):
    y = np.asarray(observed, float)
    if not y.sum():
        raise ValueError('No held-out recorded cells')
    return float(np.dot(budget_selection(scores, fraction), y) / y.sum())


def paired_fold_interval(ai_hits, base_hits, positives, seed=20260917):
    """Exploratory paired bootstrap of four held-out regions, not a guarantee."""
    rng = np.random.default_rng(seed)
    samples = rng.integers(0, len(positives), size=(4000, len(positives)))
    delta = ((np.asarray(ai_hits)[samples] - np.asarray(base_hits)[samples]).sum(axis=1)
             / np.asarray(positives)[samples].sum(axis=1))
    return np.quantile(delta, [.025, .975]).tolist()

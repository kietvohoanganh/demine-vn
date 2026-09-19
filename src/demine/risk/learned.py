"""Learned evidence ranking, adapted from the supplied Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn RiskModel.

Architecture: histogram gradient boosting (legacy sklearn backend). Only real
historical features and real recorded observations are used. Unrecorded cells
are BACKGROUND, not verified negatives.
The classifier estimates recording propensity, not remaining-UXO probability.
Legacy PU division, propensity weighting and isotonic calibration are disabled:
their identification assumptions are not supported by this public snapshot.
"""
from dataclasses import dataclass, asdict
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier


@dataclass(frozen=True)
class LearnedConfig:
    learning_rate: float = 0.06
    max_iter: int = 160
    max_leaf_nodes: int = 15
    min_samples_leaf: int = 40
    l2_regularization: float = 2.0
    random_state: int = 20260917


class EvidenceRanker:
    def __init__(self, config=None):
        self.config = config or LearnedConfig()
        # No random validation split hidden inside the learner. The pipeline
        # uses external spatial folds; parameters are fixed before evaluation.
        self.estimator = HistGradientBoostingClassifier(
            **asdict(self.config), early_stopping=False)

    def fit(self, X, observed):
        if set(np.unique(observed)) != {0, 1}:
            raise ValueError('Training requires both recorded and background cells.')
        self.estimator.fit(X, observed)
        return self

    def predict_ranking_score(self, X):
        return self.estimator.predict_proba(X)[:, 1]


FEATURE_NAMES = ['thor_percentile', 'kh9_percentile', 'thor_records',
                 'craters_in_cell', 'craters_within_300m', 'worldpop_2020']
FEATURE_LABELS = ['Điểm hồ sơ không kích', 'Điểm dấu vết hố bom',
                  'Số hồ sơ trong ô', 'Số hố bom trong ô', 'Số hố bom trong 300 m', 'Dân số WorldPop 2020']


def build_features(rows, population):
    """Existing verified-source snapshot only; no field labels or coordinates.

Percentiles are frozen unsupervised historical transforms, not target encodings.
Zero crater count means no prediction recorded; footprint/visibility is unknown.
"""
    a = np.asarray(rows, dtype=float)
    population = np.asarray(population, float)
    if population.shape != (len(a),) or (population[np.isfinite(population)] < 0).any():
        raise ValueError('Population must align with the grid and be nonnegative or missing.')
    return np.column_stack([a[:, 4], a[:, 5], np.log1p(a[:, 6:9]), np.log1p(population)])

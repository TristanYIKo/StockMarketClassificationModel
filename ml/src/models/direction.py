"""
The model wrapper that gets pickled.

It lives here, in a module that is only ever imported, rather than in the
training script. A class defined in the module you launch with `python -m` has
`__module__ == "__main__"`, and pickle records that literal string. Loading the
artifact from any other entry point then looks for `__main__.DirectionModel` in
whatever happens to be `__main__` there and raises AttributeError -- which is
exactly what the daily prediction job would hit after a retrain.
"""

from __future__ import annotations

from typing import List

import numpy as np


class DirectionModel:
    """
    Uniform wrapper over any fitted binary estimator.

    External labels are -1 (DOWN) / 1 (UP); estimators are fit on 0/1.
    predict_proba always returns columns ordered [p_down, p_up], so callers
    never have to reason about a given estimator's classes_ ordering.
    """

    def __init__(self, estimator, feature_names: List[str], horizon: str, name: str,
                 threshold: float = 0.5):
        self.estimator = estimator
        self.feature_names = feature_names
        self.horizon = horizon
        self.name = name
        # Probability of UP above which the call is UP. Tuned on VAL, not 0.5:
        # class_weight="balanced" deliberately shifts the boundary to treat the
        # rarer DOWN class as equally important, which is right for ranking but
        # produces a wildly bearish argmax on a series that rises ~68% of 20-day
        # windows. Ranking and thresholding are separate decisions.
        self.threshold = threshold

    def predict_proba(self, X) -> np.ndarray:
        proba = self.estimator.predict_proba(X)
        classes = list(getattr(self.estimator, "classes_", [0, 1]))
        down_idx, up_idx = classes.index(0), classes.index(1)
        return np.column_stack([proba[:, down_idx], proba[:, up_idx]])

    def predict(self, X) -> np.ndarray:
        return np.where(self.predict_proba(X)[:, 1] >= self.threshold, 1, -1)

    def predict_proba_display(self, X) -> np.ndarray:
        """
        Probabilities re-centred so that 0.5 is the decision boundary.

        The raw probabilities are boundary-shifted by class_weight="balanced":
        a 20d call can be UP at p_up = 0.27 because the tuned threshold is 0.22.
        Showing that verbatim gives a reader an "UP" badge beside a bar reading
        "Down 73%", which reads as a broken model rather than a shifted prior.

        The map below is piecewise-linear and strictly increasing, sending
        threshold -> 0.5, 0 -> 0 and 1 -> 1. Because it is monotone it leaves
        ranking, and therefore ROC AUC, exactly unchanged; because it sends the
        threshold to 0.5, argmax on the result agrees with predict() by
        construction. It is a presentation transform, not a second model.
        """
        p_up = self.predict_proba(X)[:, 1]
        t = float(self.threshold)
        t = min(max(t, 1e-6), 1 - 1e-6)

        shown = np.where(
            p_up <= t,
            0.5 * (p_up / t),
            0.5 + 0.5 * (p_up - t) / (1.0 - t),
        )
        shown = np.clip(shown, 1e-6, 1 - 1e-6)
        return np.column_stack([1.0 - shown, shown])

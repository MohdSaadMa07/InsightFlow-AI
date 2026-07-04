from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
from sklearn.metrics import make_scorer, f1_score
from typing import Optional

from ..config import settings


def grid_search(
    pipeline,
    param_grid: dict,
    X,
    y,
    cv: int = None,
    scoring: str = "f1",
    n_jobs: int = -1,
    verbose: int = 1,
) -> dict:
    cv = cv or settings.cv_folds
    search = GridSearchCV(
        pipeline,
        param_grid,
        cv=cv,
        scoring=scoring,
        n_jobs=n_jobs,
        verbose=verbose,
        return_train_score=True,
    )
    search.fit(X, y)
    return {
        "best_params": search.best_params_,
        "best_score": search.best_score_,
        "cv_results": search.cv_results_,
        "best_estimator": search.best_estimator_,
    }


def random_search(
    pipeline,
    param_distributions: dict,
    X,
    y,
    n_iter: int = None,
    cv: int = None,
    scoring: str = "f1",
    n_jobs: int = -1,
    verbose: int = 1,
) -> dict:
    n_iter = n_iter or settings.hp_trials
    cv = cv or settings.cv_folds
    search = RandomizedSearchCV(
        pipeline,
        param_distributions,
        n_iter=n_iter,
        cv=cv,
        scoring=scoring,
        n_jobs=n_jobs,
        verbose=verbose,
        random_state=settings.random_seed,
        return_train_score=True,
    )
    search.fit(X, y)
    return {
        "best_params": search.best_params_,
        "best_score": search.best_score_,
        "cv_results": search.cv_results_,
        "best_estimator": search.best_estimator_,
    }

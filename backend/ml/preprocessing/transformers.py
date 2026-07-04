from sklearn.base import BaseEstimator, TransformerMixin
import pandas as pd
import numpy as np


class ColumnSelector(BaseEstimator, TransformerMixin):
    def __init__(self, columns: list[str]):
        self.columns = columns

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X[self.columns]


class FeatureEncoder(BaseEstimator, TransformerMixin):
    def __init__(self, columns: list[str], drop_first: bool = True):
        self.columns = columns
        self.drop_first = drop_first
        self.encoders = {}

    def fit(self, X, y=None):
        for col in self.columns:
            if col in X.columns:
                self.encoders[col] = X[col].value_counts().index.tolist()
        return self

    def transform(self, X):
        X = X.copy()
        for col, cats in self.encoders.items():
            X[col] = pd.Categorical(X[col], categories=cats).codes
        return X


class FeatureScaler(BaseEstimator, TransformerMixin):
    def __init__(self, columns: list[str]):
        self.columns = columns
        self.mins = {}
        self.maxs = {}

    def fit(self, X, y=None):
        for col in self.columns:
            self.mins[col] = X[col].min()
            self.maxs[col] = X[col].max()
        return self

    def transform(self, X):
        X = X.copy()
        for col in self.columns:
            denom = self.maxs[col] - self.mins[col]
            if denom > 0:
                X[col] = (X[col] - self.mins[col]) / denom
            else:
                X[col] = 0
        return X

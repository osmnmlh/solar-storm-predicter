from __future__ import annotations

from statistics import mean
from typing import Iterable


def classify_trend(values: Iterable[float]) -> str:
    series = [value for value in values if value >= 0]
    if len(series) < 3:
        return "stable"

    first = mean(series[: len(series) // 2])
    second = mean(series[len(series) // 2 :])

    if first == 0 and second == 0:
        return "stable"

    ratio = (second - first) / max(first, 1e-9)
    if ratio > 0.25:
        return "rising"
    if ratio < -0.25:
        return "falling"
    return "stable"


def linear_slope(values: Iterable[float]) -> float:
    series = [value for value in values if value >= 0]
    if len(series) < 3:
        return 0.0

    n = len(series)
    x_mean = (n - 1) / 2
    y_mean = mean(series)

    numerator = 0.0
    denominator = 0.0
    for index, value in enumerate(series):
        x_diff = index - x_mean
        y_diff = value - y_mean
        numerator += x_diff * y_diff
        denominator += x_diff * x_diff

    if denominator == 0:
        return 0.0
    return numerator / denominator


def trend_boost(values: Iterable[float]) -> int:
    trend = classify_trend(values)
    if trend == "rising":
        return 1
    if trend == "falling":
        return -1
    return 0


def horizon_factor(hours: int) -> float:
    # Slightly decay certainty and predicted movement over longer windows.
    if hours <= 6:
        return 1.0
    if hours <= 12:
        return 0.8
    if hours <= 24:
        return 0.6
    return 0.45

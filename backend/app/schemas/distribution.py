from pydantic import BaseModel, Field


class MetricDistribution(BaseModel):
    """One metric's density curve for one group of games.

    Produced offline by `scripts/generate_distributions.py`, which bins the
    raw Kaggle values and smooths them. `x` holds the bin centres and
    `density` the smoothed weight at each; both are the same length, and
    `cdf` is the running total, so a client can place a game on the curve
    ("heavier than 82% of strategy games") without recomputing anything.
    """

    x: list[float] = Field(description="Bin centres, ascending.")
    density: list[float] = Field(description="Smoothed density at each bin centre.")
    cdf: list[float] = Field(description="Cumulative share at each bin centre, 0 to 1.")
    min: float = Field(description="Lower bound of the binned range.")
    max: float = Field(description="Upper bound of the binned range.")

from pydantic import BaseModel, Field, model_validator


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

    @model_validator(mode="after")
    def _is_drawable(self) -> "MetricDistribution":
        """Reject a curve no client could draw correctly.

        These are properties of every curve, not facts about the committed
        file, so they belong here rather than in a test. The three arrays are
        read positionally by everything that draws them, and a ragged or
        truncated one raises nowhere: it silently draws a line that stops
        early, or reports a percentile that is quietly wrong. Enforcing it on
        the model means a bad artifact fails on read, with the metric named,
        instead of reaching three clients.
        """
        if not self.x:
            raise ValueError("curve has no bins")
        if not len(self.x) == len(self.density) == len(self.cdf):
            raise ValueError(
                f"x, density and cdf must be the same length, got "
                f"{len(self.x)}, {len(self.density)}, {len(self.cdf)}"
            )
        if self.min >= self.max:
            raise ValueError(f"min must be below max, got {self.min} and {self.max}")
        if self.x != sorted(self.x):
            raise ValueError("bin centres must ascend")
        if self.cdf != sorted(self.cdf):
            raise ValueError("cdf must be non-decreasing")
        if abs(self.cdf[-1] - 1.0) > 1e-6:
            raise ValueError(f"cdf must reach 1.0, got {self.cdf[-1]}")
        return self

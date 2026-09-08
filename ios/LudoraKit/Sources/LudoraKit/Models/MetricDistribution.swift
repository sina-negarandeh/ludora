import Foundation

/// One metric's density curve for one group of games.
///
/// Produced offline by `scripts/generate_distributions.py` and served at
/// `GET /api/distributions`. `x` holds the bin centres, `density` the
/// smoothed weight at each, and `cdf` the running share, so a game can be
/// placed on the curve without recomputing anything.
public struct MetricDistribution: Codable, Hashable, Sendable {
    public let x: [Double]
    public let density: [Double]
    public let cdf: [Double]
    public let min: Double
    public let max: Double

    public init(x: [Double], density: [Double], cdf: [Double], min: Double, max: Double) {
        self.x = x
        self.density = density
        self.cdf = cdf
        self.min = min
        self.max = max
    }

    /// The share of the group at or below `value`, 0...1.
    ///
    /// Reads straight off the precomputed `cdf` at the nearest bin, rather
    /// than interpolating: the bins are fine (50 across the range for
    /// complexity) and a curve that was smoothed offline does not earn a
    /// second approximation on top.
    ///
    /// Nil when the curve is empty or the value sits outside the binned
    /// range, because clamping would report a game as "heavier than 100%"
    /// when the honest answer is that the curve does not cover it.
    public func share(atOrBelow value: Double) -> Double? {
        guard !x.isEmpty, x.count == cdf.count else { return nil }
        guard value >= min, value <= max else { return nil }

        var nearest = 0
        var smallestGap = Double.infinity
        for (index, centre) in x.enumerated() {
            let gap = abs(centre - value)
            if gap < smallestGap {
                smallestGap = gap
                nearest = index
            }
        }
        return cdf[nearest]
    }

    /// The tallest point on the curve, for scaling a chart.
    public var peakDensity: Double { density.max() ?? 0 }

    /// The density-weighted mean of the curve, which is the value the web
    /// labels "AVG" and marks with a dashed line.
    ///
    /// Computed from the curve rather than taken from the catalog on
    /// purpose: the marker has to sit on the shape being drawn, and a mean
    /// taken from anywhere else would land off it.
    public var averageValue: Double? {
        guard x.count == density.count else { return nil }
        let weight = density.reduce(0, +)
        guard weight > 0 else { return nil }
        return zip(x, density).reduce(0) { $0 + $1.0 * $1.1 } / weight
    }

    /// The curve's height at an arbitrary value, interpolated between the
    /// two bins that bracket it, so a marker's dot lands *on* the line
    /// rather than at the nearest bin's height.
    ///
    /// Values past either end take the end bin's height, which is what keeps
    /// a marker at the very edge on the curve instead of at zero.
    public func density(at value: Double) -> Double? {
        guard x.count == density.count, let first = x.first, let last = x.last
        else { return nil }
        if value <= first { return density.first }
        if value >= last { return density.last }

        for index in 0..<(x.count - 1) where value >= x[index] && value <= x[index + 1] {
            let span = x[index + 1] - x[index]
            guard span > 0 else { return density[index] }
            let fraction = (value - x[index]) / span
            return density[index] + fraction * (density[index + 1] - density[index])
        }
        return nil
    }

    /// Round-number axis ticks across the range, on the classic 1-2-5-10
    /// step sequence.
    ///
    /// Without this an axis reads "2.5, 62.5, 122.5" off raw bin centres.
    /// Same algorithm the web uses, so both clients label the same places.
    public func niceTicks(targetCount: Int = 6) -> [Double] {
        guard max > min, targetCount > 1 else { return [min] }

        let rawStep = (max - min) / Double(targetCount - 1)
        let magnitude = pow(10, (log10(rawStep)).rounded(.down))
        let residual = rawStep / magnitude
        let niceResidual: Double =
            residual <= 1 ? 1 : residual <= 2 ? 2 : residual <= 5 ? 5 : 10
        let step = niceResidual * magnitude

        var ticks: [Double] = []
        var value = (min / step).rounded(.up) * step
        while value <= max + step * 1e-6 {
            ticks.append((value * 1000).rounded() / 1000)
            value += step
        }
        return ticks
    }

    /// Where `value` sits across the binned range, 0...1, for positioning a
    /// marker. Nil outside the range, and when the range is degenerate.
    public func position(of value: Double) -> Double? {
        guard max > min, value >= min, value <= max else { return nil }
        return (value - min) / (max - min)
    }
}

/// Every curve the API serves: group name, then metric name.
///
/// Groups are the eight BGG subdomains plus "Overall". Not every subdomain
/// carries every metric, so `curve(for:in:)` is how a caller should reach
/// them rather than subscripting twice.
public struct MetricDistributions: Codable, Hashable, Sendable {
    /// The group every lookup falls back to.
    public static let overallGroup = "Overall"

    public let groups: [String: [String: MetricDistribution]]

    public init(groups: [String: [String: MetricDistribution]]) {
        self.groups = groups
    }

    public init(from decoder: any Decoder) throws {
        groups = try decoder.singleValueContainer()
            .decode([String: [String: MetricDistribution]].self)
    }

    public func encode(to encoder: any Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(groups)
    }

    /// The curve for a metric within a group, falling back to "Overall".
    ///
    /// A game in a thin subdomain should still get a curve to sit on; a
    /// comparison against every game is more useful than no comparison. The
    /// caller is told which group it got so the caption can say so rather
    /// than claiming a subdomain comparison it did not make.
    public func curve(
        for metric: String, in group: String
    ) -> (group: String, distribution: MetricDistribution)? {
        if let found = groups[group]?[metric] { return (group, found) }
        if let overall = groups[Self.overallGroup]?[metric] {
            return (Self.overallGroup, overall)
        }
        return nil
    }
}

import Foundation

/// One bar of the ratings histogram: a whole score and the half step above
/// it, the way the web groups them ("Score 8 - 8.5").
public struct RatingBar: Hashable, Sendable, Identifiable {
    public var id: Int { score }

    /// 1 through 10.
    public let score: Int
    /// Ratings of exactly `score`.
    public let whole: Int
    /// Ratings of `score` plus a half. Always zero for 10.
    public let half: Int

    public var total: Int { whole + half }

    public init(score: Int, whole: Int, half: Int) {
        self.score = score
        self.whole = whole
        self.half = half
    }
}

/// The ratings histogram, and the summary figures shown beside it.
///
/// `Game.ratingDistribution` is a flat array of half-step buckets starting at
/// 1.0, so index `k` is the score `1.0 + 0.5k`. It arrives with **19**
/// elements, not 20: the last bucket is 10.0 and there is no 10.5. Every
/// lookup here is bounds-checked for that reason, and because the array is
/// optional and could arrive at any length from a re-ingest.
public struct RatingBreakdown: Hashable, Sendable {
    /// Ten bars, 1 through 10, always all ten even where nobody scored.
    public let bars: [RatingBar]
    /// Ratings of 7.0 or better, which is what the web calls positive.
    public let positiveCount: Int
    /// `positiveCount` as a share of all ratings, 0...1. Nil when nothing
    /// has been rated, which is the case where a percentage would be a lie
    /// rather than a zero.
    public let positiveShare: Double?
    /// The tallest bar, for scaling the chart. Zero when nothing is rated.
    public let peak: Int

    /// The first bucket counted as positive: index 12 is score 7.0.
    static let firstPositiveIndex = 12

    /// Nil when there is no distribution to draw, so the caller can leave the
    /// section out rather than render ten empty bars.
    public init?(distribution: [Int]?, numRatings: Int?) {
        guard let distribution, !distribution.isEmpty else { return nil }

        func count(at index: Int) -> Int {
            distribution.indices.contains(index) ? distribution[index] : 0
        }

        bars = (1...10).map { score in
            let base = (score - 1) * 2
            return RatingBar(score: score, whole: count(at: base), half: count(at: base + 1))
        }
        peak = bars.map(\.total).max() ?? 0
        positiveCount = distribution.dropFirst(Self.firstPositiveIndex).reduce(0, +)

        // Prefer the reported total, but fall back to the distribution's own
        // sum: `numRatings` is optional on the model, and a share computed
        // from the bars is better than no share at all.
        let total = (numRatings ?? 0) > 0 ? numRatings! : distribution.reduce(0, +)
        positiveShare = total > 0 ? Double(positiveCount) / Double(total) : nil
    }
}

/// How a rank reads against the size of the field it was ranked in.
public enum Ranking {
    /// The share of the field this rank beats, 0...1.
    ///
    /// Nil when the field size is unknown or nonsensical, so a caller can
    /// show the rank alone rather than an invented percentage.
    public static func betterThanShare(rank: Int, outOf total: Int) -> Double? {
        guard total > 0, rank >= 1, rank <= total else { return nil }
        return Double(total - rank) / Double(total)
    }

    /// The web's formatting, kept exactly.
    ///
    /// The top of a 28,000-game catalog is all 99.99-something, so rounding
    /// would print "100%" for a game that is not first. Above 99.9 it says so
    /// without claiming a number. Between 99 and 99.9 a decimal is the only
    /// thing that separates rank 1 from rank 200.
    public static func formatBetterThan(_ share: Double) -> String {
        let percent = share * 100
        if percent > 99.9 { return ">99.9%" }
        if percent > 99 { return String(format: "%.1f%%", percent) }
        return "\(Int(percent.rounded()))%"
    }
}

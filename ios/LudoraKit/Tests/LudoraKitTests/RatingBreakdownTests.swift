import Foundation
import Testing

@testable import LudoraKit

@Suite("Rating breakdown")
struct RatingBreakdownTests {

    /// Index k is score 1.0 + 0.5k, so bar 3 pairs 3.0 (index 4) with 3.5
    /// (index 5).
    @Test("pairs each whole score with the half step above it")
    func pairsWholeAndHalf() throws {
        var distribution = Array(repeating: 0, count: 19)
        distribution[4] = 70   // 3.0
        distribution[5] = 3    // 3.5

        let breakdown = try #require(RatingBreakdown(distribution: distribution, numRatings: 73))
        let bar = breakdown.bars[2]
        #expect(bar.score == 3)
        #expect(bar.whole == 70)
        #expect(bar.half == 3)
        #expect(bar.total == 73)
    }

    @Test("always produces ten bars, scored one to ten")
    func alwaysTenBars() throws {
        let breakdown = try #require(
            RatingBreakdown(distribution: Array(repeating: 1, count: 19), numRatings: 19)
        )
        #expect(breakdown.bars.count == 10)
        #expect(breakdown.bars.map(\.score) == Array(1...10))
    }

    /// The array is 19 long, so bar 10's half step is off the end. Reading it
    /// unguarded would trap.
    @Test("survives the missing nineteenth-index half step")
    func handlesShortArray() throws {
        let breakdown = try #require(
            RatingBreakdown(distribution: Array(repeating: 2, count: 19), numRatings: 38)
        )
        #expect(breakdown.bars[9].whole == 2)
        #expect(breakdown.bars[9].half == 0)
        #expect(breakdown.bars[9].total == 2)
    }

    @Test("survives an array far shorter than expected")
    func handlesTruncatedArray() throws {
        let breakdown = try #require(RatingBreakdown(distribution: [5, 1], numRatings: 6))
        #expect(breakdown.bars.count == 10)
        #expect(breakdown.bars[0].total == 6)
        #expect(breakdown.bars[5].total == 0)
    }

    /// Score 7.0 is index 12, and it counts as positive.
    @Test("counts sevens and above as positive")
    func countsPositiveFromSeven() throws {
        var distribution = Array(repeating: 0, count: 19)
        distribution[11] = 100  // 6.5, excluded
        distribution[12] = 7    // 7.0, included
        distribution[18] = 3    // 10.0, included

        let breakdown = try #require(RatingBreakdown(distribution: distribution, numRatings: 110))
        #expect(breakdown.positiveCount == 10)
    }

    @Test("reports the tallest bar for scaling")
    func reportsPeak() throws {
        var distribution = Array(repeating: 1, count: 19)
        distribution[8] = 40   // 5.0
        let breakdown = try #require(RatingBreakdown(distribution: distribution, numRatings: 58))
        #expect(breakdown.peak == 41)  // 5.0 plus 5.5
    }

    @Test("has no share when nothing has been rated")
    func noShareWithoutRatings() throws {
        let breakdown = try #require(
            RatingBreakdown(distribution: Array(repeating: 0, count: 19), numRatings: 0)
        )
        #expect(breakdown.positiveShare == nil)
        #expect(breakdown.peak == 0)
    }

    /// `numRatings` is optional on the model. The bars still add up.
    @Test("falls back to the distribution's own sum")
    func fallsBackToSum() throws {
        var distribution = Array(repeating: 0, count: 19)
        distribution[0] = 25    // 1.0
        distribution[12] = 75   // 7.0

        let breakdown = try #require(RatingBreakdown(distribution: distribution, numRatings: nil))
        #expect(breakdown.positiveShare == 0.75)
    }

    @Test("is nil when there is nothing to draw")
    func nilWithoutDistribution() {
        #expect(RatingBreakdown(distribution: nil, numRatings: 100) == nil)
        #expect(RatingBreakdown(distribution: [], numRatings: 100) == nil)
    }

    /// Real numbers: the captured detail fixture.
    @Test("matches the fixture's reported totals")
    func matchesFixture() throws {
        let url = Bundle.module.url(
            forResource: "game_detail", withExtension: "json", subdirectory: "Fixtures"
        )
        let game = try JSONDecoder().decode(Game.self, from: Data(contentsOf: #require(url)))
        let breakdown = try #require(
            RatingBreakdown(distribution: game.ratingDistribution, numRatings: game.numRatings)
        )

        // Every rating lands in exactly one bar.
        let binned = breakdown.bars.reduce(0) { $0 + $1.total }
        #expect(binned == game.numRatings)
        // A top-ranked game should be overwhelmingly positive.
        let share = try #require(breakdown.positiveShare)
        #expect(share > 0.9 && share <= 1.0)
    }
}

@Suite("Ranking percentile")
struct RankingTests {
    @Test("computes the share of the field a rank beats")
    func computesShare() throws {
        #expect(Ranking.betterThanShare(rank: 1, outOf: 100) == 0.99)
        #expect(Ranking.betterThanShare(rank: 50, outOf: 100) == 0.5)
        #expect(Ranking.betterThanShare(rank: 100, outOf: 100) == 0)
    }

    @Test("has no answer for a field that makes no sense")
    func rejectsNonsense() {
        #expect(Ranking.betterThanShare(rank: 1, outOf: 0) == nil)
        #expect(Ranking.betterThanShare(rank: 0, outOf: 100) == nil)
        // A rank past the end of the field would give a negative share.
        #expect(Ranking.betterThanShare(rank: 101, outOf: 100) == nil)
    }

    /// Rank 1 of 28,208 is 99.996%, which must not print as "100%".
    @Test("refuses to round the top of the catalog up to 100%")
    func doesNotClaimAHundred() throws {
        let share = try #require(Ranking.betterThanShare(rank: 1, outOf: 28_208))
        #expect(Ranking.formatBetterThan(share) == ">99.9%")
    }

    @Test("keeps a decimal in the top percent")
    func keepsDecimalNearTheTop() throws {
        let share = try #require(Ranking.betterThanShare(rank: 200, outOf: 28_208))
        #expect(Ranking.formatBetterThan(share) == "99.3%")
    }

    @Test("rounds everywhere else")
    func roundsElsewhere() throws {
        let share = try #require(Ranking.betterThanShare(rank: 14_104, outOf: 28_208))
        #expect(Ranking.formatBetterThan(share) == "50%")
    }
}

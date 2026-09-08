import Foundation
import Testing

@testable import LudoraKit

@Suite("Community polls")
struct CommunityPollTests {

    private func players(_ count: String, best: String) -> PlayerCountPoll {
        PlayerCountPoll(
            numPlayers: count,
            result: [
                PollVote(value: "Best", numVotes: best),
                PollVote(value: "Recommended", numVotes: "10"),
                PollVote(value: "Not Recommended", numVotes: "3"),
            ]
        )
    }

    @Test("charts only the Best votes")
    func chartsBestVotes() {
        let bars = CommunityPoll.playerCountBars([players("3", best: "120")])
        #expect(bars.count == 1)
        #expect(bars[0].votes == 120)
    }

    @Test("has no votes when nobody picked Best")
    func noBestVotes() {
        let poll = PlayerCountPoll(
            numPlayers: "2", result: [PollVote(value: "Recommended", numVotes: "5")]
        )
        #expect(CommunityPoll.playerCountBars([poll])[0].votes == 0)
    }

    /// "4+" has no numeric value of its own. Placing it at 4 would stack it
    /// on the "4" bar; the web puts it one step past.
    @Test("places the open-ended bucket past the count it contains")
    func placesOpenBucket() {
        let bars = CommunityPoll.playerCountBars([
            players("4", best: "50"), players("4+", best: "12"),
        ])
        #expect(bars.map(\.x) == [4, 5])
        #expect(bars.map(\.label) == ["4", "4+"])
    }

    @Test("keeps the label BGG wrote")
    func keepsLabel() {
        #expect(CommunityPoll.playerCountBars([players("4+", best: "1")])[0].label == "4+")
    }

    @Test("reads age buckets")
    func readsAgeBuckets() {
        let bars = CommunityPoll.ageBars([
            PollVote(value: "8", numVotes: "40"),
            PollVote(value: "12", numVotes: "112"),
        ])
        #expect(bars.map(\.x) == [8, 12])
        #expect(bars.map(\.votes) == [40, 112])
    }

    /// The top age bucket is written "21 and up".
    @Test("parses the leading number out of the top age bucket")
    func parsesTopAgeBucket() {
        let bars = CommunityPoll.ageBars([PollVote(value: "21 and up", numVotes: "9")])
        #expect(bars[0].x == 21)
        #expect(bars[0].label == "21 and up")
    }

    /// Counts arrive as strings from an XML ingestion. A row that is not a
    /// number should read as no votes, not fail the game.
    @Test("treats an unparsable count as no votes")
    func unparsableCount() {
        #expect(PollVote(value: "Best", numVotes: "").votes == 0)
        #expect(PollVote(value: "Best", numVotes: "n/a").votes == 0)
    }

    @Test("has no bars without a poll")
    func noPoll() {
        #expect(CommunityPoll.playerCountBars(nil).isEmpty)
        #expect(CommunityPoll.ageBars(nil).isEmpty)
    }

    @Test("decodes the polls off the captured game")
    func decodesFixture() throws {
        let url = Bundle.module.url(
            forResource: "game_detail", withExtension: "json", subdirectory: "Fixtures"
        )
        let game = try JSONDecoder().decode(Game.self, from: Data(contentsOf: #require(url)))

        let counts = CommunityPoll.playerCountBars(game.suggestedNumPlayers)
        try #require(!counts.isEmpty, "fixture has no player-count poll")
        #expect(counts.map(\.x) == counts.map(\.x).sorted(), "bars must be in axis order")
        #expect(counts.contains { $0.votes > 0 }, "a top-ranked game has Best votes")

        let ages = CommunityPoll.ageBars(game.suggestedPlayerage)
        try #require(!ages.isEmpty, "fixture has no age poll")
        #expect(ages.allSatisfy { $0.x >= 0 })
    }
}

@Suite("Distribution chart maths")
struct DistributionChartMathTests {

    /// A triangle peaking at 5, so the mean is exactly the centre.
    private var triangle: MetricDistribution {
        let x = (0...10).map(Double.init)
        let density = [0, 1, 2, 3, 4, 5, 4, 3, 2, 1, 0].map(Double.init)
        let total = density.reduce(0, +)
        var running = 0.0
        let cdf = density.map { running += $0; return running / total }
        return MetricDistribution(x: x, density: density, cdf: cdf, min: 0, max: 10)
    }

    @Test("takes the density-weighted mean")
    func weightedMean() throws {
        let average = try #require(triangle.averageValue)
        #expect(abs(average - 5) < 1e-9)
    }

    @Test("has no mean for a weightless curve")
    func noMeanWithoutWeight() {
        let flat = MetricDistribution(
            x: [1, 2], density: [0, 0], cdf: [0, 0], min: 0, max: 3
        )
        #expect(flat.averageValue == nil)
    }

    /// The dot has to sit on the line, so between bins the height is
    /// interpolated rather than snapped.
    @Test("interpolates the curve height between bins")
    func interpolatesHeight() throws {
        let height = try #require(triangle.density(at: 4.5))
        #expect(abs(height - 4.5) < 1e-9)
    }

    @Test("holds the end height past either end")
    func clampsHeightAtEnds() {
        #expect(triangle.density(at: -5) == 0)
        #expect(triangle.density(at: 99) == 0)
    }

    /// Raw bin centres give axes like "2.5, 62.5, 122.5".
    @Test("labels round numbers, not bin centres")
    func niceTicks() {
        let playtime = MetricDistribution(
            x: [2.5, 62.5, 122.5], density: [1, 1, 1], cdf: [0.3, 0.6, 1], min: 0, max: 240
        )
        #expect(playtime.niceTicks() == [0, 50, 100, 150, 200])
    }

    @Test("labels a small range at a small step")
    func niceTicksSmallRange() {
        let complexity = MetricDistribution(
            x: [1, 3, 5], density: [1, 1, 1], cdf: [0.3, 0.6, 1], min: 0, max: 5
        )
        #expect(complexity.niceTicks() == [0, 1, 2, 3, 4, 5])
    }

    @Test("gives one tick for a degenerate range")
    func niceTicksDegenerate() {
        let point = MetricDistribution(x: [2], density: [1], cdf: [1], min: 2, max: 2)
        #expect(point.niceTicks() == [2])
    }
}

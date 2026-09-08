import Foundation
import Testing

@testable import LudoraKit

@Suite("Metric distributions")
struct MetricDistributionTests {

    /// A flat curve over 0...10 in ten bins, so the expected answers are
    /// arithmetic rather than guesswork.
    private var flat: MetricDistribution {
        let centres = (0..<10).map { Double($0) + 0.5 }
        return MetricDistribution(
            x: centres,
            density: Array(repeating: 0.1, count: 10),
            cdf: (1...10).map { Double($0) / 10 },
            min: 0,
            max: 10
        )
    }

    @Test("reads the share off the nearest bin")
    func readsNearestBin() {
        #expect(flat.share(atOrBelow: 0.5) == 0.1)
        #expect(flat.share(atOrBelow: 5.4) == 0.6)
        #expect(flat.share(atOrBelow: 9.5) == 1.0)
    }

    /// Clamping would report a game as sitting above the whole field when
    /// the truth is that the curve does not cover it.
    @Test("refuses to place a value outside the binned range")
    func refusesOutOfRange() {
        #expect(flat.share(atOrBelow: -1) == nil)
        #expect(flat.share(atOrBelow: 10.5) == nil)
    }

    @Test("refuses a curve it cannot read")
    func refusesRaggedCurve() {
        let ragged = MetricDistribution(x: [1, 2], density: [1, 1], cdf: [0.5], min: 0, max: 3)
        #expect(ragged.share(atOrBelow: 1) == nil)

        let empty = MetricDistribution(x: [], density: [], cdf: [], min: 0, max: 1)
        #expect(empty.share(atOrBelow: 0.5) == nil)
    }

    @Test("positions a value across the range")
    func positionsValue() {
        #expect(flat.position(of: 0) == 0)
        #expect(flat.position(of: 5) == 0.5)
        #expect(flat.position(of: 10) == 1)
        #expect(flat.position(of: 11) == nil)
    }

    @Test("has no position on a degenerate range")
    func rejectsDegenerateRange() {
        let flatRange = MetricDistribution(x: [1], density: [1], cdf: [1], min: 2, max: 2)
        #expect(flatRange.position(of: 2) == nil)
    }

    @Test("reports the tallest point for scaling")
    func reportsPeak() {
        let curve = MetricDistribution(
            x: [1, 2, 3], density: [0.1, 0.7, 0.2], cdf: [0.1, 0.8, 1.0], min: 0, max: 4
        )
        #expect(curve.peakDensity == 0.7)
    }

    // MARK: - Group lookup

    private func distributions(_ groups: [String: [String: MetricDistribution]]) -> MetricDistributions {
        MetricDistributions(groups: groups)
    }

    @Test("prefers the game's own subdomain")
    func prefersSubdomain() throws {
        let all = distributions([
            "Strategy": ["Complexity": flat],
            "Overall": ["Complexity": flat],
        ])
        let found = try #require(all.curve(for: "Complexity", in: "Strategy"))
        #expect(found.group == "Strategy")
    }

    /// A comparison against every game beats no comparison, but the caller
    /// has to be told which it got so the caption does not lie.
    @Test("falls back to Overall and says so")
    func fallsBackToOverall() throws {
        let all = distributions(["Overall": ["Complexity": flat]])
        let found = try #require(all.curve(for: "Complexity", in: "Party"))
        #expect(found.group == MetricDistributions.overallGroup)
    }

    @Test("has nothing for a metric nobody computed")
    func missingMetric() {
        let all = distributions(["Overall": ["Complexity": flat]])
        #expect(all.curve(for: "Playtime", in: "Strategy") == nil)
    }

    // MARK: - The real artifact

    @Test("decodes the captured endpoint response")
    func decodesFixture() throws {
        let url = Bundle.module.url(
            forResource: "distributions", withExtension: "json", subdirectory: "Fixtures"
        )
        let all = try JSONDecoder().decode(
            MetricDistributions.self, from: Data(contentsOf: #require(url))
        )

        #expect(all.groups.keys.contains(MetricDistributions.overallGroup))

        let complexity = try #require(all.curve(for: "Complexity", in: "Strategy"))
        #expect(complexity.group == "Strategy")
        #expect(complexity.distribution.x.count == complexity.distribution.density.count)
        #expect(complexity.distribution.x.count == complexity.distribution.cdf.count)

        // Brass is a 3.87, which should sit high among strategy games.
        let share = try #require(complexity.distribution.share(atOrBelow: 3.87))
        #expect(share > 0.5 && share <= 1.0)
    }
}

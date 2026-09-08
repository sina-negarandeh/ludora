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

    // MARK: - Degenerate curves

    /// `ClosedRange` traps on inverted bounds, so a chart must never build
    /// one straight from a decoded payload.
    @Test("has no value domain when the bounds are inverted or unusable")
    func valueDomainRejectsBadBounds() {
        func curve(min: Double, max: Double) -> MetricDistribution {
            MetricDistribution(x: [1], density: [1], cdf: [1], min: min, max: max)
        }
        #expect(curve(min: 5, max: 2).valueDomain == nil)
        #expect(curve(min: 1, max: 1).valueDomain == nil)
        #expect(curve(min: .nan, max: 2).valueDomain == nil)
        #expect(curve(min: 1, max: .infinity).valueDomain == nil)
        #expect(curve(min: 1, max: 5).valueDomain == 1...5)
    }

    @Test("has no density domain for a flat or empty curve")
    func densityDomainRejectsFlatCurves() {
        let flat = MetricDistribution(x: [1, 2], density: [0, 0], cdf: [0, 1], min: 1, max: 2)
        #expect(flat.densityDomain == nil)

        let empty = MetricDistribution(x: [], density: [], cdf: [], min: 0, max: 1)
        #expect(empty.densityDomain == nil)

        let real = MetricDistribution(x: [1, 2], density: [1, 2], cdf: [0.5, 1], min: 1, max: 2)
        #expect(real.densityDomain == 0...(2 * 1.05))
    }

    /// A step of zero would never advance the loop counter, hanging whatever
    /// thread drew the axis.
    @Test("returns bare bounds rather than looping on a degenerate range")
    func niceTicksSurvivesUnderflow() {
        // Verified: this range drives `step` to exactly zero, so without the
        // guard the loop only stops at the tick cap, emitting 64 copies of
        // the same number.
        let tiny = MetricDistribution(
            x: [1], density: [1], cdf: [1], min: 0, max: .leastNonzeroMagnitude
        )
        #expect(tiny.niceTicks() == [0, .leastNonzeroMagnitude])
        #expect(!tiny.niceTicks().contains { $0.isNaN })
    }

    @Test("never returns more ticks than the cap")
    func niceTicksIsBounded() {
        let wide = MetricDistribution(x: [1], density: [1], cdf: [1], min: 0, max: 1_000_000)
        #expect(wide.niceTicks(targetCount: 100_000).count <= MetricDistribution.maxTicks)
    }
}

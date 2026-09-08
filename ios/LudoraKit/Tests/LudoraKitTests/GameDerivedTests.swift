import Foundation
import Testing

@testable import LudoraKit

/// These derivations used to live in `GamesListView.swift` and on
/// `GameCardView`, where the app target has no tests to reach them.
@Suite("Game derivations")
struct GameDerivedTests {
    private func game(
        minPlayers: Int? = nil, maxPlayers: Int? = nil,
        minPlaytime: Int? = nil, maxPlaytime: Int? = nil, mfgPlaytime: Int? = nil,
        subdomainRanks: [String: Int]? = nil
    ) throws -> Game {
        let payload: [String: Any?] = [
            "bgg_id": 1, "name": "Test",
            "min_players": minPlayers, "max_players": maxPlayers,
            "min_playtime": minPlaytime, "max_playtime": maxPlaytime,
            "mfg_playtime": mfgPlaytime,
            "subdomain_ranks": subdomainRanks,
            "subdomains": [], "categories": [], "themes": [], "families": [],
            "mechanics": [], "designers": [], "publishers": [], "artists": [],
        ]
        let data = try JSONSerialization.data(
            withJSONObject: payload.compactMapValues { $0 }
        )
        return try JSONDecoder().decode(Game.self, from: data)
    }

    @Test("writes a player range only from the bounds it has")
    func playerRange() throws {
        #expect(try game(minPlayers: 2, maxPlayers: 4).playerRange == "2-4")
        #expect(try game(minPlayers: 3, maxPlayers: 3).playerRange == "3")
        #expect(try game(minPlayers: 2).playerRange == "2")
        #expect(try game(maxPlayers: 6).playerRange == "6")
        #expect(try game().playerRange == nil)
    }

    /// The stated figure wins, which is what the web card shows.
    @Test("prefers the manufacturer's playtime over the community range")
    func playtimePrefersStated() throws {
        let both = try game(minPlaytime: 60, maxPlaytime: 180, mfgPlaytime: 120)
        #expect(both.playtimeSummary == "120 min")
    }

    @Test("falls back to the community range, and to nothing")
    func playtimeFallback() throws {
        #expect(try game(minPlaytime: 30, maxPlaytime: 60).playtimeSummary == "30-60 min")
        #expect(try game(minPlaytime: 45, maxPlaytime: 45).playtimeSummary == "45 min")
        #expect(try game(minPlaytime: 20).playtimeSummary == "20 min")
        #expect(try game().playtimeSummary == nil)
        // A zero stated playtime is absent data, not a zero-minute game.
        #expect(try game(minPlaytime: 30, maxPlaytime: 60, mfgPlaytime: 0)
            .playtimeSummary == "30-60 min")
    }

    /// Best rank wins: that is the subdomain the game is most known for.
    @Test("picks the best-ranked subdomain as the comparison group")
    func primarySubdomain() throws {
        let ranked = try game(subdomainRanks: ["Thematic": 40, "Strategy": 3])
        #expect(ranked.primarySubdomain == "Strategy")
    }

    @Test("falls back to the overall group when unranked")
    func primarySubdomainFallback() throws {
        #expect(try game().primarySubdomain == MetricDistributions.overallGroup)
        #expect(try game(subdomainRanks: [:]).primarySubdomain == MetricDistributions.overallGroup)
    }
}

@Suite("Subdomain vocabulary")
struct SubdomainTests {
    /// Two BGG codes are abbreviations that mean nothing on sight.
    @Test("expands the abbreviated codes and leaves the rest alone")
    func displayName() {
        #expect(Subdomain.displayName("CGS") == "Collectible Game System")
        #expect(Subdomain.displayName("Childrens") == "Children's")
        #expect(Subdomain.displayName("Strategy") == "Strategy")
    }

    @Test("names the comparison field for a caption")
    func fieldName() {
        #expect(Subdomain.fieldName(MetricDistributions.overallGroup) == "All Games")
        #expect(Subdomain.fieldName("Strategy") == "Strategy Games")
        #expect(Subdomain.fieldName("CGS") == "Collectible Game System Games")
    }
}

@Suite("Metric keys")
struct MetricTests {
    /// The raw values are the wire keys, so a mismatch here is a silently
    /// missing chart rather than an error.
    @Test("matches the keys the artifact ships")
    func wireKeys() throws {
        let url = Bundle.module.url(
            forResource: "distributions", withExtension: "json", subdirectory: "Fixtures"
        )
        let served = try JSONDecoder().decode(
            MetricDistributions.self, from: Data(contentsOf: #require(url))
        )
        let overall = try #require(served.groups[MetricDistributions.overallGroup])
        for metric in Metric.allCases {
            #expect(overall[metric.rawValue] != nil, "no curve for \(metric.rawValue)")
        }
        #expect(Set(overall.keys) == Set(Metric.allCases.map(\.rawValue)))
    }
}

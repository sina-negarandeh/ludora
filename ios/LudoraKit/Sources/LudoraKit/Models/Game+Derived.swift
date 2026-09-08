import Foundation

/// Values derived from a `Game` rather than sent by the API.
///
/// These live here rather than beside the views that render them because
/// each is a branchy derivation over optional fields, which is exactly the
/// kind of thing worth a test. Previously they sat in `GamesListView.swift`
/// while three view files used them, so the app target owned logic that its
/// (absent) tests could not reach.
public extension Game {
    /// "2-4", or "3" when a single bound is known, or nil when the scrape
    /// has neither.
    var playerRange: String? {
        switch (minPlayers, maxPlayers) {
        case let (low?, high?) where low != high: "\(low)-\(high)"
        case let (low?, _): "\(low)"
        case let (_, high?): "\(high)"
        default: nil
        }
    }

    /// The manufacturer's estimate, which is what the web card shows,
    /// falling back to the community range when it is missing.
    var playtimeSummary: String? {
        if let stated = mfgPlaytime, stated > 0 { return "\(stated) min" }
        switch (minPlaytime, maxPlaytime) {
        case let (low?, high?) where low != high: return "\(low)-\(high) min"
        case let (low?, _): return "\(low) min"
        case let (_, high?): return "\(high) min"
        default: return nil
        }
    }

    /// The subdomain this game ranks highest in, which is the group its
    /// curves should be compared against.
    ///
    /// Falls back to the overall group: a game in no subdomain still
    /// deserves a curve to sit on, and a comparison against every game is
    /// more useful than none.
    var primarySubdomain: String {
        (subdomainRanks ?? [:])
            .sorted { $0.value < $1.value }
            .first?.key ?? MetricDistributions.overallGroup
    }
}

/// BGG's subdomain vocabulary.
public enum Subdomain {
    /// Two of BGG's codes are abbreviations that mean nothing on sight.
    /// Same mapping the web applies.
    public static func displayName(_ subdomain: String) -> String {
        switch subdomain {
        case "CGS": "Collectible Game System"
        case "Childrens": "Children's"
        default: subdomain
        }
    }

    /// How a curve's group reads in a caption: "All Games", or the
    /// subdomain's own name.
    public static func fieldName(_ group: String) -> String {
        group == MetricDistributions.overallGroup
            ? "All Games"
            : "\(displayName(group)) Games"
    }
}

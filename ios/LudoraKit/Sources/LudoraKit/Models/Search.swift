import Foundation

/// Which retrieval strategy the backend should use.
///
/// `hybrid` fuses the other two with Reciprocal Rank Fusion and is the
/// backend's own default, so it is the default here too. See
/// docs/ml/search.md for the formula.
public enum SearchMode: String, Codable, CaseIterable, Sendable {
    case lexical
    case semantic
    case hybrid
}

/// The POST body for `/api/search/`.
///
/// Search is a POST, not a GET, because the filter object nests too deeply
/// to express as query parameters. Browse (`/api/games/`) is the GET with
/// flat query parameters; see `GameQuery`.
public struct SearchRequest: Codable, Sendable {
    public let q: String
    public let mode: SearchMode

    public init(q: String, mode: SearchMode = .hybrid) {
        self.q = q
        self.mode = mode
    }
}

/// Why a result ranked where it did. Present on every search result, and
/// useful precisely because it is the part a user cannot see: a result can
/// come from the lexical leg, the semantic leg, or both, and only the
/// fused score decides the order.
public struct SearchDebug: Codable, Hashable, Sendable {
    public let lexicalRank: Int?
    public let semanticRank: Int?
    public let rrfScore: Double

    enum CodingKeys: String, CodingKey {
        case lexicalRank = "lexical_rank"
        case semanticRank = "semantic_rank"
        case rrfScore = "rrf_score"
    }
}

public struct SearchResult: Codable, Identifiable, Hashable, Sendable {
    public var id: Int { game.bggID }

    public let game: Game
    public let score: Double
    public let debug: SearchDebug
}

public struct PaginatedSearchResults: Codable, Sendable {
    public let total: Int
    public let items: [SearchResult]
}

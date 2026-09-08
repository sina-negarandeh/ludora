import Foundation

/// One board game, mirroring the backend's `GameResponse`.
///
/// Almost every field is optional because the source data is scraped from
/// BoardGameGeek and genuinely incomplete: a game can be missing its
/// weight, its playtime, or its rank. `bgg_id` and `name` are the only two
/// the API guarantees, so they are the only two that are not optional here.
///
/// Deliberately does not model the LLM-written `customer_summary`, the ABSA
/// aspect data, or recommendations. Those exist on the API but this client
/// does not render them, and a model that claims fields it never shows
/// invites someone to wire them up by accident.
public struct Game: Codable, Identifiable, Hashable, Sendable {
    public var id: Int { bggID }

    public let bggID: Int
    public let name: String

    public let description: String?
    public let yearPublished: Int?
    public let gameWeight: Double?
    public let avgRating: Double?
    public let bayesAvgRating: Double?
    public let rank: Int?
    public let numRatings: Int?

    public let minPlayers: Int?
    public let maxPlayers: Int?
    public let minPlaytime: Int?
    public let maxPlaytime: Int?
    public let mfgPlaytime: Int?
    public let minAge: Int?

    public let imagePath: String?
    public let thumbnailURL: String?

    /// Ten counts, one per star rating. Absent for games nobody has rated.
    public let ratingDistribution: [Int]?
    /// Rank within a subdomain leaderboard, keyed by subdomain name.
    public let subdomainRanks: [String: Int]?

    /// BGG's community polls, as ingested. Both are optional because a game
    /// nobody voted on has neither.
    public let suggestedNumPlayers: [PlayerCountPoll]?
    public let suggestedPlayerage: [PollVote]?

    // Tag vocabularies, non-optional on purpose. Verified against the live
    // API over a 200-game sample spanning the whole catalog: these keys are
    // always present and always an array, sometimes empty, never null.
    // (The backend gives each one `default_factory=list`.)
    //
    // So decoding them permissively would be worse than useless. `?? []`
    // would turn a genuine contract break into a silently empty list, which
    // is exactly the drift DecodingTests exists to catch. Let it throw.
    public let subdomains: [String]
    public let categories: [String]
    public let themes: [String]
    public let families: [String]
    public let mechanics: [String]
    public let designers: [String]
    public let publishers: [String]
    public let artists: [String]

    enum CodingKeys: String, CodingKey {
        case bggID = "bgg_id"
        case name
        case description
        case yearPublished = "year_published"
        case gameWeight = "game_weight"
        case avgRating = "avg_rating"
        case bayesAvgRating = "bayes_avg_rating"
        case rank
        case numRatings = "num_ratings"
        case minPlayers = "min_players"
        case maxPlayers = "max_players"
        case minPlaytime = "min_playtime"
        case maxPlaytime = "max_playtime"
        case mfgPlaytime = "mfg_playtime"
        case minAge = "min_age"
        case imagePath = "image_path"
        case thumbnailURL = "thumbnail_url"
        case ratingDistribution = "rating_distribution"
        case subdomainRanks = "subdomain_ranks"
        case suggestedNumPlayers = "suggested_num_players"
        case suggestedPlayerage = "suggested_playerage"
        case subdomains, categories, themes, families
        case mechanics, designers, publishers, artists
    }
}

/// A page of games. The backend returns the same envelope for browse and
/// for lexical search, so both paths decode into this.
public struct PaginatedGames: Codable, Sendable {
    public let total: Int
    public let items: [Game]
}

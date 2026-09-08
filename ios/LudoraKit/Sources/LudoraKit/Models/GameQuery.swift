import Foundation

public enum SortField: String, CaseIterable, Sendable {
    case rank, rating, year, complexity, name

    /// The backend's own parameter values, which do not all match the
    /// display names above.
    var wireValue: String {
        switch self {
        case .rank: "rank"
        case .rating: "avg_rating"
        case .year: "year_published"
        case .complexity: "game_weight"
        case .name: "name"
        }
    }
}

public enum SortOrder: String, Sendable {
    case ascending = "asc"
    case descending = "desc"
}

/// Everything `GET /api/games/` accepts, as one value.
///
/// Modelled as a struct rather than a pile of function arguments because
/// the browse screen mutates it incrementally as the user toggles filters,
/// and because it is what a saved filter set would be if that is ever
/// added. `LudoraClient.games(_:)` turns it into query items.
///
/// The tag filters are AND-ed by the backend across kinds and OR-ed within
/// a kind: `subdomains=[Strategy]&mechanics=[Deck Building,Drafting]` means
/// Strategy games having either mechanic.
public struct GameQuery: Hashable, Sendable {
    public var skip: Int = 0
    public var limit: Int = 50
    public var sortBy: SortField = .rank
    public var order: SortOrder = .ascending

    /// Lexical search over name and description. For semantic or hybrid
    /// retrieval use `LudoraClient.search(_:)` instead; this parameter is
    /// full-text only.
    public var query: String?

    public var subdomains: [String] = []
    public var categories: [String] = []
    public var themes: [String] = []
    public var families: [String] = []
    public var mechanics: [String] = []
    public var designers: [String] = []
    public var artists: [String] = []
    public var publishers: [String] = []

    /// "Playable by a group of exactly N", which is not the same as setting
    /// min and max to N: that would mean a game whose entire supported
    /// range is N to N. This is the one users almost always mean.
    public var exactPlayers: Int?
    public var minPlayers: Int?
    public var maxPlayers: Int?

    public var minWeight: Double?
    public var maxWeight: Double?
    public var minPlaytime: Int?
    public var maxPlaytime: Int?
    public var minYear: Int?
    public var maxYear: Int?

    public init() {}

    /// How many filters are narrowing the catalog right now.
    ///
    /// Counts filters the way a person would describe them, not the way the
    /// wire format spells them: a complexity band is one filter whether the
    /// user set its lower bound, its upper bound, or both, and the same goes
    /// for players, playtime and year. Counting each bound separately would
    /// report "2 filters" for one drag of one control.
    ///
    /// Paging, sorting and the search term are excluded. None of them narrow
    /// anything, and a badge that read "1" on a freshly opened screen because
    /// the sort defaults to rank would train people to ignore it.
    public var activeFilterCount: Int {
        var count = 0
        if exactPlayers != nil || minPlayers != nil || maxPlayers != nil { count += 1 }
        if minWeight != nil || maxWeight != nil { count += 1 }
        if minPlaytime != nil || maxPlaytime != nil { count += 1 }
        if minYear != nil || maxYear != nil { count += 1 }
        for tags in [subdomains, categories, themes, families, mechanics, designers, artists, publishers]
        where !tags.isEmpty {
            count += 1
        }
        return count
    }

    var queryItems: [URLQueryItem] {
        var items: [URLQueryItem] = [
            .init(name: "skip", value: String(skip)),
            .init(name: "limit", value: String(limit)),
            .init(name: "sort_by", value: sortBy.wireValue),
            .init(name: "order", value: order.rawValue),
        ]

        func add(_ name: String, _ value: String?) {
            guard let value, !value.isEmpty else { return }
            items.append(.init(name: name, value: value))
        }
        // FastAPI reads a repeated key as a list, so each tag is its own
        // query item rather than one comma-joined string.
        func addEach(_ name: String, _ values: [String]) {
            items.append(contentsOf: values.map { .init(name: name, value: $0) })
        }

        add("query", query)
        addEach("subdomains", subdomains)
        addEach("categories", categories)
        addEach("themes", themes)
        addEach("families", families)
        addEach("mechanics", mechanics)
        addEach("designers", designers)
        addEach("artists", artists)
        addEach("publishers", publishers)

        add("exact_players", exactPlayers.map { String($0) })
        add("min_players", minPlayers.map { String($0) })
        add("max_players", maxPlayers.map { String($0) })
        add("min_weight", minWeight.map { String($0) })
        add("max_weight", maxWeight.map { String($0) })
        add("min_playtime", minPlaytime.map { String($0) })
        add("max_playtime", maxPlaytime.map { String($0) })
        add("min_year", minYear.map { String($0) })
        add("max_year", maxYear.map { String($0) })

        return items
    }
}

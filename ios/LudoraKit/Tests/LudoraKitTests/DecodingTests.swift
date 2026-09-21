import Foundation
import Testing

@testable import LudoraKit

/// Decoding tests against real captured API responses.
///
/// This is the drift protection. The fixtures in `Fixtures/` were captured
/// from a running backend (`make ios-fixtures`), not hand-written, so they
/// carry the real shape including the parts that are easy to get wrong:
/// nulls where the scrape had no data, empty tag arrays, and the nested
/// game object inside a search result.
///
/// When the backend changes a field, refreshing the fixtures makes these
/// fail with the field named, instead of the app failing on screen. That
/// matters more here than in a single-repo app: three clients now read one
/// contract, and nothing type-checks Swift against Python.
struct DecodingTests {

    private func fixture(_ name: String) throws -> Data {
        let url = Bundle.module.url(
            forResource: name, withExtension: "json", subdirectory: "Fixtures"
        )
        let unwrapped = try #require(url, "missing fixture \(name).json")
        return try Data(contentsOf: unwrapped)
    }

    private func decode<T: Decodable>(_ type: T.Type, _ name: String) throws -> T {
        try JSONDecoder().decode(type, from: fixture(name))
    }

    // MARK: - Browse

    @Test func gamesListDecodes() throws {
        let page = try decode(PaginatedGames.self, "games_list")

        #expect(page.total > 0)
        #expect(!page.items.isEmpty)

        let game = try #require(page.items.first)
        #expect(game.bggID > 0)
        #expect(!game.name.isEmpty)
    }

    @Test func gameDetailDecodes() throws {
        let game = try decode(Game.self, "game_detail")

        #expect(game.bggID > 0)
        #expect(!game.name.isEmpty)
        // The detail payload is the one that carries the full tag set, so
        // this is where an empty-vs-null regression would surface.
        #expect(!game.categories.isEmpty || !game.mechanics.isEmpty)
    }

    /// Optionality here follows the backend's declared schema, not the
    /// current contents of the database, and the difference is worth
    /// stating because it is easy to get backwards.
    ///
    /// Sampling 800 games from the sparse tail of the catalog, `rank`,
    /// `game_weight`, `year_published` and `avg_rating` were never null,
    /// so a non-optional model would decode every row today. They stay
    /// optional anyway: `GameResponse` declares them `int | None`, so the
    /// contract permits null, and an ingest that adds an unranked game
    /// would crash a client that assumed otherwise. Matching the schema
    /// beats matching the data sample.
    ///
    /// `subdomain_ranks` and `rating_distribution` do go null in the real
    /// data, which is what game_sparse.json pins.
    @Test func sparseGameDecodesWithNullsAndEmptyTags() throws {
        let game = try decode(Game.self, "game_sparse")

        #expect(game.bggID == 199401)
        // Actually null in the response, not merely absent.
        #expect(game.subdomainRanks == nil)
        // Present but empty, which must decode as [] rather than throwing.
        #expect(game.subdomains.isEmpty)
        // A game can be untagged in one vocabulary and tagged in another.
        #expect(!game.categories.isEmpty)
    }

    // MARK: - Reviews

    @Test func reviewsDecodeWithBreakdowns() throws {
        let page = try decode(PaginatedReviews.self, "reviews")

        #expect(page.total > 0)
        #expect(!page.items.isEmpty)

        // The breakdowns are percentages over the whole matching set, not
        // counts over this page, and they drive the filter menus.
        if let languages = page.languageBreakdown {
            #expect(!languages.isEmpty)
            #expect(languages.values.allSatisfy { $0 >= 0 && $0 <= 100 })
        }
    }

    @Test func reviewAllowsRatingWithoutCommentAndViceVersa() throws {
        let page = try decode(PaginatedReviews.self, "reviews")
        // Neither field is guaranteed: BGG lets a user do either alone.
        for review in page.items {
            #expect(review.id > 0)
            #expect(!review.user.isEmpty)
        }
    }

    // MARK: - Search

    @Test func searchResultsDecodeIncludingTheNestedGame() throws {
        let page = try decode(PaginatedSearchResults.self, "search_results")

        #expect(page.total > 0)
        let result = try #require(page.items.first)
        #expect(!result.game.name.isEmpty)
        #expect(result.debug.rrfScore > 0)
    }

    /// A hybrid result can come from the lexical leg, the semantic leg, or
    /// both, so at least one rank is present but neither is guaranteed.
    /// Modelling both as non-optional would decode today and break on the
    /// first semantic-only hit.
    @Test func searchRanksAreIndependentlyOptional() throws {
        let page = try decode(PaginatedSearchResults.self, "search_results")
        for result in page.items {
            #expect(result.debug.lexicalRank != nil || result.debug.semanticRank != nil)
        }
    }

    // MARK: - Filter vocabularies

    @Test func subdomainsDecodeWithCounts() throws {
        let subdomains = try decode([CountedTag].self, "subdomains")
        // BGG has exactly 8 rank/leaderboard subdomains.
        #expect(subdomains.count == 8)
        #expect(subdomains.allSatisfy { $0.gameCount > 0 })
    }

    @Test func themesDecodeWithCounts() throws {
        let themes = try decode([CountedTag].self, "themes")
        #expect(!themes.isEmpty)
        #expect(themes.allSatisfy { !$0.name.isEmpty })
    }

    @Test func categoriesDecodeAsBareStrings() throws {
        // Categories and mechanics are plain strings, unlike subdomains and
        // themes. Four tag kinds, three shapes: see Metadata.swift.
        let categories = try decode([String].self, "categories")
        #expect(!categories.isEmpty)
    }

    @Test func familiesDecodeAsNamespacedGroups() throws {
        let groups = try decode([FamilyGroup].self, "families")

        let group = try #require(groups.first)
        #expect(!group.group.isEmpty)
        let value = try #require(group.values.first)
        // `name` is fully qualified "Group: Value". `value` is the bare
        // label. Filtering sends `name`, so this distinction is load-bearing.
        #expect(value.name.contains(value.value))
    }
}

/// Query-building is pure, so it needs no network and no fixtures.
struct GameQueryTests {

    @Test func defaultsMatchTheBackend() {
        let items = GameQuery().queryItems
        #expect(items.contains { $0.name == "skip" && $0.value == "0" })
        #expect(items.contains { $0.name == "limit" && $0.value == "50" })
        #expect(items.contains { $0.name == "sort_by" && $0.value == "rank" })
    }

    @Test func emptyFiltersAreOmittedEntirely() {
        // An empty filter must not become `subdomains=`, which the backend
        // would read as a filter on the empty string.
        let items = GameQuery().queryItems
        #expect(!items.contains { $0.name == "subdomains" })
        #expect(!items.contains { $0.name == "query" })
    }

    @Test func repeatedKeysCarryEachTagSeparately() {
        // FastAPI reads a repeated key as a list. Comma-joining would
        // become one filter value containing a comma.
        var query = GameQuery()
        query.mechanics = ["Worker Placement", "Deck Building"]
        let mechanics = query.queryItems.filter { $0.name == "mechanics" }

        #expect(mechanics.count == 2)
        #expect(mechanics.map(\.value) == ["Worker Placement", "Deck Building"])
    }

    @Test func sortFieldsUseTheBackendsOwnNames() {
        // The display names and the wire values deliberately differ.
        var query = GameQuery()
        query.sortBy = .rating
        #expect(query.queryItems.contains { $0.name == "sort_by" && $0.value == "avg_rating" })

        query.sortBy = .complexity
        #expect(query.queryItems.contains { $0.name == "sort_by" && $0.value == "game_weight" })
    }
}

/// `activeFilterCount`, which drives the badge on the filter button and the
/// "clear all" row in the sheet.
struct ActiveFilterCountTests {

    @Test func nothingIsActiveOnAFreshQuery() {
        #expect(GameQuery().activeFilterCount == 0)
    }

    @Test func pagingSortAndSearchTermNeverCount() {
        // A badge that read "1" on a screen nobody had filtered would teach
        // people to ignore it.
        var query = GameQuery()
        query.skip = 100
        query.limit = 10
        query.sortBy = .rating
        query.order = .descending
        query.query = "catan"
        #expect(query.activeFilterCount == 0)
    }

    @Test func eachTagVocabularyCountsOnceHoweverManyValues() {
        var query = GameQuery()
        query.mechanics = ["Worker Placement", "Deck Building", "Drafting"]
        #expect(query.activeFilterCount == 1)

        query.categories = ["Economic"]
        #expect(query.activeFilterCount == 2)
    }

    @Test func bothEndsOfOneBandAreStillOneFilter() {
        // The point of the grouping: one drag of the complexity range sets
        // two bounds, and reporting that as "2 filters" would be a lie about
        // how many decisions the user made.
        var query = GameQuery()
        query.minWeight = 2.0
        #expect(query.activeFilterCount == 1)

        query.maxWeight = 3.5
        #expect(query.activeFilterCount == 1)
    }

    @Test func playersCountsOnceWhicheverWayItWasExpressed() {
        // `exactPlayers` and the min/max pair are alternative spellings of
        // the same filter, and the sheet can leave both set.
        var exact = GameQuery()
        exact.exactPlayers = 4
        #expect(exact.activeFilterCount == 1)

        var ranged = GameQuery()
        ranged.minPlayers = 2
        ranged.maxPlayers = 5
        #expect(ranged.activeFilterCount == 1)

        var both = GameQuery()
        both.exactPlayers = 4
        both.minPlayers = 2
        #expect(both.activeFilterCount == 1)
    }

    @Test func eachBandIsCountedIndependently() {
        var query = GameQuery()
        query.minWeight = 2.0
        query.maxPlaytime = 60
        query.minYear = 2000
        query.exactPlayers = 2
        query.subdomains = ["Strategy"]
        #expect(query.activeFilterCount == 5)
    }
}

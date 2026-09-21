import Foundation
import LudoraKit
import Observation

/// State for the browse screen: the current query, the games it produced,
/// and how the last load went.
///
/// `@Observable` rather than a ViewModel per view. Post-iOS-17 that is
/// Apple's own direction, and this screen has one piece of state that
/// several views read, not one per view.
@Observable
@MainActor
final class GameBrowser {
    enum LoadState: Equatable {
        case idle
        case loading
        /// Carries a message rather than the error itself so the view has
        /// nothing to decide. `LudoraError` already writes user-facing text.
        case failed(String)
    }

    private(set) var games: [Game] = []
    private(set) var total = 0
    private(set) var state: LoadState = .idle

    /// Bumped whenever `games` is replaced rather than appended to.
    ///
    /// A new result set is a new list, and the browse screen is scrolled
    /// somewhere in the middle of the old one. Watching `games.first` would
    /// miss a search whose top result has not changed, and watching `games`
    /// itself would also fire for `loadMore`, which must not move anybody.
    private(set) var resultsVersion = 0

    /// Filters and sort. Mutating this does not reload on its own, so the
    /// filter sheet can change several things and apply them once.
    var query = GameQuery()

    /// The search box. Empty means plain browse.
    var searchText = ""

    /// Lexical search runs through `/api/games/` and keeps the active
    /// filters. Semantic and hybrid go to `/api/search/`, which does not
    /// take filters, so switching modes changes what a search can express.
    var searchMode: SearchMode = .lexical

    var hasMore: Bool { games.count < total }

    /// Whether this request goes to `/api/games/` rather than `/api/search/`.
    ///
    /// Browsing and lexical search share the games endpoint, which is what
    /// lets them keep the filters and page by offset. Semantic and hybrid go
    /// to the search endpoint, which does neither.
    private var usesGamesEndpoint: Bool {
        searchText.isEmpty || searchMode == .lexical
    }

    /// Set when appending a page failed, so the list can say so and offer a
    /// retry instead of silently stopping.
    ///
    /// Separate from `state`: the browse screen only renders `.failed` when
    /// it has nothing to show, which is right for a first load and wrong for
    /// a page that failed underneath a screenful of results.
    private(set) var pagingError: String?

    private let client: LudoraClient

    init(client: LudoraClient) {
        self.client = client
    }

    func load() async {
        state = .loading
        pagingError = nil
        query.skip = 0
        do {
            if usesGamesEndpoint {
                var q = query
                q.query = searchText.isEmpty ? nil : searchText
                let page = try await client.games(q)
                games = page.items
                total = page.total
            } else {
                let page = try await client.search(
                    SearchRequest(q: searchText, mode: searchMode)
                )
                games = page.items.map(\.game)
                total = page.total
            }
            resultsVersion += 1
            state = .idle
        } catch {
            state = .failed(message(for: error))
        }
    }

    /// Appends the next page. Only meaningful for browse and lexical
    /// search: `/api/search/` returns one fused page rather than an offset
    /// window, so paging there would need a different request shape.
    func loadMore() async {
        // Stops after a failure rather than retrying forever: every card
        // that scrolls into view calls this, so without the `pagingError`
        // guard a dead backend means one silent failed request per swipe.
        guard hasMore, state != .loading, pagingError == nil, usesGamesEndpoint
        else { return }

        state = .loading
        do {
            var q = query
            q.skip = games.count
            q.query = searchText.isEmpty ? nil : searchText
            games += try await client.games(q).items
            state = .idle
        } catch {
            pagingError = message(for: error)
            state = .idle
        }
    }

    /// Clears a paging failure and tries the same page again.
    func retryPaging() async {
        guard pagingError != nil else { return }
        pagingError = nil
        await loadMore()
    }

    private func message(for error: any Error) -> String {
        (error as? LudoraError)?.errorDescription
            ?? "Something went wrong loading games."
    }
}

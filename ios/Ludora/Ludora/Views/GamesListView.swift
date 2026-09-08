import LudoraKit
import SwiftUI

/// The browse screen: one full-screen card at a time, swiped vertically.
///
/// A pager rather than the web app's grid, because the shapes are different.
/// A 4-across grid works on a wide display; on a phone the same grid becomes
/// a single narrow column, which is the row list this replaced and which
/// wasted the box art entirely. One card per screen gives the art the room
/// it deserves.
///
/// Vertical, not horizontal, for three reasons. A left-edge horizontal swipe
/// is the navigation-back gesture, so a horizontal pager competes with the
/// system for it. A 28,000-game catalog is an unbounded feed, and unbounded
/// lists read vertically; a horizontal carousel signals a short curated
/// shelf. And a vertical page is full-height by construction, which is what
/// lets the cover expand instead of sitting in a 4:3 band.
///
/// Horizontal earns its place later, as a section inside a vertical page
/// ("Top Strategy", "Under 30 min"), not as the primary browse axis.
struct GamesListView: View {
    /// The band at the top of every page that the heading sits in. It is
    /// reserved on all pages, not just the first, so the card lands in the
    /// same place whether the heading is showing or not: nothing moves when
    /// it fades, and every card is the same height.
    private static let headingBand: CGFloat = 68

    /// The gap between one card and the next.
    ///
    /// Small on purpose. The neighbours showing at both edges is the only
    /// thing telling you the catalog continues in both directions, so this
    /// is deliberately tight rather than a comfortable margin.
    private static let cardGap: CGFloat = 12

    @State var browser: GameBrowser
    @State private var showingFilters = false
    @State private var visibleID: Game.ID?

    /// Whether the screen draws its own heading instead of borrowing the
    /// navigation bar's.
    ///
    /// Only where the search field can live in the bottom bar. Below iOS 26
    /// `searchable` puts the field in the navigation bar, so hiding that bar
    /// would take search with it, and the navigation title has to stay.
    private var drawsOwnHeading: Bool {
        if #available(iOS 26.0, *) { true } else { false }
    }

    var body: some View {
        ZStack {
            Color.ludoraBackground.ignoresSafeArea()

            switch browser.state {
            case .loading where browser.games.isEmpty:
                ProgressView().tint(.ludoraPrimary)

            case .failed(let message) where browser.games.isEmpty:
                failure(message)

            case _ where browser.games.isEmpty:
                empty

            default:
                carousel
            }
        }
        // Order matters: the scrim goes down first, the heading on top of it.
        .overlay(alignment: .top) {
            if drawsOwnHeading { topScrim }
        }
        .overlay(alignment: .topLeading) {
            if drawsOwnHeading { heading }
        }
        // Outside the heading's overlay, so it does not fade away with it:
        // the heading is decoration for the first card, this is a control.
        .overlay(alignment: .topTrailing) {
            if drawsOwnHeading { filtersButton }
        }
        .toolbar(drawsOwnHeading ? .hidden : .automatic, for: .navigationBar)
        .navigationTitle("Games")
        .navigationBarTitleDisplayMode(.inline)
        // Deliberately no `toolbarBackground`. A solid colour there replaces
        // the system's scroll edge effect with a flat slab and a hard seam,
        // and the art that slides past underneath is what makes the
        // progressive blur read at all.
        .navigationDestination(for: Int.self) { GameDetailView(bggID: $0) }
        .searchable(text: $browser.searchText, prompt: "Search games")
        // Send exactly what was typed. iOS capitalises the first letter of a
        // search field by default, and semantic and hybrid search are
        // case-sensitive on the server: "catan" and "Catan" return different
        // counts and a different top result. Autocapitalising made that
        // unreachable from the phone, and made the same keystrokes return
        // different games here than on the web, where nothing capitalises.
        // Autocorrect goes for the same reason: game titles are not words.
        .textInputAutocapitalization(.never)
        .autocorrectionDisabled()
        // Retrieval mode lives in the filter sheet, not here, and not for
        // want of trying. Two placements next to the field were built and
        // measured first: a bottom bar `ToolbarItem` is hidden by the system
        // for the whole search session, which is exactly when the mode
        // matters, and `searchScopes` renders nothing at all, because the
        // scope bar is a navigation-bar-drawer construct and there is no
        // drawer once the field sits in the bottom bar. The sheet disables
        // the filter groups the chosen mode ignores instead.
        .onSubmit(of: .search) { Task { await browser.load() } }
        // A new result set is a new list, and the pager is somewhere in the
        // middle of the old one. Without this the first card of a search sits
        // several swipes above where you are left standing, which reads as
        // the search having returned the wrong games.
        .onChange(of: browser.resultsVersion) {
            visibleID = browser.games.first?.id
        }
        // Clearing the field is a request to see the catalog again. Only on
        // empty: this is not search-as-you-type, and every other keystroke
        // still waits for submit.
        .onChange(of: browser.searchText) { _, text in
            if text.isEmpty { Task { await browser.load() } }
        }
        // Filter sits with search, not opposite it. They do the same job,
        // narrowing the catalog, and the bottom bar is both where the OS
        // puts search and where a thumb actually reaches on a tall display.
        //
        // The search field has to be placed explicitly. Adding any bottom
        // bar item makes the system give up the bottom placement it chose
        // for `searchable` and move the field to a drawer under the title,
        // which splits the pair again in the other direction.
        // `DefaultToolbarItem` puts it back and lets the two share one bar.
        //
        // Trailing, matching the web app's own phone breakpoint, which drops
        // the desktop sidebar and puts the filter trigger at bottom right
        // (`GamesList.tsx`, the `lg:hidden` pill). It is also the corner a
        // right thumb pivots from, which is what made the old top-left
        // placement the worst available.
        // Changing mode re-runs the query it applies to. Leaving the old
        // results on screen under a new mode label would misrepresent them.
        .onChange(of: browser.searchMode) {
            if !browser.searchText.isEmpty { Task { await browser.load() } }
        }
        .toolbar {
            if #available(iOS 26.0, *) {
                DefaultToolbarItem(kind: .search, placement: .bottomBar)
            } else {
                ToolbarItem(placement: .topBarLeading) { filtersButton }
                ToolbarItem(placement: .topBarTrailing) {
                    if browser.total > 0 {
                        Text("\(browser.total.formatted()) games")
                            .font(.footnote)
                            .foregroundStyle(Color.ludoraSecondaryText)
                    }
                }
            }
        }
        .sheet(isPresented: $showingFilters) { FiltersView(browser: browser) }
        .task { if browser.games.isEmpty { await browser.load() } }
    }

    /// Dissolves the top edge of the card above into the page ground.
    ///
    /// The scroll view deliberately does not clip, so the neighbouring cards
    /// stay visible past the page. The toolbar's blur used to absorb the one
    /// above; with the toolbar gone, its bottom edge ran into the status bar
    /// instead. This does that job in the palette rather than in glass, and
    /// it fades out well above the card so it never touches the card in view.
    private var topScrim: some View {
        // Solid through the status bar, then a fade that reaches clear
        // exactly at the top of the card, so the card itself is never washed.
        LinearGradient(
            stops: [
                .init(color: .ludoraBackground, location: 0),
                .init(color: .ludoraBackground, location: 0.45),
                .init(color: .ludoraBackground.opacity(0), location: 1),
            ],
            startPoint: .top,
            endPoint: .bottom
        )
        .frame(height: Self.headingBand + 62)
        .ignoresSafeArea(edges: .top)
        .allowsHitTesting(false)
    }

    /// The screen's heading, drawn rather than left to the navigation bar.
    ///
    /// The system large title was wrong here in three separate ways. It sits
    /// below a reserved band for the collapsed title, so it cannot reach the
    /// top of the screen. It is SF Pro, while the rest of the app is set in
    /// the serif. And once collapsed it only returns on a deliberate
    /// over-scroll, which a pager never produces by simply returning to the
    /// first card.
    ///
    /// Drawing it fixes all three and costs nothing in layout: it is an
    /// overlay, so it cannot affect the page geometry the cards are sized
    /// from.
    private var heading: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Games")
                .font(.ludoraTitle(34))
                .foregroundStyle(Color.ludoraText)
            if browser.total > 0 {
                Text("\(browser.total.formatted()) games")
                    .font(.subheadline)
                    .foregroundStyle(Color.ludoraSecondaryText)
            }
        }
        .padding(.horizontal, 16)
        .frame(height: Self.headingBand, alignment: .top)
        .opacity(showsHeading ? 1 : 0)
        .animation(.easeOut(duration: 0.2), value: showsHeading)
        // Decoration. It must never take a swipe away from the pager.
        .allowsHitTesting(false)
    }

    /// Showing on the first card, gone on every other.
    ///
    /// Keyed to which card is up rather than to a scroll offset: a pager
    /// snaps, so offset is either zero or a whole page and there is no
    /// gradual value to fade against.
    private var showsHeading: Bool {
        visibleID == nil || visibleID == browser.games.first?.id
    }

    /// The filter button, carrying how many filters are on.
    ///
    /// Drawn in the heading band rather than put in the bottom bar next to
    /// search, which is where it started and where it looked better. It had
    /// to move: for as long as a query exists the system runs a search
    /// session that takes the bottom bar over for the field and its cancel
    /// button, and hides every other item in it. That put the filter button
    /// out of reach exactly when someone wants to narrow a result set, and
    /// lexical search and filters are designed to combine. Neither
    /// `searchToolbarBehavior(.minimize)` nor a `ToolbarSpacer` arrangement
    /// changed that; both were tried on device.
    private var filtersButton: some View {
        let count = browser.query.activeFilterCount

        return Button { showingFilters = true } label: {
            HStack(spacing: 5) {
                Image(systemName: "slider.horizontal.3")
                    .font(.system(size: 17, weight: .semibold))
                if count > 0 {
                    Text("\(count)").font(.subheadline.bold())
                }
            }
            .foregroundStyle(Color.ludoraPrimary)
            .frame(minWidth: 44, minHeight: 44)
            .padding(.horizontal, count > 0 ? 6 : 0)
            .background(.white, in: .capsule)
            .overlay(Capsule().strokeBorder(Color.ludoraSurface, lineWidth: 1))
            .shadow(color: .ludoraText.opacity(0.08), radius: 6, y: 2)
        }
        .buttonStyle(.plain)
        .padding(.trailing, 16)
        .frame(height: Self.headingBand, alignment: .center)
        .accessibilityLabel(count == 0 ? "Filters" : "Filters, \(count) active")
    }

    /// One card per screen, snapped.
    ///
    /// Pages are the safe-area rect, so a card rests exactly between the
    /// toolbar and the search field. `scrollClipDisabled` then lets the
    /// cards leaving and entering draw outside that rect instead of being
    /// cut off at its edge, which is what gives the toolbar's progressive
    /// blur something to act on. Sizing the pages to the whole display would
    /// do the same but makes the card too tall for its own content.
    ///
    /// Sized explicitly from a `GeometryReader` rather than with
    /// `containerRelativeFrame`, which measures the scroll view's own
    /// container and put the cards a fifth of a screen short of a page.
    private var carousel: some View {
        GeometryReader { proxy in
            let pageSize = proxy.size

            ScrollView(.vertical) {
                LazyVStack(spacing: Self.cardGap) {
                    ForEach(browser.games) { game in
                        NavigationLink(value: game.bggID) {
                            page(pageSize) { GameCardView(game: game) }
                        }
                        .buttonStyle(.plain)
                        .scrollTransition { content, phase in
                            // The off-screen cards recede slightly, so the
                            // one being read is unambiguous mid-swipe.
                            content
                                .scaleEffect(phase.isIdentity ? 1 : 0.94)
                                .opacity(phase.isIdentity ? 1 : 0.7)
                        }
                        .task {
                            // Prefetch when the card three from the end
                            // appears, so the next page is already there by
                            // the time the user swipes to it.
                            if game.bggID == browser.games.suffix(3).first?.bggID {
                                await browser.loadMore()
                            }
                        }
                    }

                    if browser.hasMore {
                        page(pageSize) { ProgressView().tint(.ludoraPrimary) }
                    }
                }
                .scrollTargetLayout()
            }
            .scrollTargetBehavior(.viewAligned)
            .contentMargins(.vertical, band(in: pageSize), for: .scrollContent)
            .scrollIndicators(.hidden)
            .scrollClipDisabled()
            .scrollPosition(id: $visibleID)
        }
        // The card is sized from this proxy, so letting the keyboard inset it
        // would resize every card the moment the search field is focused, and
        // the pager would land on a different game than the one being read.
        .ignoresSafeArea(.keyboard, edges: .bottom)
    }

    /// The band above and below the resting card.
    ///
    /// Doubles as the heading's home, which is what sets its size: the
    /// heading needs this much room above the first card, and matching it
    /// below keeps the card optically centred.
    private func band(in size: CGSize) -> CGFloat {
        drawsOwnHeading ? Self.headingBand : 24
    }

    /// One card, sized to rest inside the bands with its neighbours showing.
    ///
    /// Height is derived rather than chosen, because `viewAligned` snaps to
    /// the item and the content margins inset the container: making the card
    /// exactly the inset container's height is what makes a snapped card land
    /// centred, with `cardGap` of the next one showing at each edge.
    private func page<Content: View>(
        _ size: CGSize,
        @ViewBuilder _ content: () -> Content
    ) -> some View {
        content()
            .frame(width: size.width - 32, height: size.height - 2 * band(in: size))
    }

    private var empty: some View {
        ContentUnavailableView {
            Label("No games found", systemImage: "magnifyingglass")
        } description: {
            Text(browser.searchText.isEmpty
                 ? "Try changing the filters."
                 : "Nothing matched \"\(browser.searchText)\".")
        }
        .foregroundStyle(Color.ludoraSecondaryText)
    }

    private func failure(_ message: String) -> some View {
        ContentUnavailableView {
            Label("Could not load games", systemImage: "exclamationmark.triangle")
        } description: {
            Text(message)
        } actions: {
            Button("Try Again") { Task { await browser.load() } }
                .buttonStyle(.borderedProminent)
                .tint(.ludoraPrimary)
        }
    }
}

extension Game {
    /// "2-4" or "3", or nil when the scrape has neither bound.
    var playerRange: String? {
        switch (minPlayers, maxPlayers) {
        case let (min?, max?) where min != max: "\(min)-\(max)"
        case let (min?, _): "\(min)"
        case let (_, max?): "\(max)"
        default: nil
        }
    }

    /// The web card shows the manufacturer's estimate, so this does too,
    /// falling back to the community range when that is missing.
    var playtimeSummary: String? {
        if let mfg = mfgPlaytime, mfg > 0 { return "\(mfg) min" }
        switch (minPlaytime, maxPlaytime) {
        case let (min?, max?) where min != max: return "\(min)-\(max) min"
        case let (min?, _): return "\(min) min"
        case let (_, max?): return "\(max) min"
        default: return nil
        }
    }
}

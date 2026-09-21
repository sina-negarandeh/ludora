import LudoraKit
import SwiftUI

/// One game: metadata, tags, charts, and its reviews.
///
/// Follows the web detail page (`frontend/src/pages/GameDetail.tsx`) section
/// for section: cover and serif title, the six stat tiles, the description
/// and vocabularies, Stats split into Official and Community, Rankings,
/// Ratings, then Reviews.
///
/// The one structural difference is that the big sections collapse. The web
/// lays this out in two columns you can skim past. A phone has one column and
/// no such affordance, so folding a section away is how it gets one.
///
/// Deliberately does not show the ABSA aspect breakdown, the community
/// consensus paragraph, or recommendations. Those exist on the backend and
/// are out of scope for this version. See ios/AGENTS.md.
struct GameDetailView: View {
    let bggID: Int

    @Environment(\.ludoraClient) private var client
    @State private var game: Game?
    @State private var reviews: PaginatedReviews?
    @State private var errorMessage: String?

    /// Field sizes for the ranking cards: how many games in the catalog, and
    /// how many in each subdomain. Both are decoration. When they fail to
    /// load the cards show the rank without the "out of" line rather than
    /// failing the screen.
    @State private var catalogSize: Int?
    @State private var subdomainSizes: [String: Int] = [:]

    /// Precomputed density curves. Also decoration: no curves, no section.
    @State private var distributions: MetricDistributions?

    /// Reviews are paged and filtered independently of the rest of the
    /// screen, so they reload on their own rather than through `load()`.
    @State private var reviewQuery = ReviewQuery()
    @State private var loadingReviews = false
    /// Separate from `reviews == nil`, which is also the loading state.
    /// Without it a failed fetch leaves a spinner turning forever.
    @State private var reviewsFailed = false

    @State private var showAbout = true
    @State private var showStats = true
    @State private var showRankings = true
    @State private var showRatings = true
    @State private var showReviews = true

    /// Anchor for scrolling back to the top of the reviews after paging.
    private let reviewsAnchor = "reviews"

    var body: some View {
        ZStack {
            Color.ludoraBackground.ignoresSafeArea()

            if let game {
                content(for: game)
            } else if let errorMessage {
                ContentUnavailableView {
                    Label("Could not load this game", systemImage: "exclamationmark.triangle")
                } description: {
                    Text(errorMessage)
                }
                .foregroundStyle(Color.ludoraSecondaryText)
            } else {
                ProgressView().tint(.ludoraPrimary)
            }
        }
        // No navigation title: the serif name in the hero is the title, and
        // the bar repeating it in SF a few points above was a second, worse
        // one. The bar stays for the back button and its scroll edge blur.
        .navigationBarTitleDisplayMode(.inline)
        .tint(.ludoraPrimary)
        .task { await load() }
    }

    private func content(for game: Game) -> some View {
        ScrollViewReader { scroller in
            ScrollView {
                VStack(alignment: .leading, spacing: 32) {
                    hero(for: game)
                    statGrid(for: game)
                    about(for: game)
                    tagSections(for: game)
                    // The web's order, which is not arbitrary: how this game
                    // compares to the field, then where it places, then what
                    // people scored it, then what they said.
                    statisticsSection(for: game)
                    rankingsSection(for: game)
                    ratingsSection(for: game)
                    reviewsSection(for: game, scroller: scroller)
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 48)
            }
        }
    }

    // MARK: - Hero

    private func hero(for game: Game) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            CoverArt(url: game.imagePath ?? game.thumbnailURL)

            VStack(alignment: .leading, spacing: 10) {
                Text(game.name)
                    .font(.ludoraTitle(32))
                    .foregroundStyle(Color.ludoraText)

                if let year = game.yearPublished {
                    Text("Published \(String(year))")
                        .font(.ludoraTitle(20))
                        .foregroundStyle(Color.ludoraSecondaryText)
                }

                // Two rows, as on the web: the subdomains as solid pills,
                // then the categories as outlined ones. Categories belong
                // here rather than in a section far below. They are how the
                // game is described ("Age of Reason", "Economic"), not a
                // vocabulary to go browsing through.
                if !game.subdomains.isEmpty {
                    WrapLayout(horizontalSpacing: 8, verticalSpacing: 8) {
                        ForEach(game.subdomains, id: \.self) { subdomain in
                            SubdomainPill(Subdomain.displayName(subdomain))
                        }
                    }
                    .padding(.top, 4)
                }

                if !game.categories.isEmpty {
                    WrapLayout(horizontalSpacing: 6, verticalSpacing: 6) {
                        ForEach(game.categories, id: \.self) { CategoryPill($0) }
                    }
                }
            }
        }
    }

    // MARK: - Stats tiles

    /// The web's six tiles, in its order, with its icons.
    ///
    /// Missing values show a dash instead of dropping the tile, so the grid
    /// keeps its shape between games. Rank is the one exception, omitted
    /// entirely when absent: the web does the same, because an unranked game
    /// has no rank rather than an unknown one.
    private func statGrid(for game: Game) -> some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 12), count: 2), spacing: 12) {
            if let rank = game.rank, rank > 0 {
                StatTile(icon: "trophy.fill", label: "Rank", value: "#\(rank)")
            }
            StatTile(
                icon: "star.fill",
                label: "Rating",
                value: game.avgRating.map { "\($0.formatted(.number.precision(.fractionLength(1)))) / 10" }
            )
            StatTile(icon: "clock.fill", label: "Playtime", value: game.playtimeSummary)
            StatTile(icon: "person.2.fill", label: "Players", value: game.playerRange)
            StatTile(
                icon: "graduationcap.fill",
                label: "Complexity",
                value: game.gameWeight.map { "\($0.formatted(.number.precision(.fractionLength(2)))) / 5" }
            )
            StatTile(icon: "person.fill", label: "Min Age", value: game.minAge.map { "\($0)+" })
        }
    }

    // MARK: - Description and vocabularies

    @ViewBuilder
    private func about(for game: Game) -> some View {
        if let description = game.description, !description.isEmpty {
            CollapsibleSection(title: "About the Game", expanded: $showAbout) {
                // The API returns BGG's raw HTML. Rendering it as plain text
                // is honest about that rather than half-parsing it into
                // something misleading.
                ExpandableText(description.strippingHTML)
            }
        }
    }

    /// The vocabularies below the description, each with the web's own
    /// treatment and collapse limit.
    ///
    /// Separate sections because they mean different things: see
    /// docs/data/README.md#bgg-terminology. Categories are missing here on
    /// purpose, having moved up beside the title where the web puts them.
    @ViewBuilder
    private func tagSections(for game: Game) -> some View {
        if !game.mechanics.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                DetailHeading("Mechanics")
                ExpandableChips(items: game.mechanics, limit: 8)
            }
        }

        if !game.families.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                DetailHeading("Family")
                FamilyGroups(items: game.families, groupLimit: 6)
            }
        }

        // People and companies read as a list, not as chips: they are names
        // to scan down, and a wrapped row of pills makes long ones ragged.
        ForEach([
            ("Designers", game.designers),
            ("Artists", game.artists),
            ("Publishers", game.publishers),
        ].filter { !$0.1.isEmpty }, id: \.0) { title, values in
            VStack(alignment: .leading, spacing: 12) {
                DetailHeading(title)
                ExpandableLines(items: values, limit: 3)
            }
        }
    }

    // MARK: - Stats

    /// The group whose curves this game is compared against.
    ///
    /// Its best-ranked subdomain, matching the web. Not `subdomains.first`,
    /// which is alphabetical and would compare a Thematic-and-Strategy game
    /// against whichever name sorted first rather than the one it actually
    /// places highest in.
    @ViewBuilder
    private func statisticsSection(for game: Game) -> some View {
        if let distributions {
            let group = game.primarySubdomain

            CollapsibleSection(title: "Stats", expanded: $showStats) {
                VStack(alignment: .leading, spacing: 20) {
                    DetailSubheading("Official")
                    officialCharts(for: game, in: group, from: distributions)

                    DetailSubheading("Community")
                        .padding(.top, 8)
                    communityCharts(for: game, in: group, from: distributions)
                }
            }
        }
    }

    /// What the publisher states: one chart per stated field.
    ///
    /// A table rather than four near-identical call sites. Only the title,
    /// the metric and the game's own value differ. Everything else the old
    /// version passed in per call is a property of the metric and now lives
    /// on `Metric.axis`.
    @ViewBuilder
    private func officialCharts(
        for game: Game, in group: String, from distributions: MetricDistributions
    ) -> some View {
        ForEach(Self.officialCharts, id: \.title) { spec in
            if let value = spec.value(game), value > 0 {
                curveCard(
                    spec, in: group, from: distributions,
                    markers: [CurveMarker(value: value, label: "This Game")],
                    summary: spec.summary(value)
                )
            }
        }
    }

    /// The four official charts. `Max Players` reads the `players` curve
    /// while `Min Players` reads its own, which is easy to miss when these
    /// are six lines apart in four separate call sites and obvious when they
    /// are one column apart here.
    private static let officialCharts: [CurveSpec] = [
        CurveSpec(
            title: "Playtime", metric: .playtime,
            value: { $0.mfgPlaytime.map(Double.init) },
            summary: { "\(Int($0)) Mins" }
        ),
        CurveSpec(
            title: "Minimum Age", metric: .minAge,
            value: { $0.minAge.map(Double.init) },
            summary: { "\(Int($0))+ Years" }
        ),
        CurveSpec(
            title: "Min Players", metric: .minPlayers,
            value: { $0.minPlayers.map(Double.init) },
            summary: { "\(Int($0)) Players" }
        ),
        CurveSpec(
            title: "Max Players", metric: .players,
            value: { $0.maxPlayers.map(Double.init) },
            summary: { "\(Int($0)) Players" }
        ),
    ]

    /// What players report.
    @ViewBuilder
    private func communityCharts(
        for game: Game, in group: String, from distributions: MetricDistributions
    ) -> some View {
        if let low = game.minPlaytime, let high = game.maxPlaytime {
            // BGG falls back to the manufacturer's playtime when no distinct
            // community range was recorded, so min == max == mfg means the
            // data is absent rather than that everyone agreed.
            if low == high && low == game.mfgPlaytime {
                EmptyChartCard(
                    title: "Playtime",
                    message: "No distinct community range recorded."
                )
            } else {
                curveCard(
                    CurveSpec(title: "Playtime", metric: .playtime),
                    in: group, from: distributions,
                    markers: [
                        CurveMarker(value: Double(low), label: "Community Min"),
                        CurveMarker(value: Double(high), label: "Community Max"),
                    ],
                    summary: "\(low)-\(high) Mins"
                )
            }
        }

        if let weight = game.gameWeight, weight > 0 {
            curveCard(
                CurveSpec(title: "Complexity", metric: .complexity),
                in: group, from: distributions,
                markers: [CurveMarker(value: weight, label: "This Game")],
                summary: "\(weight.formatted(.number.precision(.fractionLength(2)))) / 5"
            )
        }

        pollCard(
            title: "Suggested Player Number", metric: .players, group: group,
            from: distributions, bars: CommunityPoll.playerCountBars(game.suggestedNumPlayers),
            formatLabel: { "\($0) Players" }
        )

        pollCard(
            title: "Suggested Player Age", metric: .minAge, group: group,
            from: distributions, bars: CommunityPoll.ageBars(game.suggestedPlayerage),
            formatLabel: { $0 == "21 and up" ? $0 : "\($0) Years" }
        )
    }

    @ViewBuilder
    private func curveCard(
        _ spec: CurveSpec,
        in group: String,
        from distributions: MetricDistributions,
        markers: [CurveMarker],
        summary: String
    ) -> some View {
        if let found = distributions.curve(for: spec.metric, in: group) {
            let axis = spec.metric.axis
            DistributionChartCard(
                title: spec.title,
                summary: summary,
                markers: markers,
                distribution: found.distribution,
                fieldName: Subdomain.fieldName(found.group),
                leftLabel: axis.low,
                rightLabel: axis.high,
                comparative: axis.comparative,
                formatAverage: axis.formatAverage
            )
        }
    }

    @ViewBuilder
    private func pollCard(
        title: String,
        metric: Metric,
        group: String,
        from distributions: MetricDistributions,
        bars: [PollBar],
        formatLabel: @escaping (String) -> String
    ) -> some View {
        if bars.contains(where: { $0.votes > 0 }) {
            let axis = metric.axis
            PollChartCard(
                title: title,
                bars: bars,
                distribution: distributions.curve(for: metric, in: group)?.distribution,
                leftLabel: axis.low,
                rightLabel: axis.high,
                formatLabel: formatLabel
            )
        }
    }

    // MARK: - Rankings

    @ViewBuilder
    private func rankingsSection(for game: Game) -> some View {
        let overall = (game.rank ?? 0) > 0 ? game.rank : nil
        // Best rank first, as on the web.
        let bySubdomain = (game.subdomainRanks ?? [:]).sorted { $0.value < $1.value }

        if overall != nil || !bySubdomain.isEmpty {
            CollapsibleSection(title: "Rankings", expanded: $showRankings) {
                VStack(alignment: .leading, spacing: 16) {
                    if let overall {
                        RankingCard(
                            label: "Overall", rank: overall,
                            fieldSize: catalogSize, noun: "games"
                        )
                    }
                    ForEach(bySubdomain, id: \.key) { subdomain, rank in
                        let name = Subdomain.displayName(subdomain)
                        RankingCard(
                            label: "\(name) Games", rank: rank,
                            fieldSize: subdomainSizes[subdomain], noun: "\(name) games"
                        )
                    }
                }
            }
        }
    }

    // MARK: - Ratings

    @ViewBuilder
    private func ratingsSection(for game: Game) -> some View {
        if let breakdown = RatingBreakdown(
            distribution: game.ratingDistribution, numRatings: game.numRatings
        ) {
            CollapsibleSection(
                title: "Ratings",
                detail: game.numRatings.map { "\($0.formatted()) ratings" },
                expanded: $showRatings
            ) {
                VStack(alignment: .leading, spacing: 24) {
                    // Summary first, then the distribution: the headline
                    // numbers are what most readers came for, and the
                    // histogram is the detail behind them.
                    HStack(alignment: .top, spacing: 24) {
                        if let average = game.avgRating {
                            AverageRating(average: average)
                        }
                        Spacer(minLength: 0)
                        if let share = breakdown.positiveShare {
                            PositiveRatings(share: share)
                        }
                    }

                    RatingHistogram(breakdown: breakdown)
                }
            }
        }
    }

    // MARK: - Reviews

    @ViewBuilder
    private func reviewsSection(for game: Game, scroller: ScrollViewProxy) -> some View {
        if (game.numRatings ?? 0) > 0 {
            CollapsibleSection(
                title: "Reviews",
                detail: reviews.map { "\($0.total.formatted()) reviews" },
                expanded: $showReviews
            ) {
                VStack(alignment: .leading, spacing: 16) {
                    ReviewFilterBar(
                        query: $reviewQuery,
                        languageBreakdown: reviews?.languageBreakdown,
                        ratingBreakdown: reviews?.ratingBreakdown
                    )

                    if reviewsFailed {
                        Text("Could not load reviews. Pull to try again.")
                            .font(.callout)
                            .foregroundStyle(Color.ludoraSecondaryText)
                            .padding(.vertical, 24)
                    } else if let reviews, reviews.items.isEmpty {
                        Text("No reviews match these filters.")
                            .font(.callout)
                            .foregroundStyle(Color.ludoraSecondaryText)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.vertical, 24)
                    } else if let reviews {
                        ForEach(reviews.items) { review in
                            ReviewCard(review: review)
                        }
                        ReviewPager(
                            page: $reviewQuery.page,
                            total: reviews.total,
                            pageSize: ReviewQuery.pageSize,
                            busy: loadingReviews
                        ) {
                            // Paging without this leaves you at the bottom of
                            // the screen looking at the pager, with the new
                            // page's first review off-screen above: the list
                            // changes and nothing appears to happen.
                            withAnimation { scroller.scrollTo(reviewsAnchor, anchor: .top) }
                        }
                    } else {
                        ProgressView()
                            .tint(.ludoraPrimary)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 32)
                    }
                }
            }
            .id(reviewsAnchor)
            .task(id: reviewQuery) { await loadReviews() }
        }
    }

    private func loadReviews() async {
        loadingReviews = true
        defer { loadingReviews = false }
        do {
            reviews = try await client.reviews(
                bggID: bggID,
                page: reviewQuery.page,
                pageSize: ReviewQuery.pageSize,
                language: reviewQuery.language,
                minRating: reviewQuery.rating.range?.lowerBound,
                maxRating: reviewQuery.rating.range?.upperBound
            )
            reviewsFailed = false
        } catch {
            reviewsFailed = true
        }
    }

    private func load() async {
        guard game == nil else { return }
        do {
            // Independent requests, so run them concurrently rather than
            // making each wait on the one before. Only the detail is
            // required. The rest degrade to a missing section or a missing
            // line, so they are fetched with `try?`.
            async let detail = client.game(bggID: bggID)
            async let counts = try? client.subdomains()
            async let catalog = try? client.games(oneRow)
            async let curves = try? client.distributions()

            game = try await detail
            distributions = await curves
            subdomainSizes = Dictionary(
                (await counts ?? []).map { ($0.name, $0.gameCount) },
                uniquingKeysWith: { first, _ in first }
            )
            catalogSize = await catalog?.total
        } catch {
            errorMessage = (error as? LudoraError)?.errorDescription
                ?? "Something went wrong."
        }
    }

    /// Asks for a single game purely to read `total` off the envelope. The
    /// API has no count endpoint, and this is how the web gets the same
    /// number for its ranking cards.
    private var oneRow: GameQuery {
        var query = GameQuery()
        query.limit = 1
        return query
    }
}

// MARK: - Building blocks

/// A section heading, in the serif the web sets its headings in.
struct DetailHeading: View {
    let title: String

    init(_ title: String) { self.title = title }

    var body: some View {
        Text(title)
            .font(.ludoraTitle(24))
            .foregroundStyle(Color.ludoraText)
    }
}

struct StatTile: View {
    let icon: String
    let label: String
    let value: String?

    var body: some View {
        VStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 22))
                .foregroundStyle(Color.ludoraPrimary.opacity(0.85))
                .padding(.bottom, 2)
            Text(label)
                .font(.caption.bold())
                .foregroundStyle(Color.ludoraSecondaryText)
            Text(value ?? "—")
                .font(.title3.bold())
                .foregroundStyle(value == nil ? Color.ludoraSecondaryText : Color.ludoraText)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 16)
        .background(Color.ludoraSurface, in: .rect(cornerRadius: 16))
        .overlay {
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(Color.ludoraNeutral.opacity(0.5))
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(label), \(value ?? "unknown")")
    }
}

/// A vocabulary value in one of the sections: tan, bordered, rounded.
struct TagChip: View {
    let label: String

    init(_ label: String) { self.label = label }

    var body: some View {
        Text(label)
            .font(.system(size: 14, weight: .medium))
            .foregroundStyle(Color.ludoraSecondaryText)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(Color.ludoraSurface, in: .rect(cornerRadius: 8))
            .overlay {
                RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(Color.ludoraNeutral.opacity(0.7))
            }
    }
}

/// The solid pill beside the title. The heavier of the two hero rows,
/// because a subdomain is the game's primary classification.
struct SubdomainPill: View {
    let label: String

    init(_ label: String) { self.label = label }

    var body: some View {
        Text(label)
            .font(.system(size: 13, weight: .bold))
            .foregroundStyle(Color.ludoraText)
            .padding(.horizontal, 14)
            .padding(.vertical, 7)
            .background(Color.ludoraNeutral.opacity(0.28), in: .capsule)
    }
}

/// The outlined pill beside the title, one step quieter than a subdomain.
struct CategoryPill: View {
    let label: String

    init(_ label: String) { self.label = label }

    var body: some View {
        Text(label)
            .font(.system(size: 11, weight: .medium))
            .foregroundStyle(Color.ludoraSecondaryText)
            .padding(.horizontal, 11)
            .padding(.vertical, 5)
            .overlay { Capsule().strokeBorder(Color.ludoraNeutral.opacity(0.55)) }
    }
}

/// The "+ N more..." / "Show less" control the web uses everywhere it
/// collapses a list.
struct MoreButton: View {
    let title: String
    let action: () -> Void

    init(_ title: String, action: @escaping () -> Void) {
        self.title = title
        self.action = action
    }

    var body: some View {
        Button {
            withAnimation(.easeInOut(duration: 0.2)) { action() }
        } label: {
            Text(title)
                .font(.subheadline.bold())
                .foregroundStyle(Color.ludoraPrimary)
        }
        .buttonStyle(.plain)
    }
}

/// A wrapped chip list, collapsed past `limit`.
///
/// Truncating silently, which is what a bare `prefix` does, is the worst of
/// the options: the reader cannot tell a game with eight mechanics from one
/// with thirty. The count in the button is the point.
struct ExpandableChips: View {
    let items: [String]
    var limit: Int = 8

    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            WrapLayout(horizontalSpacing: 8, verticalSpacing: 8) {
                ForEach(expanded ? items : Array(items.prefix(limit)), id: \.self) {
                    TagChip($0)
                }
            }
            if items.count > limit {
                MoreButton(expanded ? "Show less" : "+ \(items.count - limit) more...") {
                    expanded.toggle()
                }
            }
        }
    }
}

/// Names, one per line, collapsed past `limit`.
struct ExpandableLines: View {
    let items: [String]
    var limit: Int = 3

    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(expanded ? items : Array(items.prefix(limit)), id: \.self) { item in
                Text(item)
                    .font(.callout.weight(.medium))
                    .foregroundStyle(Color.ludoraSecondaryText)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if items.count > limit {
                MoreButton(expanded ? "Show less" : "+ \(items.count - limit) more...") {
                    expanded.toggle()
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Families, grouped by their namespace rather than listed raw.
///
/// The API sends them fully qualified, as "Category: Industry / Manufacturing"
/// and "Region: Great Britain". Rendered as-is that is a column of repeated
/// prefixes, which is what this screen used to show. Splitting on the first
/// ": " turns the prefix into a heading and leaves the values readable,
/// which is what the web does with the same strings.
struct FamilyGroups: View {
    let items: [String]
    var groupLimit: Int = 6

    @State private var expanded = false

    var body: some View {
        let all = FamilyGrouping.grouping(items)
        let visible = expanded ? all : Array(all.prefix(groupLimit))

        VStack(alignment: .leading, spacing: 20) {
            ForEach(visible, id: \.name) { group in
                VStack(alignment: .leading, spacing: 10) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(group.name.uppercased())
                            .font(.system(size: 11, weight: .bold))
                            .tracking(0.8)
                            .foregroundStyle(Color.ludoraSecondaryText)
                        Rectangle()
                            .fill(Color.ludoraNeutral.opacity(0.35))
                            .frame(height: 1)
                    }
                    WrapLayout(horizontalSpacing: 8, verticalSpacing: 8) {
                        ForEach(group.values, id: \.self) { TagChip($0) }
                    }
                }
            }

            if all.count > groupLimit {
                MoreButton(expanded ? "Show less" : "+ \(all.count - groupLimit) more groups...") {
                    expanded.toggle()
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// The description, clipped with a fade until it is asked to open.
struct ExpandableText: View {
    let text: String
    /// The web collapses past 1600 characters, but that is a threshold for a
    /// wide column. The same text on a phone is roughly three screens, so
    /// this clips far sooner. The web's number would leave most descriptions
    /// uncollapsed here, which is the case that prompted this.
    private let longEnough = 600
    private let collapsedHeight: CGFloat = 260

    @State private var expanded = false

    init(_ text: String) { self.text = text }

    private var isLong: Bool { text.count > longEnough }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(text)
                .font(.body)
                .foregroundStyle(Color.ludoraText)
                .lineSpacing(3)
                .frame(maxWidth: .infinity, alignment: .leading)
                .frame(maxHeight: expanded || !isLong ? nil : collapsedHeight, alignment: .top)
                .clipped()
                .overlay(alignment: .bottom) {
                    if isLong && !expanded {
                        LinearGradient(
                            colors: [.ludoraBackground.opacity(0), .ludoraBackground],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                        .frame(height: 72)
                        .allowsHitTesting(false)
                    }
                }

            if isLong {
                MoreButton(expanded ? "Show less" : "Read more") { expanded.toggle() }
            }
        }
    }
}

extension String {
    /// BGG descriptions arrive as HTML. This is a deliberate minimum: strip
    /// tags and decode the handful of entities that actually show up,
    /// rather than pulling in a parser for text that is only ever read.
    var strippingHTML: String {
        replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
            .replacingOccurrences(of: "&amp;", with: "&")
            .replacingOccurrences(of: "&quot;", with: "\"")
            .replacingOccurrences(of: "&#10;", with: "\n")
            .replacingOccurrences(of: "&rsquo;", with: "'")
            .replacingOccurrences(of: "&mdash;", with: "-")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

/// One distribution chart: what to call it, which curve it reads, and how to
/// pull its value off a game.
///
/// The axis vocabulary and the average format are deliberately absent --
/// they belong to the metric, not to the chart, and live on `Metric.axis`.
struct CurveSpec {
    let title: String
    let metric: Metric
    var value: (Game) -> Double? = { _ in nil }
    var summary: (Double) -> String = { String(Int($0)) }
}

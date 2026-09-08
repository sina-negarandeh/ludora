import LudoraKit
import SwiftUI

// The review browser: the query that drives it, the filter bar, the pager,
// and one review. Split out of `GameDetailView` because it is a
// self-contained unit -- nothing here reads a `Game` -- and because that
// file was carrying the whole screen plus a dozen components.

/// Which slice of reviews is on screen. One value so the whole thing is a
/// single `task(id:)` key: changing a filter and changing the page are the
/// same kind of event, and both have to reset nothing else.
struct ReviewQuery: Hashable {
    /// The API caps `page_size` at 50. Ten is what the web asks for, and it
    /// is enough to fill a phone screen twice over.
    static let pageSize = 10

    var page = 1
    /// Nil is every language.
    var language: String?
    var rating: ReviewRatingFilter = .all

    /// Changing a filter has to go back to page one: page 4 of "positive
    /// only" is usually past the end of the filtered set, and the user would
    /// get an empty screen for a filter that has plenty of matches.
    mutating func apply(_ change: (inout ReviewQuery) -> Void) {
        change(&self)
        page = 1
    }
}

enum ReviewRatingFilter: String, CaseIterable, Hashable {
    case all, positive, mixed, negative

    var label: String {
        switch self {
        case .all: "All Ratings"
        case .positive: "Positive"
        case .mixed: "Mixed"
        case .negative: "Negative"
        }
    }

    /// The web's bands (`GameDetail.tsx`), matched exactly so the two
    /// clients filter identically.
    ///
    /// The upper bounds are .99 rather than .9, and negative starts at zero,
    /// because the bands have to tile the whole scale: at 6.9 and 3.9 a
    /// review rated 6.95 belonged to no band at all, so it showed under "All
    /// Ratings" and vanished from every filter, and the three filtered counts
    /// did not add up to the total.
    var range: ClosedRange<Double>? {
        switch self {
        case .all: nil
        case .positive: 7.0...10.0
        case .mixed: 4.0...6.99
        case .negative: 0.0...3.99
        }
    }

    /// The key this band appears under in the API's `rating_breakdown`.
    var breakdownKey: String? { self == .all ? nil : rawValue }
}

/// Language and rating pickers, styled as the web's two dropdown pills.
struct ReviewFilterBar: View {
    @Binding var query: ReviewQuery
    let languageBreakdown: [String: Double]?
    let ratingBreakdown: [String: Double]?

    var body: some View {
        WrapLayout(horizontalSpacing: 8, verticalSpacing: 8) {
            Menu {
                Picker("Language", selection: languageBinding) {
                    Text("All Languages").tag(String?.none)
                    ForEach(languages, id: \.code) { language in
                        Text(label(for: language)).tag(String?.some(language.code))
                    }
                }
            } label: {
                FilterPill(
                    icon: "globe",
                    title: query.language.map { $0.uppercased() } ?? "ALL"
                )
            }

            Menu {
                Picker("Rating", selection: ratingBinding) {
                    ForEach(ReviewRatingFilter.allCases, id: \.self) { option in
                        Text(label(for: option)).tag(option)
                    }
                }
            } label: {
                FilterPill(icon: "star.fill", title: query.rating.label)
            }
        }
    }

    // Bindings rather than direct writes so every change routes through
    // `apply`, which is what resets the page.
    private var languageBinding: Binding<String?> {
        Binding(
            get: { query.language },
            set: { value in query.apply { $0.language = value } }
        )
    }

    private var ratingBinding: Binding<ReviewRatingFilter> {
        Binding(
            get: { query.rating },
            set: { value in query.apply { $0.rating = value } }
        )
    }

    /// Most-used language first, which is the order the web shows.
    private var languages: [(code: String, share: Double)] {
        (languageBreakdown ?? [:])
            .map { (code: $0.key, share: $0.value) }
            .sorted { $0.share > $1.share }
    }

    private func label(for language: (code: String, share: Double)) -> String {
        let name = Locale.current.localizedString(forLanguageCode: language.code)
            ?? language.code.uppercased()
        return "\(name)  \(percent(language.share))"
    }

    private func label(for option: ReviewRatingFilter) -> String {
        guard
            let key = option.breakdownKey,
            let share = ratingBreakdown?[key]
        else { return option.label }
        return "\(option.label)  \(percent(share))"
    }

    /// The API reports these as percentages already, not as fractions.
    private func percent(_ share: Double) -> String {
        "\(Int(share.rounded()))%"
    }
}

struct FilterPill: View {
    let icon: String
    let title: String

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 12))
                .foregroundStyle(Color.ludoraSecondaryText)
            Text(title)
                .font(.system(size: 13, weight: .bold))
                .foregroundStyle(Color.ludoraText)
                .lineLimit(1)
            Image(systemName: "chevron.down")
                .font(.system(size: 10, weight: .bold))
                .foregroundStyle(Color.ludoraSecondaryText)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color.ludoraSurface, in: .capsule)
        .overlay { Capsule().strokeBorder(Color.ludoraNeutral.opacity(0.5)) }
    }
}

struct ReviewPager: View {
    @Binding var page: Int
    let total: Int
    let pageSize: Int
    let busy: Bool
    /// Called after the page changes, so the caller can scroll back up.
    let onPageChange: () -> Void

    private var lastPage: Int { max(1, Int(ceil(Double(total) / Double(pageSize)))) }

    var body: some View {
        HStack {
            step("Previous", systemImage: "chevron.left", to: page - 1, enabled: page > 1)
            Spacer()
            Text("Page \(page.formatted()) of \(lastPage.formatted())")
                .font(.caption.weight(.medium))
                .foregroundStyle(Color.ludoraSecondaryText)
                .opacity(busy ? 0.4 : 1)
            Spacer()
            step("Next", systemImage: "chevron.right", to: page + 1, enabled: page < lastPage)
        }
        .padding(.top, 4)
    }

    private func step(
        _ title: String, systemImage: String, to target: Int, enabled: Bool
    ) -> some View {
        Button {
            page = target
            onPageChange()
        } label: {
            HStack(spacing: 4) {
                if systemImage == "chevron.left" { Image(systemName: systemImage) }
                Text(title)
                if systemImage == "chevron.right" { Image(systemName: systemImage) }
            }
            .font(.system(size: 13, weight: .bold))
            .foregroundStyle(Color.ludoraText)
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
            .background(.white, in: .capsule)
            .overlay { Capsule().strokeBorder(Color.ludoraSurface) }
        }
        .buttonStyle(.plain)
        .disabled(!enabled || busy)
        .opacity(enabled && !busy ? 1 : 0.35)
    }
}

struct ReviewCard: View {
    let review: Review

    /// Long enough that clipping it saves real scrolling, short enough that
    /// most reviews are never clipped at all.
    private let longEnough = 320
    @State private var expanded = false

    private var isLong: Bool { (review.comment?.count ?? 0) > longEnough }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(review.user)
                    .font(.subheadline.bold())
                    .foregroundStyle(Color.ludoraText)
                Spacer()
                if let rating = review.rating {
                    Label {
                        Text(rating.formatted(.number.precision(.fractionLength(1))))
                            .fontWeight(.bold)
                    } icon: {
                        Image(systemName: "star.fill")
                            .foregroundStyle(Color.ludoraPrimary)
                    }
                    .font(.caption)
                    .foregroundStyle(Color.ludoraText)
                }
            }

            if let comment = review.comment, !comment.isEmpty {
                Text(comment)
                    .font(.callout)
                    .foregroundStyle(Color.ludoraText)
                    .lineSpacing(2)
                    .lineLimit(expanded || !isLong ? nil : 6)

                if isLong {
                    MoreButton(expanded ? "Show less" : "Read more") { expanded.toggle() }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(.white, in: .rect(cornerRadius: 16))
        .overlay {
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(Color.ludoraSurface)
        }
    }
}

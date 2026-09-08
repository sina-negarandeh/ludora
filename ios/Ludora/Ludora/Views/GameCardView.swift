import LudoraKit
import SwiftUI

/// A game card, matching `frontend/src/components/GameCard.tsx`.
///
/// Same anatomy as the web card, deliberately: a 4:3 cover area with the
/// art floated over a blurred copy of itself, a floating rating and rank
/// pill, a serif title with the year, subdomain chips, and a 2x2 stat grid
/// under a hairline. Two clients showing the same catalog should not look
/// like two different products.
///
/// The blurred backdrop is the detail worth keeping. Box art has wildly
/// varying aspect ratios, so fitting the art inside a fixed frame leaves
/// bars; the web app fills them with a blurred, scaled copy of the same
/// image. It reads as intentional rather than as letterboxing.
struct GameCardView: View {
    let game: Game

    var body: some View {
        VStack(spacing: 0) {
            cover
            details
        }
        .background(.white)
        .clipShape(.rect(cornerRadius: 16))
        .overlay {
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(Color.ludoraSurface, lineWidth: 1)
        }
        .shadow(color: .ludoraText.opacity(0.08), radius: 12, y: 4)
    }

    // MARK: - Cover

    /// No fixed aspect ratio: the details block has an intrinsic height and
    /// the cover takes whatever the page has left, so on a tall phone the
    /// art gets the room instead of a 4:3 sliver of it. The web card fixes
    /// 4:3 because it sits in a grid of equal cells; a full-page card has no
    /// neighbours to line up with.
    ///
    /// The art is an `overlay` on a plain `Color`, not a sibling in a
    /// `ZStack`. `scaledToFill` deliberately reports a size larger than the
    /// proposal, and a `ZStack` sizes to its largest child, so the blurred
    /// backdrop would set the cover's width and the whole card would
    /// overflow its frame. An overlay never contributes to layout, so the
    /// `Color` alone decides the size and `clipped()` trims the fill.
    private var cover: some View {
        Color.ludoraSurface
            .overlay { art }
            .clipped()
            .overlay(alignment: .bottomTrailing) { ratingPill }
    }

    @ViewBuilder
    private var art: some View {
        if let url = game.imagePath.flatMap(URL.init(string:)) {
            AsyncImage(url: url, transaction: .init(animation: .easeOut(duration: 0.25))) { phase in
                switch phase {
                case .success(let image):
                    // Both layers hang off a `Color.clear` that takes the
                    // cover's size, rather than sitting as siblings in a
                    // `ZStack`. A `ZStack` sizes to its largest child, and
                    // `scaledToFill` reports a size larger than the proposal,
                    // so the stack came out bigger than the cover and
                    // `scaledToFit` fitted the artwork to *that* instead. The
                    // whole cover was then cropped away by `clipped()`, which
                    // is `object-cover` behaviour where the web card is
                    // `object-contain`. As overlays, each layer is measured
                    // against the cover itself: the fill still overflows and
                    // is trimmed, and the artwork is whole.
                    Color.clear
                        .overlay {
                            image
                                .resizable()
                                .scaledToFill()
                                .blur(radius: 24)
                                .opacity(0.4)
                        }
                        .overlay {
                            image
                                .resizable()
                                .scaledToFit()
                                .shadow(color: .black.opacity(0.25), radius: 8, y: 4)
                        }
                        .clipped()
                        .transition(.opacity)
                case .failure:
                    placeholder
                default:
                    ProgressView().tint(.ludoraNeutral)
                }
            }
        } else {
            placeholder
        }
    }

    private var placeholder: some View {
        Image(systemName: "dice")
            .font(.system(size: 40))
            .foregroundStyle(Color.ludoraNeutral)
    }

    /// Rating and rank, floated over the art on a frosted pill.
    @ViewBuilder
    private var ratingPill: some View {
        let hasRank = (game.rank ?? 0) > 0
        if game.avgRating != nil || hasRank {
            HStack(spacing: 8) {
                if let rating = game.avgRating {
                    Label {
                        Text(rating, format: .number.precision(.fractionLength(1)))
                            .fontWeight(.bold)
                    } icon: {
                        Image(systemName: "star.fill").foregroundStyle(Color.ludoraPrimary)
                    }
                }
                if let rank = game.rank, hasRank {
                    if game.avgRating != nil {
                        Divider().frame(height: 14).overlay(Color.ludoraNeutral.opacity(0.4))
                    }
                    Label {
                        Text("#\(rank)").fontWeight(.bold)
                    } icon: {
                        Image(systemName: "trophy.fill").foregroundStyle(Color.ludoraPrimary)
                    }
                }
            }
            .font(.subheadline)
            .foregroundStyle(Color.ludoraText)
            .labelStyle(.titleAndIcon)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(.regularMaterial, in: .capsule)
            .overlay(Capsule().strokeBorder(.white.opacity(0.4)))
            .padding(12)
        }
    }

    // MARK: - Details

    private var details: some View {
        VStack(alignment: .leading, spacing: 12) {
            title
            subdomains

            Divider().overlay(Color.ludoraNeutral.opacity(0.3))

            statGrid
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var title: some View {
        // The web card scrolls an overlong title on hover. There is no
        // hover on iOS, so it wraps to two lines instead of being clipped.
        Text(game.name)
            .font(.ludoraTitle(24))
            .foregroundStyle(Color.ludoraText)
            + Text(game.yearPublished.map { " (\($0))" } ?? "")
            .font(.ludoraTitle(20))
            .foregroundStyle(Color.ludoraSecondaryText)
    }

    @ViewBuilder
    private var subdomains: some View {
        if !game.subdomains.isEmpty {
            HStack(spacing: 6) {
                ForEach(game.subdomains.prefix(3), id: \.self) { subdomain in
                    Text(Self.displayName(for: subdomain).uppercased())
                        .font(.ludoraTag)
                        .tracking(0.5)
                        .foregroundStyle(Color.ludoraSecondaryText)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.ludoraSurface, in: .rect(cornerRadius: 4))
                        .overlay {
                            RoundedRectangle(cornerRadius: 4)
                                .strokeBorder(Color.ludoraNeutral.opacity(0.3))
                        }
                }
            }
        }
    }

    /// Two of BGG's subdomain codes are abbreviations that mean nothing on
    /// sight. Same mapping the web card applies.
    static func displayName(for subdomain: String) -> String {
        switch subdomain {
        case "CGS": "Collectible Game System"
        case "Childrens": "Children's"
        default: subdomain
        }
    }

    private var statGrid: some View {
        Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 12) {
            GridRow {
                stat("person.2.fill", game.playerRange.map { "\($0) Players" })
                stat("clock.fill", game.playtimeSummary)
            }
            GridRow {
                complexityStat
                stat("person.fill", game.minAge.map { "Age \($0)+" })
            }
        }
        .font(.subheadline)
        .foregroundStyle(Color.ludoraText)
    }

    private func stat(_ symbol: String, _ value: String?) -> some View {
        HStack(spacing: 6) {
            Image(systemName: symbol)
                .font(.caption)
                .foregroundStyle(Color.ludoraNeutral)
                .frame(width: 16)
            Text(value ?? "—")
                .lineLimit(1)
                .foregroundStyle(value == nil ? Color.ludoraSecondaryText : Color.ludoraText)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Complexity as five dots, filled to the rounded weight, the way the
    /// web card shows it. A 1-to-5 scale reads faster as dots than as a
    /// decimal, and the number stays alongside for anyone who wants it.
    private var complexityStat: some View {
        HStack(spacing: 6) {
            Image(systemName: "graduationcap.fill")
                .font(.caption)
                .foregroundStyle(Color.ludoraNeutral)
                .frame(width: 16)

            if let weight = game.gameWeight {
                Text(weight, format: .number.precision(.fractionLength(1)))
                HStack(spacing: 3) {
                    ForEach(1...5, id: \.self) { step in
                        Circle()
                            .fill(step <= Int(weight.rounded())
                                  ? Color.ludoraPrimary
                                  : Color.ludoraNeutral.opacity(0.4))
                            .frame(width: 6, height: 6)
                    }
                }
            } else {
                Text("—").foregroundStyle(Color.ludoraSecondaryText)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

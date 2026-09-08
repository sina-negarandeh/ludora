import LudoraKit
import SwiftUI

// Standalone pieces of the detail screen: the ratings summary, a ranking
// card, and the hero art. Each is self-contained and none of them reads a
// `Game`, so they live here rather than lengthening `GameDetailView`.

struct AverageRating: View {
    let average: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Average Rating")
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(Color.ludoraSecondaryText)
            Text(average, format: .number.precision(.fractionLength(1)))
                .font(.system(size: 60, weight: .bold))
                .foregroundStyle(Color.ludoraText)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
            // Five stars over a ten-point scale, so each star is two points.
            HStack(spacing: 4) {
                ForEach(1...5, id: \.self) { star in
                    Image(systemName: "star.fill")
                        .font(.system(size: 20))
                        .foregroundStyle(
                            Double(star) <= (average / 2).rounded()
                                ? Color.ludoraPrimary
                                : Color.ludoraNeutral.opacity(0.4)
                        )
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(
            "Average rating \(average.formatted(.number.precision(.fractionLength(1)))) out of 10"
        )
    }
}

/// The share of ratings at 7.0 or better, on the web's three-quarter arc.
struct PositiveRatings: View {
    let share: Double

    private var percent: Int { Int((share * 100).rounded()) }

    var body: some View {
        VStack(spacing: 8) {
            ZStack {
                arc(to: 1).stroke(
                    Color.ludoraNeutral.opacity(0.25),
                    style: .init(lineWidth: 12, lineCap: .round)
                )
                arc(to: share).stroke(
                    Color.ludoraPositive,
                    style: .init(lineWidth: 12, lineCap: .round)
                )
                Text("\(percent)%")
                    .font(.system(size: percent == 100 ? 24 : 28, weight: .bold))
                    .foregroundStyle(Color.ludoraPositive)
                // Sits in the arc's own gap, which is why the gauge is three
                // quarters of a circle rather than a full ring.
                Image(systemName: "hand.thumbsup.fill")
                    .font(.system(size: 22))
                    .foregroundStyle(Color.ludoraPositive)
                    .offset(y: 58)
            }
            .frame(width: 118, height: 118)
            .padding(.bottom, 18)

            Text("Positive Ratings")
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(Color.ludoraText)
            Text("SCORES 7-10")
                .font(.system(size: 10, weight: .medium))
                .tracking(0.8)
                .foregroundStyle(Color.ludoraSecondaryText)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(percent) percent of ratings are 7 or above")
    }

    /// Three quarters of a circle, opened at the bottom, so the gap reads as
    /// a gauge rather than as an unfinished ring.
    private func arc(to fraction: Double) -> some Shape {
        Circle()
            .trim(from: 0, to: 0.75 * max(0, min(1, fraction)))
            .rotation(.degrees(135))
    }
}

/// One rank, against the size of the field it was ranked in.
struct RankingCard: View {
    let label: String
    let rank: Int
    let fieldSize: Int?
    let noun: String

    private var share: Double? {
        fieldSize.flatMap { Ranking.betterThanShare(rank: rank, outOf: $0) }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label.uppercased())
                .font(.system(size: 11, weight: .heavy))
                .tracking(1.2)
                .foregroundStyle(Color.ludoraSecondaryText)

            Text("#\(rank)")
                .font(.system(size: 40, weight: .bold))
                .foregroundStyle(Color.ludoraPrimary)

            if let fieldSize {
                Text("Out of \(fieldSize.formatted()) \(noun)")
                    .font(.caption)
                    .foregroundStyle(Color.ludoraSecondaryText.opacity(0.7))
            }

            if let share {
                VStack(alignment: .trailing, spacing: 6) {
                    Text("Better than \(Ranking.formatBetterThan(share))")
                        .font(.caption)
                        .foregroundStyle(Color.ludoraSecondaryText)
                    ProgressView(value: share)
                        .progressViewStyle(.linear)
                        .tint(.ludoraPrimary)
                }
                .frame(maxWidth: .infinity, alignment: .trailing)
                .padding(.top, 14)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(.white, in: .rect(cornerRadius: 16))
        .overlay {
            RoundedRectangle(cornerRadius: 16).strokeBorder(Color.ludoraSurface)
        }
        .accessibilityElement(children: .combine)
    }
}

/// The detail hero's art, sized by the artwork itself.
///
/// No card, no fixed aspect box, no border. The web detail page renders the
/// cover as `w-full h-auto object-contain`, so a tall box and a wide one
/// each take the height they need, and behind it puts an "ambient glow": the
/// same image blurred, scaled slightly past the edges and nudged down. The
/// browse card's letterboxed backdrop exists to fill a fixed cell in a grid;
/// nothing here is a cell, so the art is simply the art.
///
/// The glow is a `background`, applied after `clipShape` so the clip takes
/// the artwork and not the glow, which needs to spill past the edges to read
/// as light rather than as a second picture.
struct CoverArt: View {
    let url: String?

    /// The web caps the mobile column at 320px and centres it. Without a cap
    /// a square cover would eat most of a tall screen before the title.
    private let maxWidth: CGFloat = 320

    var body: some View {
        content
            .frame(maxWidth: maxWidth)
            .frame(maxWidth: .infinity, alignment: .center)
    }

    @ViewBuilder
    private var content: some View {
        if let url = url.flatMap(URL.init(string:)) {
            AsyncImage(url: url, transaction: .init(animation: .easeOut(duration: 0.25))) { phase in
                switch phase {
                case .success(let image):
                    image
                        .resizable()
                        .scaledToFit()
                        .clipShape(.rect(cornerRadius: 16))
                        .background {
                            image
                                .resizable()
                                .scaledToFill()
                                .blur(radius: 30)
                                .opacity(0.4)
                                .scaleEffect(1.05)
                                .offset(y: 16)
                        }
                        .shadow(color: .ludoraText.opacity(0.22), radius: 22, y: 12)
                case .failure:
                    placeholder
                default:
                    // Holds the row open while the image loads, so the title
                    // below does not jump up and back down. No "no image"
                    // wording here: nothing has failed yet.
                    well.overlay { ProgressView().tint(.ludoraNeutral) }
                }
            }
        } else {
            placeholder
        }
    }

    private var placeholder: some View {
        well.overlay {
            Text("No image available")
                .font(.footnote)
                .foregroundStyle(Color.ludoraSecondaryText)
        }
    }

    /// A stand-in the size of a typical box, so the layout settles once.
    private var well: some View {
        RoundedRectangle(cornerRadius: 16)
            .fill(Color.ludoraNeutral.opacity(0.15))
            .aspectRatio(3 / 4, contentMode: .fit)
    }
}

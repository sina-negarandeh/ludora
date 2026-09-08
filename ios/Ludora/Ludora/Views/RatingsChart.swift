import Charts
import LudoraKit
import SwiftUI

/// The ratings histogram: ten bars, one per whole score.
///
/// Tapping a bar reads out what it contains. The web shows the same numbers
/// on hover, which a phone has no equivalent of, so the split (how many
/// scored 8.0 against 8.5) surfaces on tap instead of being lost.
///
/// Bars are scaled against the tallest, not the rating count: the
/// distribution is heavily skewed, and scaling to the total flattens every
/// bar but one.
struct RatingHistogram: View {
    let breakdown: RatingBreakdown

    @State private var selectedScore: Int?

    private var selectedBar: RatingBar? {
        selectedScore.flatMap { score in breakdown.bars.first { $0.score == score } }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            callout

            // Categorical x, not a continuous 1...10 scale. `width:
            // .ratio` is measured against a discrete step, and on a
            // continuous scale it resolves to zero, which draws the axis and
            // the grid and no bars at all. Ten labelled bins is what this
            // chart is anyway.
            Chart(breakdown.bars) { bar in
                BarMark(
                    x: .value("Score", String(bar.score)),
                    y: .value("Ratings", bar.total),
                    width: .ratio(0.72)
                )
                .foregroundStyle(
                    selectedScore == nil || selectedScore == bar.score
                        ? Color.ludoraPrimary.opacity(0.6)
                        : Color.ludoraPrimary.opacity(0.22)
                )
                .cornerRadius(7, style: .continuous)
            }
            // Grid lines but no y labels, as on the web. The counts are on
            // the callout when a bar is tapped, and the labels cost enough
            // leading width to push the "10" tick off the trailing edge.
            .chartYAxis {
                AxisMarks(values: .automatic(desiredCount: 5)) { _ in
                    AxisGridLine().foregroundStyle(Color.ludoraNeutral.opacity(0.3))
                }
            }
            .chartXAxis {
                AxisMarks { value in
                    AxisValueLabel {
                        if let score = value.as(String.self) {
                            Text(score)
                                .font(.system(size: 12, weight: .bold))
                                .foregroundStyle(Color.ludoraSecondaryText.opacity(0.7))
                        }
                    }
                }
            }
            .chartOverlay { proxy in
                Rectangle().fill(.clear).contentShape(Rectangle())
                    .onTapGesture { location in
                        guard
                            let label = proxy.value(atX: location.x, as: String.self),
                            let score = Int(label)
                        else { return }
                        selectedScore = (selectedScore == score) ? nil : score
                    }
            }
            .frame(height: 170)
        }
        .animation(.easeOut(duration: 0.15), value: selectedScore)
    }

    /// Sits above the chart in a fixed-height row, so selecting a bar does
    /// not shove the chart down the screen.
    private var callout: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            if let bar = selectedBar {
                Text(bar.score == 10 ? "Score 10" : "Score \(bar.score)–\(bar.score).5")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(Color.ludoraText)

                Text("\(bar.total.formatted()) ratings")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(Color.ludoraPrimary)

                if bar.score < 10 {
                    Text("\(bar.score).0: \(bar.whole.formatted())  ·  \(bar.score).5: \(bar.half.formatted())")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(Color.ludoraSecondaryText)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                }
            } else {
                Text("Tap a bar to see how many rated it")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(Color.ludoraSecondaryText.opacity(0.7))
            }
            Spacer(minLength: 0)
        }
        .frame(height: 18)
    }
}

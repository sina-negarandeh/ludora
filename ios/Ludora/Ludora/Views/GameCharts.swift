import Charts
import LudoraKit
import SwiftUI

/// A value called out on a density curve: this game, or one end of its
/// community range.
struct CurveMarker: Identifiable {
    var id: String { label }
    let value: Double
    let label: String
}

/// One metric's density curve with this game marked on it.
///
/// Mirrors the web's `DistributionChart`: a filled density curve, a dashed
/// "AVG" line at the curve's own mean, one or more solid markers with a dot
/// sitting on the line, round-number ticks, a direction label at each end,
/// and a percentile sentence underneath.
///
/// Drawn with Swift Charts rather than a hand-built path so the axis,
/// scaling and accessibility come from the framework. The web hand-rolls an
/// SVG because it has to; this does not.
struct DistributionChartCard: View {
    let title: String
    let summary: String
    let markers: [CurveMarker]
    let distribution: MetricDistribution
    /// The group the curve came from, already resolved and named for display.
    let fieldName: String
    let leftLabel: String
    let rightLabel: String
    /// "Heavier than", "Longer than" — the phrase the percentile sentence uses.
    let comparative: String
    /// How the AVG chip formats its number.
    let formatAverage: (Double) -> String

    private var points: [(x: Double, y: Double)] {
        zip(distribution.x, distribution.density).map { (x: $0, y: $1) }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(title)
                    .font(.system(size: 17, weight: .bold))
                    .foregroundStyle(Color.ludoraText)
                Spacer()
                Text(summary)
                    .font(.system(size: 17, weight: .bold))
                    .foregroundStyle(Color.ludoraPrimary)
            }

            chart
                // Room above the plot for the AVG chip and the marker labels
                // stacked over it, which the web also places outside the plot.
                .padding(.top, markers.count > 1 ? 52 : 36)

            HStack {
                Text(leftLabel.uppercased())
                Spacer()
                Text(rightLabel.uppercased())
            }
            .font(.system(size: 10, weight: .bold))
            .tracking(0.8)
            .foregroundStyle(Color.ludoraSecondaryText.opacity(0.7))

            VStack(alignment: .leading, spacing: 2) {
                ForEach(markers) { marker in
                    if let share = distribution.share(atOrBelow: marker.value) {
                        Text(sentence(for: marker, share: share))
                            .font(.system(size: 13, weight: .medium))
                            .foregroundStyle(Color.ludoraSecondaryText)
                    }
                }
            }
        }
        .padding(16)
        .background(.white, in: .rect(cornerRadius: 16))
        .overlay { RoundedRectangle(cornerRadius: 16).strokeBorder(Color.ludoraSurface) }
    }

    /// One marker reads as a sentence; several are prefixed by their label so
    /// "Community Min" and "Community Max" stay apart.
    private func sentence(for marker: CurveMarker, share: Double) -> String {
        let core = "\(comparative.lowercased()) \(Int((share * 100).rounded()))% of \(fieldName)"
        if markers.count == 1 {
            return core.prefix(1).uppercased() + core.dropFirst()
        }
        return "\(marker.label) \(core)"
    }

    private var chart: some View {
        Chart {
            ForEach(points, id: \.x) { point in
                AreaMark(
                    x: .value("Value", point.x),
                    y: .value("Density", point.y)
                )
                .foregroundStyle(
                    .linearGradient(
                        colors: [.ludoraPrimary.opacity(0.3), .ludoraPrimary.opacity(0.04)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
                .interpolationMethod(.catmullRom)
            }

            ForEach(points, id: \.x) { point in
                LineMark(
                    x: .value("Value", point.x),
                    y: .value("Density", point.y)
                )
                .foregroundStyle(Color.ludoraPrimary.opacity(0.7))
                .lineStyle(StrokeStyle(lineWidth: 2))
                .interpolationMethod(.catmullRom)
            }

            if let average = distribution.averageValue {
                RuleMark(x: .value("Average", average))
                    .foregroundStyle(Color.ludoraNeutral)
                    .lineStyle(StrokeStyle(lineWidth: 1.5, dash: [4, 3]))
                    .annotation(position: .top, spacing: 2, overflowResolution: .init(x: .fit)) {
                        Text("AVG \(formatAverage(average))")
                            .font(.system(size: 9, weight: .bold))
                            .tracking(0.5)
                            .foregroundStyle(Color.ludoraSecondaryText)
                            .padding(.horizontal, 4)
                            .padding(.vertical, 1)
                            .background(Color.ludoraSurface.opacity(0.85), in: .rect(cornerRadius: 3))
                    }
            }

            ForEach(Array(markers.enumerated()), id: \.element.id) { index, marker in
                RuleMark(x: .value(marker.label, marker.value))
                    .foregroundStyle(Color.ludoraPrimary)
                    .lineStyle(StrokeStyle(lineWidth: 2))
                    // Above the AVG chip, never level with it: the two
                    // markers sit close together whenever a game is near the
                    // average, which is most of them, and at equal height the
                    // labels overlap into an unreadable smear. Several
                    // markers then stack again above that.
                    .annotation(
                        position: .top,
                        spacing: markers.count > 1 ? CGFloat(index) * 16 + 18 : 18,
                        overflowResolution: .init(x: .fit)
                    ) {
                        Text(marker.label)
                            .font(.system(size: 10, weight: .bold))
                            .foregroundStyle(Color.ludoraPrimary)
                    }

                if let height = distribution.density(at: marker.value) {
                    PointMark(
                        x: .value(marker.label, marker.value),
                        y: .value("Density", height)
                    )
                    .symbolSize(90)
                    .foregroundStyle(Color.ludoraPrimary)
                }
            }
        }
        .chartXScale(domain: distribution.min...distribution.max)
        .chartYScale(domain: 0...(distribution.peakDensity * 1.05))
        .chartYAxis(.hidden)
        .chartXAxis {
            AxisMarks(values: distribution.niceTicks()) { value in
                AxisValueLabel {
                    if let number = value.as(Double.self) {
                        Text(tickLabel(number))
                            .font(.system(size: 10, weight: .medium))
                            .foregroundStyle(Color.ludoraSecondaryText.opacity(0.6))
                    }
                }
                AxisGridLine().foregroundStyle(Color.ludoraNeutral.opacity(0.18))
            }
        }
        .frame(height: 110)
    }

    /// Whole numbers stay bare, fractional ones get one decimal.
    private func tickLabel(_ value: Double) -> String {
        value == value.rounded()
            ? String(Int(value))
            : String(format: "%.1f", value)
    }
}

/// A community poll, drawn as bars over the matching density curve.
///
/// The curve is the context the web puts behind these bars: how this game's
/// voters compare to the shape of the whole field.
struct PollChartCard: View {
    let title: String
    let bars: [PollBar]
    let distribution: MetricDistribution?
    let leftLabel: String
    let rightLabel: String
    /// Turns "4+" into "4+ Players" for the callout.
    let formatLabel: (String) -> String

    @State private var selected: PollBar.ID?

    private var peakVotes: Int { bars.map(\.votes).max() ?? 0 }
    private var selectedBar: PollBar? { bars.first { $0.id == selected } }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(title)
                    .font(.system(size: 17, weight: .bold))
                    .foregroundStyle(Color.ludoraText)
                Spacer()
                if let selectedBar {
                    Text("\(formatLabel(selectedBar.label)) · \(selectedBar.votes.formatted()) votes")
                        .font(.system(size: 13, weight: .bold))
                        .foregroundStyle(Color.ludoraPrimary)
                } else if let best = bars.max(by: { $0.votes < $1.votes }), best.votes > 0 {
                    Text(formatLabel(best.label))
                        .font(.system(size: 17, weight: .bold))
                        .foregroundStyle(Color.ludoraPrimary)
                }
            }

            Chart {
                if let distribution, distribution.peakDensity > 0 {
                    ForEach(Array(zip(distribution.x, distribution.density)), id: \.0) { x, density in
                        AreaMark(
                            x: .value("Value", x),
                            // Scaled onto the vote axis so the curve and the
                            // bars share one plot without a second scale.
                            y: .value("Votes", density / distribution.peakDensity * Double(peakVotes))
                        )
                        .foregroundStyle(Color.ludoraNeutral.opacity(0.22))
                        .interpolationMethod(.catmullRom)
                    }
                }

                ForEach(bars) { bar in
                    BarMark(
                        x: .value("Bucket", bar.x),
                        y: .value("Votes", bar.votes),
                        width: .fixed(18)
                    )
                    .foregroundStyle(
                        selected == nil || selected == bar.id
                            ? Color.ludoraPrimary.opacity(0.75)
                            : Color.ludoraPrimary.opacity(0.28)
                    )
                    .cornerRadius(4)
                }
            }
            .chartYAxis(.hidden)
            .chartXAxis {
                AxisMarks(values: bars.map(\.x)) { value in
                    AxisValueLabel {
                        if let number = value.as(Double.self),
                           let bar = bars.first(where: { $0.x == number }) {
                            Text(bar.label)
                                .font(.system(size: 10, weight: .medium))
                                .foregroundStyle(Color.ludoraSecondaryText.opacity(0.6))
                        }
                    }
                }
            }
            .chartOverlay { proxy in
                // Tap a bar to read its exact vote count.
                Rectangle().fill(.clear).contentShape(Rectangle())
                    .onTapGesture { location in
                        guard let x: Double = proxy.value(atX: location.x) else { return }
                        let nearest = bars.min { abs($0.x - x) < abs($1.x - x) }
                        selected = (selected == nearest?.id) ? nil : nearest?.id
                    }
            }
            .frame(height: 110)

            HStack {
                Text(leftLabel.uppercased())
                Spacer()
                Text(rightLabel.uppercased())
            }
            .font(.system(size: 10, weight: .bold))
            .tracking(0.8)
            .foregroundStyle(Color.ludoraSecondaryText.opacity(0.7))

            Text(selectedBar == nil ? "Tap a bar for its vote count" : "Community votes")
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(Color.ludoraSecondaryText)
        }
        .padding(16)
        .background(.white, in: .rect(cornerRadius: 16))
        .overlay { RoundedRectangle(cornerRadius: 16).strokeBorder(Color.ludoraSurface) }
    }
}

/// A section that had nothing to draw, said plainly rather than omitted.
struct EmptyChartCard: View {
    let title: String
    let message: String

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(.system(size: 17, weight: .bold))
                .foregroundStyle(Color.ludoraText)
            Text(message)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(Color.ludoraSecondaryText.opacity(0.8))
                .frame(maxWidth: .infinity, minHeight: 90, alignment: .leading)
        }
        .padding(16)
        .background(.white, in: .rect(cornerRadius: 16))
        .overlay { RoundedRectangle(cornerRadius: 16).strokeBorder(Color.ludoraSurface) }
    }
}

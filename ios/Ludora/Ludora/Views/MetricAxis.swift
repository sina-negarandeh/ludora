import LudoraKit
import SwiftUI

/// How a metric reads on an axis.
///
/// Which end is "less", how a game sitting high on the curve is described,
/// and how the average is written. All three are properties of the metric,
/// not of any one chart, but they used to be passed in at each call site:
/// "Fewer"/"More" was written three times, "Shorter"/"Longer" twice, and
/// the same average formatter appeared three times. That is a table, so it
/// is one here instead of six near-identical argument lists.
struct MetricAxis {
    let low: String
    let high: String
    /// Completes "…  82% of Strategy Games".
    let comparative: String
    let formatAverage: (Double) -> String
}

extension Metric {
    var axis: MetricAxis {
        switch self {
        case .complexity:
            MetricAxis(
                low: "Lighter", high: "Heavier", comparative: "Heavier than",
                formatAverage: { String(format: "%.2f", $0) }
            )
        case .playtime:
            MetricAxis(
                low: "Shorter", high: "Longer", comparative: "Longer than",
                formatAverage: { String(Int($0.rounded())) }
            )
        case .players:
            MetricAxis(
                low: "Fewer", high: "More", comparative: "Accommodates more players than",
                formatAverage: { String(format: "%.1f", $0) }
            )
        case .minPlayers:
            MetricAxis(
                low: "Fewer", high: "More", comparative: "Requires more players than",
                formatAverage: { String(format: "%.1f", $0) }
            )
        case .minAge:
            MetricAxis(
                low: "Younger", high: "Older", comparative: "More mature than",
                formatAverage: { String(format: "%.1f", $0) }
            )
        }
    }
}

import Foundation

/// A metric the distributions endpoint carries a curve for.
///
/// The raw value is the wire key, so a lookup cannot be misspelled into a
/// silently missing chart. These five are what
/// `scripts/generate_distributions.py` emits. Anything else is drift, and a
/// decode that meets one should say so rather than shrug.
public enum Metric: String, CaseIterable, Hashable, Sendable {
    case complexity = "Complexity"
    case playtime = "Playtime"
    case players = "Players"
    case minPlayers = "Min Players"
    case minAge = "Min Age"
}

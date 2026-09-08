import Foundation

/// Families, grouped by the namespace they are qualified with.
///
/// `Game.families` arrives fully qualified: "Category: Industry /
/// Manufacturing", "Region: Great Britain", "Components: Map (Continental /
/// National scale)". Listed raw that is a column of repeated prefixes, so
/// both the web app and this one split the namespace off and use it as a
/// heading. Grouping lives here rather than in the view because it is the
/// kind of string handling that is worth a test.
public struct FamilyGrouping: Hashable, Sendable {
    /// The namespace, e.g. "Region".
    public let name: String
    /// The values under it, in the order the API sent them.
    public let values: [String]

    public init(name: String, values: [String]) {
        self.name = name
        self.values = values
    }
}

public extension FamilyGrouping {
    /// The namespace used for a family that carries none.
    static let fallbackName = "Other"

    /// Splits on the *first* ": " only.
    ///
    /// Values contain colons of their own ("Components: Map (Continental /
    /// National scale)" is one namespace and one value), so splitting on
    /// every separator would shred them. A family with no namespace keeps
    /// its whole string as the value rather than being dropped.
    static func split(_ family: String) -> (namespace: String, value: String) {
        guard let separator = family.range(of: ": ") else {
            return (fallbackName, family)
        }
        return (
            String(family[..<separator.lowerBound]),
            String(family[separator.upperBound...])
        )
    }

    /// Groups families by namespace, sorted by namespace name.
    ///
    /// Only the groups are sorted; values keep the order they arrived in, so
    /// any ranking the API applied survives.
    static func grouping(_ families: [String]) -> [FamilyGrouping] {
        var valuesByName: [String: [String]] = [:]
        for family in families {
            let (namespace, value) = split(family)
            valuesByName[namespace, default: []].append(value)
        }
        return valuesByName.keys.sorted().map {
            FamilyGrouping(name: $0, values: valuesByName[$0]!)
        }
    }
}

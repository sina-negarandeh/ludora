import Foundation

/// The vocabularies behind the filter UI.
///
/// These are not one uniform shape, and the difference is not accidental.
/// BGG's taxonomy has four kinds of tag with genuinely different structure,
/// so the API returns four different shapes and this file models them
/// as they are rather than flattening them into one type that lies:
///
/// - subdomains and themes carry a usage count worth showing
/// - categories, mechanics, designers, publishers, artists are bare strings
/// - families are namespaced, so they arrive grouped
///
/// See docs/data/README.md#bgg-terminology for what each one means.

/// A tag with a usage count. `/subdomains` and `/themes` both return this.
public struct CountedTag: Codable, Identifiable, Hashable, Sendable {
    public let id: Int
    public let name: String
    public let gameCount: Int

    enum CodingKeys: String, CodingKey {
        case id, name
        case gameCount = "game_count"
    }
}

/// One value inside a family namespace, e.g. "Bears" under "Animals".
///
/// `value` is the bare label and `name` is the fully qualified
/// "Group: Value" string. Filtering sends `name`, because that is what the
/// games table actually stores.
public struct FamilyValue: Codable, Identifiable, Hashable, Sendable {
    public let id: Int
    public let value: String
    public let name: String
    public let gameCount: Int

    enum CodingKeys: String, CodingKey {
        case id, value, name
        case gameCount = "game_count"
    }
}

/// One family namespace and everything under it. BGG has 72 of these, and
/// some hold thousands of values, so the filter UI should lazily disclose
/// a group rather than render every value up front.
public struct FamilyGroup: Codable, Identifiable, Hashable, Sendable {
    public var id: String { group }

    public let group: String
    public let values: [FamilyValue]
}

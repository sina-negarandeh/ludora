import Foundation

/// One user review, mirroring the backend's `ReviewResponse`.
///
/// `rating` and `comment` are both optional and genuinely independent: BGG
/// lets a user rate without commenting and comment without rating, so a
/// review with neither is possible in the source data.
public struct Review: Codable, Identifiable, Hashable, Sendable {
    public let id: Int
    public let user: String
    public let rating: Double?
    public let comment: String?
}

/// A page of reviews, plus the two breakdowns the API computes over the
/// whole matching set rather than the current page.
///
/// Both breakdowns are shares, not counts: the backend sends percentages
/// (`{"en": 89.0, "es": 2.4}`), which is why they decode as `Double`.
/// They drive the language and rating filter menus, so they describe every
/// review for the game, not just the ten on screen.
public struct PaginatedReviews: Codable, Sendable {
    public let total: Int
    public let languageBreakdown: [String: Double]?
    public let ratingBreakdown: [String: Double]?
    public let items: [Review]

    enum CodingKeys: String, CodingKey {
        case total
        case languageBreakdown = "language_breakdown"
        case ratingBreakdown = "rating_breakdown"
        case items
    }
}

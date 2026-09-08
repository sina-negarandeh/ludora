import Foundation

/// One vote count in a BGG community poll.
///
/// The `@`-prefixed keys are BGG's XML attributes surviving an XML-to-JSON
/// ingestion, and the counts arrive as strings for the same reason. They are
/// kept as strings here rather than coerced during decoding, so a row that
/// is not a number degrades to zero votes instead of failing the whole game.
public struct PollVote: Codable, Hashable, Sendable {
    public let value: String
    public let numVotes: String

    enum CodingKeys: String, CodingKey {
        case value = "@value"
        case numVotes = "@numvotes"
    }

    public init(value: String, numVotes: String) {
        self.value = value
        self.numVotes = numVotes
    }

    public var votes: Int { Int(numVotes) ?? 0 }
}

/// One player count's Best / Recommended / Not Recommended tally.
public struct PlayerCountPoll: Codable, Hashable, Sendable {
    public let numPlayers: String
    public let result: [PollVote]

    enum CodingKeys: String, CodingKey {
        case numPlayers = "@numplayers"
        case result
    }

    public init(numPlayers: String, result: [PollVote]) {
        self.numPlayers = numPlayers
        self.result = result
    }

    /// Votes for this count being the *best* number of players, which is the
    /// single series the web charts. "Recommended" and "Not Recommended" are
    /// carried but not drawn.
    public var bestVotes: Int {
        result.first { $0.value == "Best" }?.votes ?? 0
    }
}

/// A bar in a community poll chart.
public struct PollBar: Hashable, Sendable, Identifiable {
    public var id: String { label }
    public let label: String
    public let votes: Int
    /// Where the bar sits on the metric's own axis, so a poll can be drawn
    /// against the same density curve as the rest of the section.
    public let x: Double

    public init(label: String, votes: Int, x: Double) {
        self.label = label
        self.votes = votes
        self.x = x
    }
}

public enum CommunityPoll {
    /// Suggested player counts, one bar per count, carrying "Best" votes.
    ///
    /// BGG writes the open-ended top bucket as "4+", which has no numeric
    /// value of its own. The web places it one step past the number it
    /// contains, and this does the same so the bar does not land on top of
    /// the "4" bar.
    public static func playerCountBars(_ poll: [PlayerCountPoll]?) -> [PollBar] {
        (poll ?? []).map { entry in
            let digits = Int(entry.numPlayers.filter(\.isNumber)) ?? 0
            let open = entry.numPlayers.contains("+")
            return PollBar(
                label: entry.numPlayers,
                votes: entry.bestVotes,
                x: Double(open ? digits + 1 : digits)
            )
        }
    }

    /// Suggested minimum age, one bar per age bucket.
    ///
    /// The top bucket is "21 and up", which parses to 21 by taking the
    /// leading digits.
    public static func ageBars(_ poll: [PollVote]?) -> [PollBar] {
        (poll ?? []).map { vote in
            PollBar(
                label: vote.value,
                votes: vote.votes,
                x: Double(vote.value.prefix { $0.isNumber }) ?? 0
            )
        }
    }
}

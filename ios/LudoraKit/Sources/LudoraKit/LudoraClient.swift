import Foundation

/// Where the backend lives.
///
/// The simulator shares the host's network, so `localhost:8000` works there
/// with no setup. A physical device does not: it needs the Mac's LAN
/// address. The backend already runs with `allow_origins=["*"]`, so nothing
/// server-side has to change for either.
public struct LudoraConfiguration: Sendable {
    public let baseURL: URL

    public init(baseURL: URL) {
        self.baseURL = baseURL
    }

    /// Works in the simulator and for `swift test` on the Mac itself.
    public static let localhost = LudoraConfiguration(
        baseURL: URL(string: "http://localhost:8000")!
    )

    /// For a physical device: pass the Mac's LAN IP, e.g. "192.168.1.42".
    public static func lan(host: String, port: Int = 8000) -> LudoraConfiguration {
        LudoraConfiguration(baseURL: URL(string: "http://\(host):\(port)")!)
    }
}

public enum LudoraError: Error, LocalizedError, Sendable {
    /// The server answered, but not with success. Carries the status so a
    /// caller can tell "no such game" (404) from "the backend is broken"
    /// (500) without parsing a message string.
    case httpStatus(Int)
    /// The response did not match the model. This is the drift case, and it
    /// keeps the underlying error rather than collapsing to a bool, because
    /// the field name is the whole diagnostic value.
    case decoding(any Error)
    case transport(any Error)

    public var errorDescription: String? {
        switch self {
        case .httpStatus(404):
            "That game could not be found."
        case .httpStatus(let code) where code >= 500:
            "The server had a problem (HTTP \(code)). Is the backend running?"
        case .httpStatus(let code):
            "The request failed (HTTP \(code))."
        case .decoding:
            "The server sent something this app could not read."
        case .transport:
            "Could not reach the server. Is it running?"
        }
    }
}

/// A typed client over the Ludora REST API.
///
/// URLSession and async/await, with no third-party networking dependency:
/// there are seven endpoints here and nothing about them needs more than
/// the standard library provides.
///
/// Scoped to what this app renders. Recommendations, the ABSA aspect data,
/// and the assistant all exist on the backend and are deliberately absent
/// here; see ios/AGENTS.md.
public actor LudoraClient {
    private let configuration: LudoraConfiguration
    private let session: URLSession
    private let decoder = JSONDecoder()

    public init(
        configuration: LudoraConfiguration = .localhost,
        session: URLSession = .shared
    ) {
        self.configuration = configuration
        self.session = session
    }

    // MARK: - Games

    /// Browse and filter the catalog. Also does lexical search when
    /// `query.query` is set; for semantic or hybrid retrieval use
    /// `search(_:)`.
    public func games(_ query: GameQuery = GameQuery()) async throws -> PaginatedGames {
        try await get("/api/games/", queryItems: query.queryItems)
    }

    public func game(bggID: Int) async throws -> Game {
        try await get("/api/games/\(bggID)")
    }

    public func reviews(
        bggID: Int,
        page: Int = 1,
        pageSize: Int = 10,
        language: String? = nil,
        minRating: Double? = nil,
        maxRating: Double? = nil
    ) async throws -> PaginatedReviews {
        var items: [URLQueryItem] = [
            .init(name: "page", value: String(page)),
            .init(name: "page_size", value: String(pageSize)),
        ]
        if let language { items.append(.init(name: "language", value: language)) }
        if let minRating { items.append(.init(name: "min_rating", value: String(minRating))) }
        if let maxRating { items.append(.init(name: "max_rating", value: String(maxRating))) }
        return try await get("/api/games/\(bggID)/reviews", queryItems: items)
    }

    // MARK: - Search

    /// Lexical, semantic, or hybrid search. A POST because the request body
    /// nests; see `SearchRequest`.
    public func search(_ request: SearchRequest) async throws -> PaginatedSearchResults {
        try await post("/api/search/", body: request)
    }

    // MARK: - Filter vocabularies

    /// Precomputed density curves, keyed by subdomain then metric. A static
    /// pipeline artifact, so it is worth fetching once per launch rather
    /// than per screen.
    public func distributions() async throws -> MetricDistributions {
        try await get("/api/distributions")
    }

    public func subdomains() async throws -> [CountedTag] { try await get("/api/subdomains") }
    public func themes() async throws -> [CountedTag] { try await get("/api/themes") }
    public func families() async throws -> [FamilyGroup] { try await get("/api/families") }
    public func categories() async throws -> [String] { try await get("/api/categories") }
    public func mechanics() async throws -> [String] { try await get("/api/mechanics") }
    public func designers() async throws -> [String] { try await get("/api/designers") }
    public func publishers() async throws -> [String] { try await get("/api/publishers") }
    public func artists() async throws -> [String] { try await get("/api/artists") }

    // MARK: - Transport

    private func get<T: Decodable>(
        _ path: String,
        queryItems: [URLQueryItem] = []
    ) async throws -> T {
        var components = URLComponents(
            url: configuration.baseURL.appending(path: path),
            resolvingAgainstBaseURL: false
        )!
        if !queryItems.isEmpty { components.queryItems = queryItems }
        return try await perform(URLRequest(url: components.url!))
    }

    private func post<Body: Encodable, T: Decodable>(
        _ path: String,
        body: Body
    ) async throws -> T {
        var request = URLRequest(url: configuration.baseURL.appending(path: path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        return try await perform(request)
    }

    private func perform<T: Decodable>(_ request: URLRequest) async throws -> T {
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw LudoraError.transport(error)
        }

        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw LudoraError.httpStatus(http.statusCode)
        }

        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw LudoraError.decoding(error)
        }
    }
}

import Foundation
import Testing

@testable import LudoraKit

/// URL construction and error decoding, offline.
///
/// These pin defects a live call would have caught only against a running
/// backend, and only on the platform that happened to expose them.
@Suite("Transport")
struct TransportTests {
    private let client = LudoraClient()

    /// `URL.appending(path:)` infers a directory from a trailing slash and
    /// adds a second one, so `/api/games/` became `/api/games//`, which the
    /// backend answers with 404. It resolved differently per platform, which
    /// is why the app worked while the package could not reach the endpoint.
    @Test("never doubles the slash on a path that ends in one")
    func noDoubleSlash() throws {
        let url = try client.url(for: "/api/games/")
        #expect(url.path() == "/api/games/")
        #expect(!url.absoluteString.contains("//api"))
        #expect(!url.absoluteString.contains("games//"))
    }

    @Test("leaves paths without a trailing slash alone")
    func plainPathsUnchanged() throws {
        #expect(try client.url(for: "/api/distributions").path() == "/api/distributions")
        #expect(try client.url(for: "/api/games/224517").path() == "/api/games/224517")
    }

    /// `URLComponents` treats `+` as legal in a query value, but the server
    /// reads it as a space, so "a+b" silently searched for "a b".
    @Test("percent-encodes a plus in a query value")
    func encodesPlus() throws {
        let url = try client.url(
            for: "/api/games/", queryItems: [URLQueryItem(name: "query", value: "a+b")]
        )
        #expect(url.absoluteString.contains("query=a%2Bb"))
        #expect(!url.absoluteString.contains("query=a+b"))
    }

    /// Ampersands must stay encoded, or one filter value would split into two
    /// parameters. 134 family values and one category contain one.
    @Test("keeps an ampersand inside a single query value")
    func encodesAmpersand() throws {
        let url = try client.url(
            for: "/api/games/",
            queryItems: [URLQueryItem(name: "categories", value: "Print & Play")]
        )
        #expect(url.absoluteString.contains("%26"))
        #expect(url.query(percentEncoded: false) == "categories=Print & Play")
    }

    @Test("reads FastAPI's detail string off an error body")
    func readsErrorDetail() throws {
        let body = Data(#"{"detail":"Run scripts/generate_distributions.py."}"#.utf8)
        #expect(LudoraClient.detail(from: body) == "Run scripts/generate_distributions.py.")
    }

    /// A 422 answers with an array of field errors rather than a string.
    @Test("reduces a validation error array to its first message")
    func readsValidationDetail() throws {
        let body = Data(#"{"detail":[{"msg":"limit must be positive","loc":["query","limit"]}]}"#.utf8)
        #expect(LudoraClient.detail(from: body) == "limit must be positive")
    }

    @Test("has no detail for a body that carries none")
    func toleratesBodiesWithoutDetail() {
        #expect(LudoraClient.detail(from: Data("not json".utf8)) == nil)
        #expect(LudoraClient.detail(from: Data(#"{"other":1}"#.utf8)) == nil)
    }

    /// The server's own sentence is more specific than anything written here.
    @Test("prefers the server's message over the generic one")
    func detailWinsOverGenericText() {
        let specific = LudoraError.httpStatus(503, detail: "Run the pipeline.")
        #expect(specific.errorDescription == "Run the pipeline.")

        let bare = LudoraError.httpStatus(404, detail: nil)
        #expect(bare.errorDescription == "That game could not be found.")
    }

    /// Pins the wiring, not just the parser: `perform` has to put the body's
    /// detail on the thrown error, or the parsing above is dead code.
    @Test("puts the server's detail on the thrown error")
    func errorCarriesServerDetail() async throws {
        let client = LudoraClient(
            configuration: .localhost,
            session: StubProtocol.session(
                status: 503,
                body: #"{"detail":"Run scripts/generate_distributions.py."}"#
            )
        )
        do {
            _ = try await client.distributions()
            #expect(Bool(false), "expected the stubbed 503 to throw")
        } catch let error as LudoraError {
            guard case .httpStatus(let code, let detail) = error else {
                #expect(Bool(false), "expected httpStatus, got \(error)")
                return
            }
            #expect(code == 503)
            #expect(detail == "Run scripts/generate_distributions.py.")
            #expect(error.errorDescription == "Run scripts/generate_distributions.py.")
        }
    }
}

/// Serves a canned response so transport behaviour can be tested without a
/// backend, keeping this suite runnable with no infrastructure.
final class StubProtocol: URLProtocol {
    nonisolated(unsafe) static var status = 200
    nonisolated(unsafe) static var body = ""

    static func session(status: Int, body: String) -> URLSession {
        Self.status = status
        Self.body = body
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [StubProtocol.self]
        return URLSession(configuration: configuration)
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func stopLoading() {}

    override func startLoading() {
        let response = HTTPURLResponse(
            url: request.url!, statusCode: Self.status, httpVersion: nil, headerFields: nil
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(Self.body.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }
}

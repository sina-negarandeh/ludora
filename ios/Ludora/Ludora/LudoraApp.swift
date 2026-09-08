import LudoraKit
import SwiftUI

@main
struct LudoraApp: App {
    /// One client for the process. `LudoraConfiguration.localhost` works in
    /// the simulator; on a physical device switch to `.lan(host:)` with the
    /// Mac's address, since the device cannot resolve the host's localhost.
    private let client = LudoraClient(configuration: .localhost)

    var body: some Scene {
        WindowGroup {
            NavigationStack {
                GamesListView(browser: GameBrowser(client: client))
            }
            .environment(client)
        }
    }
}

// The client is an actor, so it is already Sendable and safe to hand
// around. This just lets detail screens reach it without threading it
// through every view initializer.
extension EnvironmentValues {
    @Entry var ludoraClient: LudoraClient = LudoraClient()
}

extension View {
    func environment(_ client: LudoraClient) -> some View {
        environment(\.ludoraClient, client)
    }
}

// swift-tools-version: 6.0
import PackageDescription

// Every piece of app logic lives here rather than in the app target, so it
// builds and tests from the command line with `swift test`: no Xcode
// project, no simulator runtime, no booted device. That is the same rule
// backend/tests/ follows (infra-free so CI can actually run it), and it
// matters more here, because the iOS SDK is installed on this machine
// while no simulator runtime is.
//
// Nothing in this target imports SwiftUI or UIKit. The app target owns all
// of that. This one owns models, networking, and decoding.
let package = Package(
    name: "LudoraKit",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "LudoraKit", targets: ["LudoraKit"]),
    ],
    targets: [
        .target(name: "LudoraKit"),
        .testTarget(
            name: "LudoraKitTests",
            dependencies: ["LudoraKit"],
            resources: [.copy("Fixtures")]
        ),
    ]
)

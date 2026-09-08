import SwiftUI

/// The web app's palette, matched exactly.
///
/// Source of truth is `frontend/tailwind.config.js`. These are the same hex
/// values, so a change there should be mirrored here rather than eyeballed.
/// Warm cream and terracotta, not the iOS default grey-on-white, because
/// the brand is the brand on every client.
///
/// Deliberately light-only for now. The web app has no dark variant either,
/// and a dark theme is a design decision (which cream becomes which grey,
/// what happens to the terracotta) rather than a mechanical inversion. The
/// app pins `.light` until that design exists, instead of letting the
/// system produce an unintended half-dark version of a warm palette.
extension Color {
    /// #FAF6ED, the page ground.
    static let ludoraBackground = Color(hex: 0xFAF6ED)
    /// #EC5E2D, terracotta. Ratings, ranks, actions, complexity dots.
    static let ludoraPrimary = Color(hex: 0xEC5E2D)
    /// #D9785A, a softer terracotta for secondary emphasis.
    static let ludoraSecondary = Color(hex: 0xD9785A)
    /// #E9D8C3, tan. Card borders, tag chips, image placeholders.
    static let ludoraSurface = Color(hex: 0xE9D8C3)
    /// #D1B38F, for icons and hairlines that should recede.
    static let ludoraNeutral = Color(hex: 0xD1B38F)
    /// #2C2520, near-black brown. Never pure black.
    static let ludoraText = Color(hex: 0x2C2520)
    /// #6F5A4B, muted brown for secondary copy.
    static let ludoraSecondaryText = Color(hex: 0x6F5A4B)
    /// #596044, olive.
    static let ludoraAccent = Color(hex: 0x596044)
    /// #00C853, the one green in the product. The web uses it for the share
    /// of ratings that are positive and nothing else, so it reads as a
    /// verdict rather than as another brand colour.
    static let ludoraPositive = Color(hex: 0x00C853)

    init(hex: UInt32) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: 1
        )
    }
}

/// Type styles.
///
/// The web app uses Fraunces for headings and Satoshi for body, both loaded
/// from a CDN. iOS cannot use a webfont, and bundling them is a separate
/// licensing and packaging step, so this maps to the closest system faces:
/// New York for the serif headings, SF Pro for everything else. Both scale
/// with Dynamic Type, which a bundled font would need extra work to match.
extension Font {
    /// Game titles. New York, the system serif, standing in for Fraunces.
    static func ludoraTitle(_ size: CGFloat) -> Font {
        .system(size: size, weight: .regular, design: .serif)
    }

    /// The small uppercase tag chips.
    static let ludoraTag = Font.system(size: 10, weight: .bold)
}

import SwiftUI

/// A section that can be folded away.
///
/// The detail page runs long: description, six vocabularies, eight charts,
/// two ranking cards, a histogram and ten reviews. On a desktop that is a
/// two-column layout you can skim. On a phone it is one column you have to
/// scroll past. Collapsing is how a phone gets the same "skip this part"
/// affordance the web gets from its layout.
///
/// Open by default. A section that hides its content until asked is worse
/// than a long page, and the header states what is inside either way.
struct CollapsibleSection<Content: View>: View {
    let title: String
    /// Shown beside the title, e.g. a review count.
    var detail: String?
    @Binding var expanded: Bool
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: expanded ? 16 : 0) {
            Button {
                withAnimation(.easeInOut(duration: 0.22)) { expanded.toggle() }
            } label: {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    DetailHeading(title)
                    if let detail {
                        Text(detail)
                            .font(.footnote)
                            .foregroundStyle(Color.ludoraSecondaryText)
                    }
                    Spacer(minLength: 8)
                    Image(systemName: "chevron.down")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(Color.ludoraSecondaryText)
                        .rotationEffect(.degrees(expanded ? 0 : -90))
                        .padding(.top, 4)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(title)
            .accessibilityHint(expanded ? "Collapses this section" : "Expands this section")

            if expanded { content() }
        }
    }
}

/// A heading one level below `DetailHeading`, for Official and Community.
struct DetailSubheading: View {
    let title: String

    init(_ title: String) { self.title = title }

    var body: some View {
        Text(title)
            .font(.ludoraTitle(20))
            .foregroundStyle(Color.ludoraText)
    }
}

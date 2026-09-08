import SwiftUI

/// Chips that wrap onto as many lines as they need.
///
/// There is no `flex-wrap` here to borrow: `HStack` never wraps, and
/// `LazyVGrid` makes every chip share one column width, which looks wrong
/// when "Any" sits beside "60-120 min".
struct WrapLayout: Layout {
    var horizontalSpacing: CGFloat = 8
    var verticalSpacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let laid = rows(of: subviews, within: proposal.width ?? .infinity)
        let height = laid.reduce(0) { $0 + $1.height }
            + verticalSpacing * CGFloat(max(laid.count - 1, 0))
        return CGSize(width: proposal.width ?? laid.map(\.width).max() ?? 0, height: height)
    }

    func placeSubviews(
        in bounds: CGRect,
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout ()
    ) {
        var y = bounds.minY
        for row in rows(of: subviews, within: bounds.width) {
            var x = bounds.minX
            for index in row.indices {
                let size = subviews[index].sizeThatFits(.unspecified)
                subviews[index].place(
                    at: CGPoint(x: x, y: y),
                    anchor: .topLeading,
                    proposal: ProposedViewSize(size)
                )
                x += size.width + horizontalSpacing
            }
            y += row.height + verticalSpacing
        }
    }

    private struct Row {
        var indices: [Int] = []
        var width: CGFloat = 0
        var height: CGFloat = 0
    }

    private func rows(of subviews: Subviews, within maxWidth: CGFloat) -> [Row] {
        var laid: [Row] = []
        var current = Row()

        for index in subviews.indices {
            let size = subviews[index].sizeThatFits(.unspecified)
            let extended = current.indices.isEmpty
                ? size.width
                : current.width + horizontalSpacing + size.width

            // A chip wider than the row on its own still has to go
            // somewhere, so only wrap when the row already holds something.
            if extended > maxWidth, !current.indices.isEmpty {
                laid.append(current)
                current = Row(indices: [index], width: size.width, height: size.height)
            } else {
                current.indices.append(index)
                current.width = extended
                current.height = max(current.height, size.height)
            }
        }

        if !current.indices.isEmpty { laid.append(current) }
        return laid
    }
}

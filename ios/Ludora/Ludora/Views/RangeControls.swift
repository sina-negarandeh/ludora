import LudoraKit
import SwiftUI

// The two numeric range controls: a two-thumb slider, and the
// paired min/max fields beneath it.

/// Two thumbs on one track.
///
/// SwiftUI has no range slider, and the alternative here was two `Slider`s
/// that can cross each other into an empty query. Each thumb clamps against
/// the other, so the invalid state is unrepresentable rather than merely
/// discouraged.
struct RangeSlider: View {
    @Binding var lower: Double
    @Binding var upper: Double
    let bounds: ClosedRange<Double>
    let step: Double

    private let thumb: CGFloat = 26
    private let track: CGFloat = 6
    private let space = "rangeSlider"

    var body: some View {
        GeometryReader { proxy in
            let usable = max(proxy.size.width - thumb, 1)
            let midY = proxy.size.height / 2

            ZStack {
                Capsule()
                    .fill(Color.ludoraNeutral.opacity(0.3))
                    .frame(height: track)
                    .padding(.horizontal, thumb / 2)

                Capsule()
                    .fill(Color.ludoraPrimary)
                    .frame(
                        width: max(x(upper, usable) - x(lower, usable), 0),
                        height: track
                    )
                    .position(x: (x(lower, usable) + x(upper, usable)) / 2, y: midY)

                knob(
                    at: x(lower, usable), y: midY, usable: usable,
                    label: "Minimum complexity", value: lower
                ) { lower = min($0, upper) }

                knob(
                    at: x(upper, usable), y: midY, usable: usable,
                    label: "Maximum complexity", value: upper
                ) { upper = max($0, lower) }
            }
            .coordinateSpace(.named(space))
        }
        .frame(height: thumb)
        .overlay(alignment: .bottomLeading) { bound(lower) }
        .overlay(alignment: .bottomTrailing) { bound(upper) }
        .padding(.bottom, 18)
    }

    private func bound(_ value: Double) -> some View {
        Text(value.formatted(.number.precision(.fractionLength(1))))
            .font(.caption.bold())
            .foregroundStyle(Color.ludoraSecondaryText)
            .offset(y: 18)
    }

    private func x(_ value: Double, _ usable: CGFloat) -> CGFloat {
        let fraction = (value - bounds.lowerBound) / (bounds.upperBound - bounds.lowerBound)
        return thumb / 2 + CGFloat(fraction) * usable
    }

    private func value(atX position: CGFloat, _ usable: CGFloat) -> Double {
        let clamped = min(max(position - thumb / 2, 0), usable)
        let fraction = Double(clamped / usable)
        let raw = bounds.lowerBound + fraction * (bounds.upperBound - bounds.lowerBound)
        return (raw / step).rounded() * step
    }

    private func knob(
        at position: CGFloat,
        y: CGFloat,
        usable: CGFloat,
        label: String,
        value current: Double,
        onDrag: @escaping (Double) -> Void
    ) -> some View {
        Circle()
            .fill(.white)
            .frame(width: thumb, height: thumb)
            .overlay(Circle().strokeBorder(Color.ludoraPrimary, lineWidth: 3))
            .shadow(color: .ludoraText.opacity(0.25), radius: 3, y: 1)
            // Attached before `position` so the gesture only claims the
            // knob's own area. A gesture added afterwards would cover the
            // whole track and the second knob would never see a drag.
            .gesture(
                DragGesture(minimumDistance: 0, coordinateSpace: .named(space))
                    .onChanged { onDrag(value(atX: $0.location.x, usable)) }
            )
            .position(x: position, y: y)
            .accessibilityLabel(label)
            .accessibilityValue(current.formatted(.number.precision(.fractionLength(1))))
            .accessibilityAdjustableAction { direction in
                switch direction {
                case .increment: onDrag(min(current + step, bounds.upperBound))
                case .decrement: onDrag(max(current - step, bounds.lowerBound))
                @unknown default: break
                }
            }
    }
}

/// The web's "Specify Min/Max" disclosure: collapsed by default, because
/// the presets above cover almost every real request.
struct CustomRange: View {
    let title: String
    let unit: String
    @Binding var minimum: Int?
    @Binding var maximum: Int?
    let onEdit: () -> Void

    init(
        _ title: String,
        unit: String,
        minimum: Binding<Int?>,
        maximum: Binding<Int?>,
        onEdit: @escaping () -> Void
    ) {
        self.title = title
        self.unit = unit
        self._minimum = minimum
        self._maximum = maximum
        self.onEdit = onEdit
    }

    var body: some View {
        DisclosureGroup {
            HStack(spacing: 10) {
                field("Min", value: $minimum)
                field("Max", value: $maximum)
            }
            .padding(.top, 4)
        } label: {
            Text(title)
                .font(.footnote.weight(.medium))
                .foregroundStyle(Color.ludoraSecondaryText)
        }
    }

    private func field(_ placeholder: String, value: Binding<Int?>) -> some View {
        TextField(placeholder, text: Binding(
            get: { value.wrappedValue.map { String($0) } ?? "" },
            set: {
                // Empty clears the bound rather than pinning it to zero.
                value.wrappedValue = $0.isEmpty ? nil : Int($0)
                onEdit()
            }
        ))
        .keyboardType(.numberPad)
        .font(.subheadline)
        .foregroundStyle(Color.ludoraText)
        .padding(.horizontal, 12)
        .padding(.vertical, 9)
        .background(Color.ludoraNeutral.opacity(0.15), in: .rect(cornerRadius: 10))
        .accessibilityLabel("\(placeholder) \(unit)")
    }
}

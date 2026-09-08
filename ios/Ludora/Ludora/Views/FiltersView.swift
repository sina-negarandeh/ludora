import LudoraKit
import SwiftUI

/// Filter and sort, applied on dismiss rather than per-toggle.
///
/// Batching matters here: every filter change is a network round trip, and
/// a user narrowing by subdomain, then players, then weight would otherwise
/// fire three queries and see two throwaway result sets.
///
/// Grouped into Classification / Gameplay / Experience, the same three
/// headings the web sidebar uses (`frontend/src/pages/GamesList.tsx`). The
/// flat list this replaced put sort, search mode and content filters in one
/// undifferentiated run of sections.
///
/// Search mode is deliberately absent. It picks which endpoint runs, and in
/// semantic and hybrid the backend ignores filters entirely, so a control
/// that invalidates the rest of the sheet had no business living inside it.
/// It sits next to the search field now, which is also where the web keeps
/// it (a dropdown inside the search bar).
struct FiltersView: View {
    @Bindable var browser: GameBrowser
    @Environment(\.dismiss) private var dismiss
    @Environment(\.ludoraClient) private var client

    // Loaded from the API rather than hardcoded: the vocabularies are
    // derived from the ingested data, so a hardcoded list would drift from
    // whatever is actually in the database.
    @State private var subdomains: [CountedTag] = []
    @State private var categories: [String] = []
    @State private var mechanics: [String] = []
    @State private var families: [FamilyGroup] = []

    /// Edited locally so Cancel is real.
    @State private var draft = GameQuery()

    var body: some View {
        NavigationStack {
            Form {
                if browser.searchMode != .lexical && !browser.searchText.isEmpty {
                    inertFiltersNotice
                }
                if draft.activeFilterCount > 0 {
                    activeSummary
                }

                searchGroup
                sortGroup

                // Disabled rather than hidden: a section that vanishes reads
                // as a bug, while a dimmed one that is still legible shows
                // what you would get back by switching mode.
                Group {
                    classificationGroup
                    gameplayGroup
                    experienceGroup
                }
                .disabled(filtersAreInert)
            }
            .scrollContentBackground(.hidden)
            .background(Color.ludoraBackground)
            .tint(.ludoraPrimary)
            .navigationTitle("Filters")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button("Apply") {
                        browser.query = draft
                        dismiss()
                        Task { await browser.load() }
                    }
                    .bold()
                }
                // Dismisses the number pad, which has no return key of its
                // own, so the custom min/max fields would otherwise trap it.
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("Done") { dismissKeyboard() }
                }
            }
            .task {
                draft = browser.query
                await loadVocabularies()
            }
        }
    }

    // MARK: - Notices

    /// Semantic and hybrid go to `/api/search/`, which takes no filters.
    /// The old sheet admitted this in grey caption text under the mode
    /// picker; saying it once, up top, where it changes what the whole sheet
    /// means, is more honest than a footnote.
    private var inertFiltersNotice: some View {
        Section {
            Label {
                Text("\(browser.searchMode.rawValue.capitalized) search ignores filters. Switch to Lexical to combine them with a query.")
                    .font(.footnote)
                    .foregroundStyle(Color.ludoraSecondaryText)
            } icon: {
                Image(systemName: "info.circle.fill")
                    .foregroundStyle(Color.ludoraPrimary)
            }
        }
        .listRowBackground(Color.ludoraSurface.opacity(0.5))
    }

    private var activeSummary: some View {
        Section {
            Button(role: .destructive) {
                draft = GameQuery()
            } label: {
                LabeledContent {
                    Text("Clear all")
                        .font(.subheadline.bold())
                        .foregroundStyle(Color.ludoraPrimary)
                } label: {
                    Text(draft.activeFilterCount == 1
                         ? "1 filter active"
                         : "\(draft.activeFilterCount) filters active")
                        .foregroundStyle(Color.ludoraText)
                }
            }
        }
        .listRowBackground(Color.white)
    }

    // MARK: - Groups

    /// Whether the chosen retrieval mode ignores everything below it.
    ///
    /// Only with a query in the box: with no query the browse endpoint runs
    /// and the filters apply whatever the mode says.
    private var filtersAreInert: Bool {
        browser.searchMode != .lexical && !browser.searchText.isEmpty
    }

    /// Retrieval mode.
    ///
    /// First, above sort and the filters, because it decides whether any of
    /// them apply. It was buried mid-sheet under the heading "Search mode",
    /// with the consequence spelled out in grey caption text below it.
    private var searchGroup: some View {
        Section {
            Picker("Mode", selection: $browser.searchMode) {
                ForEach(SearchMode.allCases, id: \.self) { mode in
                    Text(mode.rawValue.capitalized).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            .listRowBackground(Color.clear)
        } header: {
            GroupHeading("Retrieval")
        } footer: {
            Text(browser.searchMode == .lexical
                 ? "Keyword matching. Combines with every filter below."
                 : "Meaning-based matching. Runs on its own endpoint, which takes no filters.")
                .font(.footnote)
                .foregroundStyle(Color.ludoraSecondaryText)
        }
    }

    private var sortGroup: some View {
        Section {
            Picker("Sort by", selection: $draft.sortBy) {
                ForEach(SortField.allCases, id: \.self) { field in
                    Text(field.rawValue.capitalized).tag(field)
                }
            }
            Picker("Order", selection: $draft.order) {
                Text("Ascending").tag(SortOrder.ascending)
                Text("Descending").tag(SortOrder.descending)
            }
        } header: {
            GroupHeading("Sort")
        }
        .listRowBackground(Color.white)
    }

    private var classificationGroup: some View {
        Section {
            TagRow("Subdomain", options: subdomains.map(\.name), selection: $draft.subdomains)
            TagRow("Category", options: categories, selection: $draft.categories)
            FamilyRow(groups: families, selection: $draft.families)
        } header: {
            GroupHeading("Classification")
        }
        .listRowBackground(Color.white)
    }

    private var gameplayGroup: some View {
        Section {
            VStack(alignment: .leading, spacing: 12) {
                FieldLabel("Players")
                WrapLayout {
                    ForEach(PlayerPreset.all) { preset in
                        FilterChip(preset.label, isSelected: isSelected(preset)) {
                            // Exactly-N and a min/max range are alternative
                            // spellings of one filter, so picking a chip
                            // clears the range, the way the web does.
                            draft.exactPlayers = preset.value
                            draft.minPlayers = nil
                            draft.maxPlayers = nil
                        }
                    }
                }
                CustomRange(
                    "Custom player range",
                    unit: "players",
                    minimum: $draft.minPlayers,
                    maximum: $draft.maxPlayers,
                    onEdit: { draft.exactPlayers = nil }
                )
            }
            .padding(.vertical, 4)

            TagRow("Mechanic", options: mechanics, selection: $draft.mechanics)
        } header: {
            GroupHeading("Gameplay")
        }
        .listRowBackground(Color.white)
    }

    private var experienceGroup: some View {
        Section {
            VStack(alignment: .leading, spacing: 12) {
                FieldLabel("Playtime")
                WrapLayout {
                    ForEach(PlaytimePreset.all) { preset in
                        FilterChip(preset.label, isSelected: isSelected(preset)) {
                            draft.minPlaytime = preset.minimum
                            draft.maxPlaytime = preset.maximum
                        }
                    }
                }
                CustomRange(
                    "Custom playtime",
                    unit: "minutes",
                    minimum: $draft.minPlaytime,
                    maximum: $draft.maxPlaytime,
                    onEdit: {}
                )
            }
            .padding(.vertical, 4)

            VStack(alignment: .leading, spacing: 12) {
                FieldLabel("Complexity (1.0 - 5.0)")
                WrapLayout {
                    ForEach(WeightPreset.all) { preset in
                        FilterChip(preset.label, isSelected: isSelected(preset)) {
                            draft.minWeight = preset.minimum
                            draft.maxWeight = preset.maximum
                        }
                    }
                }
                weightRange
            }
            .padding(.vertical, 4)
        } header: {
            GroupHeading("Experience")
        }
        .listRowBackground(Color.white)
    }

    /// One range, one control.
    ///
    /// This was two independent toggles and two sliders, which let you ask
    /// for a minimum of 4.0 and a maximum of 2.0: a guaranteed empty result
    /// the interface would happily help you build. Two thumbs on one track
    /// cannot express that, because each clamps against the other.
    private var weightRange: some View {
        RangeSlider(
            lower: Binding(
                get: { draft.minWeight ?? 1 },
                set: { draft.minWeight = $0; draft.maxWeight = draft.maxWeight ?? 5 }
            ),
            upper: Binding(
                get: { draft.maxWeight ?? 5 },
                set: { draft.maxWeight = $0; draft.minWeight = draft.minWeight ?? 1 }
            ),
            bounds: 1...5,
            step: 0.1
        )
    }

    // MARK: - Selection

    private func isSelected(_ preset: PlayerPreset) -> Bool {
        draft.exactPlayers == preset.value && draft.minPlayers == nil && draft.maxPlayers == nil
    }

    private func isSelected(_ preset: PlaytimePreset) -> Bool {
        draft.minPlaytime == preset.minimum && draft.maxPlaytime == preset.maximum
    }

    private func isSelected(_ preset: WeightPreset) -> Bool {
        draft.minWeight == preset.minimum && draft.maxWeight == preset.maximum
    }

    private func dismissKeyboard() {
        UIApplication.shared.sendAction(
            #selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil
        )
    }

    private func loadVocabularies() async {
        // Four independent lookups; no reason to serialize them.
        async let subs = try? await client.subdomains()
        async let cats = try? await client.categories()
        async let mechs = try? await client.mechanics()
        async let fams = try? await client.families()
        subdomains = await subs ?? []
        categories = await cats ?? []
        mechanics = await mechs ?? []
        families = await fams ?? []
    }
}

// MARK: - Presets
//
// Values match the web sidebar exactly rather than being re-invented here.
// A game that is "Medium" on one client and "Medium" on the other had
// better mean the same band.

struct PlayerPreset: Identifiable {
    var id: String { label }
    let label: String
    let value: Int?

    static let all = [
        PlayerPreset(label: "Any", value: nil),
        PlayerPreset(label: "1 (Solo)", value: 1),
        PlayerPreset(label: "2", value: 2),
        PlayerPreset(label: "3", value: 3),
        PlayerPreset(label: "4", value: 4),
        PlayerPreset(label: "5", value: 5),
        PlayerPreset(label: "6+", value: 6),
    ]
}

struct PlaytimePreset: Identifiable {
    var id: String { label }
    let label: String
    let minimum: Int?
    let maximum: Int?

    static let all = [
        PlaytimePreset(label: "Any", minimum: nil, maximum: nil),
        PlaytimePreset(label: "< 30 min", minimum: nil, maximum: 30),
        PlaytimePreset(label: "30-60 min", minimum: 30, maximum: 60),
        PlaytimePreset(label: "60-120 min", minimum: 60, maximum: 120),
        PlaytimePreset(label: "120+ min", minimum: 120, maximum: nil),
    ]
}

struct WeightPreset: Identifiable {
    var id: String { label }
    let label: String
    let minimum: Double?
    let maximum: Double?

    static let all = [
        WeightPreset(label: "Any", minimum: nil, maximum: nil),
        WeightPreset(label: "Light (1-2)", minimum: 1.0, maximum: 2.0),
        WeightPreset(label: "Medium (2-3.5)", minimum: 2.0, maximum: 3.5),
        WeightPreset(label: "Heavy (3.5-5)", minimum: 3.5, maximum: 5.0),
    ]
}

// MARK: - Building blocks

/// The web's section heading: small, bold, uppercase, letterspaced.
struct GroupHeading: View {
    let title: String

    init(_ title: String) { self.title = title }

    var body: some View {
        Text(title.uppercased())
            .font(.system(size: 12, weight: .bold))
            .tracking(1.2)
            .foregroundStyle(Color.ludoraSecondaryText)
    }
}

struct FieldLabel: View {
    let title: String

    init(_ title: String) { self.title = title }

    var body: some View {
        Text(title)
            .font(.subheadline.bold())
            .foregroundStyle(Color.ludoraSecondaryText)
    }
}

struct FilterChip: View {
    let label: String
    let isSelected: Bool
    let action: () -> Void

    init(_ label: String, isSelected: Bool, action: @escaping () -> Void) {
        self.label = label
        self.isSelected = isSelected
        self.action = action
    }

    var body: some View {
        Button(action: action) {
            Text(label)
                .font(.subheadline.weight(.bold))
                .foregroundStyle(isSelected ? .white : Color.ludoraSecondaryText)
                .padding(.horizontal, 14)
                .padding(.vertical, 7)
                .background(
                    isSelected ? Color.ludoraPrimary : Color.ludoraNeutral.opacity(0.2),
                    in: .capsule
                )
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(isSelected ? [.isButton, .isSelected] : .isButton)
    }
}

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
            // knob's own area; a gesture added afterwards would cover the
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

/// A multi-select over a long vocabulary. Mechanics alone runs to hundreds
/// of values, so this is a searchable pushed list, not an inline picker.
struct TagRow: View {
    let title: String
    let options: [String]
    @Binding var selection: [String]

    init(_ title: String, options: [String], selection: Binding<[String]>) {
        self.title = title
        self.options = options
        self._selection = selection
    }

    var body: some View {
        NavigationLink {
            TagPicker(title: title, options: options, selection: $selection)
        } label: {
            LabeledContent {
                SelectionSummary(count: selection.count)
            } label: {
                Text(title).foregroundStyle(Color.ludoraText)
            }
        }
    }
}

struct SelectionSummary: View {
    let count: Int

    var body: some View {
        Text(count == 0 ? "Any" : "\(count) selected")
            .foregroundStyle(count == 0 ? Color.ludoraSecondaryText : Color.ludoraPrimary)
            .fontWeight(count == 0 ? .regular : .bold)
    }
}

struct TagPicker: View {
    let title: String
    let options: [String]
    @Binding var selection: [String]
    @State private var search = ""

    private var visible: [String] {
        search.isEmpty
            ? options
            : options.filter { $0.localizedCaseInsensitiveContains(search) }
    }

    var body: some View {
        List(visible, id: \.self) { option in
            SelectableRow(label: option, isSelected: selection.contains(option)) {
                toggle(option, in: &selection)
            }
            .listRowBackground(Color.white)
        }
        .scrollContentBackground(.hidden)
        .background(Color.ludoraBackground)
        .searchable(text: $search)
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
    }
}

/// Families are namespaced ("Animals: Bears"), and some namespaces hold
/// thousands of values, so the groups are a level of their own rather than
/// one flat list. Searching cuts across all of them.
struct FamilyRow: View {
    let groups: [FamilyGroup]
    @Binding var selection: [String]

    var body: some View {
        NavigationLink {
            FamilyPicker(groups: groups, selection: $selection)
        } label: {
            LabeledContent {
                SelectionSummary(count: selection.count)
            } label: {
                Text("Family").foregroundStyle(Color.ludoraText)
            }
        }
    }
}

struct FamilyPicker: View {
    let groups: [FamilyGroup]
    @Binding var selection: [String]
    @State private var search = ""

    private var matches: [FamilyValue] {
        guard !search.isEmpty else { return [] }
        return groups
            .flatMap(\.values)
            .filter { $0.name.localizedCaseInsensitiveContains(search) }
    }

    var body: some View {
        List {
            if search.isEmpty {
                ForEach(groups) { group in
                    NavigationLink {
                        FamilyValueList(
                            title: group.group,
                            values: group.values,
                            selection: $selection
                        )
                    } label: {
                        LabeledContent {
                            SelectionSummary(count: selectedCount(in: group))
                        } label: {
                            Text(group.group).foregroundStyle(Color.ludoraText)
                        }
                    }
                    .listRowBackground(Color.white)
                }
            } else {
                ForEach(matches) { value in
                    SelectableRow(label: value.name, isSelected: selection.contains(value.name)) {
                        toggle(value.name, in: &selection)
                    }
                    .listRowBackground(Color.white)
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(Color.ludoraBackground)
        .searchable(text: $search, prompt: "Search families")
        .navigationTitle("Family")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func selectedCount(in group: FamilyGroup) -> Int {
        group.values.count { selection.contains($0.name) }
    }
}

struct FamilyValueList: View {
    let title: String
    let values: [FamilyValue]
    @Binding var selection: [String]

    var body: some View {
        List(values) { value in
            SelectableRow(label: value.value, isSelected: selection.contains(value.name)) {
                toggle(value.name, in: &selection)
            }
            .listRowBackground(Color.white)
        }
        .scrollContentBackground(.hidden)
        .background(Color.ludoraBackground)
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct SelectableRow: View {
    let label: String
    let isSelected: Bool
    let toggle: () -> Void

    var body: some View {
        Button(action: toggle) {
            HStack {
                Text(label).foregroundStyle(Color.ludoraText)
                Spacer()
                if isSelected {
                    Image(systemName: "checkmark")
                        .foregroundStyle(Color.ludoraPrimary)
                        .fontWeight(.bold)
                }
            }
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(isSelected ? [.isButton, .isSelected] : .isButton)
    }
}

private func toggle(_ value: String, in selection: inout [String]) {
    if let index = selection.firstIndex(of: value) {
        selection.remove(at: index)
    } else {
        selection.append(value)
    }
}

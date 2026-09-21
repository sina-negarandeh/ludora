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
    /// picker. Saying it once, up top, where it changes what the whole sheet
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
                    ForEach(RangePreset.playtime) { preset in
                        FilterChip(preset.label, isSelected: preset.matches(draft.minPlaytime, draft.maxPlaytime)) {
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
                    ForEach(RangePreset.weight) { preset in
                        FilterChip(preset.label, isSelected: preset.matches(draft.minWeight, draft.maxWeight)) {
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



    private func dismissKeyboard() {
        UIApplication.shared.sendAction(
            #selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil
        )
    }

    private func loadVocabularies() async {
        // Four independent lookups. No reason to serialize them.
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

/// A named band over a numeric field, generic in the bound so playtime
/// (whole minutes) and complexity (a decimal weight) share one type instead
/// of two identical ones.
struct RangePreset<Bound: Equatable>: Identifiable {
    var id: String { label }
    let label: String
    let minimum: Bound?
    let maximum: Bound?

    /// Whether a query currently sits exactly on this band.
    func matches(_ lower: Bound?, _ upper: Bound?) -> Bool {
        lower == minimum && upper == maximum
    }
}

extension RangePreset where Bound == Int {
    static var playtime: [RangePreset<Int>] {
        [
            .init(label: "Any", minimum: nil, maximum: nil),
            .init(label: "< 30 min", minimum: nil, maximum: 30),
            .init(label: "30-60 min", minimum: 30, maximum: 60),
            .init(label: "60-120 min", minimum: 60, maximum: 120),
            .init(label: "120+ min", minimum: 120, maximum: nil),
        ]
    }
}

extension RangePreset where Bound == Double {
    static var weight: [RangePreset<Double>] {
        [
            .init(label: "Any", minimum: nil, maximum: nil),
            .init(label: "Light (1-2)", minimum: 1.0, maximum: 2.0),
            .init(label: "Medium (2-3.5)", minimum: 2.0, maximum: 3.5),
            .init(label: "Heavy (3.5-5)", minimum: 3.5, maximum: 5.0),
        ]
    }
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

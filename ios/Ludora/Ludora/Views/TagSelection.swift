import LudoraKit
import SwiftUI

// Choosing values from a vocabulary: the summary rows on the sheet,
// the pushed pickers behind them, and the two-level family browser.

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

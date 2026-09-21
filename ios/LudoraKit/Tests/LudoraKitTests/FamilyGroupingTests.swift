import Foundation
import Testing

@testable import LudoraKit

@Suite("Family grouping")
struct FamilyGroupingTests {
    @Test("splits a family on its namespace")
    func splitsNamespace() {
        let split = FamilyGrouping.split("Region: Great Britain")
        #expect(split.namespace == "Region")
        #expect(split.value == "Great Britain")
    }

    /// The case that makes a naive `split(separator: ":")` wrong: the value
    /// carries separators of its own.
    @Test("splits on the first separator only")
    func splitsOnFirstSeparatorOnly() {
        let split = FamilyGrouping.split("Components: Maps: Continental scale")
        #expect(split.namespace == "Components")
        #expect(split.value == "Maps: Continental scale")
    }

    @Test("keeps an unqualified family instead of dropping it")
    func keepsUnqualifiedFamily() {
        let split = FamilyGrouping.split("Solitaire Games")
        #expect(split.namespace == FamilyGrouping.fallbackName)
        #expect(split.value == "Solitaire Games")
    }

    /// A bare colon is not the separator: "Brass: Birmingham" is one name,
    /// not a namespace and a value.
    @Test("requires the space after the colon")
    func requiresSpaceAfterColon() {
        #expect(FamilyGrouping.split("Game:Brass").namespace == FamilyGrouping.fallbackName)
    }

    @Test("collects values under one namespace")
    func collectsValues() {
        let grouped = FamilyGrouping.grouping([
            "Region: Great Britain",
            "Category: Economic",
            "Region: Europe",
        ])
        #expect(grouped.count == 2)
        #expect(grouped.map(\.name) == ["Category", "Region"])
        #expect(grouped[1].values == ["Great Britain", "Europe"])
    }

    @Test("sorts namespaces but preserves value order")
    func sortsNamespacesOnly() {
        let grouped = FamilyGrouping.grouping([
            "Zebra: last",
            "Alpha: second",
            "Alpha: first",
        ])
        #expect(grouped.map(\.name) == ["Alpha", "Zebra"])
        // Not ["first", "second"]: the API's order is the one that matters.
        #expect(grouped[0].values == ["second", "first"])
    }

    @Test("groups nothing into nothing")
    func handlesEmpty() {
        #expect(FamilyGrouping.grouping([]).isEmpty)
    }

    /// The real strings, from the captured detail fixture. Hand-written
    /// cases above cover the parsing. This checks the grouping survives
    /// whatever the catalog actually contains.
    @Test("groups the fixture's families")
    func groupsFixtureFamilies() throws {
        let url = Bundle.module.url(
            forResource: "game_detail", withExtension: "json", subdirectory: "Fixtures"
        )
        let game = try JSONDecoder().decode(
            Game.self, from: Data(contentsOf: #require(url))
        )
        let grouped = FamilyGrouping.grouping(game.families)

        try #require(!game.families.isEmpty, "fixture has no families to group")

        #expect(grouped.count <= game.families.count)
        #expect(grouped.map(\.values).reduce(0) { $0 + $1.count } == game.families.count)
        // Sorted, and no namespace repeated.
        #expect(grouped.map(\.name) == grouped.map(\.name).sorted())
        #expect(Set(grouped.map(\.name)).count == grouped.count)
    }
}

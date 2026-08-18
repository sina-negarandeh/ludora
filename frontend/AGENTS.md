# frontend/AGENTS.md

Scope: `frontend/`. Read [../AGENTS.md](../AGENTS.md) first.

## Stack

React 19, TypeScript ~6.0 (strict), Vite 8, TanStack React Query 5, React Router 7, Tailwind CSS 3, Axios, DOMPurify. Package manager: npm.

## Commands

```bash
npm install
npm run dev     # Vite dev server, port 5173 — no backend proxy, calls VITE_API_URL directly
npm run build    # tsc -b && vite build — this is the type-check; must pass with zero errors
npm run lint      # oxlint, not ESLint — there is no ESLint config, don't add one
```

No test framework is installed (no Vitest, Jest, React Testing Library, or Playwright). `npm run build` is the closest thing to an automated check on this side — necessary, not sufficient. If you add a framework, use Vitest + React Testing Library — it matches the existing Vite toolchain.

## Code style

`tsconfig.app.json` has `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`, and `erasableSyntaxOnly` on. Do not disable any of them to make a build pass — fix the underlying issue. `oxlint` enforces `react/rules-of-hooks`.

## Existing conventions

- API calls go through `src/api/games.ts`'s shared `apiClient` (Axios, reads `VITE_API_URL`). One call site (`GameDetail.tsx`'s aspects fetch) bypasses it with an inline `axios` call — that's a known inconsistency, not a pattern to extend.
- Paginated/filtered views use TanStack Query's `keepPreviousData` to avoid layout flicker during refetch (`GamesList.tsx`, `GameReviews` in `GameDetail.tsx`). Use it for any new paginated view.
- Any HTML from the backend (game descriptions) goes through `DOMPurify.sanitize()` before `dangerouslySetInnerHTML` — see the one existing usage in `GameDetail.tsx`. Never use `dangerouslySetInnerHTML` without it.
- `GamesList.tsx` (~820 lines) and `GameDetail.tsx` (~1,380 lines) hold most of their page's logic inline by design. Check these two files before assuming a feature lives in `src/components/`, which holds only pieces shared across pages (`GameCard`, `AssistantDrawer`, `AssistantMessageBubble`, `CompactGameRow`, `SearchableCombobox`, `MultiSelectDropdown`, `GroupedMultiSelect`).

## Environment

`VITE_API_URL` (default `http://localhost:8000`) is the only env var this side reads. There is no dev-server proxy.

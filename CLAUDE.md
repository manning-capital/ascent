# Ascent

## Documentation

See `llms.txt` for LLM-optimized PrimeNG component documentation used by the Angular UI (`src/ascent/ui/`).

## UI Stack

The Angular UI at [src/ascent/ui/](src/ascent/ui/) uses a deliberate three-library split. Stay within these lanes — don't reach for a different library just because it's familiar.

- **PrimeNG** — the default component library. Use it for buttons, inputs, dialogs, menus, selects, toasts, layout primitives, forms, and anything else it covers. If PrimeNG has a component for the job, use it. See `llms.txt` for the component reference.
- **ag-grid** — tables *only*. Whenever data is presented as a row/column grid (sortable, filterable, paginated, virtualized, editable cells, etc.), use ag-grid — not PrimeNG's `p-table`. PrimeNG tables are not to be added to this codebase.
- **D3** — custom visualizations only. Charts, diagrams, or interactive graphics that don't map to a PrimeNG component go to D3. Don't pull in a second charting library (Chart.js, ECharts, Highcharts, etc.) — if it's not PrimeNG and not a table, it's D3.

Picking the right one:
1. Is it a table of rows and columns? → **ag-grid**
2. Does PrimeNG have a component for it? → **PrimeNG**
3. Otherwise → **D3**

If a task seems to require a component outside these three, stop and ask before adding a new dependency.

### Layout and Theming

- **Tailwind CSS** — for layout and arrangement only. Spacing, flex/grid, sizing, positioning, responsive breakpoints, and visibility utilities. Use Tailwind classes directly in templates; don't reinvent these in component SCSS.
- **PrimeNG theme** — the single source of truth for all *theming*: colors, typography, surfaces, borders, radii, shadows, focus rings, states. Reference PrimeNG theme tokens (CSS variables / design tokens) — never hardcode hex values, custom font stacks, or bespoke color palettes in components or Tailwind classes.
  - Do not use Tailwind color utilities (`bg-blue-500`, `text-gray-700`, etc.) for component theming. Use PrimeNG tokens instead.
  - ag-grid and D3 visualizations must also pull colors and typography from PrimeNG theme tokens so the whole UI stays in sync when the theme changes.
  - If a token you need doesn't exist, extend the PrimeNG theme — don't inline a one-off value.

Rule of thumb: **Tailwind arranges boxes; PrimeNG paints them.**

## Code Design

Code in this repo should follow Robert C. Martin's (Uncle Bob) *Clean Code* and object-oriented principles. Factor these into every change — not just new code, but edits and refactors too.

### Clean Code (Uncle Bob)

- **Meaningful names**: names should reveal intent. No abbreviations, no single-letter vars outside tight loops, no disinformation. A name should answer why it exists, what it does, how it's used.
- **Small functions**: functions do one thing, at one level of abstraction, with few arguments (ideally 0–2). Extract until you cannot extract further.
- **No comments as deodorant**: prefer expressive code over comments. Only write a comment when the *why* cannot be expressed in code (invariants, non-obvious constraints, legal notes).
- **Formatting matters**: related code stays vertically close; conceptually distant code stays apart.
- **Error handling is one thing**: don't mix happy-path logic with error handling. Prefer exceptions over return codes; never return or pass `null` where an empty collection or explicit type will do.
- **Boy Scout Rule**: leave the code cleaner than you found it — within the scope of the task.
- **DRY**: duplication is the root of most bad code. But avoid premature abstraction — three similar lines are fine; a wrong abstraction is expensive.

### Object-Oriented Principles (SOLID)

- **S — Single Responsibility**: a class has one reason to change. If it serves two actors, split it.
- **O — Open/Closed**: open for extension, closed for modification. Add new behavior via new types, not by editing stable ones.
- **L — Liskov Substitution**: subtypes must be usable anywhere their base type is, without surprising the caller. No strengthened preconditions, no weakened postconditions.
- **I — Interface Segregation**: many small, role-specific interfaces beat one fat one. Clients shouldn't depend on methods they don't use.
- **D — Dependency Inversion**: depend on abstractions, not concretions. High-level policy shouldn't import low-level detail — both should depend on an interface the policy owns.

### Additional OO guidance

- **Tell, don't ask**: push behavior to the data, not the other way around. Methods on objects, not procedures that inspect them.
- **Law of Demeter**: a method should only talk to its own fields, its parameters, objects it creates, and direct components. No `a.getB().getC().doSomething()` chains across unrelated boundaries.
- **Composition over inheritance**: prefer composing behavior from small objects over deep class hierarchies.
- **Encapsulation**: hide state behind behavior. Public getters/setters on every field defeat the purpose of having a class.

### When these conflict with project guidance

The project-level guidance in this CLAUDE.md and in conversation takes precedence (e.g. "only change what's asked", "no premature abstraction"). Clean Code is a lens for *how* to write the code that's in scope — not a license to expand scope into cleanup passes the user didn't request.

## Python Formatting and Linting

Run `ruff format` and `ruff check` regularly while working on Python code — typically between phases of a larger change or between bullet points in a multi-step task. Don't batch all formatting to the end; catch issues early so each phase lands clean. Fix lint findings as they come up rather than letting them accumulate.

# Design skill audit

## Skills requested and what was found

I inspected the installed skills in `~/.claude/skills`, the synced plugin skills under `~/.claude/plugins/synced`, and the skill list exposed to this session.

| Requested skill | Status |
|---|---|
| UI UX Pro Max | **Not installed.** No skill, plugin or file by that name. |
| Taste Skill | **Not installed.** |
| Hallmark | **Not installed.** |
| Impeccable | **Not installed.** |
| Better-UI | **Not installed.** |

None of the five could be read or used. I did not search a marketplace and install them: adding third-party skills is a configuration change the user should make deliberately.

## Skills available and read

| Skill | Read | Used | Why |
|---|---|---|---|
| `frontend-design:frontend-design` (plugin) | Yes, in full | **Yes, primary** | Design direction, typography, layout, restraint, copy, self-critique |
| `flutter-premium-ui` (user) | Yes | Principles only | 8pt grid, 200–350 ms motion, light-first. Its Flutter APIs do not apply |
| `nextjs-saas-generator` (user) | Yes | No | SaaS concerns (RBAC, server actions, feature flags) do not fit a static reading app |
| `artifact-design`, `dataviz` | Listed | No | For hosted artifacts and charts; this is a local application |
| `code-review`, `architecture-review` | Listed | Not invoked | Self-review done in the validation passes instead |

The user's global `CLAUDE.md` also acts as a design brief: premium light theme, generous whitespace, minimalism, smooth animations, accessible typography; plus engineering rules (feature-first, no god components, error/loading/empty states, analytics, logging, tests).

## Principles taken from `frontend-design`, and how they shaped the product

| Principle | Applied as |
|---|---|
| Ground the design in the subject's own materials | Drafting vellum, blueprint grids, lanes and wires of an architecture diagram; the hero is a working retrieval pipeline, the most characteristic thing in this subject |
| Spend boldness in one place | One memorable element: the live fusion bench in the hero (and its sibling, the architecture map). Everything else is quiet |
| Avoid the listed tells: cream + serif + terracotta, acid accent on black, SaaS card kits, ALL-CAPS eyebrows, `·` meta strings, `→` in buttons | Cool vellum paper instead of cream; one sans family; no all-caps labels; sentence case; no arrows in button text; middle dots removed from meta lines; radii vary with size (3/6/10/14 px) |
| Structure encodes information | Numbers appear only where content is a sequence (chapters, steps, ADR ids). Colour is semantic: teal = lexical leg and executed evidence, blue = dense leg and sources, amber = assumptions and in-progress |
| One orchestrated motion moment | The bench's wires draw in when a query changes; elsewhere motion only answers an action (sheet, palette, dialog, reveal once per band) |
| Line length under 80 characters | Reading measure is 70ch at 17.5 px with 1.72 line height |
| Copy in the user's words, active voice, errors that direct | "Start with chapter 1", "Reset to script", "Nothing matches … Remove a word", "No captured run yet. Run npm run exercises…" |
| Critique with screenshots | Two browser passes at 1440, 1280, 1024, 768, 390 and 360 px; see `VALIDATION_REPORT.md` |

## Conflicts resolved

- `flutter-premium-ui` asks for Inter, large radii and soft elevation everywhere. `frontend-design` warns that this is the generic default. Resolution: Geist (from the brief's list) with Geist Mono for code, small radii that scale with element size, elevation only on floating things (bench, dialogs, popovers).
- The brief's palette included Warm Paper `#F7F5F0`, which sits next to the "cream" tell. Resolution: shift to a cooler drafting vellum `#F4F4EF`, keep the rest of the brief's palette, and darken teal and blue for text contrast (see `DESIGN_SYSTEM.md`).

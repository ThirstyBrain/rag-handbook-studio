# Design system: Midnight Blueprint

> **Revision 2 (2026-11-09), reference-driven.** The identity was rebuilt from the supplied reference poster: warm ivory reading surfaces, midnight-navy ink and technical canvases, architectural teal and electric cyan signals, soft azure illumination. Tokens live in `src/design/tokens.css`; `src/design/theme.css` carries the identity into every internal page. The sections below describe the token *roles*, which are unchanged; the values are now:
>
> | Token | Value | Use | Contrast on ivory |
> |---|---|---|---|
> | `--ink` | #06182C Deep Midnight Navy | text, primary buttons | 16.4 |
> | `--navy` / `--navy-3` | #0B223D / #031020 | dark canvases (hero waves, architecture map, footer, exercise overview) | — |
> | `--paper` | #F8F5EF Warm Ivory | page | — |
> | `--teal` (text) / `--teal-bright` (fill) | #007577 / #00A6A6 | accent, lexical leg, executed evidence | 5.06 / fill only (2.75) |
> | `--cyan` | #31D4E5 Electric Cyan | glow, active wires, accents on navy (9.9:1 on navy) | fill only |
> | `--blue` (text) / `--blue-bright` (fill) | #2A64A8 / #6FAFE5 Soft Azure | semantic leg, sources, illumination | 5.53 / fill only |
> | `--muted` / `--faint` | #556479 / #5F6E84 | secondary / tertiary text | 5.54 / 4.8 |
> | `--grad-hero`, `--grad-deep`, `--glow-cyan` | gradients | hero and page-head bands, dark bands, focus glow | — |
>
> Radii: 4 / 8 / 12 / 18 px and pills (999 px) for nav items, chips, buttons and search. Header height 76 px (64 px on phones). Every internal page head has an uppercase teal eyebrow and a full-bleed ivory-to-azure blueprint band; chapters show teal section indices; code and terminal surfaces are #06182C.
>
> The original Drafting Vellum notes follow for history.

# (Revision 1) Drafting Vellum

A light, cool-paper engineering publication. The page is the drafting sheet; structure is drawn with hairlines; colour is reserved for meaning. Tokens live in `src/design/tokens.css`; every component reads them through CSS custom properties.

## Positioning

A premium interactive handbook for architects and engineers building production RAG systems. *Architecture is not just something to read; it is something to understand, explore and reason about.* So the boldest thing on the site is a working piece of architecture (the hybrid retrieval bench in the hero), and the rest stays quiet and readable.

## Colour

| Token | Value | Role | Contrast on paper / white |
|---|---|---|---|
| `--ink` | `#111827` | Text, structure rules, primary buttons | 16.1 / 17.7 |
| `--ink-2` | `#2B3445` | Reading text | 11.3 / 12.5 |
| `--navy` | `#17243A` | Footer, explore band, selected map node | — |
| `--paper` | `#F4F4EF` | Page background (cool drafting vellum) | — |
| `--surface` | `#FFFFFF` | Panels, tables, bench | — |
| `--muted` | `#556072` | Secondary text | 5.76 / 6.36 |
| `--faint` | `#666F7F` | Tertiary text: numbers, meta | 4.59 / 5.07 |
| `--rule`, `--rule-strong` | `#DCDDD4`, `#C3C5BA` | Hairlines, borders (non-text) | — |
| `--teal` / `--teal-bright` / `--teal-wash` | `#0B7A70` / `#20B8A9` / `#E2F2EF` | **Lexical leg, executed evidence, success** | text 4.72 / 5.21 |
| `--blue` / `--blue-bright` / `--blue-wash` | `#3A5AA3` / `#6B8FD6` / `#E7EDF8` | **Dense leg, cited sources, indexing path** | text 6.00 / 6.62 |
| `--amber` / `--amber-bright` / `--amber-wash` | `#8D5A00` / `#D9A03A` / `#F8EFDB` | **Assumptions, illustrative, in progress, ADR ids** | text 5.29 / 5.84 |
| `--red` | `#A03636` | Vendor-reported evidence, errors | 6.19 / 6.83 |
| `--code-bg` / `--code-fg` / `--code-dim` | `#142033` / `#DDE4EE` / `#8494AB` | Code and terminal surface | fg 12.8, dim 5.3 |

Refinements from the brief's starting palette, with reasons:

- Warm Paper `#F7F5F0` → `#F4F4EF`: cooler, reads as drafting film rather than the generic cream look.
- Architectural Teal `#20B8A9` is 2.47:1 on white, so it is used only for fills, strokes and dots; text uses `#0B7A70`.
- Muted Slate `#64748B` is 4.31:1 on paper (below AA for body text); text uses `#556072`.
- Subtle Blue `#6B8FD6` likewise kept for fills; text uses `#3A5AA3`.

Colour is never decoration. The same mapping holds everywhere: the bench wires, the lab tables, the architecture map lanes, the evidence bar and the evidence marks in the prose.

## Typography

- **Geist Variable** for everything readable; **Geist Mono Variable** for code, terminal output, ADR and source ids. Self-hosted through `@fontsource-variable`, so there is no third-party font request.
- Scale: major third (1.25) anchored at 16 px for UI and 17.5 px for reading. Tokens `--fs-2xs` … `--fs-3xl`, display `clamp(2.6rem, 1.4rem + 4.2vw, 4.6rem)`.
- Reading: 70ch measure, 1.72 line height, `text-wrap: pretty`; headings `text-wrap: balance`, tracking −0.02 to −0.045 em as size grows.
- Numbers: `tabular-nums` wherever they line up (ranks, scores, counts, section numbers).
- No all-caps labels, no eyebrows above headings, sentence case throughout.

## Space, layout and shape

- 4 px base: `--s-1` (4) … `--s-10` (128).
- Page max 1320 px; gutter `clamp(16px, 3.2vw, 40px)`.
- Recurring structural device: `.band-head`, a heading and its explanation above a 1 px ink rule.
- Reader: 232 px chapters | article (70ch) | 236 px outline at ≥1280; outline only at 1024–1279; single column with a sticky section bar and bottom sheet below 1024.
- Radii scale with the object: 3 px (marks, kbd), 6 px (buttons, fields), 10 px (code, diagrams), 14 px (bench, dialogs). Elevation only on floating things.

## Components

| Component | File | Notes |
|---|---|---|
| Buttons, chips, fields, status dots | `design/components.css` | `.btn--primary` ink, `.btn--quiet` outlined; status dot colours follow the evidence mapping |
| Prose | `design/prose.css` | Headings with hover anchors, tables in their own scroll container, callouts, evidence marks with a focus mode |
| Code | `design/code.css` | Shared dark surface; highlight.js tokens tuned to ≥4.5:1 |
| Exercise panel | `features/exercises/` | Tabs (output, variants, source, helpers), split layout on wide screens, classified terminal lines, staleness check |
| Fusion diagram | `features/playground/FusionDiagram.tsx` | Fixed-row geometry so wires are computed from real rank movements |
| Architecture map | `features/architecture/ArchitectureMap.tsx` | SVG blueprint, roving keyboard focus, list fallback below 760 px |
| Search palette | `features/search/` | Native `<dialog>`, combobox/listbox semantics, filters, highlighted snippets |
| Dialog, States | `shared/ui/` | Native `<dialog>`; loading, empty and error states with directions |

## Motion

- Durations: `--t-fast` 140 ms, `--t-med` 240 ms, `--t-slow` 420 ms; easing `cubic-bezier(.22,1,.36,1)`.
- The one orchestrated moment: fusion wires draw in (640 ms) and rows settle when the query changes.
- Route changes use the View Transitions API (160 ms out, 280 ms in with a 6 px rise) when available.
- Bands reveal once on scroll; the evidence bars grow once.
- Everything else answers an action: palette, sheets, dialogs, popovers, hover on links and rows.
- `prefers-reduced-motion: reduce` zeroes the duration tokens and disables view transitions and wire drawing.

## Accessibility

- AA text contrast on all text tokens (table above).
- Visible focus ring (`--focus`) on every interactive element; skip link; landmark structure (`header`, `nav`, `main`, `footer`, `aside`).
- Keyboard: Ctrl/⌘ K or `/` opens search; arrows and Enter in results; `[` and `]` move between chapters; arrow keys move across tabs and architecture stages; Escape closes sheets, popovers and dialogs.
- Diagrams get `role="img"` with their caption as the label; the fusion diagram has a text equivalent.
- Touch targets at least 40 px on mobile controls.

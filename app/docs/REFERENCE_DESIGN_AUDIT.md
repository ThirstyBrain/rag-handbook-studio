# Reference design audit

Both sites were opened in the built-in browser on 2026-11-08 at a 1024 px viewport. I took screenshots, scrolled the pages, opened a tutorial article, and read computed styles with JavaScript. Observations are limited to what that session showed; I did not test their mobile layouts or keyboard flows in depth.

## 1. DataCamp — AI tutorials (`datacamp.com/tutorial/category/ai`)

### Observed

- Header: dark navy bar with logo, Category menu, language, Log in, Get Started; a promotional banner above it during the visit.
- Category hero: a saturated purple panel with a vertical "CATEGORY" label, H1 "AI Tutorials" (Studio Feixen Sans, 40 px / 700, white), and a dense cloud of all-caps technology tags (AI AGENTS, AIRFLOW, AWS …).
- Listing: "Featured" then "All Posts" sections, three-column grids of cards with a green category pill, a bold title, a two-line summary, and author/date. About 140 tutorial links on the page.
- Article page: left table of contents, H2s every few screens, body copy at 14 px with 21 px line height and a measured paragraph width of about 350 px at this viewport, code in JetBrains Mono on a light lavender background `#EFEFF5`.
- Body colour `#05192D` on white; Studio Feixen Sans throughout.

### What works

- A table of contents on long tutorials.
- Strong scannability on the index: every card carries a category pill.
- Distinct monospace face and tinted background for code.

### Useful for us

- Every long chapter needs an outline; ours gets scroll-spy and nests H3s under the active H2.
- Category signalling, but expressed as structure (part, chapter number, evidence colour) rather than pills on cards.

### Not to copy

- Brand: purple hero, green pills, the font, the promo banner.
- Three-column card grids for everything: the brief explicitly rejects it, and it hides sequence.
- Small reading type (14 px) for long technical prose.
- All-caps tag clouds.

### Opportunity

DataCamp's index is a feed. A handbook is a sequence with prerequisites, so our contents page is an architectural index: parts as stages, chapters as numbered rows with a one-sentence problem statement taken from the chapter, planned chapters shown honestly, and a progress spine across all 33.

## 2. Google AI — Learn AI skills (`ai.google/learn-ai-skills/`)

### Observed

- Dark theme: background `#121317`, text `#F8F9FC`, Google Sans Flex at 17.5 px body, H1 30 px / 500.
- Centred hero: small "AI SKILLS" eyebrow, "Learn essential AI skills", a paragraph, then a pill tab bar ("Learn the basics", "Advance your skills", "Transform your business", …) that scrolls horizontally.
- Course sections: a heading with description on the right, then horizontally scrolling cards with photography, title, and metadata chips ("No charge", "Beginner", certificate). Carousel arrows.
- A promotional band for a professional certificate, then a testimonial quote.

### What works

- Learning progression is explicit: basics → advance → transform.
- Each course states level and cost up front, so a learner can self-select.
- Generous spacing and a calm hierarchy.

### Useful for us

- Make progression explicit. We use the handbook's own parts (Fundamentals → Retrieval and Architecture → Advanced Techniques → Implementation) as the reading path, with reading time per chapter and part.
- State what a page offers before the reader commits: reading time, sections, diagrams and runnable exercises in every chapter header.

### Not to copy

- Dark marketing aesthetic, photography of people, carousels (they hide content and are poor for keyboard users), certificate promotion, centred hero.
- Eyebrow-over-heading pattern.

### Opportunity

Google's page sells courses; it does not let you touch the subject. Our hero runs the subject: a real hybrid retrieval pipeline on the handbook's own toy corpus, with the honest caveat in its caption.

## 3. Design patterns adapted

| Pattern | Source | Our version |
|---|---|---|
| Article TOC | DataCamp | Sticky outline with scroll-spy, nested H3s for the current H2, reading percentage, and an evidence highlighter |
| Explicit progression | Google | Reading path built from the handbook's parts, with reading time; progress spine on Contents |
| Level and effort metadata | Google | Chapter facts row: reading time, sections, diagrams, runnable exercises |
| Distinct code styling | DataCamp | Dark navy code surface shared by code blocks and terminal output, Geist Mono, copy button, language label |

## 4. Where we go further

- Evidence is a first-class UI element: every `[S#]` opens its citation, every chapter shows its evidence mix, and readers can highlight one kind of claim.
- Executed claims link to the script and its real captured output, shown side by side.
- Architecture is explorable: a blueprint of both paths whose stages open the handbook's own Mermaid diagrams, chapters, ADRs and terms.
- Decisions are navigable by their reasoning arc (context → options → decision → trade-offs → consequences → reversal).

# Industry-panel reviews

This directory contains strategic-input artifacts: critiques and
synthesis documents from a panel of **AI personas role-playing
greeting-card-industry experts**, used to evaluate the project's
direction and specific feature proposals.

> **Important caveat:** these are AI-persona simulations, not real
> industry experts. They cannot replace actual industry feedback (a
> real prepress manager has never touched a real PDF from this
> project). They are useful because they force honest critique from
> angles a software-only review would miss — bleed, color
> management, sentiment voice, retail merchandising, IP risk, the
> non-engineer user experience.

## What's here

```
docs/industry-review/
├── README.md                          (this file)
├── consensus-general.md               (Synthesis: panel review #1 — overall project)
├── consensus-ai-feature.md            (Synthesis: panel review #2 — proposed AI imagery feature)
├── openai-image-api-snapshot.md       (API facts as of 2026-05; for ai-feature context)
└── critiques/
    ├── general-prepress.md            (Round 1 — overall project critique, per persona)
    ├── general-designer.md
    ├── general-copywriter.md
    ├── general-buyer.md
    ├── general-diy-crafter.md
    ├── general-pod-vetter.md
    ├── ai-prepress.md                 (Round 2 — should we add AI image generation?)
    ├── ai-designer.md
    ├── ai-copywriter.md
    ├── ai-buyer.md
    ├── ai-diy-crafter.md
    └── ai-pod-vetter.md
```

## The panel's six personas

1. **Prepress / Print Production Manager** — production printability,
   bleed, CMYK, ICC, embedded fonts, fold/score.
2. **Greeting Card Designer / Art Director** — typography, color,
   composition, illustration quality, brand identity.
3. **Greeting Card Copywriter** — sentiment voice, register,
   image-text relationship, cultural sensitivity.
4. **Stationery Buyer / Retail Merchandiser** — SKU coverage,
   occasion mix, market positioning, demographic fit.
5. **DIY Crafter ("Sandy")** — non-programmer Etsy stationer.
   Stress-tests UX claims with a real audience persona.
6. **Print-on-Demand Service Vetter** — file specs for MOO,
   Vistaprint, Catprint, Printful etc.; export workflow.

A seventh agent (a synthesis moderator) reads all six critiques per
round and produces the consensus document.

## What the panel recommended (TL;DR)

### Round 1 — overall project (`consensus-general.md`)

> *"The architecture is genuinely above-average and the artifact is
> genuinely embarrassing — spend the next quarter on taste
> (illustrator + sentiment library + curated fonts + bleed) and one
> POD target end-to-end (`--export-for moo-a6`), not on more
> features, more refactors, or more SKUs at the current quality bar."*

**Five jointly-endorsed leapfrog moves**, ranked:
1. `--export-for` POD targeting (ship MOO-A6 end-to-end first)
2. Curated taste layer — illustrator commission + sentiment library + 6-8 curated fonts
3. AI-native authoring against the curated asset library
4. Cards-as-code identity — GitHub Action, CI-rendered, blank-inside, multi-line copy
5. Template microsite — auto-generated single-page form per template

**Defects fixed since the review:** all 9 (PRs #16-#18). See
`consensus-general.md` sec. "Defects (not critiques) — fix these
regardless of strategy" for the original list.

**Audience:** stay Tyler-first (engineer audience). Sandy is
well-served by Canva/Cricut/Shutterfly; competing there is a
multi-year project. Add a narrow microsite escape hatch for Sandy
without pretending to be Canva.

### Round 2 — proposed OpenAI image generation feature (`consensus-ai-feature.md`)

> *"Don't ship this now — ship `--export-for moo-a6` and the curated
> taste layer first; then in Q1 2027 ship AI as an authoring-time,
> image-reference-mode-default, POD-aware, provenance-tagged,
> category-gated `ai-asset generate` subcommand that bakes assets to
> disk and never appears in the render path."*

**The strongest cross-cutting agreement (5 of 6 critics):**
authoring-time bake-to-disk, never render-time API call. The render
pipeline must never call OpenAI. Generated assets are PNG files +
sidecar provenance YAML committed to the repo.

**Sequencing relative to the round-1 leapfrogs:**
- Q3 2026 → Leapfrog 1 (`--export-for moo-a6`)
- Q4 2026 → Leapfrog 2 (curated taste layer + occasion taxonomy
  expansion incl. gated categories)
- Q1 2027 → AI generation in its full recommended shape, as a
  *consumer* of both prior leapfrogs

Bringing AI forward of these breaks the prerequisites the AI
feature itself depends on (the category gates need the expanded
taxonomy; the POD-aware sizing needs the export targets; the style
anchoring needs the curated assets).

**Hard rails (default-refuse, override requires `--i-know-what-im-doing`):**
sympathy / bereavement / condolence / miscarriage / pet-loss /
funeral / serious-get-well / divorce-support / religious holiday
cards with iconography / photo-card slots / cards with recognizable
likenesses of real people.

## How to use these documents

If you're evaluating a new feature, a new template, or a new
strategic direction:

1. **Read `consensus-general.md`** for the overall strategic
   backdrop and the panel's audience recommendation.
2. If the new work touches AI imagery, **also read
   `consensus-ai-feature.md`** for the panel's verdict on that
   specific proposal.
3. **Drill into the individual critiques** in `critiques/` when you
   need a specific persona's depth — e.g., the Designer's full
   typography critique, or the POD vetter's per-service spec table.
4. Treat these as **input to your decision, not the decision**. The
   personas are simulations; the maintainer makes the call.

## How these were generated

Each persona was run as an independent Claude agent with a
role-specific prompt and read access to the repo. The agent produced
its critique in isolation. The synthesis moderator was a seventh
agent that read all six critiques and identified cross-cutting
agreements + tensions. None of these agents communicated with each
other in real time; the "panel" is structural, not interactive.

If you want to re-run a panel review on a new feature proposal, the
prompts used are reproducible — ask Claude Code to "spin up the
industry panel to evaluate [new proposal]" and it'll know what to
do.

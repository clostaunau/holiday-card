# Sentiment library

Hand-curated greeting copy organized by **occasion → voice → role**.
Loaded by `holiday_card.core.sentiments` and surfaced via the CLI's
`--voice` flag.

## Layout

```
sentiments/
  {occasion}/{voice}/{role}.yaml
```

* **occasion** — matches `OccasionType`. Celebratory: `christmas`,
  `birthday`, `hanukkah`, `mothers_day`, `generic`. Sympathy-class:
  `sympathy`, `condolence`, `miscarriage`, `pet_loss` (each ships a
  curated subset of voices; see "Voice gating" below).
* **voice** — one of:
  - `warm` — heartfelt, family-first, sincere
  - `witty` — playful, light, self-aware
  - `spare` — minimal, terse, four-words-or-less
  - `devotional` — religious / scriptural register
  - `irreverent` — anti-saccharine, dry, irreverent
* **role** — one of `cover` (front-panel greeting) or `inside`
  (interior message)

## File schema

```yaml
voice: warm           # must match the directory name
occasion: christmas   # must match the directory name
role: cover           # cover | inside
sentiments:
  - "Merry Christmas"
  - "Wishing you the warmest of holidays"
  - "Christmas wishes from our home to yours"
```

`sentiments` is a non-empty list of strings. The CLI picks one (random
by default; reproducible with `--seed`).

## Voice gating (sympathy-class occasions)

The sympathy-class occasions deliberately ship a curated subset of
voices rather than the full 5×2 grid. The "absent rather than wrong"
principle: a bad sympathy card is worse than no sympathy card.

| Occasion      | Voices shipped               |
|---------------|------------------------------|
| `sympathy`    | warm, spare, devotional      |
| `condolence`  | warm, spare, devotional      |
| `miscarriage` | warm, spare                  |
| `pet_loss`    | warm, spare                  |

Witty and irreverent are always inappropriate for grief contexts and
are not shipped for any sympathy-class occasion. Devotional is
omitted for `miscarriage` and `pet_loss` because religious framing
of those losses is delicate enough that absence beats getting it
wrong. Asking the CLI for an un-shipped combination raises
`SentimentNotFoundError` — the fail-loud convention.

## v0 content disclaimer

The lines shipped here are an engineering-grade starter set, not
copywriter-grade. They prove the mechanism end-to-end and give Tyler
a working knob to turn. Hand-curated copy by an actual copywriter is
on the roadmap (industry-panel review, Agreement 1 / Leapfrog 2,
"copy subset"). Pull requests with better lines welcome.

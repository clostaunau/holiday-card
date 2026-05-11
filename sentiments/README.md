# Sentiment library

Hand-curated greeting copy organized by **occasion → voice → role**.
Loaded by `holiday_card.core.sentiments` and surfaced via the CLI's
`--voice` flag.

## Layout

```
sentiments/
  {occasion}/{voice}/{role}.yaml
```

* **occasion** — matches `OccasionType` (`christmas`, `birthday`,
  `hanukkah`, `mothers_day`, `generic`)
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

## v0 content disclaimer

The lines shipped here are an engineering-grade starter set, not
copywriter-grade. They prove the mechanism end-to-end and give Tyler
a working knob to turn. Hand-curated copy by an actual copywriter is
on the roadmap (industry-panel review, Agreement 1 / Leapfrog 2,
"copy subset"). Pull requests with better lines welcome.

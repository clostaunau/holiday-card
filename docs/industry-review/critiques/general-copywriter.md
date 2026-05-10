# Greeting Card Copywriter Critique — holiday-card

## Verdict in one sentence

This is a beautifully engineered card-making engine that ships with the linguistic equivalent of beige paint — every default line is a placeholder masquerading as a sentiment, and the data model can't even hold a salutation, a signoff, or a line break.

---

## The default copy: a tonal audit

I read every shipped front-and-inside pair. Here is what's actually on the page.

### Christmas — and there are EIGHT of these

Front lines used across christmas templates:
- `Merry Christmas!` (classic, artist, geometric, festive_stripes)
- `Season's Greetings` (modern, holly_wreath, holiday_masterpiece)
- `Joy & Peace` (metallic_ornaments)
- `Happy Holidays!` (photo_ornament)
- `Peace on Earth` (winter_sky)

Inside lines:
- `Wishing you joy and happiness this holiday season!` (classic, geometric, festive_stripes)
- `Wishing you a colorful and creative holiday season!` (artist)
- `Wishing you peace and joy this holiday season` (modern, holly_wreath)
- `May your holidays shine bright with happiness!` (metallic_ornaments)
- `May this holiday season bring you warmth, happiness, and cherished moments with loved ones.` (holiday_masterpiece)
- `Treasured moments from our family to yours` (photo_ornament)
- `May this season bring you tranquility and warmth.` (winter_sky)

**The diagnosis.** Every single inside line begins with `Wishing` or `May` plus a string of generic abstract nouns: joy, happiness, warmth, peace, tranquility, cherished moments. This is the "thoughts-and-prayers school" of card writing. It is the default voice of a corporate holiday email. None of these lines knows it is being held by a person who knows the recipient. A real card line — even a classic one — does at least ONE of three things: it makes a small specific image (`May your tree be crooked and your house be loud`), it admits the year was hard (`Lighting candles for everyone we lost. And for us, still here.`), or it lands on one verb that does work (`Stay warm. Stay close.`). None of these defaults do any of those things. They are all the same line in eight outfits.

**The cumulative effect.** If a user generates four christmas cards and sends them to four different people, the recipients receive *the identical sentiment*. The system gives them no nudge to change it. That is worse than a blank card.

### Birthday — `birthday-balloons`

- Front: `Happy Birthday!`
- Inside: `Wishing you a wonderful day filled with joy!`

**The diagnosis.** "Happy Birthday!" with an exclamation point is not copy, it's a default in a phone reminder. The inside line could be on a Hallmark birthday card from 1987 *or* a screen at the DMV. There is no register choice — is this a 6-year-old's card? A 70-year-old's? A coworker's? A best friend's? The line works for none of them, which is its own kind of failure: it has no opinion. Compare to a real birthday line: "You're getting old. So am I. Let's keep doing it together." Or: "One more orbit. Glad you're still on the ride."

### Hanukkah — `hanukkah-menorah`

- Front: `Happy Hanukkah!`
- Inside: `May your Festival of Lights be filled with joy!`

**The diagnosis.** "Festival of Lights" capitalized like a brand name is the move of someone Wikipedia-ing the holiday five minutes before writing the card. A Jewish recipient reads this and clocks immediately that the writer is not Jewish — which is fine, but the line should land warmly anyway. "Wishing you eight nights of light" is better. "Chag sameach — and a quiet, full house" is better. Also: there is exactly ONE Hanukkah template. Christmas has eight. The disparity itself is a tonal statement.

### Generic — `generic-celebration`

- Front: `Congratulations!`
- Inside: `Wishing you all the best on this special occasion!`

**The diagnosis.** "Special occasion" is the giveaway phrase of someone who doesn't know what the occasion is. This is the thing taped to a vase of flowers that arrived from accounts payable. If the "celebration" template is meant to be all-purpose, it needs to ASK the user what is being celebrated and adapt. Otherwise it's a monument to vagueness.

### Mother's Day — `generic/mothers-day.yaml`

- Front: `Happy Mother's Day` / subtitle `with love`
- Inside: `Thank you for everything, Mom.`

**The diagnosis — and this is the most damning one.** Let me interrogate that line.

`Thank you for everything, Mom.`

- "Everything" is the cheat word. It means nothing. It is what you write when you have no specific thing to thank her for, which is the opposite of what the day is about.
- "Mom" — assumes one mom, alive, in a normal-good relationship, and that the recipient calls her "Mom." Not Mum. Not Mama. Not Ma. Not "my mom" (when the card is going to a friend whose mom died). Not "the woman who actually raised me." Not anything that recognizes adoption, stepmoms, two-mom households, or grief.
- The period at the end lands like a closed door. Cards almost never end on a period for the closing line. They end on a comma into a signature, an em dash, or an open beat.
- "Happy Mother's Day" + "with love" + "Thank you for everything, Mom" is three pieces of placeholder stacked on top of each other. The user gets a card that says, three times, "I did not write anything here."

What a real Mother's Day inside line looks like: `I picked you.` `Casserole queen. Boundary-modeling queen. My queen.` `You were the only person who ever knew exactly when to bring the tea.` `I don't say it enough: I see how hard you worked.` Em & Friends sells one that says only `My mom is hotter than your mom.` THAT is a card. "Thank you for everything, Mom." is a Post-it.

It is also worth noting: this template is filed under `generic/` not `mothers-day/`, and its `occasion` field is `generic`. So Mother's Day isn't even a real first-class holiday in the system — it's a one-off in the misc drawer.

### Christmas masterpiece — special call-out

`May this holiday season bring you warmth, happiness, and cherished moments with loved ones.` is the most words used to say the least amount in the entire repo. It is the inside-of-a-Costco-card line. The longer the sentiment, the more carefully each word has to earn its keep — and "cherished moments" earns nothing.

---

## The 3 biggest copy/voice problems

1. **Every default starts with "Wishing" or "May."** Both are the verb-tense of someone who isn't actually in the room. Real warmth is in the indicative or the imperative: "I'm thinking of you." "Hold these eight nights close." "Eat the second slice." The repo has no examples of either.

2. **Abstract noun stacking.** `joy`, `happiness`, `warmth`, `peace`, `tranquility`, `cherished moments`, `the best`, `everything`. Twelve templates, the same eight nouns. A card needs ONE concrete image — a candle, a kitchen, a phone call, a casserole, a knee, a porch — to land. There are zero concrete nouns in the default copy across the entire shipped library.

3. **No register variance and no register choice.** Every card is set to "earnest, mid-volume, lightly formal, pastel." There is no irreverent register, no devotional register, no funny-friend register, no spare-and-modern register. And the user can't ask for one. This is the single biggest miss: cards are sorted in stores by *voice* (Em & Friends ≠ American Greetings ≠ Papyrus ≠ Sapling), and this tool acts like voice doesn't exist as a dimension.

---

## What's missing from the data model

`TextElement.content: str = Field(min_length=1, max_length=1000)`. That's the surface. From a copywriter's view, a card needs:

- **Salutation** — `Dear Mom,` / `Hey kiddo,` / `For Sarah,`. First-class field, not a hack into `content`. Should default off so the user isn't forced to write one.
- **Body** — what we have, but it should accept multi-line. Currently `content: "single string"` and the renderer doesn't `splitlines()` (verified — no newline handling in `text_utils.py` or `text_fitting.py`). You cannot do "Roses are red / Violets are blue" properly. You cannot quote a stanza. You cannot do a haiku. This is a major hole.
- **Signoff** — `Love,` / `Always,` / `Yours,` / `xo` / `— C`. Separate field with sensible defaults per occasion.
- **Signature line** — separately stylable, often handwritten-feeling font.
- **P.S.** — the most-read line on any card. Not a hack — a first-class optional field with smaller font convention.
- **Date/year** — for keepsakes. `Christmas 2026` in tiny type at the bottom is a Hallmark trick families remember 30 years later.
- **Voice tag** — `warm | witty | spare | devotional | irreverent` on the template, surfacing copy options that match.
- **Recipient relationship** — `mom | spouse | friend | coworker | child` to gate the right defaults. A "Happy Birthday" card to a coworker should not say the same thing as one to your spouse.
- **Blank-mode flag** — `inside_blank: true` means the inside renders as truly empty (or with a hairline date stamp), no default copy injected, ready for handwriting.

The `min_length=1` on `content` is also worth flagging — it actively prevents an empty text element. If a user wants to render a card with no inside copy, they have to remove the element from YAML rather than blank it. Small thing, but it telegraphs the project's assumption that copy is mandatory.

---

## A sentiment library would change everything

Right now the default copy lives inline in YAML, one line per template, frozen. The fix is to extract sentiments into a library indexed by `(occasion, register, length)` and let the user pick:

```text
sentiments/
  christmas/
    warm/
      cover/
        - "Merry Christmas"
        - "All is bright"
        - "Warmth & Light"
        - "Hold the season close"
        - "From our house to yours"
      inside/
        - "Thinking of you in the quiet hours of this season."
        - "May your house be loud and your tree be crooked."
        - "Wherever you are this year — we're glad you're there."
        - "Light a candle. Pour the thing. We love you."
        - "One more Christmas with you in the world. Lucky us."
    witty/
      cover:
        - "Yule be fine"
        - "Santa's watching. Behave a little."
      inside:
        - "Hope your in-laws are tolerable and your gravy is not."
        - "Wishing you the precise number of cookies."
    spare/
      cover: ["Peace.", "December."]
      inside: ["Quietly thinking of you.", "More soon. Love now."]
    devotional/
      cover: ["Glory to God in the Highest", "Emmanuel"]
      inside: ["For unto us a child is born — and unto us, this card. With love."]
```

Three to five voice registers × six occasions × five lines each = ~120 hand-written sentiments. That is one good afternoon with a copywriter and it transforms the product. CLI: `--voice witty`, `--voice spare`. Or `--surprise-me` which picks one at random. The technical work is trivial — load YAML, pick a string. The hard part is writing the strings, and the project hasn't done it.

Bonus: `--seed <name>` so the same recipient gets a *different* sentiment than the last person, but a *consistent* one across re-renders.

---

## The "leave it blank" pattern

Half of all premium cards are bought specifically because they are blank inside. The buyer wants the *cover* to do the work and to write the sentiment by hand — that is the point of the card. Right now this project cannot do that without manually editing YAML to delete the `text_elements` block. There should be:

- `--blank-inside` flag on `create` that suppresses inside copy regardless of template defaults.
- A first-class `BlankInside` template variant for every occasion: cover does the heavy lifting, inside is white space (or, ideally, a single hairline horizontal rule a third of the way down — the universal "write here" cue, which is itself a thoughtful design move).
- The model should permit `content: ""` and treat it as "render nothing." Drop the `min_length=1` constraint on TextElement, or wrap blank-handling at the template layer.

This is the easiest, cheapest tonal win in the whole repo. Some of the most beautiful cards ever sold say nothing inside.

---

## Cultural / situational sensitivity gaps

The repo does not acknowledge:

- **Mother's Day / Father's Day for the bereaved or estranged.** No "Thinking of you on a hard day" variant. No "For the woman who chose to raise me" variant. The single Mother's Day template defaults to a line that assumes the recipient has a living, loving mom they call "Mom." That is the *median* case — but cards are bought disproportionately by people in the *non-median* case, who are the ones who actually need a card with care in it.
- **Christmas for non-Christians.** "Season's Greetings" handles this politely on the cover, but every inside line then leans on "holiday season" / "warmth" with no acknowledgment that the recipient might celebrate differently or not at all. No Solstice option. No "Happy Saturday in late December" sense of humor.
- **Birthdays, full stop.** No distinction between a kid's, a teen's, a milestone (40/50/60), a grieving adult's first birthday after a loss, a partner's, a sibling's. One `Happy Birthday!` to rule them all.
- **Hanukkah.** One template. Christmas has eight. Even within Hanukkah, no acknowledgment that for many Jewish families post-2023, the holiday landed differently. A line like "Eight nights, holding each other a little closer" would land — the current line could not.
- **Father's Day, Pride, Lunar New Year, Diwali, Eid, Juneteenth, Easter, baby-loss remembrance, sympathy, get-well, congratulations-on-divorce, congratulations-on-sobriety, thank-you, thinking-of-you.** None present. The "occasion" enum (`christmas | hanukkah | birthday | generic | valentine`) reveals the worldview.
- **Sympathy cards.** The single hardest category to write well, and absent entirely. Probably right to leave for v2 — but worth flagging that the "celebration" framing in the codebase (`generic-celebration`, `description: "Versatile celebration card"`) actively excludes the half of card-buying that isn't celebratory.

---

## What's surprisingly good

- **`mothers-day.yaml` cover/subtitle stacking.** "Happy Mother's Day" set in italic Times-Roman with "with love" floating as a subtitle is — visually — a real card move. The art direction is more sophisticated than the words.
- **`winter_sky` — `Peace on Earth`.** The only cover line in the repo with three words and no punctuation, and it's the only one that breathes. Whoever wrote this one knew what they were doing. The inside line then immediately undoes it.
- **`metallic_ornaments` — `Joy & Peace`.** Same. Three characters, an ampersand, restraint. Better than every other cover in the file.
- **`holiday_masterpiece` "Memories to Treasure"** as a photo-section header — fine, that's a category convention and it works.
- **`overflow_strategy: shrink` and `wrap`.** The engineering accommodates writers who go long. That is generous infrastructure. It is being wasted on copy that should be short.
- **The decorative element library (`heart_simple`, `geometric_tree`, `wreath`).** Visual vocabulary is being curated thoughtfully. Linguistic vocabulary is not. The asymmetry is the whole problem.
- **The valentine spec in `CLAUDE.md` (`"You make my heart smile"`)** is *also* a weak line, but the *infrastructure* it documents — heart clipping, custom fonts, polaroid frames — is exactly the foundation a real copy library would deserve. (Worth noting: the templates/valentine/ directory documented in CLAUDE.md does not actually exist in the repo.)

---

## The leapfrog opportunity

**Ship a curated, registered, voice-tagged sentiment library and a `--voice` flag — and make blank-inside a first-class mode.**

That's it. That is the whole thing.

Right now this project is a card-shaped PDF generator. After this change, it would be the only open-source greeting-card tool that takes the words seriously. You'd run:

```bash
holiday-card create christmas-classic --voice witty --recipient sister --blank-inside no
# Renders: cover "Yule be fine", inside "Hope your in-laws are tolerable and your gravy is not."

holiday-card create mothers-day --voice spare --recipient estranged
# Renders: cover "For my mother", inside "Thinking of you today. — C"

holiday-card create birthday-balloons --voice warm --recipient kid --blank-inside yes
# Renders: cover only. Inside is a single hairline rule. Write to your kid by hand.
```

The technical work is small (YAML library, CLI flags, lookup by tags). The writing work is one focused day with someone who has done this before. The output: a tool that ships *with a voice*, instead of a tool that ships with the literal phrase "Wishing you all the best on this special occasion!" eight times.

The cards-with-good-copy tool does not yet exist in the open-source world. This project is one library and one flag away from being it.

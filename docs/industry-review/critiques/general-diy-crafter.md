# DIY Crafter Critique — holiday-card

*(Sandy, 38, Etsy shop "PaperPeonyCo", two kids, Cricut Maker 3, Silhouette Cameo 4, Canva Pro subscriber since 2018, screen-prints in the garage on weekends.)*

## My honest first reaction (in character)

Okay so my nephew Tyler sent me this link and said "Aunt Sandy you'll LOVE this, it makes holiday cards." I clicked the link and the very first thing on the page is a black box that says `pip install -e ".[dev]"`. I scrolled past it looking for screenshots or a "Get Started" button or honestly just a picture of a card. There aren't any. The whole README is grey boxes of text-commands. I scrolled to the bottom hoping for a gallery — nope, it ends with "MIT (see pyproject.toml)." What is a pyproject.toml. I don't know.

I'm going to be straight with you — I closed the tab. Then I felt bad because Tyler is sweet and I reopened it. The word "card" appears 14 times, the word "pip" or "PDF" or "command" or "CLI" appears way more. This is not a website that wants me here. This is for Tyler.

## The install step (in character)

`pip install -e ".[dev]"`

I do not know what any of those characters mean and I am a fully functioning adult who runs a small business. Let me try to parse it: "pip" — is that a person? "install" — okay, install something. "-e" — what is e. "[dev]" — dev like developer? I'm not a developer. Am I supposed to skip this part? Is this for me?

The SETUP_AND_RUN.md tells me to first run `python3 -m venv venv` and then `source venv/bin/activate`. I don't have Python on my computer (I just checked — apparently I do? "Python 2.7"? It's saying that's wrong somehow?). The Troubleshooting section helpfully tells me what to do if I get "No module named 'reportlab'" — but it doesn't tell me what reportlab IS or why I would care.

Compare: Canva. I went to canva.com. I clicked "Mother's Day card." I'm editing. Elapsed time: 9 seconds.

Compare: Cricut Design Space. Double-click the desktop icon. It opens. There are templates. I'm in.

I would not get past step 1 of this tool. And I'm above-average tech-comfortable for my demographic — I've rooted a Kindle, I solder, I write Cricut SVGs by hand sometimes. If I bounce, the average mom-with-a-Cricut bounces in 4 seconds.

## Trying to change a color (in character)

So I peeked at the Mother's Day template (`templates/generic/mothers-day.yaml`) because, well, that's the one that's actually about my life right now. The pink is too pink. I want a dustier rose. In Canva I'd click the background, click the color circle, drag the eyedropper or type a hex code. Done in 4 seconds.

In this thing, I have to:

1. Find the file `templates/generic/mothers-day.yaml`. (Where's "templates"? Where's "generic"? My Finder doesn't show me this folder structure. I'd have to navigate through Terminal? Or open it with TextEdit? Will TextEdit mess up the formatting?)
2. Find the right block. There are FOUR `background_color` blocks. I have to know that "front" is the one I want, not "inside_left."
3. The color isn't a hex code, it's:
   ```
   r: 0.98
   g: 0.86
   b: 0.88
   ```
   I do not know what 0.98 means as a color. I know `#FCDBE0`. I know "blush pink." I do not know "0.98 red point eighty-six green point eighty-eight blue." Now I have to Google "convert hex to rgb decimal." Find a calculator. Convert. Type carefully. **Don't** mess up the indentation (my nephew warned me YAML breaks if you use a tab instead of spaces. WHAT.).
4. Save the file. Run the command in Terminal. Wait. Open the PNG. Look. Adjust. Repeat.

And here's the *kicker* — the same template uses `r: 0.98, g: 0.86, b: 0.88` for the background BUT `"#E89BA6"` for the circles. So the file uses **two different color formats in the same card** and I'm supposed to know when to use which. I'd type a hex into the background field and the whole thing would crash and I'd cry.

And THEN — I actually ran the preview command on this Mother's Day template just to see what the "soft pink half-fold" looks like. The greeting is on the **right side, oriented sideways**, the underline is **above** the "with love" text instead of below, and the front of the card takes up the bottom right quadrant of a portrait letter sheet. I get that this is a half-fold layout printed flat, and once you fold it, it works. But I had to *think really hard* to figure that out. Canva would show me the folded preview AND the print sheet, side by side, with the fold line labeled. This shows me one PNG and trusts me to imagine the rest.

## Visual feedback loop

Canva: I type. The card updates as I type. I see the kerning change in real time. If I don't like it I undo with Cmd-Z and we're back where we started in 200 milliseconds. The loop is "thought to validation" in under one second.

This tool: edit YAML → save → switch to Terminal → arrow-up → enter → wait 2-3 seconds → switch to Preview app → close old PNG → open new PNG → squint → "oh that's wrong" → switch back to editor → repeat. Best case the loop is 15 seconds. Realistic case with a typo or formatting error is 90+ seconds because I have to debug the YAML and re-Google what indentation is.

If I want to fine-tune the position of one circle, I'd be doing this 40-50 times. That's an hour for what would take me 5 minutes in any visual editor. I would never finish a card. I would quit and open Canva.

## Fonts

Canva account: 600+ fonts, all preview-able by hovering. I can search "script" or "wedding" and see them. I can favorite ones I love. I have a folder called "Sandy's Wedding Invite Fonts."

This tool: ships with Helvetica, Times-Roman, and Courier. The "basic 3." (My grandfather had more font choices on his typewriter.)

The "drop your own .ttf" affordance: I do not know what TTF means. I half-remember installing a font on my old Windows laptop once by double-clicking it and a window said "Install" and I clicked it. Where do I "drop" it here? In the `fonts/` folder? Where IS the fonts folder? Inside the holiday-card folder? Inside venv? I'm guessing. And then once it's there I have to **edit a YAML file** to reference it by exact filename, and if I get the casing wrong it silently falls back to Helvetica. My Etsy customers want "Great Vibes" and "Allura" and "Petit Formal Script" — they want options I don't have here and a way to find them I don't have here.

## Photos

This is the hard stop. **Half my Etsy listings are personalized photo cards.** Grandkid in front of the Christmas tree. Sonogram announcement. Pet memorial. Engagement reveal.

The README says nothing about photos. SETUP_AND_RUN.md mentions a `--image / -i` flag. I tried to picture using it: one image, presumably plopped at one location, no crop control from the command line, no rotate, no opacity, no "round the corners," no caption-overlay. To do anything custom I'd be back in YAML.

The CLAUDE.md mentions a `HeartClipMask` and "polaroid frame" and "sepia." That's actually cool feature-wise! But it's all driven from YAML — I can't drag a photo onto a canvas, I can't crop it visually, I can't see the heart mask move as I drag. So even when the *capability* exists, the *interaction* makes it useless to me.

If I can't quickly drop in a photo of a customer's grandkid, smile-crop it, and ship it — this tool is dead to my Etsy shop.

## Print to your home printer

I have a Canon Pixma TS9120 inkjet. I print on Hammermill 80lb cardstock for cards. I have been *burned* so many times by Word printing the card 3mm offset and ruining 8 sheets at $0.40 each.

Letter PDF output is theoretically the right format. But I have very specific questions this tool doesn't answer:
- Does it have **bleed**? My Pixma can't borderless on cardstock, so I need a 1/8" white margin all around. Are these templates designed for that?
- Are the fold lines marked, or do I have to eyeball it? (The preview I generated shows a faint dashed line — okay, that's nice — but is it accurate enough that a folded card lines up at the spine?)
- Will the colors match what I see on screen? No color profile mention, no "calibrate to your printer" workflow, no test-strip mode. Cricut Print Then Cut at least registers cuts to printed marks.
- The pink in the Mother's Day card is going to print *very* differently on my inkjet than what I see in Preview. I'd want a tiny printable swatch sheet first. Doesn't exist.

I would do one test print, hate the alignment, and never try again.

## Sell on Etsy

Etsy listings need flat JPG/PNG at specific dimensions (2000x2000 minimum for the listing thumbnail, 5x7 print files at 300dpi for digital downloads). My customers buy the digital file and print at home or at Walgreens.

Could I produce that with this tool? Technically yes — PNG at high DPI is supported. But:
- Etsy customers expect a **template they can personalize themselves** (Corjl, Templett, Canva-share). I can't say "here, edit this YAML." That's the listing-killer.
- I can't list "Cricut-cut SVG with score lines" because this tool doesn't output Cricut-friendly SVGs (no score line layer, no cut-vs-print separation).
- I can't list "editable in Canva" because the output is flat.

My existing Etsy workflow: design in Canva → export PNG and PDF → upload to Corjl with personalization fields marked → buyer customizes name themselves → done. This tool replaces approximately zero of those steps.

## What I'd actually do instead

For a Mother's Day card for my own mom: **Canva.** 5 minutes, drag a photo of my kids in, hit print. Done.

For my Etsy shop: **Canva + Corjl.** Customer self-personalizes.

For a school teacher gift card with all 22 kids' names: **Cricut Design Space.** Set type, weld names, print-then-cut on the Maker.

For a screen-printed birthday banner: **Silhouette Studio** to make the stencil, then garage time.

This tool would not enter my workflow at any step.

## The audience confusion

The README literally calls this a "small utility to create Holiday cards from regular printer paper." That's *cozy* language. That's "stay-at-home mom in slippers" language. That's the same vibe as a Pinterest tutorial titled "Easy DIY Cards for the Holidays."

But the actual interface is `pip install -e ".[dev]"` followed by editing YAML files where colors are stored as decimal RGB triples. That is the most extreme possible mismatch between message and product. The README is selling Sandy. The product is built for Tyler.

This gap isn't just unfortunate — it's actively harmful. Either Sandy clicks the link, bounces, and tells her mom-friends "my nephew sent me this thing and it was incomprehensible" (bad word of mouth in the demographic), OR Tyler clicks the link, sees "small utility for printer paper," dismisses it as a toy, and never realizes there's a legitimately interesting IR-based PDF/SVG/PNG compiler under the hood (lost technical audience).

## What this tool would need to be FOR me

Realistically, to win me over you'd need:

1. **A web app.** Browser-based. No install. canva.com style. I open it, I see templates, I click one, I'm editing.
2. **Drag-and-drop photo import.** With a visual crop circle, a slider for the heart mask, a click-to-rotate.
3. **Color picker.** A real swatch picker with hex input AND a slider AND eyedropper. Never, ever ask me to type `r: 0.98`.
4. **Live preview as I type.** Not a regenerate-the-PNG loop. Live.
5. **Cricut/Silhouette export.** "Export for Cricut" button that gives me an SVG with cut lines and print-then-cut registration marks. THIS would actually be a thing Canva doesn't do well, and it would matter.
6. **Print test sheet** — a one-click "print a calibration page" so I can verify my printer's alignment before I waste cardstock.
7. **A font browser** with previews. Even just the 50 most popular Google Fonts pre-loaded.

Realistically, items 1-4 alone make this Canva-with-fewer-features. Items 5-6 are where this tool could actually carve out a niche I'd pay for.

## What this tool is actually for (honest answer)

This tool is for my nephew Tyler. Tyler maintains his blog with Hugo, version-controls his resume in LaTeX, and thinks "edit a YAML file" is a feature, not a bug. Tyler likes that his card design lives in `git`, can be diffed, can be regenerated identically every December, and can be kept in the same repo as his Christmas-letter Markdown. Tyler likes that it has 324 tests and CI on three Python versions. Tyler probably likes that the renderer is swappable.

That is a real audience. It's small but it exists. It's "engineers who send a holiday card to 40 family members every year and have decided that the *card itself* should be reproducibly built from source." Which is honestly kind of charming.

The README should just **say that.** "Holiday cards as code, for engineers who already think this way." Lean into it. Stop pretending it's for Sandy.

## What's surprisingly good

Even from my grumpy crafter perspective, a few things are legitimately impressive:

- **One template renders to PDF, SVG, AND PNG.** That's actually useful — SVG means I could in theory bring it into Inkscape or Illustrator and tweak. I might actually do this.
- **The Valentine's Day release notes** in CLAUDE.md — heart clipping masks, sepia/vignette/blur effects, polaroid frames — those are *good craft features*. The capability is there. It's just locked behind YAML.
- **324 tests in 3 seconds, mypy strict, lint clean.** I don't care about this directly, but it tells me Tyler's nephew-equivalents (the maintainers) are serious people. The tool won't break next month.
- **It works.** I ran `holiday-card preview mothers-day` and got a PNG. The whole pipeline didn't fight me. That's more than I can say for some Cricut Design Space updates.
- **Free and offline.** Canva tries to upcharge me to Pro every five minutes. This thing just runs.

## The leapfrog opportunity

Pick ONE of these — don't try both. They go in opposite directions.

**Path A — win Sandy:** Build a single-page web UI that loads the same YAML templates and lets me edit visually in the browser. Drag a photo in, color-pick the background, hit "download PDF." Keep the engine; replace the input. The tagline becomes "Canva, but it produces clean PDFs that print right." Genuinely possible because the IR-compiler is already there. Hardest part is honest: drag-and-drop visual editor is itself a 6-month engineering project. But the **leapfrog** version of Path A is narrower — **do not build a full editor. Build "fork-this-template-and-fill-in-the-blanks."** A single web page per template with form fields: "Greeting:", "Inside message:", "Drop photo here:", "Background color: [picker]". Output a PDF. That's a weekend project that captures 80% of Sandy's use case for 5% of the engineering cost.

**Path B — win Tyler:** Ship a **`holiday-card` GitHub Action** that auto-renders cards from YAML on every push, posts the PNG as a PR comment, and on release tags emails the PDF to a configured list. Add a "Christmas letter mode" where you write Markdown and it composes the inside panel with proper typography. Add bleed, crop marks, and CMYK PDF output for actual print shops. Lean into the "cards as code" identity. The tagline becomes "git-tracked greeting cards with CI." Tyler's whole demographic eats this up and Canva literally can't compete.

**My honest pick:** Path B. It's a smaller, more loyal, more reachable audience, and it's where the existing architecture already lives. Path A is rebuilding Canva, and Canva is free and excellent. Path B is building something Canva *cannot* build, for people who are already wired to want it. That's the actual competitive moat.

But for the love of God, change the README to match whichever path you pick. The current "small utility for printer paper" framing is selling to me, and I am the wrong customer.

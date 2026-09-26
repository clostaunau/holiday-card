# Curated fonts

Six intentionally-chosen open-source typefaces shipped with the project
(the two editorial-serif families ship full Regular + Bold + Italic +
BoldItalic statics)
(SIL Open Font License). Templates reference these by their canonical
short name (the IR ``font_id``) — the same name appears in
``CURATED_FONTS`` in
``src/holiday_card/renderers/font_registry.py`` and in the ``font_family``
field of any panel ``TextElement``.

These replace the Liberation default chain as the *recommended* fonts
for new templates. Existing templates that reference ``Helvetica`` /
``Times-Roman`` / ``Courier`` continue to work — the Liberation fonts
remain registered and embedded.

## What's here

| Font ID                        | Family               | Style                          | Suggested use |
|--------------------------------|----------------------|--------------------------------|---------------|
| ``Cormorant``                  | Cormorant Garamond   | Editorial serif (variable)     | Devotional, editorial body |
| ``Cormorant-Bold``             | Cormorant Garamond   | Bold editorial serif           | Bold Markdown spans on Cormorant text |
| ``Cormorant-Italic``           | Cormorant Garamond   | Italic editorial serif         | Italic Markdown spans on Cormorant text |
| ``Cormorant-BoldItalic``       | Cormorant Garamond   | Bold-italic editorial serif    | ``***both***`` Markdown spans on Cormorant text |
| ``PlayfairDisplay``            | Playfair Display     | High-contrast serif (variable) | Display covers, formal greetings |
| ``PlayfairDisplay-Bold``       | Playfair Display     | Bold display serif             | Bold Markdown spans on Playfair text |
| ``PlayfairDisplay-Italic``     | Playfair Display     | Italic display serif           | Italic Markdown spans on Playfair text |
| ``PlayfairDisplay-BoldItalic`` | Playfair Display     | Bold-italic display serif      | ``***both***`` Markdown spans on Playfair text |
| ``Lato``                       | Lato                 | Friendly geometric sans        | Warm voice, body text |
| ``Lato-Bold``                  | Lato                 | Bold geometric sans            | Cover greetings paired with Lato body |
| ``Inter``                      | Inter                | Modern variable sans           | Modern voice, spare voice |
| ``Caveat``                     | Caveat               | Handwritten script (variable)  | Signatures, irreverent voice |
| ``Comfortaa``                  | Comfortaa            | Rounded display (variable)     | Witty voice, playful covers |

## License

All thirteen TTF files are SIL Open Font License 1.1. The license
text is shipped alongside each font as ``{Family}-LICENSE.txt`` (one
license per family — every variant shares the same OFL as the
Regular). The Cormorant + Playfair Bold and BoldItalic statics were
generated from their variable masters by instancing at weight=700
(``fontTools.varLib.instancer``); the OFL covers derivative works
of this kind. The OFL allows:

* Free use, modification, and redistribution
* Bundling with any application or document
* Modification provided the modified version isn't called by the
  font's "Reserved Font Name"

It forbids selling the fonts on their own (we're not).

## Why these six

Per the industry-panel review (``docs/industry-review/consensus-general.md``,
Agreement 1, "font subset"):

> Ship 6-8 curated open-source fonts in ``fonts/`` and remove
> Helvetica/Times-Roman from the default chain.

The selection covers the dimensions a greeting card needs: editorial
serif (Cormorant), display serif (Playfair), friendly sans (Lato),
modern sans (Inter), handwritten script (Caveat), and rounded display
(Comfortaa). Pairings the panel called out — display/body/script —
are all reachable with combinations of these six.

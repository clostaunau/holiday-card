# DIY Crafter Critique — AI Image Generation in holiday-card

*(Sandy, 38, PaperPeonyCo on Etsy, Cricut Maker 3, Canva Pro since 2018, two kids, husband works graveyard at the hospital, dog named Biscuit. Tyler emailed me again. Here we go.)*

---

## My honest first reaction (in character)

Tyler emailed me at 6:47am — the kid does not understand normal-people hours — and the subject line was "AUNT SANDY THIS CHANGES EVERYTHING 🎉." Three hours later I sat down with my coffee to read it. He says "good news, the holiday-card thing now lets you generate parts of the card with AI — you just write a prompt!"

Okay. Tyler. Sweetie. Let me tell you what "you just write a prompt" looks like from where I'm sitting.

I opened the link he sent — same repo, same `pip install -e ".[dev]"` at the top of the README that made me close the tab in 4 seconds last time. Nothing about that has changed. He's added a sparkly new feature on top of the same un-clickable foundation. Putting AI image generation on top of this CLI is like putting a Ferrari engine in a car with no doors. Yes, it goes fast. I cannot get in.

And then I read the OpenAI doc he pasted at the bottom of the email and my coffee went cold. **"Requires API Organization Verification before access."** Tyler. *Tyler.* I sell paper goods on Etsy. I do not have an "API Organization." I do not know what that *is*.

So my first reaction is: this didn't fix anything for me. It added a second wall on top of the first wall.

But — okay — let me be fair. Let me actually walk through it instead of just venting.

---

## The API key step (in character)

So the workflow Tyler is describing for me, a human person, is:

1. Go to platform.openai.com (a website I've literally never been to).
2. Sign up. Verify my email. Verify my phone.
3. **"Organization Verification"** — I have to upload my driver's license? Or my LLC paperwork? I don't even know. PaperPeonyCo is a sole prop. I don't have an EIN. Am I allowed to do this?
4. Add a credit card. To a thing called an "API." For a service that bills me **per image**, in fractions of pennies, with no monthly cap that I can find.
5. Click "Create new secret key." Copy a long string of letters and numbers — `sk-proj-aB3xQ9...` — that I'm now responsible for not leaking.
6. Open Tyler's project. Find the right config file. Paste the key in. **Don't** commit it to git (Tyler's words, with a scary all-caps warning).
7. *Now* I can run a command in Terminal that maybe makes an image.

Compare to Canva Magic Studio: I click the purple sparkle button. A box appears. I type "watercolor peonies on cream background." I wait 8 seconds. I get four options. I click the one I like. It's on my card. **Total clicks: 4. Total time: 12 seconds. Credit cards entered: zero.** It's billed against the $13/mo I already pay, which I budget like Netflix.

The OpenAI key flow is not a feature. It is a **gauntlet** designed to keep me out. The fact that Tyler doesn't see it as a gauntlet is exactly the Tyler/Sandy gap the panel already identified. He has 14 API keys in his password manager. I have one (1) password manager and I'm not entirely sure how to log into it on my phone.

**Verdict on the API key step:** Non-starter on its own. If this were the only friction, I would still bounce.

---

## The 2-minute latency (in character)

Tyler's email says "complex prompts may take up to 2 minutes." Tyler thinks this is fine because Tyler is used to compiling things.

Let me describe what designing a card actually looks like. I'm making a custom card for Mrs. Patterson's anniversary. I want a watercolor of the koi pond from her backyard (she sent me a photo). I type a prompt. I wait. While I wait, I... what? Stare at the screen? Open Instagram? Get distracted? Forget what I was doing?

Two minutes is **the exact wrong amount of time.** It's too long to wait actively, too short to go fold laundry. Canva's 8 seconds is "watch the spinner, see the result, react." OpenAI's 2 minutes is "lose the thread, come back, the image is wrong, try again, lose the thread again."

And here's the thing about iterating on AI images — and I do this in Canva all the time — **you don't get it on the first try.** Not even on the second. I usually need 6-10 generations to dial in the vibe. In Canva that's 80 seconds total. In Tyler's tool that's **20 minutes**, and that's if every generation succeeds. If half of them come back with weird hands or muddy colors, that's 40 minutes. For one image. On one card.

And remember, after I get the image I still have to put it into the card by **editing a YAML file**, regenerating the PDF, opening it in Preview, looking at it, going back to YAML, etc. The 90-second YAML loop from my last critique stacks ON TOP of the 2-minute generation loop. We're now at 3.5 minutes per iteration, minimum. That is not a creative tool. That is a punishment.

**Verdict on latency:** Canva's instant-feedback loop is the actual feature. Strip that away and AI generation is just slow stock photography I'm paying per-image for.

---

## The pay-per-image model (in character)

Let me actually do the math, because this matters to my business.

I make about 30 cards a month — mix of Etsy custom orders, family birthdays, my Junior League stuff, and the occasional bridal-shower order from a friend-of-a-friend. Let's say half of those would benefit from a custom image. So 15 cards/month with AI imagery.

But — I just said — I iterate 6-10 times per image to get one I like. Let's say 8 generations average. At "high quality" (because for sale on Etsy I'm not shipping low-quality 1024×1024 — that's a thumbnail, not a card cover), that's **$0.211 × 8 generations × 15 cards = $25.32/month.**

Plus the OpenAI account itself, plus the input tokens (which the doc warns about but doesn't price for me), plus whatever rate limit I bump into, plus tax.

Versus: Canva Pro is **$12.99/mo and includes unlimited Magic Studio image generations.** I already pay it. I have paid it every month for 8 years. I will pay it every month forever because it's *also* my mood board, my client mockup tool, my Instagram template generator, my baby shower invite shop, and my emergency Father's-Day-card-the-night-before backup.

The OpenAI thing isn't replacing my Canva subscription. It's an *additional* line item, billed in unpredictable per-image increments, that gives me LESS than what I already have. That's not how I think about software costs. I think about software costs as **predictable monthly bills under $20 that do five things each.** OpenAI image gen, as exposed through this tool, is the opposite of that.

And — this is the part that scares me — **what if I leave my key in a script and accidentally run it 1,000 times?** I've seen the AWS-bill horror stories on Reddit. ($30,000 from a forgotten Lambda loop.) I do not want a card-making hobby that has the energy of "could ruin my month financially if I typo something."

**Verdict on cost:** Mathematically worse than Canva for my volume. Psychologically much worse because it's unpredictable. Existentially worse because of the runaway-bill risk.

---

## The "I made this myself" thing (in character)

This is the one Tyler doesn't get at all and it's actually the deepest one.

Half the *point* of me sending a handmade card is the recipient knowing I sat at my kitchen table and made it. When my mother-in-law gets her birthday card and it's a watercolor I painted at 11pm, badly, of her dog — she cries. She has cried at three of my last four birthday cards. She does not cry because the watercolor is good. She cries because **I thought about her dog while I painted it.**

If I prompt "watercolor of a goldendoodle in a garden" and OpenAI spits something out and I print it and send it — she's not crying. She's getting a thing. A nice thing, sure, but a *thing*, not an act of love. And worse — she's getting **the same kind of thing she could've bought at Target for $4.99.** The whole reason a handmade card has value is that it's NOT one of those.

There's a whole category of recipient who would actually be **insulted** to get an AI card from me. My mom. My grandma (94, still sharp). My oldest customers who've been buying from me for 6 years and follow my Instagram for the *behind-the-scenes* of me making things. They follow me for the *making.* If I quietly start shipping AI work I'm betraying the actual product they're buying, which is "Sandy's hands made this."

Now — and this is where I have to be honest — there are *also* recipients who would not care at all. My nephew Jake who's 8 and just wants a dragon. My friend Becca who needs 40 thank-you cards for a fundraiser. The PTA bake sale. For those, AI is fine. For those, AI is *better* than fine because I don't have time to hand-illustrate 40 bake sale cards.

So it's not all bad. But it changes the *meaning* of what I'm making, and I have to be careful about which stack each card goes into.

**Verdict on authorship:** It changes the product. Sometimes that's fine. Sometimes that's a quiet betrayal of the entire brand.

---

## The Etsy reality (in character)

Okay this one is the actual business risk and I have to talk about it carefully because Tyler will not understand.

In the last 18 months, **the bottom of my Etsy listings has changed.** Where I used to write "Ships in 3-5 days, message me with personalization details," I now write things like:

> "100% human-designed. No AI imagery used. Hand-illustrated by Sandy in Ohio."

I added that line in October 2024 because customers started *asking*. Like, multiple times a week, in the chat-before-buying messages: "Is this AI? I don't want AI." Etsy as a marketplace has a whole **AI controversy** I'm not going to relitigate here, but the short version is: a chunk of my customer base is **actively shopping FOR human-made and AGAINST AI-made**, and they're vocal about it.

If I quietly start mixing AI imagery into my listings and one customer figures it out — one screenshot to the "ArtistsAgainstAI" subreddit, one Etsy review that says "I think this seller is using AI" — my shop is **done.** Not "takes a hit." Done. The reviews are searchable, they sit there forever, and Etsy's algorithm punishes shops with controversy.

So even if AI generation in this tool worked *perfectly* — instant, free, beautiful, copyright-clean — I would have to keep it out of my Etsy workflow entirely. I might use it for personal cards. I will not use it for paid work.

And that's before we get to the **commercial-use question Tyler's doc explicitly flags as unresolved.** "Commercial / IP / copyright: Not specified in this doc." That's a giant red flag waving in my face. I am not putting AI imagery on a thing I sell for money when the licensing is "consult separately." I have a small business. I do not have a lawyer.

**Verdict on Etsy:** AI generation is actively dangerous to my existing shop. Not just unhelpful — *dangerous*.

---

## Three concrete use cases where I'd actually want AI imagery

Being fair. There ARE cases.

1. **Custom dragon for Jake's 8th birthday.** Jake is obsessed with dragons. He wants a *specific* dragon — green with purple wings, one chipped tooth, holding a slice of pizza. No stock illustration exists for this. I cannot draw a dragon. AI can. He will be delighted. I am buying him goodwill at $0.21 a pop, which is cheaper than the LEGO set I would otherwise feel guilty about. **This is the use case AI image gen was actually invented for.**

2. **Pet portrait for a sympathy card.** When my friend Marisol's dog Cookie passed last year, I wanted to send a card with Cookie on it. I had a photo. In Canva I cropped Cookie out, cartoon-filtered her, and put her on a "gone too soon" card. Marisol cried, in the good way. AI image-edit (the "image + prompt → modified image" mode in Tyler's doc) could do this *better* — a real watercolor of Cookie, not a Canva filter. For a personal card, with no commercial stakes, this is exactly right.

3. **A specific scene from a kid's favorite book.** My friend's daughter is OBSESSED with the book "Julián Is a Mermaid." For her birthday card I want a Julián-style mermaid (her, in a flower crown, swimming). No stock image exists. I can't draw it. The illustrator's actual book is copyrighted (so I'm not, like, ripping the actual art). But "watercolor of a child in a mermaid costume with flowers in her hair, in the style of children's book illustration" — that's a thing AI does well, for one personal card, where nobody's making money. Yes please.

Common thread on all three: **personal use, recipient is in on it, no commercial stakes, image doesn't exist anywhere else.** That's the wedge.

---

## Three concrete use cases where I'd be horrified by AI imagery

1. **My grandma's 95th birthday card.** She is 94 right now. She has lived through actual war. She gets one card a year from me and it has my handwriting on it and a dried flower from my garden taped inside. Generating an AI image for her card would feel like a desecration. I would rather send no card than send an AI card. *(I would actually rather send a stick-figure drawing I made with my non-dominant hand.)*

2. **Anything I sell on Etsy.** Already covered. Existential business risk. Don't care how good the image is.

3. **Sympathy cards in general** — *unless* the AI is editing a real photo of the deceased the family gave me. A generic AI "sympathy flowers" image is *worse* than the Hallmark equivalent because at least Hallmark's was painted by a real human in 1987 who was thinking about grief. An AI sympathy bouquet is mathematically averaged sadness and you can feel it. No.

Common thread: **high stakes, real relationships, paid work, or grief.** Three contexts where AI imagery makes the card feel cheap *because* the recipient knows what AI is now.

---

## The single feature/UX change that would let me actually USE this

Okay if you actually want me to use AI generation, here is the **one** change that matters.

**Forget the API key. Build a hosted version where I pay you, the project, $5/month and you handle OpenAI billing on the backend. Bundle a budget — say, "20 high-quality images per month included, $0.25 per image after that, hard cap at $30/month so I can sleep at night." Show me the running total in the UI. Make me click "yes" before each generation if I'm about to exceed the cap.**

In other words: **wrap the API in a SaaS that solves the gauntlet AND solves the runaway-bill anxiety AND solves the "I have to manage a key" problem.** This is what Canva did. It's what every consumer-facing AI image tool that succeeded did. Midjourney did it. Adobe Firefly did it. There's a reason.

The AI generation feature could be incredible for me. But not as a CLI flag that takes an `OPENAI_API_KEY` env var. As a hosted button in a web UI that bills me predictably and lets me iterate fast.

(Bonus: if you do this, you can negotiate volume discount with OpenAI and pocket the margin. That's the actual business model. Tyler will not think of this because Tyler does not run a small business.)

If I had to pick a *second* change, it would be: **show me 4 options per generation, like Canva does**, instead of one. That alone would cut my iteration count from 8 to maybe 3 because I'd be picking from a grid instead of rerolling one slot machine.

---

## Has anything actually changed from my last verdict?

**No. And honestly — slightly worse?**

Here's why. Last time I said "this isn't for me, it's for Tyler, and that's actually fine — lean into Tyler." The panel agreed. The recommended path was "stay Tyler-first with a narrow microsite escape hatch for Sandy."

The AI generation feature, as currently scoped (CLI flag, BYO API key, pay-per-image, 2-minute latency, commercial rights unclear), is **a Tyler feature**. It is exactly the kind of thing Tyler will think is amazing. He will set up his key, he will write a prompt in his terminal, he will wait the 2 minutes happily because he's also got a Helm chart to debug, and he will get a cool image for $0.21 and post it on Hacker News.

I do not get any closer to using the tool because of this feature. The visual gap (I can't draw, I can't make custom art) is now bridgeable in theory — but the YAML/CLI gap, the install gap, the API-key gap, the iteration-loop gap, the print-preview gap, the photo-handling gap, the cost-predictability gap, the Etsy-safety gap — none of those are touched by adding AI generation.

Worse: AI generation **uses up engineering budget** that could have gone to the microsite escape hatch the panel actually recommended for me. If I'm reading this right, the maintainer chose to ship a Tyler feature instead of a Sandy escape hatch. Which, fine — Tyler-first was the recommendation — but don't dress it up as "good news for Aunt Sandy." It isn't.

The one thing AI generation *could* be for me is the dragon card for Jake. But for that one card, twice a year, I will use Canva Magic Studio because I already pay for it, it's instant, and my key isn't sitting in a YAML file somewhere ready to bankrupt me.

**Has the project gotten more for me? No.**
**Has it gotten more impressive? Yes — for Tyler.**
**Is that a problem? Only if you keep telling me it's for me.**

Stop telling me it's for me.

---

## Honest verdict

Tyler's "good news" is not good news for me. The AI generation feature, in its current shape (CLI + BYO key + pay-per-image + 2-min latency + unclear commercial rights), is a power-tool for power-users and it makes the Tyler/Sandy gap **wider**, not narrower.

The bridge that would let me use this is not "add AI." It's "wrap the whole thing — including the AI — in a hosted, billed, web-based product where I never see a YAML file or an API key." That's a different product. It's a product I would happily pay for. But it's not the product Tyler keeps emailing me about at 6:47am.

I love that Tyler thinks of me. Tell him to stop sending me links until there's a button I can click that says "Make a card."

— Sandy

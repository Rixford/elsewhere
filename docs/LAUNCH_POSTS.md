# Launch drafts

These are drafts for the project owner to post. No personal browsing data or screenshots are bundled. The model name in the demo is based on the owner's supplied screenshot; it is not a benchmark or a claim that every generation looks the same.

## Twitter / X

I built a browser that hallucinates the internet.

Type google.com. It never visits Google. An LLM imagines the page in HTML/CSS.

Elsewhere: open source, Windows. Local Qwen or your own OpenAI/Claude API key.

What would you visit first?

https://github.com/Rixford/elsewhere

### Optional reply with the demo

This screenshot used OpenAI Astra via its API. Local Qwen works offline after setup; cloud models need internet and have API costs.

Links can generate the next imagined page with context from the last. Back/Forward restores saved pages. Bookmark a discovery to keep it.

The fun question: how far can you wander before an invented site loses its identity?

## Reddit

**Title:** I built an open-source browser that hallucinates websites instead of visiting them

**Body:**

I typed `google.com` into a browser I made, and it generated the page in this screenshot. It never connected to Google or fetched Google's assets. The model wrote its interpretation as HTML/CSS, with inline SVG where needed.

It's called **Elsewhere**. The address bar is a prompt: a familiar domain, a made-up website, or something like “a library on Mars.” Follow a link and it can generate the next page, carrying some context from the site you're exploring.

I wanted to see what browsing would feel like if the internet were being invented as you moved through it.

What it currently does:

- Runs on Windows with **Qwen3.5 4B locally**, offline after the initial setup/download.
- Optionally uses **OpenAI or Anthropic with your own API key**. The screenshot used OpenAI Astra; cloud generation requires internet and incurs API charges.
- Supports tabs, cached Back/Forward navigation and permanent local bookmarks.
- Uses optional model review to check presentation and language. Review is another model call; code checks always run.
- Keeps generated pages isolated: no remote assets, real sign-ins or purchases. Page controls are simulated by the app.

It's experimental. Smaller models can produce awkward layouts, continuity is imperfect, and the text is invented rather than verified. The app supplies continuity context, so coherent pages alone aren't evidence of emergent memory or consciousness. What interests me is which visual patterns and site identities survive as you keep following links.

The source is **MIT licensed**, with no bundled account, API key or personal browsing data. Run setup for your own machine, use the local model or bring your own API key, and change the settings to suit you. Downloaded model/runtime components have their own licenses.

Source and setup: https://github.com/Rixford/elsewhere

What would you type first? And what would make a good test of whether an imagined site stays coherent over five or ten clicks?

## Reusing these drafts

For a fork, replace the project name and repository URL, identify the model that actually produced your demo, and update the supported platforms/features. Attach a screenshot of your own non-personal example. The supplied demo screenshot should be cropped to exclude the hardware/performance overlay before posting; keep the CLOUD/model indicator visible so the mode is clear. Do not imply that the Astra screenshot was generated offline.

Use a relevant community's permitted project-sharing format. These drafts make no guarantee of reach and do not claim measured emergent behavior.

# Elsewhere

**A browser that hallucinates the internet.**

> What happens when a browser generates a representation of a website entirely from a model's learned knowledge, without retrieving the actual website?

Type a familiar address, ask a question, or invent somewhere new. Elsewhere turns the model's learned associations into HTML, CSS and SVG you can explore. Follow a link to imagine the next page. Go back to the exact saved generation. Keep a discovery, or look behind it to see how it was made.

**No target websites. No remote page assets. No fixed website templates.** Local Qwen works offline after setup. Optional OpenAI and Claude models use your own API key and an internet connection.

## Try it

Windows 10/11 x64, [Python 3.13](https://www.python.org/downloads/), [Microsoft Edge WebView2](https://developer.microsoft.com/en-us/microsoft-edge/webview2/), a Vulkan-capable GPU and several GB of free disk space are required. The local configuration has been tested on an RTX 3060 12 GB with 16 GB system RAM; other hardware is unverified.

1. Clone this repository or choose **Code → Download ZIP** on GitHub and extract it.
2. Run **Setup Elsewhere.cmd** once with internet access. It installs dependencies and downloads approximately 3.4 GB of model files plus the runtime.
3. Open **Start Elsewhere.vbs**. Enter a destination in the address bar and press Enter.

Try `google.com`, `a library under the ocean`, or `Wikipedia for imaginary animals`. The start-page examples fill the address bar so you can edit before submitting. Local model startup and generation can take time; you can browse saved pages in another tab while it works.

For a cloud model, open **Settings**, choose OpenAI or Anthropic, select a model or enter its exact ID, and supply your own API key. The panel explains what is sent and that provider API charges apply. Keys stay in backend memory for this session and are forgotten on exit. Every launch defaults to Local. A ChatGPT or Claude subscription is not an API key.

After updating, close and reopen Elsewhere. Existing bookmarks, browsing records and settings stay in your local data directory. Setup does not need to run again for this update.

## Browse, then look behind the page

| Control | What happens |
| --- | --- |
| Address bar · Ctrl+L | Imagine a website, question, idea, or a design with your own criteria. A fresh entry starts an independent interpretation. |
| Links and forms | Imagine the next page with the current site's identity and clicked-topic context. Local sections, menus, filters and dialogs use app-supplied interactions. |
| Back / Forward | Restore saved pages, scroll, ordinary form values and expanded sections without another model call. |
| Reload · Ctrl+R | Restore the saved page without generation. |
| Reimagine | Generate another interpretation, carrying this page's site identity. |
| Tabs · Ctrl+T | Browse another tab while a page builds. Additional generation requests queue; one model task runs at a time. |
| Stop · Escape | Cancel the current tab's generation and keep its preceding page. |
| History | Reopen saved pages. New pages and generation records persist until you clear history. |
| Bookmark · Ctrl+D | Keep a favorite page and its record even when you clear history. Removing a bookmark returns it to saved history. |
| Page details | See the model, parent page, seed where supported, timing, review and refinement; inspect HTML and the generation record. |
| Export HTML / Export record (JSON) | Save a standalone page or a structured record locally for later study or sharing. |

The browser opens on a simple start page. There is no Evaluate workspace, task setup or rating screen. Traceability stays behind the page rather than interrupting exploration.

## What is preserved

Every completed generation saves its page and a separate generation record. The record includes the prompt, parent page ID, clicked link, supplied continuity context, model/provider, sampling settings, instructions, timing, available token usage, original response and any refinement. New records include source-code fingerprints and SHA-256 hashes of the original and saved HTML. Partial responses supplied by the inference adapter are kept when generation fails or is cancelled.

**Export record (JSON)** uses the versioned `elsewhere.page-record` format. It contains the stored HTML/CSS/SVG snapshot and generation record, with original and refined responses kept separate. Opening a saved page reapplies current safety and interaction code; the JSON export preserves the stored snapshot. It does not capture later browser DOM changes or guarantee pixel-identical rendering on another machine. See [the record format](docs/PAGE_RECORDS.md).

Exports include prompts and generated content; linked-page context may contain earlier content or submitted text. Review before sharing. No API keys or automatic machine paths are added to records. Nothing is uploaded automatically. See [Privacy and sharing](PRIVACY.md).

Old evaluation files remain untouched in the local `evaluations` directory. The previous application is preserved in Git under [`pre-browser-focus-2026-10-12`](https://github.com/Rixford/elsewhere/tree/pre-browser-focus-2026-10-12); this version neither loads nor modifies those runs. Older temporary cache entries retain their original expiry behavior; newly generated pages use durable storage.

## The experiment's boundaries

These are model-generated interpretations, **not retrieved websites or verified information**. Familiar logos, coherent prose and working controls do not establish factual accuracy or reveal exactly what is stored in a model's weights. Sites may be surprising, mistaken, beautiful, or broken. Smaller local models and frontier API models can give very different results.

The application supplies a prompt, limited continuity, safe rendering and interactions. Its optional reviewer checks presentation and language with a separate call to the same selected model. At most one refinement runs; original output is retained. Review is not an independent factual judge. A technical review failure keeps an otherwise usable page and displays a notice. Cancellation and explicit provider refusals stop the request; there is no automatic provider fallback.

Generated JavaScript and remote assets are removed. HTML/CSS/SVG pass through a sanitizer, restrictive Content Security Policy and sandbox. The Windows host blocks external page requests, navigation, popups and downloads. Links become prompts for further generation. Sign-ins, purchases and submissions are fictional local interactions.

Local inference runs one Qwen3.5-4B Q4_K_M model through llama.cpp b11007 (Vulkan), bound to authenticated loopback with `--offline`. All normal Local-mode generation and review occur on this computer. Setup is explicitly online; the app never runs it automatically. Cloud inference uses official provider HTTPS endpoints with no browsing or retrieval tools configured by Elsewhere. Provider internals cannot be audited by this application.

Settings control the model, browser dark theme, site continuity, language/structure review and optional screenshot review. Imagined pages keep their own visual style. API calls may include the prompt, continuity, generated HTML and an enabled review screenshot. Review and refinement can add calls and charges. Model access depends on your provider account.

## Local files and development

Setup writes an ignored `runtime-path.txt` pointing to your own runtime and private data. Python dependencies, weights, history, credentials and generated files are excluded from Git. See [portable preference examples](examples/README.md) for a reusable setup without personal configuration.

- `pages/<id>.json` and `<id>.trace.json`: durable page snapshots and generation records, including records for failed attempts.
- `bookmarks/`: favorite page snapshots and records, preserved by Clear history.
- `cache/`: temporary pages created by older versions.
- `history.json`, `domains.json`, `settings.json`: local browsing state and preferences.
- `exports/`: explicit local HTML and JSON exports.

Clear history removes browsing snapshots and traces, resets Back/Forward, and keeps bookmarks and exports. It does not erase old evaluation runs or all logs. Form state is kept in memory for Back/Forward; password and email values are excluded. Repeating a seed does not guarantee identical generation across hardware, context or runtime changes.

Using the interpreter at `<runtime-path>/python/Scripts/python.exe`, run:

```text
python -m unittest -v test_core test_cloud test_records
node test_ui.cjs
node --check web/app.js
node --check web/page-controller.js
python test_browser.py
```

Node.js is only needed for development checks. The last command opens a model-free local fixture with temporary data; it does not represent model quality. `app.py --headless` is also available for development, but rendering validation still needs a frontend. Never share `session.json`, which holds a temporary local authentication token. See [validation evidence](VALIDATION.md) and [changes](CHANGELOG.md).

## License

Application code is **MIT licensed**. Downloaded model/runtime files have their own licenses; see [THIRD_PARTY.md](THIRD_PARTY.md). There is no bundled account, API key or personal browsing data. [Launch drafts](docs/LAUNCH_POSTS.md) are provided for the project owner to adapt.

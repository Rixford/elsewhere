# Elsewhere — rev0

A local imagination browser for Windows. Open **Start Elsewhere.vbs**, type anything in the address bar, and let the model render its learned impression of a website or concept. Familiar domains can evoke recognizable layouts and identities; unfamiliar ideas invite invention. No actual website is fetched or used as a reference.

The application opens on an empty page. The status at bottom left tells you when the local model is ready.

## Install

Windows 10/11 x64, Python 3.13 on PATH, Microsoft Edge WebView2, a Vulkan-capable GPU, and several GB of free disk space are required. Tested on an RTX 3060 12GB with 16GB system RAM; performance on other hardware is unverified.

1. Download or clone this repository.
2. Run **Setup Elsewhere.cmd** once with internet access. Setup installs Python dependencies and downloads about 3.4GB of model weights plus the runtime.
3. Open **Start Elsewhere.vbs**. Subsequent operation is offline.

After updating source files, close and reopen Elsewhere. Setup does not need to run again for rev0. The project is experimental; generated sites and statements are interpretations, not verified information.

## Use

- **Address bar / Ctrl+L:** enter a place, idea, phrase, or address.
- **Links:** continue within the same imagined site, carrying the seed identity/style, the previous page, and the clicked label with nearby text. Local section links scroll within the page. During review, the latest navigation click queues with visible feedback and survives switching tabs; Stop cancels it.
- **Back / Forward:** restore cached pages without generation, including scroll, ordinary form fields and expanded sections. Back during generation cancels it and returns to the previous page.
- **Reload / Ctrl+R:** restore the saved page without running the model.
- **Reimagine:** generate a new interpretation, with a fresh seed.
- **New tab / Ctrl+T:** open another blank page. Switch freely while another tab builds; finished pages, history and bookmarks stay usable. Up to eight tabs; one model task at a time. New requests in other tabs queue automatically, with the latest request retained per tab. Completion never switches your selected tab.
- **Stop / Escape:** cancel the selected tab's model call and retain its previous page. Queued requests in other tabs continue afterward.
- **History:** reopen recent cached pages and the preserved pre-update archive. New unbookmarked pages expire after 24 hours, cleaned up on a later launch.
- **Star / Ctrl+D:** bookmark the current finished page permanently on this computer. The Bookmarks button lists saved pages. Click the filled star to return a bookmark to temporary storage.
- **Page details:** inspect timing, seed, review results, source HTML, and the full generation record. Export saves a standalone HTML file in the local `exports` directory.

The Settings panel controls continuity memory, the validation reviewer, and screenshot review. Turning memory off produces independent interpretations. With memory on, each new page stores a compact seed-site snapshot that persists through subsequent links, including after reopening a bookmark. Fresh address-bar entries start independent interpretations. Older pages recover the nearest preceding seed for that domain when available. This guides the model; perfect narrative or visual consistency is not guaranteed. The reviewer checks presentation and internal consistency only. It must preserve inventions, unusual ideas, and intentional design choices.

All generated JavaScript is removed. The app supplies a small trusted controller for imagined navigation, local anchors, native details/summary, basic tabs/toggles, local filtering, and simulated forms. No accounts, purchases, or other real submissions take place. Exported HTML retains its appearance and local controls; further imagined navigation requires Elsewhere.

## Local model and efficiency

The default installation uses **Qwen3.5-4B Q4_K_M** plus its vision projector through **llama.cpp b11007 (Vulkan)**. Model and projector occupy approximately 3.4 GB on disk. One resident model handles both generation and separate validation contexts. These are reviewer calls, not multiple model copies or collaborating generators.

The pipeline generates a bounded HTML document, parses and sanitizes it, renders it in a separate validation frame, and requests a language/structure review. If enabled and the generated tab is visible, the reviewer also receives a crop of the page viewport. A missing screenshot is recorded accurately as text/structure review. Reviewer-only issues use at most four exact substring edits in one bounded model call. Structural failures can receive one full regeneration. Unapplicable cosmetic edits retain the original with a recorded warning. A failed final layout check preserves your prior page.

App UI and code are small compared with model files. Generation speed varies with page length, screenshot review, refinement, and GPU load. The first request can take longer while the GPU runtime warms up. Nothing pre-generates pages in the background.

## Offline operation

**Setup Elsewhere.cmd** is the explicit one-time online installer; it downloads pinned model/runtime files and verifies their SHA-256 digests. The application never invokes setup or downloads anything on launch. After installation the browser, model, fonts, CSS, illustrations, history, and validation all run locally. No API key or subscription is needed.

Generated pages are isolated in a sandbox without same-origin access. HTML/SVG and CSS are parsed and restricted; remote assets, generated scripts, event handlers, embedded pages, and unsafe navigation are removed. The native host denies external page requests, popups, downloads, and permissions. Content Security Policy denies page network connections. The model server uses `--offline` and loopback-only binding with a random credential. The local app server checks Host, Origin, and a separate session credential. These controls concern Elsewhere; they do not change your computer's network settings or other programs.

## Files and reproducibility

`runtime-path.txt` points to this PC's installed model, runtime, isolated Python environment, and saved data. The physical path may be inside the Codex application's local cache because of Windows app filesystem redirection. The launcher uses that full physical path, so it can be started from Explorer as well.

- `cache/<id>.json`: temporary page and review result, retained for at least the current session and 24 hours.
- `bookmarks/<id>.json`: permanent bookmarked snapshot.
- `pages/<id>.json`: preserved older archive.
- `pages/<id>.trace.json`: prompt, context, seed, original model output, review, any repair, and timings.
- `history.json`, `domains.json`, `settings.json`: local browsing state.
- `exports/`: standalone HTML exports.
- `logs/model.log`, `logs/app.log`: local diagnostics.

The active window starts blank on each launch; prior pages remain in History. Closing the app stops its owned model process. A second launch does not load a second model. New unbookmarked cache entries are removed on startup once older than 24 hours. Bookmarks and the older pages archive are never expired automatically. Form state is held in memory for Back/Forward; password and email field values are excluded. “Repeat seed” reuses the seed, but exact regeneration is not guaranteed across hardware or changed context; a saved snapshot is the exact original.

To explore surprising behavior, compare the same entries with continuity memory on and off, and inspect the original versus reviewed HTML. Coherent invented worlds are interesting observations; the records help distinguish model output from continuity supplied by the application.

## Development and checks

Python dependencies are isolated under the data directory. Node.js is needed only for JavaScript development checks. Run tests using the interpreter at `<runtime-path>/python/Scripts/python.exe`:

```text
python -m unittest -v test_core
node test_ui.cjs
node --check web/app.js
node --check web/page-controller.js
python test_browser.py  # optional deterministic interactive fixture, no model
```

The final small-page smoke test took 68.9 seconds including a validation review and one refinement. Earlier larger examples took 151–193 seconds with refinement. These are measurements on this PC, not latency guarantees; model output length and GPU load matter. See `VALIDATION.md` for the checks and their limits.

`app.py --headless` runs the local HTTP host for development. Rendering validation still requires an attached frontend; there is no fake generated-page fallback. `session.json` contains local diagnostic connection details and a temporary session token; do not share it.

Upstream sources: [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B), [pinned GGUF files](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/tree/e87f176479d0855a907a41277aca2f8ee7a09523), [llama.cpp b11007](https://github.com/ggml-org/llama.cpp/releases/tag/b11007), [pywebview](https://pywebview.flowrl.com/), [WebView2](https://learn.microsoft.com/en-us/microsoft-edge/webview2/).

## License

Application code is MIT licensed. Downloaded model/runtime files have separate licenses; see [THIRD_PARTY.md](THIRD_PARTY.md). Local history, credentials, logs, runtime paths, and weights are excluded from Git. See [CHANGELOG.md](CHANGELOG.md) for rev0 changes.

## Interaction updates after rev0

Expanded panels use document flow, related tabs stay within their own tab group, filter buttons can filter locally, and native dialogs close with their close button or Escape. A bounded layout check on load, expansion and resize returns colliding positioned content to normal flow. Stacked viewport-height sidebars stop sticking over articles. These checks preserve copy and styling where possible; arbitrary model-generated layouts can still need regeneration.

# Privacy and sharing

## What is distributed

This repository contains application source, tests, documentation and the app icon. It does not include a user's installed model/runtime, API keys, session credentials, generated pages, browsing history, bookmarks, exported pages or local machine paths. The public project handle remains in the MIT copyright notice and GitHub's no-reply commit attribution.

Setup discovers the current user's Windows data directory. `runtime-path.txt` is a local installation pointer, not a reusable configuration file. Each person runs setup for their own machine and enters their own optional cloud API key in Settings.

## What stays on the computer

In Local mode, inference uses the installed Qwen model. Generated HTML, prompts, continuity context, generation traces, bookmarks, history and diagnostic logs are stored locally. They can contain whatever you entered or the model generated. Local storage is not encrypted by this application.

History clearing removes recent and archived browsing snapshots and their traces; it intentionally keeps bookmarks and exports. It is not a complete deletion of all application files or logs. API keys stay in backend memory for the session and are forgotten when the application exits. The temporary `session.json` file contains a local authentication token and must not be shared.

## Optional cloud mode

Choosing OpenAI or Anthropic and supplying your own key sends inference requests directly from the backend to that provider's official API. These can contain the prompt, linked-page context, generated HTML and, if enabled and available, a review screenshot. Provider charges and data policies apply. The renderer still blocks real website navigation and remote page assets. Cloud mode is not offline.

## Sharing a fork or reporting a bug

- Publish source from Git, not a ZIP of an installed application/data folder. For a source archive after committing, use `git archive --format=zip --output=elsewhere-source.zip HEAD`.
- Git ignores local runtime/data folders, history, traces, exports, `.env` files, session files and common credential/private-key files. Ignore rules are a convenience; they do not remove previously committed files or recognize every possible secret.
- Inspect `git status` and the staged diff before publishing. Keep real credentials out of source, tests, issue reports and examples. Tests use deliberately fake keys.
- Reproduce bugs with a new, non-personal prompt. Share the error code, model ID and minimal reproduction instead of a complete trace or data directory.
- Check screenshots for API keys, account names, local paths, bookmarks, prompts and unrelated overlays before posting. Do not include Settings or Page details merely to prove the model selection; the status bar is enough.

The included preference template contains no credentials or personal data. It can be reused unchanged or adjusted for each installation.

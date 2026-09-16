# Local update after rev0

- Add portable setup/preference examples, privacy and safe-sharing guidance, and reusable launch-post drafts. Extend Git exclusions for common credential and diagnostic files.
- Preserve usable generated pages when optional cloud review or targeted refinement has a technical failure; report unavailable review without discarding the page. Refusals, cancellation and failed final layout checks remain terminal.
- Use strict OpenAI Structured Outputs schemas for review and targeted edits; record safe API error codes/parameter names and trace pipeline phase/layout for diagnosis.
- Add History → Clear history with confirmation; delete cached/archived history and traces while preserving bookmarks and exports, and reset tab history. Active generation must finish or stop first.
- Add optional OpenAI Responses and Anthropic Claude Messages routing in Settings; local Qwen remains the default on every launch.
- Keep API keys in backend session memory only, disclose cloud data transfer and billing, and retain the selected provider/model throughout each job.
- Handle current streaming formats, Claude workspace headers and structured refusals; keep generated-page network restrictions and never fall back to another provider automatically.
- Add a persistent dark browser theme covering tabs, address bar, panels and status bar, while imagined pages retain their own styling.
- Carry an immutable seed-site identity, content excerpt and style through descendant pages; include the clicked label, destination and nearby text instead of treating generic paths as the topic.
- Recover the nearest preceding seed for older domain-based pages where available; keep fresh address entries independent.
- Keep active generation and its preview attached to the originating tab while other tabs remain usable.
- Queue generation requests from other tabs without cancelling active work; preserve review-time navigation when switching away.
- Opening history or bookmarks in another tab no longer stops active generation. Background completion does not steal focus.
- Retain tab elements across unchanged status polls so clicks and keyboard focus are not disrupted.
- Add permanent bookmarks (star / Ctrl+D) and a bookmarks panel.
- Store new pages in a 24-hour cache; preserve the older archive and bookmark snapshots.
- Restore page scroll, ordinary form values and expanded sections with Back/Forward.
- Back during generation cancels the pending page without skipping the prior page.
- Replace the sandbox frame on navigation to avoid blank restored documents.
- Keep expanded panels in flow; repair positioned content collisions after load/resize/expansion and unstick full-width tall sidebars.
- Add local native dialogs, category filter controls and scoped tabs.
- Add cache-expiry, bookmark-retention and navigation regression coverage.

# rev0

First public source release of the Windows offline imagination browser.

- Generate learned impressions of recognizable sites; unfamiliar concepts remain open to invention.
- Allow a larger illustration budget; prompt for relevant, explicitly sized SVG assets and responsive composition.
- Fresh address entries no longer inherit stale domain styling; onward navigation retains continuity.
- Preserve submit/reset/button inputs and carry action labels and named form values into navigation.
- Queue the latest navigation during review, with visible feedback and tab-aware cancellation.
- Retry layout measurement handshakes during polling and allow 30 seconds for rendering.
- Use bounded exact text replacements for reviewer-only refinements; reserve full regeneration for structural failures.
- Reapply current sanitization/controller fixes when reopening saved pages; original traces stay unchanged.
- Add regression tests, a model-free browser fixture, MIT license, and private-data exclusions.

The resident model remains Qwen3.5-4B Q4_K_M on llama.cpp Vulkan. Alternate
models and CUDA benchmarking are future experiments, not features of rev0.

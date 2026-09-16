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

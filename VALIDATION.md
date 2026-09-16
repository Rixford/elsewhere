# Local interaction/cache update validation

- 23 Python tests and four JavaScript regression scenarios pass.
- Browser fixture: an absolutely positioned expanded paragraph became normal-flow content; a native modal opened and closed.
- Bookmark created and reopened after frontend reload. Backend restart/expiry test confirms permanent retention while expired temporary files are removed; legacy archive remains intact.
- Browser Back/Forward restored input values Nick / Death Knight, the open panel and vertical scroll position 899, without model regeneration.
- Back during an active review returned to the preceding page. Fresh sandbox frames fixed the blank-document restoration observed during this test.
- Inspected the user's Philosophy HTML in isolated temporary test data. Its full-width sticky sidebar retains viewport height when the layout stacks; the controller now returns that pattern to normal flow. Reopened that exact sample and visually confirmed the article reads without the sidebar/filter panel over it.
- Layout recovery is conservative and bounded, not a guarantee against every possible model-generated composition. Desktop model weights and inference runtime are unchanged.

# rev0 validation — 2026-09-16

- 20 Python tests pass, including preservation of submit buttons, saved-page recovery from original traces, fresh-domain context isolation, and exact/ambiguous targeted edits.
- Three JavaScript regression scenarios pass: wide/narrow layout sequencing, late cancellation, and review-time navigation queues carrying the completed parent.
- JavaScript syntax and installed Python dependency checks pass.
- A deterministic browser fixture accepted an Ascend form and navigated with the action, named user input and class preserved. This test uses no model or personal history.
- A live local Qwen3.5-4B test for google.com produced a recognizable light search-oriented page with a colored wordmark, sized search icon, service links and footer. It completed in 51.1 seconds including text review and a targeted refinement. Wide/narrow layout checks passed. This is one sample, not a performance or visual-quality guarantee.
- That sample exposed a false-positive reviewer complaint about colored letter spans. The reviewer prompt was subsequently tightened; its revised judgement has not been benchmarked across a dataset.
- The test used a separate local host and the already-resident model. Native desktop screenshot-review plumbing was not changed. Close and reopen the desktop app to load rev0 backend changes.
- GPU/runtime remains Vulkan with Qwen3.5-4B. No CUDA comparison or alternate-model speed claim is included in this release.

Earlier pre-release measurements follow for context; their counts describe the earlier build.

# Validation — 2026-09-16

Installed and tested on Windows 11, Ryzen 5 5600G, approximately 16 GB system RAM, and an RTX 3060 with 12 GB VRAM.

## Automated checks

- 16 Python regression tests passed: markup sanitation, external HTML/CSS/SVG resource removal, escaped CSS URLs, event-handler stripping, identifier quote normalization, preservation of prose after inline elements, comment removal, nesting/size limits, duplicate IDs, local-link mediation, authentication, origin/host checks, absolute-form request rejection, path containment, arbitrary creative text, and capability-token handling.
- Two JavaScript regression scenarios passed against the actual shell source: duplicate wide-layout events cannot skip the narrow check; a late cancellation response cannot clear a newer job.
- Python compilation, JavaScript syntax checks, and dependency consistency (`pip check`) passed.
- Pinned model, projector, and llama.cpp archive SHA-256 hashes verified at setup.

## Live application checks

- The desktop shortcut launches the native app, with its own icon and an empty page.
- The local model loaded successfully using Vulkan. Token generation measured approximately 50–53 tokens/second during the longer test runs.
- A second launch did not create another model process.
- Generated a Mars library, followed its invented Reading Halls link with continuity context, and generated a separate moon bakery.
- The screenshot provider captured the generated viewport and the local reviewer processed it successfully. Background-tab review correctly reported that it used text/structure without a screenshot.
- Offscreen layout checks ran independently of the visible tab. The bakery's initial version passed at measured content widths of 1249 and 625 pixels. A duplicated-wide-report defect during refinement was then fixed and covered by the JavaScript regression test.
- Back and Forward restored the saved entries without new inference. History persisted across app restarts.
- Escape cancelled a live model call, retained the prior page, and left the model ready. History count did not change.
- Export produced a complete standalone HTML document with its own CSP and no remote `src` or `href` assets.
- During a live generation, the model process's observed established TCP connection was loopback-only. The app reported zero attempted external page requests during the successful smoke tests. Native external-navigation/resource guards and restrictive page CSP were active; inference launched with `--offline`.
- Closing the app stopped its owned model process; it was subsequently relaunched through the installed desktop shortcut.

## Measured examples and limits

| Example | Total time | Result |
|---|---:|---|
| Mars library, early long-output attempt | 223 seconds | Rejected after output and repair exceeded their limit; no partial page published as complete |
| Mars library, second attempt | 151.1 seconds | Saved, with visual/language review and one refinement |
| Reading Halls, followed link | 192.7 seconds | Saved in a background tab, with text review and one refinement |
| Tiny moon bakery | 68.9 seconds | Saved, with visual/language review and one refinement |

Early tests led to compact-output instructions, corrected comment handling, more specific reviewer instructions, and a fix for accidentally escaped identifier attributes. Validators remain fallible; an unconventional or awkward layout is still possible. The refinement budget is intentionally bounded to one pass. A refined page is checked again by code, not by another unbounded chain of model reviewers.

The machine's network adapter was not disabled. Offline readiness was checked through local-only model/runtime operation, renderer isolation and request restrictions, resource inspection, and adversarial containment tests. No claim is made about unrelated Windows or browser background traffic.

The experiment intentionally performs no comparison with real websites and no factual verification of invented content. Continuity across pages is partly supplied by the app's optional stored context; the examples do not establish emergent behavior by themselves.

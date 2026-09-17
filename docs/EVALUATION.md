# Closed-book visual expression protocol v1

Elsewhere probes the model's ability to express learned websites and concepts through code. It also probes transfer: applying an understood structure to an unrelated subject or following a user's new criteria. It does not inspect weights, determine where a fact was learned, establish memorization, or measure general intelligence.

## Tasks and typed criteria

| Type | Example | Human assessment focus |
| --- | --- | --- |
| Familiar website | `wikipedia.org` | Recognizable structure and identity, without requiring today's exact page |
| Thought or concept | `The feeling of remembering a place that never existed` | Translation of meaning into composition, content and visual choices |
| Search or question | `How could cities be quieter without becoming less lively?` | Relevant organization of a question and its possible answers; results are invented, not retrieved |
| Transfer / reinterpretation | `Translate an encyclopedia into a field guide to emotions` | Retention of useful structure while adapting it to a different concept |

Criteria are sent to the generating model verbatim as task data. They may specify content, contrasts, layout, visual metaphors, typography, accessibility or native controls. They are part of the task, not a hidden answer key. Prepare any reference rubric independently and keep it out of the prompt if you want to test recall rather than instruction following.

Human dimensions are intent, criteria, identity/transfer, coherence and visual clarity. The UI uses 1 (misses the goal), 3 (mixed), and 5 (strongly meets it), with intermediate scores and unscored available. Means show the number of rated attempts; unscored does not mean zero. Scores are subjective and should not be presented as standardized benchmark accuracy. Assess factual accuracy externally if needed; this mode supplies no retrieval-based fact check.

## First-response measurement

- Each task/repetition makes one generation call with the same versioned system instructions. No browser history, seed-site memory, screenshot, reference asset or other attempt is supplied. Criteria and task text are logged in the exact user message.
- The original response and its SHA-256 are saved before rendering. Partial output is preserved when the adapter can recover it. A first response is never replaced by a repaired one. Reports include failed/cancelled attempts and scheduled attempts that did not run.
- All rendering still uses the safety sanitizer and sandbox. Browser HTML parsing and sanitation can alter a document; this is not an unrestricted execution benchmark. The report retains parser-error count, removed element types, raw script count, and URL-reference count. A URL string can be a navigation link rather than an asset dependency.
- Evaluation does not inject Explore's CSS reset, collision corrections or simulated navigation/forms/dialogs/tabs. The small trusted controller only measures layout, prevents real submissions/navigation and allows local anchors. Native HTML controls can still work. Interaction correctness is not automatically scored.
- Measurements use 1280 × 720 and 640 × 720 CSS-pixel frames. CSS animations are paused and transitions disabled by the evaluation controller to reduce timing variation. The aggregate structural/width pass requires a stopped completion, no reported structural issues, a closing HTML tag and no measured horizontal overflow. It is not proof of perfect HTML, no overlapping elements, accessibility, visual quality or correct meaning. Parser errors and sanitation changes remain visible separately.
- Optional advisory review uses a separate context in the selected model and cannot modify the original. It is not an independent judge or a score. Technical review failures are recorded; explicit provider refusals stop the remaining batch. No automatic network retry or provider fallback occurs.

## Comparing models

Use **Reuse these tasks**, choose another model in Settings, then run again. Model selection is fixed for the whole active run. Explore and Evaluate share one inference pipeline, so there are no extra model copies.

The report fingerprint covers the task set, exact instructions, token budget, starting seed, fixed viewport policy, recorded OS/Python environment and evaluation-renderer source hashes. Repetition counts may differ and are displayed. A different fingerprint produces a warning rather than hiding the results. This is an aid to comparison, not a guarantee of equivalent inference conditions: tokenizers, provider defaults, model architectures, local versus cloud sampling, fonts and browser versions can differ. Browser versions are not currently captured automatically. Keep the same machine and app build for a controlled comparison.

Local sampling is temperature 0.7, top-p 0.92, top-k 40, with each repetition incrementing the starting seed. Cloud adapters use supported provider settings and no reproducibility seed. GPT-5/6 use low reasoning; cloud output caps add 4,096 tokens for reasoning to the requested budget. A local token budget and a cloud token budget are therefore not identical compute budgets. Settings are recorded rather than hidden.

The UI can hide model labels, but the person selecting a model already knows it. Full records reveal model identity. Truly blind scoring requires another evaluator and an independently randomized set; this release does not claim fully blinded experiments.

## Records, errors, usage and privacy

Run records persist in the local data directory's `evaluations` folder. Startup marks interrupted runs and their unfinished attempts; raw output already saved survives. Human ratings live in a separate file and never rewrite original output. Explore's Clear history does not delete evaluations. Delete a run explicitly in its report; prior exported copies remain.

Generation time, character counts and reported token usage are recorded when available. No prices are guessed. Optional cost estimates use your input/output prices per million tokens, including reported advisory-review usage. They omit unreported failures and cache discounts and are not billing totals. Local token counts are currently unavailable; local timing and characters remain measurable.

Summary exports contain model identity, protocol/task fingerprint and aggregate operational metrics, without prompts, generated code or rating notes. Full exports include those contents and require acknowledgment. Both remain local until you share them. No credentials or machine-specific data-directory paths are put in a run record. Evaluation files and exports are excluded from Git; do not package a working data directory as a source release.

Closed-book means no target retrieval, tools or remote assets configured by Elsewhere. Local mode is offline after installation. Cloud inference still calls the provider over HTTPS; provider-side internals cannot be audited by this application. Interpret outputs as observable behavior under these conditions, not direct evidence of a particular internal representation or emergent memory.

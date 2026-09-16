# Personalize an installation

The easiest way to change preferences is through Settings. This optional template contains the same four persisted preferences as a fresh installation:

| Preference | Meaning |
| --- | --- |
| `memory` | Carry the seed site's identity and recent context through links. |
| `visual` | Include a page screenshot in review when available. In cloud mode this sends the screenshot to the selected provider. |
| `review` | Ask the selected model to review the generated page. Cloud review is another billable API request. Code checks always run. |
| `dark_settings` | Use a dark theme for browser controls and panels; generated pages keep their own styling. The name is retained for compatibility. |

For a repeatable setup, run the installer, close Elsewhere, and copy `settings.example.json` to `settings.json` in the data directory identified by your own `runtime-path.txt`. This replaces the four preferences. Otherwise use Settings to preserve your existing choices. JSON values must be `true` or `false`, not strings.

There are deliberately no provider credentials, usernames, file paths, browsing seeds or saved pages in the template. Select a cloud provider and enter your own API key in Settings for each session. Keys and model selection are not loaded from this file or an `.env` file; every launch defaults to local Qwen.

Harmless starting prompts: `a library on Mars`, `a bakery on the moon`, or `an underwater museum`. Familiar domains are also creative prompts; Elsewhere never visits them.

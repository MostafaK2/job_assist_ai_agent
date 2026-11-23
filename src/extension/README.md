# Job Assist Chrome extension

Fills an application you approved in the Job Assist chat on the real Greenhouse page, in your own
Chrome. It never submits: you check the form and press Submit yourself.

## Install (development)
1. Open `chrome://extensions` and turn on **Developer mode**.
2. Click **Load unpacked** and pick this `src/extension` folder.
3. The ID must be `nkkmkjenpmkclkbephgefeajnomcfmgp` (fixed by the `key` in manifest.json). The chat
   page talks to this ID; set `NEXT_PUBLIC_EXTENSION_ID` in the root `.env` if you change it.
4. After editing these files, press the reload icon on the extension's card.

## How it works
- `background.js`: the chat page (only `http://localhost:3000`, see `externally_connectable`) sends
  it the fill plan; it opens the Greenhouse tab and relays progress back to the chat.
- `content.js`: on Greenhouse pages opened by Job Assist, fills the form and shows a small panel.
  While it fills, the form can't be submitted.
- `fill.js`: finds fields (by Greenhouse name, then label) and fills text boxes, "Select..."
  dropdowns (including search-as-you-type ones like Location), native dropdowns, checkboxes,
  radio buttons and the resume upload.
- `match.js`: picks the right option in code (synonyms, US states, Yes/No wording, word overlap).

Outlines on the page: green = from your profile, amber = written by the assistant, red = needs you.

## Sharing it later
Add your real domain to `externally_connectable`, protect `/api/fills/*` with login, and publish
to the Chrome Web Store.

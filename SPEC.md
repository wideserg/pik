# Cursor Model Price Overlay — MVP spec

Director spec. Implement this, nothing else.

## Goal

Global Windows hotkey reads UI text under the mouse, matches it to Cursor model list prices, shows a click-through tooltip next to the cursor.

## Stack

- Python 3.13 (already installed)
- `uiautomation` (pip) for `ElementFromPoint`
- stdlib: `tkinter` overlay, `ctypes` `RegisterHotKey`, `json`, `re`
- `winocr` + `mss` + `Pillow` for Windows.Media.Ocr fallback when UIA is insufficient
- No AHK, no Electron

## UX

- Hotkey: **Ctrl+Alt+P**
- Tooltip near cursor, `topmost`, no activate, auto-hide ~4s
- Click-through (`WS_EX_TRANSPARENT` + `WS_EX_NOACTIVATE` + `WS_EX_TOOLWINDOW`)
- If no match: show captured text + “no price”
- Console window may stay open (“running — Ctrl+Alt+P, Ctrl+C to quit”)

## Data

`prices.json` is already generated from https://cursor.com/docs/models-and-pricing (2026-08-27, 47 models). Do not invent prices. Do not hardcode a second table.

Show: name, provider, pool, **in / out** per 1M tokens, cache read if present.

Effort labels in the Cursor picker (`High`, `Medium`, `Extra High`, `Low`) are **not** price tiers. Strip them before match.

`Fast` **is** a price tier when it appears in the captured name (`Grok 4.6 (Fast)`, `GPT-5 Fast`). Prefer the Fast row when “fast” is in the haystack.

## Files

```
cursor-model-price/
  prices.json          # already exists — do not overwrite unless regenerating from docs
  requirements.txt
  run.bat
  README.md
  src/app.py           # hotkey loop + overlay
  src/read_ui.py       # UIA text under cursor + OCR fallback
  src/ocr.py           # screenshot strip + Windows.Media.Ocr
  src/match.py         # fuzzy match haystack → model
  src/overlay.py       # tkinter tooltip
  scripts/refresh_prices.py  # fetch https://cursor.com/docs/models-and-pricing.md and rewrite prices.json
```

Keep `scripts/refresh_prices.py` parsing markdown tables the same way as the existing JSON shape.

## Match rules

1. Collect element Name, AutomationId, HelpText, Value, and up to 3 ancestors’ Names.
2. Normalize: lowercase, collapse spaces, strip effort words.
3. Exact alias or name substring wins.
4. Else token overlap / SequenceMatcher; require a reasonable score or return None.
5. If both base and Fast could match, Fast wins only if haystack contains `fast`.

## Capture fallback

If UIA haystack is empty or useless (generic Chromium hwnd names, no model-like tokens), OCR a ~420×70 DIP strip around the cursor via `mss` + Windows.Media.Ocr (`winocr`, en-US). Feed OCR text into the same `match_model()` path.

## Out of scope

Tray icon, autostart, CDP, injecting into Cursor, reading Fast toggle if it’s not in the text, git.

## Run

```
cd D:\My\_Chrome\_apps\_ideas\cursor-model-price
python -m pip install -r requirements.txt
python src\app.py
```

`run.bat` does the same.

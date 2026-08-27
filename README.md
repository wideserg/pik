# Pik

Windows companion for Cursor model picker prices — hover a model, press **Alt+P**, pin cards to compare.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Windows](https://img.shields.io/badge/Windows-10%2B-0078D4?logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)

![Pik demo: hover a model, then Alt+P](assets/pik-demo.mp4)

## Why it exists

I switch models constantly and want to know which one is actually cheaper for the job. You can't inject into Cursor's UI, and the picker isn't one surface — desktop, VS Code, web, agents — so Pik sits outside and reads whatever is under the cursor.

## What it does

- Lives in the system tray; compact welcome window on launch.
- Refreshes model prices once per day from [Cursor's pricing docs](https://cursor.com/docs/models-and-pricing). On startup, shows what changed — price moves and new models.
- **Alt+P** captures the model name under your cursor and spawns a floating price card.
- Pin up to 8 cards, drag them around, compare models side by side.
- Dark / light theme, persisted locally.

## Requirements

- Windows 10 or later
- Python 3.13 ([python.org](https://www.python.org/downloads/))
- English OCR language pack (usually preinstalled; see Notes)

## Install & run

```bat
git clone https://github.com/wideserg/pik.git
cd pik
python -m pip install -r requirements.txt
python src\app.py
```

Or double-click **`run.bat`** (keeps a console open for testing).

### Run at startup (no console)

Double-click **`run-startup.bat`**, or drop a shortcut into your Windows Startup folder. Uses `pythonw.exe` so Pik runs quietly in the tray.

## Usage

| Action | How |
|--------|-----|
| Tray icon | Left-click → welcome window. Right-click → Open / Quit. |
| Welcome | Daily price summary, theme toggle, last-fetch status. |
| Hotkey | Hover a model in Cursor's picker, press **Alt+P**. |
| Cards | Pin (📌) to keep open, drag the title bar, **×** to close. Unpinned cards auto-hide after ~4 s of no hover. |
| Theme | Toggle Light / Dark in the welcome window. |

## Price data

Prices are fetched from https://cursor.com/docs/models-and-pricing and stored in `prices.json`. Pik checks on launch whether today's fetch succeeded; if not, it pulls fresh data and logs any changes.

Manual refresh:

```bat
python scripts\refresh_prices.py
```

## Notes

- **Text capture:** UI Automation under the cursor first; if that fails, a small screenshot strip is OCR'd via **Windows.Media.Ocr** (en-US). No Tesseract, no extra deps.
- **OCR pack:** if OCR fails, install the English pack:
  ```powershell
  Add-WindowsCapability -Online -Name "Language.OCR~~~en-US~0.0.1.0"
  ```
- Cursor does **not** need `--force-renderer-accessibility` — UIA works for the model picker as-is; OCR is the fallback.
- Local state (`theme`, `lastFetch`) is written to `state.json` in the project folder (gitignored).

## Architecture

`app.py` registers the global hotkey and wires tray, welcome, and card manager. `read_ui.py` tries UIA, then `ocr.py` (winocr). `match.py` fuzzy-matches captured text against `prices.json`. `overlay.py` renders Tkinter price cards. `prices.py` handles daily fetch/parse from Cursor docs.

## Contributing

PRs welcome. Keep changes small and focused — this is a single-purpose tray tool, not a framework.

## License

[MIT](LICENSE)

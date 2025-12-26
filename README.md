# Hall Analog Mapper

Hall-effect keyboard to Xbox 360 gamepad mapper. Generic (no vendor VID/PID hardcodes). UI in English; also supports headless mode.

## Features
- Auto-detect analog HID devices by 0xA0 header; wizard for manual selection.
- Saves mappings/settings + device info to `hall_config.json` (legacy `mchose_config.json` read-only).
- Adjustable deadzone, sensitivity, max pressure, response curves; live monitor and stress-test.
- Outputs via ViGEm virtual Xbox 360 pad; headless mode available (`--noui`).

## Requirements
- Windows 10+.
- ViGEmBus driver installed (https://vigem.org/).
- HID-capable hall-effect keyboard.
- If running from source: Python 3.11+, packages `customtkinter`, `hidapi`, `vgamepad`.

## Run (packaged)
- Use the built folder: `dist/HallAnalogMapper/HallAnalogMapper.exe`.
- First run will prompt for device detection; config is saved to `hall_config.json` next to the exe.
- Keep `ViGEmClient.dll` bundled inside the same folder (already included).

## Run from source
```bash
D:/Code/.venv/Scripts/python.exe HallAnalogMapper.py
```
- Optional fast UI mode: `--fast`.
- Headless mode: `--noui`.

## Build a new executable
From the repo root:
```bash
D:/Code/.venv/Scripts/python.exe -m PyInstaller --noconfirm --clean --onedir \
  --name HallAnalogMapper \
  --hidden-import=hid --hidden-import=vgamepad \
  --add-data "D:/Code/.venv/Lib/site-packages/vgamepad/win/vigem/client/x64/ViGEmClient.dll;vgamepad/win/vigem/client/x64" \
  HallAnalogMapper.py
```
Output lands in `dist/HallAnalogMapper/`.

## Config files
- `hall_config.json`: current config; auto-generated on first successful run.
- `mchose_config.json`: legacy fallback read-only.
- You can delete `hall_config.json` to force the detection wizard again.

## Device detection flow
1) Use saved device info if present.
2) Silent auto-scan (0xA0 header) when auto-connect is triggered.
3) Wizard: press-based detection, else manual list selection.

## Notes
- Ensure ViGEmBus driver is installed on any target machine.
- If SmartScreen/AV blocks the exe, unblock in Properties or add an allow rule.

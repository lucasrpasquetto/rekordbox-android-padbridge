# PadBridge

**English** · [Português](README.md)

Turn an Android tablet into a **pad and stem controller for Rekordbox** (Windows), to use next to your DJ controller.

The tablet UI sends MIDI to a small program on your PC (the "bridge"), which writes to a [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) virtual port. Rekordbox reads that port through an **importable mapping file**, so no per-pad MIDI Learn is needed.

```
Tablet (browser)  --USB/Wi-Fi-->  PadBridge (PC)  -->  loopMIDI "PadBridge"  -->  Rekordbox
        ^                                                                            |
        '----------------- stem state (feedback) <-----------------------------------'
```

> Independent project, not affiliated with Pioneer DJ / AlphaTheta or Rekordbox. Trademarks belong to their owners.


![PadBridge screen on the tablet](docs/tela.png)

## Features
- 2 decks side by side, with **zoom** (one big deck) and **fullscreen**
- **Stems** (Vocal / Inst / Bass / Drums) in mute mode, state follows Rekordbox
- 4 pad modes: **Hot Cue** (12 pads, A-L), **Beat Loop** (8), **Sampler** (8 slots, 4 banks), **Keyboard** (8)
- **SHIFT**, **KEY -**, **KEY +**, **KEY SYNC**, **KEY RESET**
- Tray icon, automatic `adb reverse` (USB), start with Windows

## Requirements
| Item | Detail |
|---|---|
| PC | Windows 10 or 11 |
| Rekordbox | 7.x (tested on 7.2) |
| [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) | free, creates the virtual MIDI port |
| Android tablet | designed for 1340x800 landscape; any modern browser |
| [Android platform-tools (adb)](https://developer.android.com/tools/releases/platform-tools) | USB mode only |
| Python 3.12 | only to run from source or build the `.exe` |

## Setup, step by step

### 1. Get PadBridge
```powershell
git clone https://github.com/lucasrpasquetto/rekordbox-android-padbridge.git
cd rekordbox-android-padbridge
```
Then pick **one** way to run it:
- **A) Executable (recommended day to day):** build it with `scripts\construir_exe.bat`. The result is `dist\PadBridge.exe`, a single file that needs no Python. To use it on another computer, copy just that file.
- **B) From source (testing and development):** `scripts\rodar.bat` creates the virtual environment on first run and runs in the terminal.

### 2. Create the loopMIDI port
1. Install and open loopMIDI.
2. In *New port-name* type exactly **`PadBridge`** and click **+**.
3. In loopMIDI's settings enable **Autostart loopMIDI**.

There must be **only one** port named `PadBridge`.

### 3. Import the mapping in Rekordbox
1. Open Rekordbox **after** loopMIDI (it only reads MIDI ports at startup).
2. Go to *Preferences > Controller > MIDI tab*.
3. Select the **PadBridge** device and **Import** `mapping/PadBridge.midi.csv` from this repository.

This is done once per Rekordbox installation.

### 4. Install adb (USB mode)
1. Download [platform-tools](https://developer.android.com/tools/releases/platform-tools) and extract it to `C:\platform-tools`, so that `C:\platform-tools\adb.exe` exists.
2. The bridge looks for adb on its own in `C:\platform-tools`, `C:\adb`, the Android SDK folder, a `platform-tools` folder next to the program, and the `PATH`. Anywhere else: use `--adb` or the `adb` field of `padbridge_config.json`.

### 5. Prepare the tablet
1. Enable **Developer options** (tap *Build number* 7 times under About tablet).
2. Enable **USB debugging**.
3. Plug in the cable and set USB mode to **File transfer**.
4. Accept *Allow USB debugging?* and tick *Always allow*.

### 6. Run
1. Start the bridge: `dist\PadBridge.exe` (tray icon) or `scripts\rodar.bat` (terminal).
2. In the tablet browser open **`http://localhost:8765`**. Tip: add it to the home screen.
3. In Rekordbox load a track and tap a pad.

## Daily use
1. Boot the PC: loopMIDI and PadBridge start by themselves (tick *Iniciar com o Windows* in the tray menu).
2. Open Rekordbox.
3. Plug in the tablet and open `http://localhost:8765`.

Tray icon: **green** = tablet connected, **yellow** = waiting for the tablet, **red** = problem (e.g. loopMIDI closed). Right-click for MIDI/USB status, the last state from Rekordbox, reconnect, program folder and log.

## Wi-Fi (no cable)
```powershell
scripts\rodar.bat --wifi
```
On the tablet open `http://PC-IP:8765` (see `ipconfig`). Both must be on the same network. Allow Python/PadBridge through Windows Firewall on **Private networks**, or open the port (PowerShell as administrator):
```powershell
New-NetFirewallRule -DisplayName "PadBridge" -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow -Profile Private
```
Without `--wifi` the bridge only accepts connections from the PC itself.

## Options
```
--console        run in the terminal, no tray icon
--debug          print all MIDI sent and received
--porta NAME     part of the loopMIDI port name (default: PadBridge)
--http 8765      server port
--wifi           accept network connections besides USB
--adb PATH       path to adb.exe
--sem-adb        do not run adb reverse automatically
--sem-feedback   do not listen to MIDI coming from Rekordbox (diagnostics)
```
Defaults can be stored in `padbridge_config.json` next to the program (`porta_midi`, `http`, `wifi`, `adb`, `usar_adb`, `feedback`). The log is `padbridge.log` in the same folder.

## Troubleshooting
| Symptom | What to do |
|---|---|
| Pads react on screen but Rekordbox does not | Run with `--debug`. You should see `[enviado]` followed by `[chegou] ... (eco do que enviamos)`. No `[chegou]` means the loopMIDI port is stuck: remove it, restart loopMIDI and recreate `PadBridge`. If it appears, check that the **PadBridge** device is selected in Rekordbox and restart Rekordbox. |
| Console says the MIDI port was not found | loopMIDI must be running with a `PadBridge` port. For another name use `--porta`. |
| `localhost:8765` does not open on the tablet | `adb reverse` is not active. Check the tray icon or log: install adb, accept USB debugging on the tablet, use *Reconectar o tablet agora*. |
| PC IP keeps loading | You did not use `--wifi`, or the firewall blocks it. See the Wi-Fi section. |
| A "PadBridge 2" device shows up in Rekordbox | Duplicate ports in loopMIDI. Keep only one. |
| Tablet stems do not follow Rekordbox | Use the current `PadBridge.midi.csv` and restart Rekordbox after importing it. |
| SmartScreen warns about the `.exe` | Common for unsigned programs. Build the `.exe` yourself from source. |

## Development
```powershell
pip install -r requirements-dev.txt
python tools/gerar.py          # regenerates mapping/PadBridge.midi.csv and padbridge/web/index.html
python tests/test_servico.py
python tests/test_ui.py        # needs: playwright install chromium
```
Protocol details (Portuguese): [docs/PROTOCOLO.md](docs/PROTOCOLO.md). The UI and the mapping come from the same generator, so they stay consistent.

## Limitations
- Groove Circuit and Slide FX are not included (plan/extension required, or no MIDI response).
- Stems work in MUTE mode only, which is Rekordbox's default.
- Windows only.

## License
MIT. See [LICENSE](LICENSE).

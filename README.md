<p align="center"><img src="voicefx/assets/icon.png" width="96" alt="VoiceFX"></p>

<h1 align="center">VoiceFX</h1>

<p align="center">
  <b>English</b> · <a href="README.ko.md">한국어</a> · <a href="README.ja.md">日本語</a> · <a href="README.zh-CN.md">简体中文</a>
</p>

A real-time voice changer + soundboard for Windows that works with Discord, games and OBS.

```
[Your mic] → VoiceFX (noise suppression → voice effects) ─┬→ CABLE Input ──(VB-CABLE)──> CABLE Output → Discord
                                   Soundboard ────────────┘  └→ Headphones (hear yourself)
```

## Screenshots
<table>
  <tr><td width="50%"><img src="docs/screenshots/voices.png" alt="Voices — fine-tune the selected voice"><br><sub>Voices — fine-tune the selected voice</sub></td><td width="50%"><img src="docs/screenshots/custom-voice.png" alt="Create your own voice from effect modules"><br><sub>Create your own voice from effect modules</sub></td></tr>
  <tr><td width="50%"><img src="docs/screenshots/soundboard.png" alt="Soundboard"><br><sub>Soundboard</sub></td><td width="50%"><img src="docs/screenshots/shortcut-map.png" alt="Shortcut map"><br><sub>Shortcut map</sub></td></tr>
</table>

## Install
1. Download **`VoiceFX-Setup-x.y.z.exe`** from [Releases](../../releases) and run it. No administrator rights needed.
   To run without installing, unzip `VoiceFX-x.y.z-portable.zip` and run `VoiceFX.exe`.
2. If **VB-CABLE** (a free virtual audio device) is missing, the installer opens its download page at the end.
   Unzip it, **run `VBCABLE_Setup_x64.exe` as administrator** → Install Driver → restart.
3. VoiceFX turns on as soon as it starts. It makes `CABLE Output` the Windows default microphone, so if Discord's
   input device is **Default** there is nothing else to set up. Turning it off or quitting restores your original mic.
4. In Discord **User Settings → Voice & Video**, set **Noise Suppression** to **None**.
   Discord's noise suppression removes voice effects and soundboard sounds as "noise"; VoiceFX's own noise suppression
   takes over that job. Turning off Echo Cancellation and Automatic Gain Control also helps.

Requirements: Windows 10/11 64-bit, Microsoft Edge WebView2 Runtime (built into Windows 11), VB-CABLE.

## Features
- **22 voices**: Female, Male, Baby, Helium, Giant, Monster, Demon, Space villain, Robot, Alien, Ghost, Walkie-talkie,
  Telephone, Megaphone, Underwater, Cave, Stadium, 8-bit and more. Select a voice to fine-tune pitch, timbre, reverb and
  other key values in the right panel — changes apply instantly, even mid-call, and are saved automatically.
- **Create your own voices**: combine 12 effect modules (Pitch, Low cut, EQ, Ring modulator, Distortion, Bitcrush,
  High cut, Chorus, Phaser, Echo, Reverb, Compressor), tweak every value, and save it as a preset card with your own
  name, icon and color. You can also start from a copy of any built-in voice.
- **Soundboard**: add sounds with **＋ Add sounds** or by dragging files onto the window (wav · mp3 · flac · ogg, up to
  3 minutes). Sounds reach others untouched by voice effects or noise suppression, and you hear them too when
  "Also play to me" is on. The 14 default sounds are CC0 (public domain) sounds from freesound.org
  (`voicefx/assets/sounds/CREDITS.md`).
- **Noise suppression**: RNNoise-based. Removes keyboard, fan and background noise from your mic only.
- **Shortcuts**: no defaults — assign your own. Voices and sounds in the right panel; voice changer / hear myself /
  stop all sounds in Settings, or click any key on the **Shortcut map** (keyboard view) in Settings. They work even
  when another window is focused. If they don't work inside a game running as administrator, run VoiceFX as administrator too.
- **Favorites**: click ★ on a card to pin it to the top.
- **Languages**: 한국어 · English · 日本語 · 简体中文. Settings → Display → Language (defaults to your Windows language).

Settings, sounds and logs are stored in `%APPDATA%\VoiceFX` (`settings.json`, `sounds\`, `voicefx.log`).

## Development
```
pip install -r requirements.txt
python -m voicefx
```
Developed and tested with Python 3.10 (64-bit).

| File | Role |
|---|---|
| `voicefx/launcher.py` | Entry point: logging, single instance, `--restore` (restores the mic on uninstall) |
| `voicefx/engine.py` | Audio engine: mic → noise suppression → effects → virtual cable / monitor, sound mixer, jitter buffer |
| `voicefx/dsp.py` | Rubber Band R3 real-time pitch shifter (pitch and formant separately), RNNoise, ring modulator |
| `voicefx/presets.py` | 12 effect modules and the built-in voices (module recipe + values) |
| `voicefx/controller.py` | Settings, devices, custom voices, soundboard, shortcuts, default mic / VB-CABLE switching and restore |
| `voicefx/soundboard.py` | Adding/decoding/removing sound files, default sounds |
| `voicefx/windefault.py` | Windows default recording device and device enable/disable (IPolicyConfig) |
| `voicefx/i18n.py`, `voicefx/locales/` | Translations (Korean source text → translation) |
| `voicefx/webui.py`, `voicefx/ui/index.html` | GUI (pywebview) |
| `tools/` | Voice tuning, default sound fetching, icon generation, translation tools |

To add a built-in voice, add a module recipe (`recipe`) and the panel's key sliders (`quick`) to `PRESETS` in
`presets.py`, then listen and tune with `python tools/render_presets.py --record 5 --only <key>`.

### Translations
The Korean source text is the translation key (`t("...")` in Python, `T("...")` in the UI; other on-screen text is
translated automatically). After adding or changing text:
```
python tools/i18n_check.py          # check missing translations per language
# add a row (Korean, English, 日本語, 简体中文) to ROWS in tools/i18n_table.py
python tools/i18n_table.py          # regenerate voicefx/locales/*.json
```
To add a language, add it to `LANGUAGES` in `voicefx/i18n.py` and add a column in `tools/i18n_table.py`.

## Build
Requires [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`).
```
pip install pyinstaller
powershell -ExecutionPolicy Bypass -File build.ps1
```
Output: `dist\VoiceFX\VoiceFX.exe`, `dist\VoiceFX-x.y.z-portable.zip`, `dist\VoiceFX-Setup-x.y.z.exe`.
If the VoiceFX in `dist` is running it can't be overwritten — close it or build to another folder with `-OutDir dist-test`.

## Release (GitHub Releases)
1. Bump `__version__` in `voicefx/__init__.py` and commit.
2. Push a tag with the same version: `git tag v0.1.0` → `git push origin v0.1.0`
3. GitHub Actions (`.github/workflows/release.yml`) builds on Windows and uploads the installer and portable zip to a
   **draft release**. Review it, then click **Publish release** on GitHub.

The app is not code-signed, so Windows SmartScreen may warn on first run ("Windows protected your PC") → More info → Run anyway.

## License
[GPL-3.0](LICENSE). VoiceFX bundles GPL-licensed libraries — the Rubber Band library (via pylibrb) and pedalboard — so the
app as a whole is distributed under GPL-3.0. Other libraries: RNNoise (BSD), pywebview (BSD), sounddevice/PortAudio (MIT),
numpy (BSD), keyboard (MIT), pycaw (MIT), comtypes (MIT). VB-CABLE is not bundled; users install it themselves.
The default sounds are CC0 (`voicefx/assets/sounds/CREDITS.md`).

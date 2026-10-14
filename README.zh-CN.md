<p align="center"><img src="voicefx/assets/icon.png" width="96" alt="VoiceFX"></p>

<h1 align="center">VoiceFX</h1>

<p align="center">
  <a href="README.md">English</a> · <a href="README.ko.md">한국어</a> · <a href="README.ja.md">日本語</a> · <b>简体中文</b>
</p>

适用于 Discord、游戏和 OBS 的 Windows 实时变声器 + 音效板。

```
[你的麦克风] → VoiceFX（噪声抑制 → 变声效果）─┬→ CABLE Input ──(VB-CABLE)──> CABLE Output → Discord
                          音效板 ────────────┘  └→ 耳机（监听自己）
```

## 截图
<table>
  <tr><td width="50%"><img src="docs/screenshots/voices.png" alt="变声 — 调整所选变声"><br><sub>变声 — 调整所选变声</sub></td><td width="50%"><img src="docs/screenshots/custom-voice.png" alt="用效果模块制作自己的变声"><br><sub>用效果模块制作自己的变声</sub></td></tr>
  <tr><td width="50%"><img src="docs/screenshots/soundboard.png" alt="音效板"><br><sub>音效板</sub></td><td width="50%"><img src="docs/screenshots/shortcut-map.png" alt="快捷键地图"><br><sub>快捷键地图</sub></td></tr>
</table>

## 安装
1. 从 [Releases](../../releases) 下载 **`VoiceFX-Setup-x.y.z.exe`** 并运行。无需管理员权限。
   如不想安装，可解压 `VoiceFX-x.y.z-portable.zip` 后运行 `VoiceFX.exe`。
2. 如果没有 **VB-CABLE**（免费的虚拟音频设备），安装结束时会打开下载页面。
   解压后 **以管理员身份运行 `VBCABLE_Setup_x64.exe`** → Install Driver → 重启。
3. VoiceFX 启动后会立即开启。它会把 Windows 默认麦克风切换为 `CABLE Output`，
   因此只要 Discord 的输入设备是 **Default** 就无需其他设置。关闭或退出后会恢复原来的麦克风。
4. 在 Discord **用户设置 → 语音和视频** 中，将 **噪声抑制** 设为 **无**。
   Discord 的噪声抑制会把变声效果和音效当成噪音去掉；降噪改由 VoiceFX 自带的噪声抑制负责。
   同时关闭回声消除和自动增益控制，效果会更清晰。

系统要求：Windows 10/11 64 位、Microsoft Edge WebView2 运行时（Windows 11 已内置）、VB-CABLE。

## 功能
- **22 种变声**：女声、男声、婴儿、氦气、巨人、怪物、恶魔、太空反派、机器人、外星人、幽灵、对讲机、电话、扩音器、水下、山洞、
  体育场、8 位等。选中变声后，可在右侧面板调整音高、音色、混响等关键参数（通话中也会立即生效，并自动保存）。
- **制作自己的变声**：组合 12 种效果模块（音高、低切、均衡器、环形调制器、失真、降位、高切、合唱、相位器、回声、混响、压缩器），
  调整所有参数，并设置名称、图标和颜色，保存为预设卡片。也可以从内置变声复制后开始。
- **音效板**：点击 **＋ 添加音效** 或将文件拖到窗口中即可添加（wav · mp3 · flac · ogg，3 分钟以内）。
  音效不经过变声和噪声抑制，原样传给对方；打开“自己也能听到”后，你的耳机里也能听到。
  14 个默认音效来自 freesound.org 的 CC0（公共领域）声音（`voicefx/assets/sounds/CREDITS.md`）。
- **噪声抑制**：基于 RNNoise，只去除麦克风中的键盘声、风扇声和环境噪音。
- **快捷键**：没有默认值，由你自己分配。变声和音效在右侧面板设置；变声开关、监听自己、停止所有音效在设置中设置，
  也可以在设置里的 **快捷键地图**（键盘图）上点击按键分配。即使其他窗口在前台也能使用。
  如果在以管理员身份运行的游戏中无效，请同样以管理员身份运行 VoiceFX。
- **收藏**：点击卡片上的 ★ 即可置顶。
- **语言**：한국어 · English · 日本語 · 简体中文。设置 → 显示 → 语言（默认跟随 Windows 语言）。

设置、音效和日志保存在 `%APPDATA%\VoiceFX`（`settings.json`、`sounds\`、`voicefx.log`）。

## 开发
```
pip install -r requirements.txt
python -m voicefx
```
使用 Python 3.10（64 位）开发和测试。

| 文件 | 作用 |
|---|---|
| `voicefx/launcher.py` | 入口：日志、防止多开、`--restore`（卸载时恢复麦克风） |
| `voicefx/engine.py` | 音频引擎：麦克风 → 噪声抑制 → 效果 → 虚拟线缆/监听，音效混音器，抖动缓冲 |
| `voicefx/dsp.py` | Rubber Band R3 实时变调器（音高与音色分离）、RNNoise、环形调制器 |
| `voicefx/presets.py` | 12 种效果模块和内置变声（模块组合 + 参数） |
| `voicefx/controller.py` | 设置、设备、自制变声、音效板、快捷键、默认麦克风与 VB-CABLE 的切换和恢复 |
| `voicefx/soundboard.py` | 音效文件的添加、解码、删除，默认音效 |
| `voicefx/windefault.py` | Windows 默认录音设备及设备启用/禁用（IPolicyConfig） |
| `voicefx/i18n.py`、`voicefx/locales/` | 多语言（韩语原文 → 译文） |
| `voicefx/webui.py`、`voicefx/ui/index.html` | 图形界面（pywebview） |
| `tools/` | 变声调试、获取默认音效、生成图标、翻译工具 |

要添加内置变声，请在 `presets.py` 的 `PRESETS` 中加入模块组合（`recipe`）和面板显示的关键滑块（`quick`），
然后用 `python tools/render_presets.py --record 5 --only <键>` 试听并调整。

### 翻译
韩语原文本身就是翻译键（Python 中为 `t("...")`，界面中为 `T("...")`，其余界面文字会自动翻译）。
添加或修改文字后：
```
python tools/i18n_check.py          # 检查各语言缺失的翻译
# 在 tools/i18n_table.py 的 ROWS 中添加一行（韩语, English, 日本語, 简体中文）
python tools/i18n_table.py          # 生成 voicefx/locales/*.json
```
如需添加语言，在 `voicefx/i18n.py` 的 `LANGUAGES` 和 `tools/i18n_table.py` 中各加一列即可。

## 构建
需要 [Inno Setup 6](https://jrsoftware.org/isinfo.php)（`winget install JRSoftware.InnoSetup`）。
```
pip install pyinstaller
powershell -ExecutionPolicy Bypass -File build.ps1
```
输出：`dist\VoiceFX\VoiceFX.exe`、`dist\VoiceFX-x.y.z-portable.zip`、`dist\VoiceFX-Setup-x.y.z.exe`。
如果 `dist` 中的 VoiceFX 正在运行则无法覆盖，请先关闭，或用 `-OutDir dist-test` 指定其他文件夹。

## 发布（GitHub Releases）
1. 提高 `voicefx/__init__.py` 中的 `__version__` 并提交。
2. 推送相同版本的标签：`git tag v0.1.0` → `git push origin v0.1.0`
3. GitHub Actions（`.github/workflows/release.yml`）会在 Windows 上构建，并把安装程序和便携版 zip 上传到 **草稿（draft）发布**。
   确认内容后，在 GitHub 上点击 **Publish release** 即可公开。

程序没有代码签名，首次运行时 Windows SmartScreen 可能会提示（“Windows 已保护你的电脑”）→ 更多信息 → 仍要运行。

## 许可证
[GPL-3.0](LICENSE)。由于包含 GPL 库（Rubber Band（pylibrb）、pedalboard），整个应用以 GPL-3.0 发布。
其他库：RNNoise（BSD）、pywebview（BSD）、sounddevice/PortAudio（MIT）、numpy（BSD）、keyboard（MIT）、pycaw（MIT）、comtypes（MIT）。
VB-CABLE 不随附，需由用户自行安装。默认音效为 CC0（`voicefx/assets/sounds/CREDITS.md`）。

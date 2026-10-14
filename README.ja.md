<p align="center"><img src="voicefx/assets/icon.png" width="96" alt="VoiceFX"></p>

<h1 align="center">VoiceFX</h1>

<p align="center">
  <a href="README.md">English</a> · <a href="README.ko.md">한국어</a> · <b>日本語</b> · <a href="README.zh-CN.md">简体中文</a>
</p>

Discord・ゲーム・OBS で使える Windows 用リアルタイム ボイスチェンジャー + サウンドボード。

```
[実際のマイク] → VoiceFX（ノイズ抑制 → ボイスエフェクト）─┬→ CABLE Input ──(VB-CABLE)──> CABLE Output → Discord
                            サウンドボード ──────────────┘  └→ ヘッドホン（自分の声を聞く）
```

## スクリーンショット
<table>
  <tr><td width="50%"><img src="docs/screenshots/voices.png" alt="ボイス — 選んだボイスを細かく調整"><br><sub>ボイス — 選んだボイスを細かく調整</sub></td><td width="50%"><img src="docs/screenshots/custom-voice.png" alt="エフェクトモジュールでマイボイスを作成"><br><sub>エフェクトモジュールでマイボイスを作成</sub></td></tr>
  <tr><td width="50%"><img src="docs/screenshots/soundboard.png" alt="サウンドボード"><br><sub>サウンドボード</sub></td><td width="50%"><img src="docs/screenshots/shortcut-map.png" alt="ショートカットマップ"><br><sub>ショートカットマップ</sub></td></tr>
</table>

## インストール
1. [Releases](../../releases) から **`VoiceFX-Setup-x.y.z.exe`** をダウンロードして実行します。管理者権限は不要です。
   インストールせずに使う場合は `VoiceFX-x.y.z-portable.zip` を展開して `VoiceFX.exe` を実行してください。
2. **VB-CABLE**（無料の仮想オーディオデバイス）がない場合、インストールの最後にダウンロードページが開きます。
   展開して **`VBCABLE_Setup_x64.exe` を管理者として実行** → Install Driver → 再起動。
3. VoiceFX は起動するとすぐにオンになります。Windows の既定のマイクを `CABLE Output` に切り替えるので、
   Discord の入力デバイスが **Default** なら追加の設定は不要です。オフにするか終了すると元のマイクに戻ります。
4. Discord の **ユーザー設定 → 音声・ビデオ** で **ノイズ抑制** を **なし** にしてください。
   Discord のノイズ抑制はボイスエフェクトやサウンドボードの音をノイズとして消してしまいます。ノイズ除去は VoiceFX のノイズ抑制が代わりに行います。
   エコー除去と自動ゲイン調整もオフにすると、よりきれいに伝わります。

動作環境: Windows 10/11 64 ビット、Microsoft Edge WebView2 ランタイム（Windows 11 には標準搭載）、VB-CABLE。

## 機能
- **22 種類のボイス**: 女性・男性・赤ちゃん・ヘリウム・巨人・モンスター・悪魔・宇宙の悪役・ロボット・宇宙人・幽霊・無線機・電話・
  拡声器・水中・洞窟・スタジアム・8 ビットなど。ボイスを選ぶと右パネルで声の高さ・声質・響きなどを調整できます（通話中でもすぐに反映、自動保存）。
- **マイボイス作成**: 12 種類のエフェクトモジュール（ピッチ・低音カット・EQ・リングモジュレーター・ディストーション・ビットクラッシュ・
  高音カット・コーラス・フェイザー・エコー・リバーブ・コンプレッサー）を組み合わせてすべての値を調整し、名前・アイコン・色を付けて
  プリセットカードとして保存できます。既存のボイスをコピーして始めることもできます。
- **サウンドボード**: **＋ サウンドを追加** またはファイルをウィンドウにドラッグして追加（wav・mp3・flac・ogg、3 分以内）。
  ボイスエフェクトやノイズ抑制を通らずにそのまま相手に届き、「自分にも聞こえるように」がオンなら自分のヘッドホンでも聞こえます。
  標準サウンド 14 種類は freesound.org の CC0（パブリックドメイン）の音です（`voicefx/assets/sounds/CREDITS.md`）。
- **ノイズ抑制**: RNNoise ベース。マイクのキーボード音・ファン音・生活音だけを消します。
- **ショートカット**: 初期設定はなく、自分で割り当てます。ボイス・サウンドは右パネルで、ボイスチェンジ／自分の声を聞く／すべて停止は
  設定で、または設定の **ショートカットマップ**（キーボード図）でキーを押して設定します。他のウィンドウが前面にあっても動作します。
  管理者として実行したゲーム内で効かない場合は、VoiceFX も管理者として実行してください。
- **お気に入り**: カードの ★ を押すと一覧の上部にまとまります。
- **言語**: 한국어・English・日本語・简体中文。設定 → 表示 → 言語（初期値は Windows の言語）。

設定・サウンド・ログは `%APPDATA%\VoiceFX` に保存されます（`settings.json`、`sounds\`、`voicefx.log`）。

## 開発
```
pip install -r requirements.txt
python -m voicefx
```
Python 3.10（64 ビット）で開発・テストしています。

| ファイル | 役割 |
|---|---|
| `voicefx/launcher.py` | エントリーポイント: ログ、多重起動防止、`--restore`（アンインストール時のマイク復元） |
| `voicefx/engine.py` | マイク → ノイズ抑制 → エフェクト → 仮想ケーブル/モニターのオーディオエンジン、サウンドミキサー、ジッターバッファー |
| `voicefx/dsp.py` | Rubber Band R3 リアルタイム ピッチシフター（高さと声質を分離）、RNNoise、リングモジュレーター |
| `voicefx/presets.py` | 12 種類のエフェクトモジュールと標準ボイス（モジュールの組み合わせ + 値） |
| `voicefx/controller.py` | 設定、デバイス、マイボイス、サウンドボード、ショートカット、既定のマイク・VB-CABLE の切り替えと復元 |
| `voicefx/soundboard.py` | サウンドファイルの追加・デコード・削除、標準サウンド |
| `voicefx/windefault.py` | Windows の既定の録音デバイス・デバイスの有効/無効の変更（IPolicyConfig） |
| `voicefx/i18n.py`、`voicefx/locales/` | 多言語対応（韓国語の原文 → 翻訳） |
| `voicefx/webui.py`、`voicefx/ui/index.html` | GUI（pywebview） |
| `tools/` | ボイス調整、標準サウンドの取得、アイコン生成、翻訳ツール |

標準ボイスを追加するには、`presets.py` の `PRESETS` にモジュールの組み合わせ（`recipe`）とパネル用の主要スライダー（`quick`）を追加し、
`python tools/render_presets.py --record 5 --only <キー>` で聞きながら調整します。

### 翻訳
韓国語の原文がそのまま翻訳キーです（Python では `t("...")`、画面では `T("...")`、それ以外の画面の文字は自動で翻訳）。
文章を追加・変更したら:
```
python tools/i18n_check.py          # 言語ごとの未翻訳を確認
# tools/i18n_table.py の ROWS に (韓国語, English, 日本語, 简体中文) を 1 行追加
python tools/i18n_table.py          # voicefx/locales/*.json を生成
```
言語を追加するには `voicefx/i18n.py` の `LANGUAGES` と `tools/i18n_table.py` に列を 1 つ追加します。

## ビルド
[Inno Setup 6](https://jrsoftware.org/isinfo.php) が必要です（`winget install JRSoftware.InnoSetup`）。
```
pip install pyinstaller
powershell -ExecutionPolicy Bypass -File build.ps1
```
出力: `dist\VoiceFX\VoiceFX.exe`、`dist\VoiceFX-x.y.z-portable.zip`、`dist\VoiceFX-Setup-x.y.z.exe`。
`dist` の VoiceFX を実行中だと上書きできないので、終了するか `-OutDir dist-test` のように別のフォルダーを指定してください。

## 配布（GitHub Releases）
1. `voicefx/__init__.py` の `__version__` を上げてコミットします。
2. 同じバージョンでタグを push します: `git tag v0.1.0` → `git push origin v0.1.0`
3. GitHub Actions（`.github/workflows/release.yml`）が Windows でビルドし、インストーラーとポータブル zip を **下書き（draft）リリース** にアップロードします。
   内容を確認したら GitHub で **Publish release** を押すと公開されます。

コード署名がないため、初回起動時に Windows SmartScreen の警告（「Windows によって PC が保護されました」）が出ることがあります。詳細情報 → 実行。

## ライセンス
[GPL-3.0](LICENSE)。GPL ライブラリ（Rubber Band（pylibrb）、pedalboard）を同梱しているため、アプリ全体を GPL-3.0 で配布します。
その他のライブラリ: RNNoise（BSD）、pywebview（BSD）、sounddevice/PortAudio（MIT）、numpy（BSD）、keyboard（MIT）、pycaw（MIT）、
comtypes（MIT）。VB-CABLE は同梱せず、ユーザーが各自インストールします。標準サウンドは CC0 です（`voicefx/assets/sounds/CREDITS.md`）。

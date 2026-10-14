; VoiceFX 설치 프로그램 (Inno Setup 6)
;   iscc installer\VoiceFX.iss /DAppVersion=0.1.0      → dist\VoiceFX-Setup-0.1.0.exe
; 먼저 `pyinstaller VoiceFX.spec --noconfirm`으로 dist\VoiceFX 를 만들어 둬야 한다.

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef DistDir
  #define DistDir "..\dist"
#endif
#define AppName "VoiceFX"
#define AppExe "VoiceFX.exe"
#define CableUrl "https://vb-audio.com/Cable/"

[Setup]
AppId={{6F3C2A57-8E0B-4C1D-9B7A-5D2E1F0A9C41}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Eastar0102
AppPublisherURL=https://github.com/Eastar0102/VoiceFX
AppSupportURL=https://github.com/Eastar0102/VoiceFX/issues
AppUpdatesURL=https://github.com/Eastar0102/VoiceFX/releases
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; 관리자 권한 없이 사용자 폴더에 설치
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#DistDir}
OutputBaseFilename=VoiceFX-Setup-{#AppVersion}
SetupIconFile=..\voicefx\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; 업데이트 설치 시 실행 중인 VoiceFX를 자동으로 닫는다
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[CustomMessages]
korean.DesktopIcon=바탕화면에 바로가기 만들기
english.DesktopIcon=Create a desktop shortcut
japanese.DesktopIcon=デスクトップにショートカットを作成
korean.LaunchApp=VoiceFX 실행
english.LaunchApp=Launch VoiceFX
japanese.LaunchApp=VoiceFX を起動
korean.NeedCable=VoiceFX를 Discord에서 쓰려면 무료 가상 오디오 장치 VB-CABLE이 필요한데, 이 PC에는 설치되어 있지 않습니다.%n%n지금 다운로드 페이지를 열까요?%n(압축을 풀고 VBCABLE_Setup_x64.exe를 관리자 권한으로 실행 → Install Driver → 재부팅)
english.NeedCable=VoiceFX needs the free VB-CABLE virtual audio device, which is not installed on this PC.%n%nOpen the download page now?%n(Unzip it, run VBCABLE_Setup_x64.exe as administrator → Install Driver → restart)
japanese.NeedCable=Discord で VoiceFX を使うには無料の仮想オーディオデバイス VB-CABLE が必要ですが、この PC にはインストールされていません。%n%n今すぐダウンロードページを開きますか？%n（展開して VBCABLE_Setup_x64.exe を管理者として実行 → Install Driver → 再起動）
korean.RemoveData=설정과 추가한 사운드(%APPDATA%\VoiceFX)도 삭제할까요?
english.RemoveData=Also delete settings and added sounds (%APPDATA%\VoiceFX)?
japanese.RemoveData=設定と追加したサウンド (%APPDATA%\VoiceFX) も削除しますか？

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; Flags: unchecked

[Files]
Source: "{#DistDir}\VoiceFX\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; 실행 중인 VoiceFX를 닫고, 바꿔 둔 기본 마이크·VB-CABLE 상태를 원래대로 되돌린다
Filename: "{app}\{#AppExe}"; Parameters: "--restore"; Flags: waituntilterminated runhidden; RunOnceId: "RestoreAudio"

[Code]
function CableInstalled(): Boolean;
begin
  Result := RegKeyExists(HKLM64, 'SOFTWARE\VB-Audio\Cable') or RegKeyExists(HKLM32, 'SOFTWARE\VB-Audio\Cable');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ErrorCode: Integer;
begin
  if (CurStep = ssPostInstall) and (not WizardSilent) and (not CableInstalled()) then
    if MsgBox(ExpandConstant('{cm:NeedCable}'), mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', '{#CableUrl}', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    if MsgBox(ExpandConstant('{cm:RemoveData}'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{userappdata}\VoiceFX'), True, True, True);
end;

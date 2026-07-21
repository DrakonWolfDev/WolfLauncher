#ifndef AppVersion
  #error AppVersion must be supplied by the build script
#endif
#ifndef BundleRoot
  #error BundleRoot must be supplied by the build script
#endif
#ifndef NumericVersion
  #error NumericVersion must be supplied by the build script
#endif
#ifndef OutputRoot
  #error OutputRoot must be supplied by the build script
#endif
#ifndef SetupIcon
  #error SetupIcon must be supplied by the build script
#endif
#ifndef ArtifactLabel
  #define ArtifactLabel "windows-x64"
#endif

[Setup]
AppId={{E4A3A1B2-39D8-4B94-9617-7E2361DE281A}
AppName=WolfLauncher
AppVersion={#AppVersion}
AppVerName=WolfLauncher {#AppVersion}
AppPublisher=WolfLauncher contributors
AppPublisherURL=https://github.com/DrakonWolfDev/WolfLauncher
AppSupportURL=https://github.com/DrakonWolfDev/WolfLauncher/issues
AppUpdatesURL=https://github.com/DrakonWolfDev/WolfLauncher/releases
DefaultDirName={localappdata}\Programs\WolfLauncher
DefaultGroupName=WolfLauncher
DisableProgramGroupPage=auto
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#OutputRoot}
OutputBaseFilename=wolflauncher-{#AppVersion}-setup-{#ArtifactLabel}
SetupIconFile={#SetupIcon}
UninstallDisplayIcon={app}\WolfLauncher.exe
LicenseFile={#BundleRoot}\LICENSE
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
UsePreviousGroup=yes
VersionInfoVersion={#NumericVersion}
VersionInfoCompany=WolfLauncher contributors
VersionInfoDescription=WolfLauncher installer
VersionInfoProductName=WolfLauncher
VersionInfoProductVersion={#NumericVersion}

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#BundleRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\WolfLauncher"; Filename: "{app}\WolfLauncher.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\WolfLauncher"; Filename: "{app}\WolfLauncher.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\WolfLauncher.exe"; Description: "Launch WolfLauncher"; Flags: nowait postinstall skipifsilent

# Third-Party Notices

WolfLauncher includes third-party open-source software.

## Noto Sans CJK SC

- Use: Bundled fallback font for CJK server names in the Server Browser.
- Version: Regular OTF from the Noto CJK repository.
- License: SIL Open Font License, Version 1.1.
- Copyright: Copyright 2014-2021 Adobe (http://www.adobe.com/).
- Source: https://github.com/notofonts/noto-cjk
- License text: `wolflauncher/assets/fonts/NotoSansCJK-LICENSE`.

## dayz-linux-cli-launcher

- Path: `external/dayz-linux-cli-launcher/`
- License: MIT
- Copyright: Copyright (c) 2021-2024 Sebastian Meyer
- Source: https://github.com/bastimeyer/dayz-linux-cli-launcher

The upstream license text is preserved at `external/dayz-linux-cli-launcher/LICENSE`.

## python-a2s

- Use: Direct Valve A2S query transport, challenge handling and split-packet
  reassembly for selected DayZ server mod manifests.
- Version: 1.4.2
- License: MIT
- Copyright: Copyright (c) 2020 Gabriel Huber
- Source: https://github.com/Yepoleb/python-a2s

The package includes its MIT license in its installed distribution metadata.

## Inno Setup

- Use: Builds the Windows Setup executable; its setup/uninstall runtime is
  contained in that generated artifact.
- Version: 6.7.3
- Copyright: Copyright (C) 1997-2026 Jordan Russell; portions Copyright (C)
  2000-2026 Martijn Laan.
- Source and license: https://github.com/jrsoftware/issrc

The compiler installer is fetched only during the Windows build and is verified
against its official release SHA-256 before execution. The pinned compiler is
used under its non-commercial license; commercial builds require an appropriate
Inno Setup license.

# Third-Party Notices

WolfLauncher includes third-party open-source software.

## dayz-linux-cli-launcher

- Path: `external/dayz-linux-cli-launcher/`
- License: MIT
- Copyright: Copyright (c) 2021-2024 Sebastian Meyer
- Source: https://github.com/bastimeyer/dayz-linux-cli-launcher

The upstream license text is preserved at `external/dayz-linux-cli-launcher/LICENSE`.

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

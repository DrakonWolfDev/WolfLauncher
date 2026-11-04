# Isolated Linux package validation

The optional extended smoke mode exercises synthetic browser/filter/edition,
mod-table, thumbnail-cache and harmless runtime-child checks inside the frozen
application. Normal startup and the existing basic smoke mode are unchanged.

Build from a clean development checkout with the pinned runtime/build inputs.
Keep the output separate from existing artifacts; no version bump, installation,
publication or Steam/game action is needed. Verify its provenance before testing:

```sh
python -m wolflauncher.build_provenance verify \
  --manifest path/to/WolfLauncher-VERSION-x86_64.AppImage.provenance.json \
  --commit SOURCE_COMMIT --require-clean path/to/WolfLauncher-VERSION-x86_64.AppImage
python scripts/validate-linux-package.py path/to/WolfLauncher-VERSION-x86_64.AppImage
python scripts/validate-linux-package.py path/to/WolfLauncher-VERSION-x86_64.AppImage --scale 2
```

The runner requires Linux bubblewrap with usable user/network namespaces. It
creates a dedicated temporary output directory and private `/tmp`, XDG paths,
PID and network namespaces. This isolates the single-instance socket as well as
user settings and prevents public requests. It retains `result.json`, stdout,
stderr and a synthetic UI screenshot for inspection. Exit success requires a
passing JSON result and normal application termination. The test uses AppImage
extraction-and-run rather than requiring FUSE.

The internal mode requires both `WOLFLAUNCHER_SMOKE_TEST=1` and
`WOLFLAUNCHER_SMOKE_VALIDATE_UI=1`, plus a dedicated `WOLFLAUNCHER_SMOKE_ROOT`
containing the application's config, data and database under the temporary
directory. It rejects normal user-data locations before inserting fixtures.
Use the runner rather than invoking these flags against everyday data. No code,
commands or server fixtures can be supplied through the flags.

Checks cover 1,000 Stable and 10 Experimental browser rows, rapid latest-query
replacement, edition separation, scrolling/selection, 200 mod rows with item and
selection reuse, a validated cached synthetic preview, bundled Node/GameDig
availability, and host Python's SSL isolation. The event-loop gap measurement
includes fixture creation and synchronous checks; it is not a frame-rate or
normal-use latency benchmark. The external wall time also includes extraction.

These offscreen checks do not certify FUSE mounting, native Wayland/X11 rendering,
manual accessibility, actual Steam/Workshop/game joins, native Windows or older
Linux distributions. Keep those boundaries separate from a local passing result.

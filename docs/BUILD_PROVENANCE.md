# Build provenance

The AppImage, Windows portable/Setup, DEB, RPM and Linux installer archive
build scripts write an adjacent
`<artifact>.provenance.json` automatically. Build from a Git checkout with the
normal pinned build dependencies. Source archives without Git metadata cannot
supply this evidence; use the matching checkout.

Each sidecar records the source commit and snapshot (including dirty development
work), tool versions and supplied tool binary hashes, dependency/input file hashes,
the artifact hash/size and a bundle file/mode/symlink inventory. Source changes
during the build fail completion. Nonignored untracked files are part of the
snapshot; keep outputs under ignored `build/` and `dist/`.

Verify a downloaded artifact, retaining its original filename:

```sh
python -m wolflauncher.build_provenance verify \
  --manifest path/to/artifact.provenance.json path/to/artifact
```

Also compare a built or separately extracted bundle against its recorded inventory:

```sh
python -m wolflauncher.build_provenance verify \
  --manifest path/to/artifact.provenance.json \
  --bundle-root path/to/bundle path/to/artifact
```

The tag-release workflow additionally passes `--commit "$GITHUB_SHA" --require-clean`.
A development build may be dirty and is labelled accordingly; it fails that
release gate. The inventories describe the build's staged bundle, not a second
independent decoding of the opaque native artifact. Existing native startup smoke
tests remain necessary. Verification of a moved bundle includes file permissions;
archive extraction must preserve executable bits and relative symlinks.

For a separate build integration, capture before compilation and finish only
after packaging and its required checks:

```sh
python -m wolflauncher.build_provenance begin \
  --output build/provenance-inputs.json --tool node=/path/to/bundled/node
# Compile and package without changing source.
python -m wolflauncher.build_provenance finish \
  --inputs build/provenance-inputs.json --bundle-root path/to/staged-bundle \
  path/to/artifact
```

These are unsigned evidence and consistency checks. They do not independently
authenticate a publisher or establish byte-reproducible builds. Do not generate
current-source provenance retrospectively for an older binary.

Native packages additionally seal the staged input inventory before packaging and
compare it afterward. DEB records the entire staging root, including `DEBIAN`
control files/hooks. RPM records its payload tree, including the installed wrapper
and notices; its generated scriptlets are defined by the source build script.
Windows Setup records its portable bundle, with compiler and generated icon hashes.
The Linux installer archive records its AppImage and installer/support files.

RPM and Windows Setup require the parent AppImage/portable ZIP sidecar, verify
that its staged bundle still matches, and require the identical full source
snapshot (including dirty files, not just commit). The Linux archive similarly
verifies and binds its parent AppImage, and compares the copied payload bytes.
The parent artifact and manifest identities are captured before wrapping and
rechecked at completion. Reusing an unverified/stale AppDir or supplying a ZIP
from an earlier snapshot fails rather than attributing it to current source.
Windows Setup accepts `-PortableArchive` when the portable ZIP is not adjacent
to `-BundleRoot`; its default filename uses the version and artifact label.

For an integration with a parent artifact:

```sh
python -m wolflauncher.build_provenance begin --output build/wrapper-inputs.json \
  --parent-artifact dist/parent.archive --parent-bundle build/parent-bundle
# Stage the wrapper payload without changing source or parent inputs.
python -m wolflauncher.build_provenance seal --inputs build/wrapper-inputs.json \
  --bundle-root build/wrapper-payload
# Run the native packaging tool.
python -m wolflauncher.build_provenance finish --inputs build/wrapper-inputs.json \
  --bundle-root build/wrapper-payload --parent-artifact dist/parent.archive \
  --parent-bundle build/parent-bundle dist/wrapper.package
```

`seal` is single-use. Existing direct AppImage/portable integrations remain
compatible without it. Parent checks run during wrapper creation; ordinary
`verify` checks the selected artifact and optional bundle, without requiring
external parent files. Parent identities in the child record support separately
verifying the original parent artifact and its sidecar. No absolute checkout or
parent paths are retained. Inventories describe staged inputs rather than an
independent decoding of Setup/RPM/DEB; extracted payload comparisons and native
startup checks remain separate evidence.

CI retains the new native/wrapper sidecars and the tag-only release gate verifies
all four formats against the clean expected commit before its existing publish
step. This does not trigger a release. Original filenames are recorded; public
aliases must be restored to their recorded filename before artifact verification.
Native builds and extracted payload validation must be recorded per platform;
source tests do not establish Windows compiler/install/uninstall behaviour.

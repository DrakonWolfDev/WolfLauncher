# Build provenance

The AppImage and Windows portable build scripts write an adjacent
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
current-source provenance retrospectively for an older binary. Setup installers,
DEB/RPM packages and installer wrappers still need their own staged-input chain;
no complete provenance claim is made for those formats yet.

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from wolflauncher.build_provenance import begin, bundle_inventory, finish, source_state, verify


class BuildProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "source"
        self.root.mkdir()
        for args in (
            ("init", "-q"),
            ("config", "user.name", "Build test"),
            ("config", "user.email", "build@example.test"),
        ):
            subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)
        (self.root / "app.py").write_text("print('example')\n")
        subprocess.run(["git", "-C", str(self.root), "add", "app.py"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "Fixture"], check=True)
        self.bundle = Path(self.directory.name) / "bundle"
        self.bundle.mkdir()
        (self.bundle / "program").write_bytes(b"example executable")
        self.artifact = Path(self.directory.name) / "example.archive"
        self.artifact.write_bytes(b"opaque artifact")
        self.inputs = Path(self.directory.name) / "inputs.json"

    def test_source_inputs_tool_hashes_and_bundle_are_bound_to_artifact(self):
        begin(self.root, self.inputs, ["tool=" + str(self.bundle / "program")])
        manifest = finish(self.root, self.inputs, self.bundle, self.artifact)
        verify(manifest, self.artifact, self.bundle)
        evidence = json.loads(manifest.read_text())
        self.assertFalse(evidence["source"]["dirty"])
        self.assertEqual(evidence["source"]["files"][0]["path"], "app.py")
        self.assertEqual(
            evidence["toolchain"]["tools"]["tool"]["sha256"], evidence["bundle"][0]["sha256"]
        )
        self.assertIn("Unsigned", evidence["assurance"])
        (self.bundle / "program").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "Packaged files"):
            verify(manifest, self.artifact, self.bundle)
        verify(manifest, self.artifact)
        self.artifact.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "Artifact"):
            verify(manifest, self.artifact)

    def test_changed_added_and_removed_sources_abort_build_evidence(self):
        for mutation in ("change", "add", "remove"):
            (self.root / "app.py").write_text("print('example')\n")
            (self.root / "extra.py").unlink(missing_ok=True)
            begin(self.root, self.inputs, [])
            if mutation == "change":
                (self.root / "app.py").write_text("print('changed')\n")
            elif mutation == "add":
                (self.root / "extra.py").write_text("new module\n")
            else:
                (self.root / "app.py").unlink()
            with (
                self.subTest(mutation=mutation),
                self.assertRaisesRegex(ValueError, "Source changed"),
            ):
                finish(self.root, self.inputs, self.bundle, self.artifact)
        self.assertFalse(self.artifact.with_name(self.artifact.name + ".provenance.json").exists())

    def test_dirty_development_build_is_labelled_and_ignored_outputs_do_not_change_snapshot(self):
        (self.root / "app.py").write_text("dirty development snapshot\n")
        (self.root / ".gitignore").write_text("build/\n")
        state = source_state(self.root)
        self.assertTrue(state["dirty"])
        (self.root / "build").mkdir()
        (self.root / "build/output").write_text("build output")
        self.assertEqual(state, source_state(self.root))

    def test_bundle_symlinks_are_preserved_and_escaping_links_are_rejected(self):
        link = self.bundle / "link"
        try:
            link.symlink_to("program")
        except OSError:
            self.skipTest("Symlink creation unavailable")
        records = bundle_inventory(self.bundle)
        self.assertIn({"path": "link", "symlink": "program"}, records)
        link.unlink()
        link.symlink_to(self.artifact)
        with self.assertRaisesRegex(ValueError, "escapes"):
            bundle_inventory(self.bundle)

    def test_release_verification_requires_the_expected_commit_and_clean_source(self):
        begin(self.root, self.inputs, [])
        manifest = finish(self.root, self.inputs, self.bundle, self.artifact)
        expected = source_state(self.root)["commit"]
        verify(manifest, self.artifact, expected_commit=expected, require_clean=True)
        with self.assertRaisesRegex(ValueError, "source commit"):
            verify(manifest, self.artifact, expected_commit="0" * 40)
        (self.root / "app.py").write_text("dirty source\n")
        begin(self.root, self.inputs, [])
        manifest = finish(self.root, self.inputs, self.bundle, self.artifact)
        with self.assertRaisesRegex(ValueError, "clean source"):
            verify(manifest, self.artifact, expected_commit=expected, require_clean=True)

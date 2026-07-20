"""Prepare bundled command-line tools before WolfLauncher imports application code."""

import os
import sys
from pathlib import Path


bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
node_runtime = bundle_root / "node-runtime"
node_bin = bundle_root / "node" / "node_modules" / ".bin"
gamedig_script = bundle_root / "node" / "node_modules" / "gamedig" / "bin" / "gamedig.js"

bundled_path_entries = [path for path in (node_runtime, node_bin) if path.is_dir()]
if bundled_path_entries:
    current_path = os.environ.get("PATH", "")
    prefix = os.pathsep.join(str(path) for path in bundled_path_entries)
    os.environ["PATH"] = prefix + (os.pathsep + current_path if current_path else "")

if gamedig_script.is_file():
    os.environ.setdefault("WOLFLAUNCHER_GAMEDIG_SCRIPT", str(gamedig_script))

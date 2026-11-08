"""Run the byte-preserved development screen in an isolated ignored workspace."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="New empty workspace, normally below the repository's ignored work/ directory")
    args = parser.parse_args()
    evidence = Path(__file__).resolve().parent
    repository = evidence.parents[1]
    source = evidence / "candidate_screening.py"
    manifest = json.loads((evidence / "artifact-manifest.json").read_text())
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest["executed_script_sha256"]:
        raise ValueError("Executed screening script checksum differs from the recorded evidence")
    workspace = args.output.resolve()
    workspace.mkdir(parents=True, exist_ok=False)
    scripts = workspace / "model-development"
    scripts.mkdir()
    (workspace / "repos").mkdir()
    # The executed original has a fixed layout. Recreate it rather than edit
    # that source and lose the script checksum recorded before development.
    (workspace / "repos" / "FraudLens").symlink_to(repository, target_is_directory=True)
    copied = scripts / source.name
    shutil.copyfile(source, copied)
    environment = os.environ.copy()
    environment.update({"PYTHONPATH": str(repository), "OMP_NUM_THREADS": "1",
                        "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                        "VECLIB_MAXIMUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    print(f"Development-only output: {scripts}", flush=True)
    subprocess.run([sys.executable, str(copied)], cwd=repository, env=environment, check=True)


if __name__ == "__main__":
    main()

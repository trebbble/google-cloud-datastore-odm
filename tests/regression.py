#!/usr/bin/env python3
"""
Local CI Matrix Runner for Google Cloud Datastore ODM.
Tests multiple Python versions against multiple Datastore SDK versions using `uv`.
"""

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from typing import List

PYTHON_VERSIONS = ["3.10", "3.11", "3.12", "3.13", "3.14"]
MIN_DATASTORE_VERSION = (2, 20, 1)
MATRIX_DIR = ".venv-regression-matrix"


def fetch_datastore_versions(min_version=MIN_DATASTORE_VERSION) -> List[str]:
    """Fetches and sorts stable releases of google-cloud-datastore from PyPI."""
    print("  🌐  Fetching Datastore versions from PyPI...")
    url = "https://pypi.org/pypi/google-cloud-datastore/json"

    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read())
    except Exception as e:
        print(f"  ❌ Failed to fetch google-cloud-datastore versions from PyPI: {e}")
        sys.exit(1)

    versions = []
    for v in data.get("releases", {}):
        try:
            parts = tuple(int(x) for x in v.split(".") if x.isdigit())
            if parts >= MIN_DATASTORE_VERSION:
                versions.append((parts, v))
        except ValueError:
            print(f"Could not parse google-cloud-datastore version: {v}, ignoring it.")

    versions.sort(key=lambda x: x[0])
    valid_versions = [v[1] for v in versions]
    return valid_versions + ["latest"]


def run_command(cmd: List[str], env: dict, quiet: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, env=env, capture_output=quiet, text=True)


def main():
    datastore_versions = fetch_datastore_versions()
    total_runs = len(PYTHON_VERSIONS) * len(datastore_versions)

    print("\n" + "=" * 50)
    print(f" 🚀  Regression matrix:\n"
          f"    x {len(PYTHON_VERSIONS)} Python versions\n"
          f"    x {len(datastore_versions)} google-cloud-datastore versions\n"
          f"    = {total_runs} total runs")

    if os.path.exists(MATRIX_DIR):
        shutil.rmtree(MATRIX_DIR)
    os.makedirs(MATRIX_DIR)

    failed_runs = []
    skipped_runs = []

    try:
        for python_version in PYTHON_VERSIONS:
            print("\n" + "=" * 50)
            print(f"    --- 🐍  Python {python_version} ---")
            venv_path = os.path.join(MATRIX_DIR, f"venv-{python_version}")
            python_exe = os.path.join(venv_path, "bin", "python")
            env = os.environ.copy()
            env["UV_PROJECT_ENVIRONMENT"] = venv_path

            res = run_command(["uv", "venv", venv_path, "--python", python_version], env)
            if res.returncode != 0:
                print(f"⚠️  Skipping Python {python_version} (Not installed locally or uv failed to fetch it).")
                continue

            for datastore_version in datastore_versions:
                run_command(["uv", "sync"], env)

                if datastore_version == "latest":
                    install_cmd = [
                        "uv", "pip", "install", "--python", python_exe, "--upgrade", "google-cloud-datastore"
                    ]
                else:
                    install_cmd = [
                        "uv", "pip", "install", "--python", python_exe, f"google-cloud-datastore=={datastore_version}"
                    ]

                install_res = run_command(install_cmd, env)
                if install_res.returncode != 0:
                    print(f"⚠️ google-cloud-datastore @ {datastore_version.ljust(8)} : INSTALL FAILED")
                    skipped_runs.append((python_version, datastore_version))
                    continue

                datastore_version_installed = None
                datastore_version_cmd = run_command(
                    [
                        python_exe, "-c",
                        "import importlib.metadata; print(importlib.metadata.version('google-cloud-datastore'))"
                    ],
                    env
                )

                if datastore_version_cmd.returncode == 0:
                    datastore_version_installed = datastore_version_cmd.stdout.strip()

                target_version = datastore_version if datastore_version != "latest" else datastore_versions[-2]
                if datastore_version_installed != target_version:
                    print(f"⚠️ google-cloud-datastore @ {target_version.ljust(8)} "
                          f": VERSION INSTALLED MISMATCH: {datastore_version_installed}")
                    skipped_runs.append((python_version, target_version))
                    continue

                res = run_command(
                    [
                        python_exe, "-m", "pytest",
                        "-q", "--no-header", "-o", "log_cli=false"
                    ],
                    env
                )

                if res.returncode == 0:
                    print(f"  ✅  google-cloud-datastore @ {datastore_version.ljust(7)}: PASSED")
                else:
                    print(f"  ❌  google-cloud-datastore @ {datastore_version.ljust(7)}: FAILED")
                    failed_runs.append((python_version, datastore_version))

    finally:
        print("\n" + "=" * 50)
        print("\n  🧹 Cleaning up isolated environments...")
        shutil.rmtree(MATRIX_DIR, ignore_errors=True)

    print("\n" + "=" * 50)
    if not failed_runs and not skipped_runs:
        print("\n  🎉 All Regression tests passed successfully! 🎉")
    else:
        print(f"\n  ✅ {total_runs - len(failed_runs) - len(skipped_runs)} Regression tests passed")

    if skipped_runs:
        print(f"\n  ⚠️ {len(skipped_runs)} Regression tests skipped")
        for python_version, datastore_version in skipped_runs:
            print(f"[Python {python_version} | google-cloud-datastore @ {datastore_version}]")

    if failed_runs:
        print(f"\n  ❌ {len(failed_runs)} Regression tests failed")
        for python_version, datastore_version in failed_runs:
            print(f"[Python {python_version} | google-cloud-datastore @ {datastore_version}]")


if __name__ == "__main__":
    main()

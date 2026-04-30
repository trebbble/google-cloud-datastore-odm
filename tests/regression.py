#!/usr/bin/env python3
"""
Local CI Matrix Runner for Google Cloud Datastore ODM.
Tests multiple Python versions against multiple Datastore SDK versions using `uv`.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from typing import List, Tuple

BASE_PYTHON_VERSIONS = ["3.10", "3.11", "3.12", "3.13", "3.14"]
MATRIX_DIR = ".venv-regression-matrix"


def parse_version(v: str) -> Tuple[int, ...]:
    """Helper to convert a string version '2.20.1' into a math-comparable tuple (2, 20, 1)."""
    return tuple(int(x) for x in v.split(".") if x.isdigit())


def fetch_datastore_versions():
    """Fetches and sorts stable releases of google-cloud-datastore from PyPI."""
    url = "https://pypi.org/pypi/google-cloud-datastore/json"

    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read())
    except Exception as e:
        print(f"  ❌ Failed to fetch google-cloud-datastore versions from PyPI: {e}")
        sys.exit(1)

    versions = []
    for v in data.get("releases", {}):
        if any(marker in v for marker in ["rc", "b", "a", "dev"]):
            continue
        try:
            parts = parse_version(v)
            versions.append((parts, v))
        except ValueError:
            print(f"Could not parse google-cloud-datastore version: {v}, ignoring it.")

    versions.sort(key=lambda x: x[0])
    return versions


def run_command(cmd: List[str], env: dict, quiet: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, env=env, capture_output=quiet, text=True)


def parse_args():
    parser = argparse.ArgumentParser(description="Run regression matrix against Python and Datastore versions.")

    ds_group = parser.add_mutually_exclusive_group()
    ds_group.add_argument("--ds-version", type=str,
                          help="Pinpoint a specific Datastore version (e.g., '2.24.0' or 'latest')")
    ds_group.add_argument("--min-ds-version", type=str, help="Minimum Datastore version to test (default: 2.20.1)")

    py_group = parser.add_mutually_exclusive_group()
    py_group.add_argument("--py-version", type=str, choices=BASE_PYTHON_VERSIONS,
                          help="Pinpoint a specific Python version (e.g., '3.12')")
    py_group.add_argument("--min-py-version", choices=BASE_PYTHON_VERSIONS,
                          type=str, help="Minimum Python version to test (default: 3.10)")

    return parser.parse_args()


def main():
    args = parse_args()

    if args.py_version:
        python_versions = [args.py_version]
    else:
        min_py_str = args.min_py_version or "3.10"
        min_py = parse_version(min_py_str)
        python_versions = [v for v in BASE_PYTHON_VERSIONS if parse_version(v) >= min_py]

    if args.ds_version:
        if args.ds_version != "latest":
            datastore_versions = [args.ds_version]
        else:
            datastore_versions = [fetch_datastore_versions()[-1][1]]
    else:
        min_ds_str = args.min_ds_version or "2.20.1"
        min_ds = parse_version(min_ds_str)

        datastore_versions = [
            v[1]
            for v in fetch_datastore_versions()
            if v[0] >= min_ds
        ]

    is_single_run = len(python_versions) == 1 and len(datastore_versions) == 1
    total_runs = len(python_versions) * len(datastore_versions)

    print("\n" + "=" * 50)
    print(f" 🚀  Regression matrix:\n"
          f"    x {len(python_versions)} Python versions: {', '.join(python_versions)}\n"
          f"    x {len(datastore_versions)} google-cloud-datastore versions: {', '.join(datastore_versions)}\n"
          f"    = {total_runs} total runs")

    if os.path.exists(MATRIX_DIR):
        shutil.rmtree(MATRIX_DIR)
    os.makedirs(MATRIX_DIR)

    failed_runs = []
    skipped_runs = []

    try:
        for python_version in python_versions:
            print("\n" + "=" * 50)
            if is_single_run:
                print("\n  ▶️ Running targeted test (Full Pytest Output)...\n")
            else:
                print(f"    --- 🐍  Python {python_version} ---")

            venv_path = os.path.join(MATRIX_DIR, f"venv-{python_version}")
            python_exe = os.path.join(venv_path, "bin", "python")

            env = os.environ.copy()
            env["VIRTUAL_ENV"] = venv_path
            env["UV_PROJECT_ENVIRONMENT"] = venv_path
            # Force pure Python Protobuf just in case older SDKs are tested
            env["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

            res = run_command(["uv", "venv", venv_path, "--python", python_version], env)
            if res.returncode != 0:
                print(f"⚠️  Skipping Python {python_version} (Not installed locally or uv failed to fetch it).")
                continue

            for datastore_version in datastore_versions:
                run_command(["uv", "sync", "--python", python_exe], env)

                install_res = run_command(
                    [
                        "uv", "pip", "install",
                        "--python", python_exe,
                        f"google-cloud-datastore=={datastore_version}"
                    ],
                    env
                )
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

                if datastore_version_installed != datastore_version:
                    print(f"⚠️ google-cloud-datastore @ {datastore_version.ljust(7)} "
                          f": VERSION INSTALLED MISMATCH: {datastore_version_installed}")
                    skipped_runs.append((python_version, datastore_version))
                    continue

                if is_single_run:
                    subprocess.run([python_exe, "-m", "pytest"], env=env)
                else:
                    res = run_command([
                        python_exe, "-m", "pytest",
                        "-q", "--no-header", "-o", "log_cli=false"
                    ], env)

                    if res.returncode == 0:
                        print(f"  ✅  google-cloud-datastore @ {datastore_version.ljust(7)}: PASSED")
                    else:
                        print(f"  ❌  google-cloud-datastore @ {datastore_version.ljust(7)}: FAILED")
                        failed_runs.append((python_version, datastore_version))

    finally:
        print("\n" + "=" * 50)
        print("  🧹 Cleaning up isolated environments...")
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

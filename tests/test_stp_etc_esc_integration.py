"""
Integration test: run stp_etc_esc's test suite against the config_um_esc in this checkout.

This test clones uasal/stp_etc_esc, installs its dependencies (excluding
config_um_esc so the local checkout remains active), and then runs the
stp_etc_esc tests that exercise config_um_esc.

A failure here means the current config changes break a **downstream consumer**
(stp_etc_esc), not that the config files themselves are malformed.
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
STP_ETC_ESC_REPO = "https://github.com/uasal/stp_etc_esc.git"
STP_ETC_ESC_BRANCH = "develop"

# stp_etc_esc tests that are relevant to config_um_esc compatibility.
DOWNSTREAM_TEST_FILES = [
    "tests/test_config_um_esc.py",
    "tests/test_esc_etc_initialization.py",
]


def _run(cmd, cwd=None, env=None, check=True):
    """Run *cmd*, stream a labelled header + full output, and fail on error."""
    cmd_str = " ".join(str(c) for c in cmd)
    print(f"\n{'='*72}")
    print(f"$ {cmd_str}")
    if cwd:
        print(f"  (cwd: {cwd})")
    print(f"{'='*72}")

    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Always print output so CI logs show what happened.
    if result.stdout:
        print(result.stdout, end="")

    if check and result.returncode != 0:
        pytest.fail(
            f"Command failed (exit {result.returncode}):\n"
            f"  {cmd_str}\n\n"
            f"--- output ---\n{result.stdout}"
        )
    return result


def _pip_install(*args, cwd=None, env=None):
    """Run ``pip install <args>`` and stream output."""
    return _run([sys.executable, "-m", "pip", "install"] + list(args), cwd=cwd, env=env)


def _filter_requirements(src_path, dst_path, exclude_pattern):
    """Copy *src_path* to *dst_path*, dropping lines that match *exclude_pattern*."""
    lines = src_path.read_text().splitlines(keepends=True)
    filtered = [ln for ln in lines if not re.search(exclude_pattern, ln, re.IGNORECASE)]
    dst_path.write_text("".join(filtered))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def stp_etc_esc_env():
    """
    Set up a temporary directory with a clone of stp_etc_esc and return a
    dict with ``clone_dir`` (Path) and ``env`` (os.environ copy suitable for
    running pytest inside the clone).

    The fixture installs packages in the *same* Python environment that is
    running this test so that no virtual-env creation is needed in CI.
    """
    with tempfile.TemporaryDirectory(prefix="stp_etc_esc_") as tmpdir:
        clone_dir = Path(tmpdir) / "stp_etc_esc"

        print(f"\n{'#'*72}")
        print("# DOWNSTREAM INTEGRATION FIXTURE — setup start")
        print(f"# Temp dir : {tmpdir}")
        print(f"# config_um_esc root: {REPO_ROOT}")
        print(f"{'#'*72}")

        # 1. Clone stp_etc_esc -----------------------------------------------
        print("\n--- Step 1: clone stp_etc_esc ---")
        _run(
            ["git", "clone", "--depth", "1", "--branch", STP_ETC_ESC_BRANCH,
             STP_ETC_ESC_REPO, str(clone_dir)],
        )

        # 1a. Create test_data/test_STP path alias (Linux case-sensitive fix) -
        # The tests reference 'test_data/test_STP' relative to the repo root, but
        # the actual directory is tests/test_data/test_stp (different depth + lowercase).
        print("\n--- Step 1a: create test_data/test_STP symlink ---")
        test_data_root = clone_dir / "test_data"
        test_data_root.mkdir(exist_ok=True)
        link_target = clone_dir / "test_data" / "test_STP"
        if not link_target.exists():
            link_target.symlink_to(Path("../tests/test_data/test_stp"))
            print(f"Created symlink: {link_target} -> ../tests/test_data/test_stp")

        # 2. Install local config_um_esc FIRST so it takes priority ----------
        print("\n--- Step 2: install local config_um_esc ---")
        _pip_install("--no-deps", str(REPO_ROOT))

        # Confirm which config_um_esc is active.
        _run([sys.executable, "-m", "pip", "show", "config_um_esc"])

        # 3. Install stp_etc_esc deps, skipping config_um_esc ---------------
        print("\n--- Step 3: install stp_etc_esc dependencies (excluding config_um_esc) ---")
        orig_req = clone_dir / "requirements.txt"
        filtered_req = clone_dir / "requirements_filtered.txt"
        # Drop lines that reference config_um_esc (git URL or bare name).
        _filter_requirements(orig_req, filtered_req, r"config_um_esc")

        print("Filtered requirements.txt (config_um_esc line removed):")
        print(filtered_req.read_text())

        _pip_install("-r", str(filtered_req))

        # 4. Install stp_etc_esc itself (no deps to avoid overwriting config) -
        print("\n--- Step 4: install stp_etc_esc (--no-deps) ---")
        _pip_install("--no-deps", str(clone_dir))

        # Final package inventory for traceability.
        print("\n--- Installed package versions (key packages) ---")
        _run(
            [sys.executable, "-m", "pip", "show",
             "config_um_esc", "stp_etc_esc", "utils_config", "astropy"],
        )

        # 5. Build an env with MPLBACKEND=Agg for headless CI -----------------
        env = os.environ.copy()
        env["MPLBACKEND"] = "Agg"

        print(f"\n{'#'*72}")
        print("# DOWNSTREAM INTEGRATION FIXTURE — setup complete")
        print(f"{'#'*72}\n")

        yield {"clone_dir": clone_dir, "env": env}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_downstream_config_um_esc(stp_etc_esc_env):
    """
    Run stp_etc_esc's test_config_um_esc.py against the local config_um_esc checkout.

    A failure here means the current config changes break stp_etc_esc's
    config-loading tests, NOT that config_um_esc itself is malformed.
    """
    clone_dir = stp_etc_esc_env["clone_dir"]
    env = stp_etc_esc_env["env"]

    test_file = clone_dir / "tests" / "test_config_um_esc.py"
    result = _run(
        [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=long", "-s"],
        cwd=str(clone_dir),
        env=env,
        check=False,
    )

    if result.returncode != 0:
        pytest.fail(
            "DOWNSTREAM COMPATIBILITY FAILURE — stp_etc_esc/tests/test_config_um_esc.py "
            "failed against this config_um_esc branch.\n\n"
            "This is a downstream integration failure, not a config validation failure.\n\n"
            f"--- pytest output ---\n{result.stdout}"
        )


@pytest.mark.integration
def test_downstream_validate_ETC_snr_calculation(stp_etc_esc_env):
    """
    Run stp_etc_esc's test_validate_ETC_snr_calculation (from
    test_esc_etc_initialization.py) against the local config_um_esc checkout.

    This is an independent end-to-end SNR validation: it computes planet and
    background count rates from first principles and checks that the ETC's
    SNR result agrees to within 0.5 %.

    A failure here means the current config changes affect the ETC's numerical
    SNR output, NOT that the config files themselves are malformed.
    """
    clone_dir = stp_etc_esc_env["clone_dir"]
    env = stp_etc_esc_env["env"]

    test_file = clone_dir / "tests" / "test_esc_etc_initialization.py"
    result = _run(
        [
            sys.executable, "-m", "pytest",
            str(test_file), "-v", "--tb=long", "-s",
            "-k", "test_validate_ETC_snr_calculation",
        ],
        cwd=str(clone_dir),
        env=env,
        check=False,
    )

    if result.returncode != 0:
        pytest.fail(
            "DOWNSTREAM COMPATIBILITY FAILURE — stp_etc_esc/tests/test_esc_etc_initialization.py "
            "::test_validate_ETC_snr_calculation failed against this config_um_esc branch.\n\n"
            "This is a downstream integration failure, not a config validation failure.\n\n"
            f"--- pytest output ---\n{result.stdout}"
        )


@pytest.mark.integration
def test_downstream_esc_etc_initialization(stp_etc_esc_env):
    """
    Run stp_etc_esc's test_esc_etc_initialization.py (specifically
    test_configs_instrument) against the local config_um_esc checkout.

    A failure here means the current config changes break stp_etc_esc's
    ETC initialization, NOT that config_um_esc itself is malformed.
    """
    clone_dir = stp_etc_esc_env["clone_dir"]
    env = stp_etc_esc_env["env"]

    test_file = clone_dir / "tests" / "test_esc_etc_initialization.py"
    result = _run(
        [
            sys.executable, "-m", "pytest",
            str(test_file), "-v", "--tb=long", "-s",
            "-k", "test_configs_instrument",
        ],
        cwd=str(clone_dir),
        env=env,
        check=False,
    )

    if result.returncode != 0:
        pytest.fail(
            "DOWNSTREAM COMPATIBILITY FAILURE — stp_etc_esc/tests/test_esc_etc_initialization.py "
            "::test_configs_instrument failed against this config_um_esc branch.\n\n"
            "This is a downstream integration failure, not a config validation failure.\n\n"
            f"--- pytest output ---\n{result.stdout}"
        )

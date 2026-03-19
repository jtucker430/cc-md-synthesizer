import subprocess
import sys
import importlib.util


# ── helper ──────────────────────────────────────────────────────────────────
def _load_script():
    """Import scripts/build_html.py as a module without executing main()."""
    spec = importlib.util.spec_from_file_location("build_html", "scripts/build_html.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── CLI tests ────────────────────────────────────────────────────────────────
def test_cli_help():
    result = subprocess.run(
        [sys.executable, "scripts/build_html.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "synthesis" in result.stdout.lower()


def test_cli_missing_synthesis(tmp_path):
    result = subprocess.run(
        [sys.executable, "scripts/build_html.py", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "synthesis" in output.lower()

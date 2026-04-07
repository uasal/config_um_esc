import importlib.metadata
import config_um_esc


def test_version_consistency():
    """Ensure __version__ and importlib.metadata.version report the same value."""
    package_version = importlib.metadata.version("config_um_esc")
    module_version = config_um_esc.__version__
    assert module_version == package_version, (
        f"Version mismatch: __version__={module_version}, metadata.version={package_version}. Verify package is up-to-date."
    )

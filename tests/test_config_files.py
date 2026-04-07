import config_um_esc
from pathlib import Path
import pytest

from utils_config import ConfigLoader

CONFIGS_PATH = Path(config_um_esc.__file__).parent / "configs"


def test_load_configs_valid():
    """
    Test that all TOML files in the package's 'configs' directory are valid.
    If any file is malformed, ConfigLoader.load_configs() raises an error, causing the test to fail.
    """
    loader = ConfigLoader(str(CONFIGS_PATH), mode="parsed", recursive=False)
    try:
        configs = loader.load_configs()
    except Exception as e:
        pytest.fail(f"Failed to load TOML configs: {e}")
    assert configs, "No configuration files were loaded."


def test_astropy_units():
    """
    Test that all unit strings in the parsed configuration files ("parsed" format) are valid Astropy units.
    uses the ConfigLoader class + validate_astropy() method to parse configs installed in this package
    and then return either True for no errors (passing assert), or a list containing information on each violation
    """
    result = config_um_esc.load_config_values(
        "parsed", return_loader=True
    ).validate_astropy()

    if result is True:
        return  # All units are valid

    assert not result, "Invalid astropy units found:\n" + "\n".join(result)

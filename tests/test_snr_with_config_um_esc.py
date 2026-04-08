"""
Test that stp_etc_esc can compute an SNR using config_um_esc's configuration.

This validates that the config files in src/config_um_esc/configs/ (including
common_params.toml) don't break the downstream ETC when used as the instrument
configuration.

Run this after installing both stp_etc_esc and config_um_esc.
"""

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

import config_um_esc  # noqa: E402
import astropy.units as u  # noqa: E402
from pathlib import Path  # noqa: E402

etsc = pytest.importorskip("stp_etc_esc.ExposureTimeSNRCalculatorESC")


def test_snr_calculation_with_config_um_esc():
    """Initialize the ETC with config_um_esc and verify SNR computation succeeds.

    This proves that common_params.toml is structurally compatible with
    stp_etc_esc and produces a valid (positive) SNR result.
    """
    esc_config = config_um_esc.load_config_values()
    esc_data_path = Path(config_um_esc.get_data_path())

    obs = etsc.Observatory("STP", 2.4 * u.m, 36.45 * u.m)
    obs.make_STP(escconfig=esc_config, escpath=esc_data_path)

    obs.set_generic_source(1e-8, 0)
    obs.set_background(background_file=None, plot=False)
    obs.make_observation(
        hoststarflux=esc_config["common_params"]["sources"]["host"]["magnitude"],
        planetdeltamag=esc_config["common_params"]["sources"]["companion"][
            "delta_magnitude"
        ],
        bg_flux=22.5,
        flux_units="vega",
        plot=False,
        exobg_flux=21,
    )

    snr = obs.calc_SNR(600.0 * u.s, 10.0 * u.s)
    assert snr > 0, f"SNR should be positive, got {snr}"
    print(f"SUCCESS: SNR with config_um_esc = {snr}")

"""Review round 3, item 4: NaN/inf geometry and invalid hashes are rejected.

Reproduces the report: NaN geometry, NaN gaps, infinite loss coefficients,
and a malformed source hash were all accepted by the catalogue validators.
"""

import pytest

from datasheet_studio.models.magnetics_catalog import (
    CatalogValidationError,
)

from tests.unit.test_magnetics_catalog import bobbin, core, material, pack

NAN = float("nan")
INF = float("inf")


def test_nan_geometry_is_rejected():
    with pytest.raises(CatalogValidationError):
        core(ae_mm2=NAN)
    with pytest.raises(CatalogValidationError):
        bobbin(winding_width_mm=NAN)


def test_nan_gap_option_is_rejected():
    with pytest.raises(CatalogValidationError):
        core(gap_options_um=(100.0, NAN))


def test_infinite_loss_coefficients_are_rejected():
    with pytest.raises(CatalogValidationError):
        material(loss_k=INF, loss_alpha=1.5, loss_beta=2.5)
    with pytest.raises(CatalogValidationError):
        material(loss_k=100.0, loss_alpha=INF, loss_beta=2.5)


def test_malformed_source_hash_is_rejected():
    with pytest.raises(CatalogValidationError, match="منبع"):
        core(source_hash="not-a-real-hash")
    with pytest.raises(CatalogValidationError, match="منبع"):
        material(source_hash="XYZ")


def test_valid_pack_still_passes():
    pack().validate()  # must not raise

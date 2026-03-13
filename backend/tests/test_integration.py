"""
PharmaCheck — Integration tests
Llaman a la API real de OpenFDA (requieren red).
Run:  python3 -m pytest backend/tests/test_integration.py -v -m integration
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import backend.main as main_module
from backend.main import fetch_openfda_raw, openfda_to_drug

pytestmark = pytest.mark.integration


# ─────────────────────────────────────────
# fetch_openfda_raw — red real
# ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_ibuprofen_returns_data():
    raw = await fetch_openfda_raw("ibuprofen")
    assert raw is not None
    assert "openfda" in raw


@pytest.mark.asyncio
async def test_fetch_spanish_name_resolves():
    """'ibuprofeno' (español) debe resolverse a ibuprofen en FDA."""
    raw = await fetch_openfda_raw("ibuprofeno")
    assert raw is not None
    openfda = raw.get("openfda", {})
    generic = " ".join(openfda.get("generic_name", [])).lower()
    assert "ibuprofen" in generic


@pytest.mark.asyncio
async def test_fetch_paracetamol_resolves():
    """'paracetamol' debe resolverse a acetaminophen."""
    raw = await fetch_openfda_raw("paracetamol")
    assert raw is not None
    openfda = raw.get("openfda", {})
    generic = " ".join(openfda.get("generic_name", [])).lower()
    assert "acetaminophen" in generic


@pytest.mark.asyncio
async def test_fetch_unknown_returns_none():
    raw = await fetch_openfda_raw("xyzfakedrugnotexists999")
    assert raw is None


@pytest.mark.asyncio
async def test_fetch_brand_name_nurofen():
    """'nurofen' (marca) debe encontrar ibuprofen."""
    raw = await fetch_openfda_raw("nurofen")
    assert raw is not None


@pytest.mark.asyncio
async def test_openfda_result_has_required_fields():
    raw = await fetch_openfda_raw("ibuprofen")
    assert raw is not None
    drug = openfda_to_drug(raw)
    assert drug["name"]
    assert drug["uses"] or drug["dosage"]
    assert isinstance(drug["sideEffects"], list)
    assert isinstance(drug["sources"], list)


@pytest.mark.asyncio
async def test_fetch_amoxicillin():
    raw = await fetch_openfda_raw("amoxicilina")
    assert raw is not None
    openfda = raw.get("openfda", {})
    generic = " ".join(openfda.get("generic_name", [])).lower()
    assert "amoxicillin" in generic


@pytest.mark.asyncio
async def test_fetch_omeprazole():
    raw = await fetch_openfda_raw("omeprazol")
    assert raw is not None

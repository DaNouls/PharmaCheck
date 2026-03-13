"""
PharmaCheck — End-to-end tests
Ejercitan el flujo HTTP completo a través de FastAPI (sin red externa).
OpenFDA y Gemini se mockean; Argos Translate también (sin modelo instalado).
Run:  python3 -m pytest backend/tests/test_e2e.py -v -m e2e
"""

import sys
import os
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

with __import__("unittest.mock", fromlist=["patch"]).patch.dict("sys.modules", {
    "argostranslate": MagicMock(),
    "argostranslate.package": MagicMock(),
    "argostranslate.translate": MagicMock(),
}):
    import backend.main as main_module

from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e

client = TestClient(main_module.app)

# ── Fixtures ──────────────────────────────────────────────────────────────────

IBUPROFEN_RAW = {
    "openfda": {
        "brand_name": ["Advil"],
        "generic_name": ["ibuprofen"],
        "substance_name": ["IBUPROFEN"],
        "manufacturer_name": ["Pfizer Inc."],
        "route": ["ORAL"],
        "pharm_class_epc": ["Nonsteroidal Anti-inflammatory Drug [EPC]"],
    },
    "indications_and_usage": [
        "Temporarily relieves minor aches and pains due to headache, toothache, backache and fever."
    ],
    "dosage_and_administration": [
        "Adults and children 12 years and over: take 1 tablet every 4 to 6 hours."
    ],
    "adverse_reactions": [
        "• Nausea\n• Headache\n• Dizziness\n• Stomach pain or upset"
    ],
    "contraindications": [
        "Contraindicated in patients with known hypersensitivity to ibuprofen or any NSAID."
    ],
    "warnings": [
        "Use with caution in patients with renal impairment. Monitor renal function."
    ],
    "pregnancy": ["Use with caution during pregnancy. Contraindicated in third trimester."],
    "pediatric_use": ["Safety in children under 12 has not been established."],
    "geriatric_use": ["Use with caution in elderly patients. Increased risk of GI bleeding."],
}

AMOXICILLIN_RAW = {
    "openfda": {
        "brand_name": ["Amoxil"],
        "generic_name": ["amoxicillin"],
        "pharm_class_epc": ["Penicillin-class Antibacterial [EPC]"],
    },
    "indications_and_usage": ["Treatment of mild to moderate infections caused by susceptible bacteria."],
    "dosage_and_administration": ["Adults: 500mg every 8 hours or 875mg every 12 hours."],
    "adverse_reactions": ["• Diarrhea\n• Nausea\n• Rash"],
    "contraindications": ["Do not use in patients with hypersensitivity to penicillins."],
    "warnings": ["Serious hypersensitivity reactions including anaphylaxis have been reported."],
}


# ── /api/drugs/search ─────────────────────────────────────────────────────────

class TestSearchEndpointE2E:
    def test_full_flow_en(self):
        """Flujo completo en inglés: busca, parsea, devuelve ficha estructurada."""
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=IBUPROFEN_RAW)), \
             patch.object(main_module, "enrich_drug_data", new=AsyncMock(side_effect=lambda d, l: d)):
            resp = client.get("/api/drugs/search?query=ibuprofen&lang=en")

        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        drug = data["drug"]
        assert drug["name"] == "Advil"
        assert "pain" in drug["uses"].lower() or "ache" in drug["uses"].lower()
        assert isinstance(drug["sideEffects"], list)
        assert isinstance(drug["compat"], dict)

    def test_full_flow_es_name_translated(self):
        """En modo ES, el nombre genérico se traduce con SPANISH_NAMES."""
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=IBUPROFEN_RAW)), \
             patch.object(main_module, "enrich_drug_data", new=AsyncMock(side_effect=lambda d, l: d)):
            resp = client.get("/api/drugs/search?query=ibuprofeno&lang=es")

        assert resp.status_code == 200
        assert resp.json()["drug"]["name"] == "Ibuprofeno"

    def test_full_flow_es_class_translated(self):
        """En modo ES, la clase farmacológica se traduce."""
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=IBUPROFEN_RAW)), \
             patch.object(main_module, "enrich_drug_data", new=AsyncMock(side_effect=lambda d, l: d)):
            resp = client.get("/api/drugs/search?query=ibuprofeno&lang=es")

        drug_class = resp.json()["drug"]["class"]
        assert "AINE" in drug_class or "antiinflamatorio" in drug_class.lower()

    def test_not_found_returns_correct_shape(self):
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=None)):
            resp = client.get("/api/drugs/search?query=xyzfake")

        assert resp.status_code == 200
        assert resp.json() == {"found": False, "drug": None}

    def test_compat_sections_present(self):
        """La ficha incluye compat con renal, pregnancy, etc. según el raw."""
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=IBUPROFEN_RAW)), \
             patch.object(main_module, "enrich_drug_data", new=AsyncMock(side_effect=lambda d, l: d)):
            resp = client.get("/api/drugs/search?query=ibuprofen&lang=en")

        compat = resp.json()["drug"]["compat"]
        assert "renal" in compat
        assert "pregnancy" in compat

    def test_gemini_fun_fact_added(self):
        """El fun fact de Gemini se añade al campo 'fact' si está disponible."""
        async def fake_enrich(drug, lang):
            drug["fact"] = "Ibuprofen was first synthesized in 1961 by Stewart Adams."
            return drug

        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=IBUPROFEN_RAW)), \
             patch.object(main_module, "enrich_drug_data", new=AsyncMock(side_effect=fake_enrich)):
            resp = client.get("/api/drugs/search?query=ibuprofen&lang=en")

        assert "1961" in resp.json()["drug"]["fact"]

    def test_sources_list_populated(self):
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=IBUPROFEN_RAW)), \
             patch.object(main_module, "enrich_drug_data", new=AsyncMock(side_effect=lambda d, l: d)):
            resp = client.get("/api/drugs/search?query=ibuprofen&lang=en")

        sources = resp.json()["drug"]["sources"]
        assert len(sources) >= 2
        labels = [s["label"] for s in sources]
        assert "OpenFDA" in labels


# ── /api/drugs/external ───────────────────────────────────────────────────────

class TestExternalEndpointE2E:
    def test_returns_brand_and_generic(self):
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=IBUPROFEN_RAW)):
            resp = client.get("/api/drugs/external?query=ibuprofen&lang=en")

        assert resp.status_code == 200
        data = resp.json()
        assert data["brand_name"] == "Advil"
        assert data["generic_name"] == "ibuprofen"
        assert data["manufacturer"] == "Pfizer Inc."

    def test_indications_in_english(self):
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=IBUPROFEN_RAW)):
            resp = client.get("/api/drugs/external?query=ibuprofen&lang=en")

        assert "pain" in resp.json()["indications"].lower()

    def test_not_found(self):
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=None)):
            resp = client.get("/api/drugs/external?query=fake")

        assert resp.json()["found"] is False


# ── /api/drugs/compatibility ──────────────────────────────────────────────────

class TestCompatEndpointE2E:
    def test_renal_patient_flagged(self):
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=IBUPROFEN_RAW)):
            resp = client.post("/api/drugs/compatibility", json={
                "drug_name": "ibuprofen",
                "patient_text": "insuficiencia renal crónica",
                "symptom_text": "dolor",
            })

        data = resp.json()
        assert data["found"] is True
        keys = [f["key"] for f in data["flags"]]
        assert "renal" in keys

    def test_pregnant_patient_flagged(self):
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=IBUPROFEN_RAW)):
            resp = client.post("/api/drugs/compatibility", json={
                "drug_name": "ibuprofen",
                "patient_text": "paciente embarazada tercer trimestre",
                "symptom_text": "fiebre",
            })

        data = resp.json()
        assert data["found"] is True
        assert data["verdict"] in ("risky", "not-recommended")

    def test_healthy_adult_verdict(self):
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=IBUPROFEN_RAW)):
            resp = client.post("/api/drugs/compatibility", json={
                "drug_name": "ibuprofen",
                "patient_text": "adulto sano de 35 años sin antecedentes",
                "symptom_text": "dolor de cabeza",
            })

        data = resp.json()
        assert data["verdict"] in ("suitable", "risky", "not-recommended", "uncertain")
        assert "explanation" in data

    def test_penicillin_allergy_with_amoxicillin(self):
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=AMOXICILLIN_RAW)):
            resp = client.post("/api/drugs/compatibility", json={
                "drug_name": "amoxicillin",
                "patient_text": "alergia a penicilinas conocida",
                "symptom_text": "infección",
            })

        data = resp.json()
        assert data["verdict"] == "not-recommended"

    def test_not_found_drug_returns_generic_risks(self):
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=None)):
            resp = client.post("/api/drugs/compatibility", json={
                "drug_name": "xyzfake",
                "patient_text": "paciente embarazada con insuficiencia renal",
                "symptom_text": "dolor",
            })

        data = resp.json()
        assert data["found"] is False
        assert len(data["generic_risks"]) > 0

    def test_response_has_required_keys(self):
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=IBUPROFEN_RAW)):
            resp = client.post("/api/drugs/compatibility", json={
                "drug_name": "ibuprofen",
                "patient_text": "adulto",
                "symptom_text": "dolor",
            })

        data = resp.json()
        for key in ("found", "verdict", "flags", "explanation", "sources"):
            assert key in data, f"Missing key: {key}"

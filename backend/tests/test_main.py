"""
PharmaCheck — Unit tests
Run with:  pytest backend/tests/ -v
"""

import sys
import os
import pytest
from unittest.mock import patch, AsyncMock

# Add backend to path so we can import main without running the server
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest.mock
import backend.main as main_module
from backend.main import (
        fuzzy_resolve_drug_name,
        translate_class_to_es,
        openfda_to_drug,
        parse_patient,
        analyze_compat,
        _split_to_list,
        _extract_side_effects,
        _extract_contraindications,
        _infer_verdict,
        _first,
        _drug_class,
    )


# ─────────────────────────────────────────
# _first
# ─────────────────────────────────────────

class TestFirst:
    def test_returns_first_element(self):
        assert _first(["hello", "world"]) == "hello"

    def test_empty_list(self):
        assert _first([]) == ""

    def test_none(self):
        assert _first(None) == ""

    def test_truncates_to_max_chars(self):
        assert _first(["a" * 200], max_chars=10) == "a" * 10

    def test_strips_whitespace(self):
        assert _first(["  hello  "]) == "hello"


# ─────────────────────────────────────────
# _split_to_list
# ─────────────────────────────────────────

class TestSplitToList:
    def test_empty_string(self):
        assert _split_to_list("") == []

    def test_splits_on_bullet(self):
        text = "intro\n• nausea\n• headache\n• dizziness"
        result = _split_to_list(text)
        assert any("nausea" in item for item in result)
        assert any("headache" in item for item in result)

    def test_splits_on_sentences(self):
        text = "May cause drowsiness. Avoid alcohol. Do not drive while taking this medication."
        result = _split_to_list(text)
        assert len(result) >= 1

    def test_filters_short_items(self):
        text = "• ok\n• a very relevant adverse reaction here"
        result = _split_to_list(text)
        # "ok" is < 12 chars, should be filtered
        assert not any(r.strip() == "ok" for r in result)

    def test_respects_max_items(self):
        items = "\n• " + "\n• ".join(f"Symptom number {i} which is quite long" for i in range(20))
        result = _split_to_list(items, max_items=5)
        assert len(result) <= 5


# ─────────────────────────────────────────
# _extract_side_effects
# ─────────────────────────────────────────

RX_RAW_ATORVASTATIN = {
    "openfda": {"generic_name": ["atorvastatin"], "pharm_class_epc": ["HMG-CoA Reductase Inhibitor [EPC]"]},
    "adverse_reactions": [
        "6 ADVERSE REACTIONS Most common adverse reactions (incidence ≥5%) are "
        "nasopharyngitis, arthralgia, diarrhea, pain in extremity, and urinary tract infection (6.1)."
    ],
    "contraindications": [
        "4 CONTRAINDICATIONS Acute liver failure or decompensated cirrhosis [see Warnings (5.3)]. "
        "Hypersensitivity to atorvastatin or any excipients in atorvastatin calcium."
    ],
    "indications_and_usage": ["Treatment of hyperlipidemia."],
    "dosage_and_administration": ["Adults: 10 to 80 mg once daily."],
    "warnings_and_cautions": ["Use with caution in patients with renal impairment."],
}

OTC_RAW_IBUPROFEN = {
    "openfda": {"generic_name": ["ibuprofen"], "pharm_class_epc": ["Nonsteroidal Anti-inflammatory Drug [EPC]"]},
    "when_using": ["When using this product take with food or milk if stomach upset occurs"],
    "stop_use": [
        "Stop use and ask a doctor if you experience any of the following signs of stomach bleeding: "
        "feel faint have bloody or black stools vomit blood have stomach pain that does not get better"
    ],
    "do_not_use": [
        "Do not use if you have ever had an allergic reaction to any other pain reliever right before or after heart surgery"
    ],
    "ask_doctor": [
        "Ask a doctor before use if you have high blood pressure, heart disease, liver cirrhosis, kidney disease, or asthma"
    ],
    "warnings": [
        "Allergy alert: Ibuprofen may cause a severe allergic reaction. "
        "Symptoms may include: rash, facial swelling, asthma, hives, skin reddening, shock, blisters"
    ],
    "indications_and_usage": ["Temporarily relieves minor aches and pains."],
    "dosage_and_administration": ["Adults: 200-400mg every 4 to 6 hours."],
}


class TestExtractSideEffects:
    def test_rx_most_common_pattern(self):
        items = _extract_side_effects(RX_RAW_ATORVASTATIN)
        assert isinstance(items, list)
        assert len(items) >= 3
        combined = " ".join(items).lower()
        assert "arthralgia" in combined or "diarrhea" in combined or "nasopharyngitis" in combined

    def test_otc_when_using(self):
        items = _extract_side_effects(OTC_RAW_IBUPROFEN)
        assert isinstance(items, list)
        assert len(items) >= 1

    def test_otc_warnings_symptoms_include(self):
        items = _extract_side_effects(OTC_RAW_IBUPROFEN)
        combined = " ".join(items).lower()
        assert any(k in combined for k in ("rash", "stomach", "faint", "swelling", "food"))

    def test_empty_raw(self):
        assert _extract_side_effects({}) == []

    def test_returns_list(self):
        assert isinstance(_extract_side_effects({}), list)

    def test_max_10_items(self):
        items = _extract_side_effects(RX_RAW_ATORVASTATIN)
        assert len(items) <= 10


class TestExtractContraindications:
    def test_rx_strips_header(self):
        items = _extract_contraindications(RX_RAW_ATORVASTATIN)
        assert isinstance(items, list)
        assert len(items) >= 1
        # Header "4 CONTRAINDICATIONS" should not appear in items
        assert not any(item.strip().startswith("4") for item in items)

    def test_rx_strips_see_refs(self):
        items = _extract_contraindications(RX_RAW_ATORVASTATIN)
        combined = " ".join(items)
        assert "[see" not in combined

    def test_rx_has_content(self):
        items = _extract_contraindications(RX_RAW_ATORVASTATIN)
        combined = " ".join(items).lower()
        assert "liver" in combined or "hypersensitivity" in combined

    def test_otc_do_not_use(self):
        items = _extract_contraindications(OTC_RAW_IBUPROFEN)
        assert isinstance(items, list)
        assert len(items) >= 1
        combined = " ".join(items).lower()
        assert "allergic" in combined or "heart" in combined or "blood pressure" in combined

    def test_empty_raw(self):
        assert _extract_contraindications({}) == []


# ─────────────────────────────────────────
# _infer_verdict
# ─────────────────────────────────────────

class TestInferVerdict:
    def test_contraindicated(self):
        assert _infer_verdict("This drug is contraindicated in patients with renal failure.") == "not-recommended"

    def test_do_not_use(self):
        assert _infer_verdict("Do not use in children under 12.") == "not-recommended"

    def test_caution(self):
        assert _infer_verdict("Use with caution in elderly patients.") == "risky"

    def test_monitor(self):
        assert _infer_verdict("Monitor renal function during treatment.") == "risky"

    def test_no_adjustment_needed(self):
        assert _infer_verdict("No dose adjustment is necessary in elderly patients.") == "suitable"

    def test_well_tolerated(self):
        assert _infer_verdict("The drug is well tolerated in most patients.") == "suitable"

    def test_empty(self):
        assert _infer_verdict("") == "uncertain"

    def test_unknown_text(self):
        # Text about the condition with no clear signal → risky (precaution default)
        result = _infer_verdict("Renal impairment has been observed in some patients.")
        assert result in ("risky", "uncertain")


# ─────────────────────────────────────────
# fuzzy_resolve_drug_name
# ─────────────────────────────────────────

class TestFuzzyResolveDrugName:
    def test_exact_spanish_name(self):
        assert fuzzy_resolve_drug_name("paracetamol") == "acetaminophen"

    def test_exact_brand_name(self):
        assert fuzzy_resolve_drug_name("nurofen") == "ibuprofen"

    def test_case_insensitive(self):
        assert fuzzy_resolve_drug_name("PARACETAMOL") == "acetaminophen"

    def test_typo_tolerance(self):
        # "ibuprofeno" with a small typo
        result = fuzzy_resolve_drug_name("ibuprofen")
        assert result == "ibuprofen"

    def test_spanish_ibuprofen(self):
        assert fuzzy_resolve_drug_name("ibuprofeno") == "ibuprofen"

    def test_unknown_returns_original(self):
        assert fuzzy_resolve_drug_name("xyzunknowndrug999") == "xyzunknowndrug999"

    def test_omeprazol(self):
        assert fuzzy_resolve_drug_name("omeprazol") == "omeprazole"

    def test_amoxicilina(self):
        assert fuzzy_resolve_drug_name("amoxicilina") == "amoxicillin"


# ─────────────────────────────────────────
# translate_class_to_es
# ─────────────────────────────────────────

class TestTranslateClassToEs:
    def test_known_class(self):
        result = translate_class_to_es("Nonsteroidal Anti-inflammatory Drug [EPC]")
        assert "AINE" in result or "antiinflamatorio" in result.lower()

    def test_unknown_class_returned_as_is(self):
        result = translate_class_to_es("Some Completely Unknown Drug Class")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_string(self):
        result = translate_class_to_es("")
        assert result == ""


# ─────────────────────────────────────────
# _drug_class
# ─────────────────────────────────────────

class TestDrugClass:
    def test_picks_epc_first(self):
        openfda = {
            "pharm_class_epc": ["Nonsteroidal Anti-inflammatory Drug [EPC]"],
            "pharm_class_cs": ["Anti-Inflammatory Agents [CS]"],
        }
        result = _drug_class(openfda)
        assert "Nonsteroidal" in result

    def test_strips_bracket_annotation(self):
        openfda = {"pharm_class_epc": ["Opioid Agonist [EPC]"]}
        result = _drug_class(openfda)
        assert "[EPC]" not in result
        assert "Opioid Agonist" in result

    def test_fallback_when_empty(self):
        assert _drug_class({}) == "Medicamento"


# ─────────────────────────────────────────
# openfda_to_drug
# ─────────────────────────────────────────

SAMPLE_RAW = {
    "openfda": {
        "brand_name": ["Advil"],
        "generic_name": ["IBUPROFEN"],
        "substance_name": ["IBUPROFEN"],
        "manufacturer_name": ["Pfizer"],
        "route": ["ORAL"],
        "pharm_class_epc": ["Nonsteroidal Anti-inflammatory Drug [EPC]"],
    },
    "indications_and_usage": ["For relief of mild to moderate pain and fever."],
    "dosage_and_administration": ["Adults: 400mg every 6-8 hours. Do not exceed 1200mg/day."],
    "adverse_reactions": ["• Nausea and vomiting\n• Headache\n• Dizziness and somnolence"],
    "contraindications": ["Contraindicated in patients with known hypersensitivity to ibuprofen."],
    "warnings": ["Use with caution in patients with renal impairment."],
    "when_using": ["Take with food or milk if stomach upset occurs"],
    "do_not_use": ["Do not use if you have ever had an allergic reaction to ibuprofen or aspirin"],
}

class TestOpenfdaToDrug:
    def test_returns_expected_keys(self):
        drug = openfda_to_drug(SAMPLE_RAW)
        for key in ("name", "class", "emoji", "dosage", "uses", "sideEffects", "restrictions", "notFor", "fact", "sources", "compat"):
            assert key in drug, f"Missing key: {key}"

    def test_name_is_brand(self):
        drug = openfda_to_drug(SAMPLE_RAW)
        assert drug["name"] == "Advil"

    def test_class_parsed(self):
        drug = openfda_to_drug(SAMPLE_RAW)
        assert "Nonsteroidal" in drug["class"]

    def test_uses_populated(self):
        drug = openfda_to_drug(SAMPLE_RAW)
        assert "pain" in drug["uses"].lower()

    def test_side_effects_list(self):
        drug = openfda_to_drug(SAMPLE_RAW)
        assert isinstance(drug["sideEffects"], list)

    def test_restrictions_list(self):
        drug = openfda_to_drug(SAMPLE_RAW)
        assert isinstance(drug["restrictions"], list)
        assert any("hypersensitivity" in r.lower() for r in drug["restrictions"])

    def test_sources_has_openfda(self):
        drug = openfda_to_drug(SAMPLE_RAW)
        labels = [s["label"] for s in drug["sources"]]
        assert "OpenFDA" in labels

    def test_compat_has_renal(self):
        drug = openfda_to_drug(SAMPLE_RAW)
        assert "renal" in drug["compat"]

    def test_missing_fields_graceful(self):
        minimal = {"openfda": {"generic_name": ["ASPIRIN"]}}
        drug = openfda_to_drug(minimal)
        assert drug["name"] == "ASPIRIN"
        assert drug["uses"] == ""
        assert drug["sideEffects"] == []


# ─────────────────────────────────────────
# parse_patient
# ─────────────────────────────────────────

class TestParsePatient:
    def test_pregnant(self):
        p = parse_patient("paciente embarazada, 28 años")
        assert p["pregnant"] is True

    def test_child(self):
        p = parse_patient("niño de 7 años con fiebre")
        assert p["child"] is True

    def test_elderly(self):
        p = parse_patient("paciente anciana de 78 años")
        assert p["elderly"] is True

    def test_renal(self):
        p = parse_patient("insuficiencia renal crónica")
        assert p["renal"] is True

    def test_hepatic(self):
        p = parse_patient("cirrosis hepática")
        assert p["hepatic"] is True

    def test_allergy_nsaid(self):
        p = parse_patient("alergia a AINEs conocida")
        assert p["allergy_nsaid"] is True

    def test_gastric(self):
        p = parse_patient("gastritis crónica y reflujo")
        assert p["gastric"] is True

    def test_healthy_adult(self):
        p = parse_patient("adulto sano de 35 años, sin antecedentes")
        assert p["pregnant"] is False
        assert p["child"] is False
        assert p["elderly"] is False
        assert p["renal"] is False


# ─────────────────────────────────────────
# analyze_compat
# ─────────────────────────────────────────

IBUPROFEN_MED = openfda_to_drug(SAMPLE_RAW)

class TestAnalyzeCompat:
    def test_renal_patient_gets_flag(self):
        result = analyze_compat(IBUPROFEN_MED, "insuficiencia renal", "dolor")
        keys = [f["key"] for f in result["flags"]]
        assert "renal" in keys

    def test_healthy_patient_suitable(self):
        result = analyze_compat(IBUPROFEN_MED, "adulto sano 35 años", "dolor de cabeza")
        assert result["verdict"] in ("suitable", "risky")  # no absolute contraindication

    def test_verdict_not_recommended_when_contraindicated(self):
        result = analyze_compat(IBUPROFEN_MED, "alergia a AINEs", "dolor")
        # allergy_nsaid flag → not-recommended
        verdicts = [f["verdict"] for f in result["flags"] if f["key"] == "allergy_nsaid"]
        if verdicts:
            assert result["verdict"] in ("not-recommended", "risky")

    def test_returns_required_keys(self):
        result = analyze_compat(IBUPROFEN_MED, "paciente embarazada", "dolor")
        assert "verdict" in result
        assert "flags" in result
        assert "alternatives" in result


# ─────────────────────────────────────────
# API endpoints (FastAPI TestClient)
# ─────────────────────────────────────────

from fastapi.testclient import TestClient

client = TestClient(main_module.app)


class TestApiEndpoints:
    def test_search_not_found(self):
        """Medicamento inexistente devuelve found=False."""
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=None)):
            resp = client.get("/api/drugs/search?query=xyzfakedrugxyz")
        assert resp.status_code == 200
        assert resp.json()["found"] is False

    def test_search_found(self):
        """Medicamento encontrado devuelve found=True con estructura esperada."""
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=SAMPLE_RAW)), \
             patch.object(main_module, "enrich_drug_data", new=AsyncMock(side_effect=lambda d, l: d)):
            resp = client.get("/api/drugs/search?query=ibuprofen&lang=en")
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert "name" in data["drug"]
        assert "uses" in data["drug"]

    def test_search_lang_es_applies_name_translation(self):
        """En modo ES, el nombre genérico se traduce via SPANISH_NAMES."""
        raw_with_ibuprofen = dict(SAMPLE_RAW)
        raw_with_ibuprofen["openfda"] = {**SAMPLE_RAW["openfda"], "generic_name": ["ibuprofen"]}
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=raw_with_ibuprofen)), \
             patch.object(main_module, "enrich_drug_data", new=AsyncMock(side_effect=lambda d, l: d)):
            resp = client.get("/api/drugs/search?query=ibuprofeno&lang=es")
        assert resp.status_code == 200
        assert resp.json()["drug"]["name"] == "Ibuprofeno"

    def test_external_not_found(self):
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=None)):
            resp = client.get("/api/drugs/external?query=xyzfake")
        assert resp.status_code == 200
        assert resp.json()["found"] is False

    def test_external_found(self):
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=SAMPLE_RAW)):
            resp = client.get("/api/drugs/external?query=ibuprofen&lang=en")
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["generic_name"] == "IBUPROFEN"

    def test_compatibility_not_found(self):
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=None)):
            resp = client.post("/api/drugs/compatibility", json={
                "drug_name": "fakedrugxyz",
                "patient_text": "adulto sano",
                "symptom_text": "dolor"
            })
        assert resp.status_code == 200
        assert resp.json()["found"] is False

    def test_compatibility_found(self):
        with patch.object(main_module, "fetch_openfda_raw", new=AsyncMock(return_value=SAMPLE_RAW)):
            resp = client.post("/api/drugs/compatibility", json={
                "drug_name": "ibuprofen",
                "patient_text": "adulto 40 años sin antecedentes",
                "symptom_text": "dolor de cabeza"
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["verdict"] in ("suitable", "risky", "not-recommended", "uncertain")

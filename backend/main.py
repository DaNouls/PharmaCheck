"""
PharmaCheck — Backend (FastAPI) v2.0
Fuente principal de datos: OpenFDA Drug Label API
https://open.fda.gov/apis/drug/label/
"""

import re
import json
import asyncio
import httpx
from difflib import get_close_matches
from typing import Optional, List
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="PharmaCheck API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENFDA_URL   = "https://api.fda.gov/drug/label.json"
GEMINI_KEY    = "AIzaSyCXS4Kg9yRrzQ5XOmZ8ZwiZAeU3GxSh-wE"
GEMINI_URL    = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent"

# Nombres europeos/españoles/franceses/portugueses/italianos → nombre FDA (inglés)
NAME_TRANSLATIONS = {
    # Analgésicos / Antipiréticos
    "paracetamol":        "acetaminophen",
    "acetaminofén":       "acetaminophen",
    "acetaminofen":       "acetaminophen",
    "gelocatil":          "acetaminophen",
    "efferalgan":         "acetaminophen",
    "termalgín":          "acetaminophen",
    "termalgín":          "acetaminophen",
    "doliprane":          "acetaminophen",   # francés
    "panadol":            "acetaminophen",
    "tylenol":            "acetaminophen",
    "tachipirina":        "acetaminophen",   # italiano
    # AINEs
    "ibuprofeno":         "ibuprofen",
    "ibuprofén":          "ibuprofen",
    "brufen":             "ibuprofen",
    "nurofen":            "ibuprofen",
    "advil":              "ibuprofen",
    "motrin":             "ibuprofen",
    "aspirina":           "aspirin",
    "ácido acetilsalicílico": "aspirin",
    "acido acetilsalicilico": "aspirin",
    "acide acétylsalicylique": "aspirin",   # francés
    "acetilsalicílico":   "aspirin",
    "acetilsalicilico":   "aspirin",
    "diclofenaco":        "diclofenac",
    "diclofénac":         "diclofenac",     # francés
    "voltaren":           "diclofenac",
    "naproxeno":          "naproxen",
    "naproxène":          "naproxen",       # francés
    "metamizol":          "metamizole",
    "dipirona":           "metamizole",
    "nolotil":            "metamizole",
    "ketorolaco":         "ketorolac",
    "ketorolac trometamol": "ketorolac",
    # Antibióticos
    "amoxicilina":        "amoxicillin",
    "amoxicilline":       "amoxicillin",    # francés
    "azitromicina":       "azithromycin",
    "azithromycine":      "azithromycin",   # francés
    "zithromax":          "azithromycin",
    "claritromicina":     "clarithromycin",
    "ciprofloxacino":     "ciprofloxacin",
    "ciprofloxacine":     "ciprofloxacin",  # francés
    "levofloxacino":      "levofloxacin",
    "levofloxacine":      "levofloxacin",   # francés
    "doxiciclina":        "doxycycline",
    "doxycycline":        "doxycycline",
    "cefalexina":         "cephalexin",
    "cephalexine":        "cephalexin",     # francés
    "amoxicilina clavulánico": "amoxicillin clavulanate",
    "amoxicilina clavulanato": "amoxicillin clavulanate",
    "augmentine":         "amoxicillin clavulanate",
    "augmentin":          "amoxicillin clavulanate",
    "trimetoprim":        "trimethoprim",
    "sulfametoxazol":     "sulfamethoxazole",
    "cotrimoxazol":       "trimethoprim sulfamethoxazole",
    "septrin":            "trimethoprim sulfamethoxazole",
    # Antidiabéticos
    "metformina":         "metformin",
    "metformine":         "metformin",      # francés
    "sitagliptina":       "sitagliptin",
    "empagliflozina":     "empagliflozin",
    "dapagliflozina":     "dapagliflozin",
    "canagliflozina":     "canagliflozin",
    "glibenclamida":      "glyburide",
    "glipizida":          "glipizide",
    "insulina":           "insulin",
    # Gastrointestinal
    "omeprazol":          "omeprazole",
    "oméprazole":         "omeprazole",     # francés
    "pantoprazol":        "pantoprazole",
    "lansoprazol":        "lansoprazole",
    "esomeprazol":        "esomeprazole",
    "ranitidina":         "ranitidine",
    "famotidina":         "famotidine",
    "metoclopramida":     "metoclopramide",
    "domperidona":        "domperidone",
    # Cardiovascular
    "atorvastatina":      "atorvastatin",
    "atorvastatine":      "atorvastatin",   # francés
    "simvastatina":       "simvastatin",
    "simvastatine":       "simvastatin",    # francés
    "rosuvastatina":      "rosuvastatin",
    "amlodipino":         "amlodipine",
    "amlodipine":         "amlodipine",
    "enalapril":          "enalapril",
    "lisinopril":         "lisinopril",
    "ramipril":           "ramipril",
    "losartán":           "losartan",
    "losartan":           "losartan",
    "valsartán":          "valsartan",
    "valsartan":          "valsartan",
    "bisoprolol":         "bisoprolol",
    "metoprolol":         "metoprolol",
    "carvedilol":         "carvedilol",
    "furosemida":         "furosemide",
    "furosémide":         "furosemide",     # francés
    "torasemida":         "torsemide",
    "espironolactona":    "spironolactone",
    "clopidogrel":        "clopidogrel",
    "digoxina":           "digoxin",
    "amiodarona":         "amiodarone",
    "nitroglicerina":     "nitroglycerin",
    # Anticoagulantes
    "acenocumarol":       "acenocoumarol",
    "sintrom":            "acenocoumarol",
    "warfarina":          "warfarin",
    "warfarine":          "warfarin",       # francés
    "apixabán":           "apixaban",
    "apixaban":           "apixaban",
    "rivaroxabán":        "rivaroxaban",
    "rivaroxaban":        "rivaroxaban",
    "dabigatrán":         "dabigatran",
    "dabigatran":         "dabigatran",
    "enoxaparina":        "enoxaparin",
    "heparina":           "heparin",
    # Psiquiátricos / Neurológicos
    "alprazolam":         "alprazolam",
    "lorazepam":          "lorazepam",
    "diazepam":           "diazepam",
    "clonazepam":         "clonazepam",
    "sertralina":         "sertraline",
    "sertraline":         "sertraline",
    "fluoxetina":         "fluoxetine",
    "fluoxétine":         "fluoxetine",     # francés
    "escitalopram":       "escitalopram",
    "citalopram":         "citalopram",
    "paroxetina":         "paroxetine",
    "paroxétine":         "paroxetine",     # francés
    "venlafaxina":        "venlafaxine",
    "venlafaxine":        "venlafaxine",
    "duloxetina":         "duloxetine",
    "pregabalina":        "pregabalin",
    "gabapentina":        "gabapentin",
    "lamotrigina":        "lamotrigine",
    "levetiracetam":      "levetiracetam",
    "valproato":          "valproic acid",
    "ácido valproico":    "valproic acid",
    "acido valproico":    "valproic acid",
    "carbamazepina":      "carbamazepine",
    "risperidona":        "risperidone",
    "olanzapina":         "olanzapine",
    "quetiapina":         "quetiapine",
    "donepezilo":         "donepezil",
    "memantina":          "memantine",
    "zolpidem":           "zolpidem",
    "melatonina":         "melatonin",
    # Respiratorio
    "salbutamol":         "albuterol",
    "ventolin":           "albuterol",
    "ventolín":           "albuterol",
    "terbutalina":        "terbutaline",
    "budesonida":         "budesonide",
    "beclometasona":      "beclomethasone",
    "fluticasona":        "fluticasone",
    "montelukast":        "montelukast",
    "tiotropio":          "tiotropium",
    "ipratropio":         "ipratropium",
    "teofilina":          "theophylline",
    # Hormonas / Otros
    "levotiroxina":       "levothyroxine",
    "eutirox":            "levothyroxine",
    "prednisona":         "prednisone",
    "prednisolona":       "prednisolone",
    "dexametasona":       "dexamethasone",
    "hidrocortisona":     "hydrocortisone",
    "betametasona":       "betamethasone",
    "testosterona":       "testosterone",
    "estrógeno":          "estrogen",
    "estradiol":          "estradiol",
    "progesterona":       "progesterone",
    "anticonceptivo":     "ethinyl estradiol",
    # Antihistamínicos
    "cetirizina":         "cetirizine",
    "loratadina":         "loratadine",
    "fexofenadina":       "fexofenadine",
    "difenhidramina":     "diphenhydramine",
    "ebastina":           "ebastine",
    # Antivirales
    "aciclovir":          "acyclovir",
    "valaciclovir":       "valacyclovir",
    "oseltamivir":        "oseltamivir",
    "tamiflu":            "oseltamivir",
    # Oncología / Otros
    "metotrexato":        "methotrexate",
    "ciclofosfamida":     "cyclophosphamide",
    "tamoxifeno":         "tamoxifen",
    "alopurinol":         "allopurinol",
    "colchicina":         "colchicine",
    "hidroxicloroquina":  "hydroxychloroquine",
}

# Pre-computar lista de todas las claves (para fuzzy matching)
_ALL_KNOWN_NAMES = list(NAME_TRANSLATIONS.keys())


def fuzzy_resolve_drug_name(query: str) -> str:
    """
    Resuelve el nombre de un medicamento tolerando errores tipográficos,
    nombres en otros idiomas y grafías alternativas.

    Estrategia:
    1. Coincidencia exacta en NAME_TRANSLATIONS → devuelve traducción FDA
    2. Coincidencia parcial (el query está contenido en alguna clave, o viceversa)
    3. difflib.get_close_matches con cutoff 0.72 contra todas las claves conocidas
    4. difflib más permisivo (0.60) para errores más graves
    5. Fallback: devuelve el query original tal cual

    Devuelve siempre el nombre FDA si se resuelve, o el query original si no.
    """
    q = query.lower().strip()

    # 1. Coincidencia exacta
    if q in NAME_TRANSLATIONS:
        return NAME_TRANSLATIONS[q]

    # 2. Coincidencia parcial — el query es prefijo/subcadena de una clave conocida
    for key, fda_name in NAME_TRANSLATIONS.items():
        if len(q) >= 4 and (key.startswith(q) or q.startswith(key[:max(4, len(key)-2)])):
            return fda_name

    # 3. Fuzzy matching estricto (0.72)
    matches = get_close_matches(q, _ALL_KNOWN_NAMES, n=1, cutoff=0.72)
    if matches:
        return NAME_TRANSLATIONS[matches[0]]

    # 4. Fuzzy matching más permisivo (0.60) para errores graves o idiomas
    matches = get_close_matches(q, _ALL_KNOWN_NAMES, n=1, cutoff=0.60)
    if matches:
        return NAME_TRANSLATIONS[matches[0]]

    # 5. Fallback: query original (OpenFDA podría entenderlo directamente en inglés)
    return query

DEFAULT_SOURCES = [
    {"label": "CIMA AEMPS", "url": "https://cima.aemps.es"},
    {"label": "Vademecum",  "url": "https://www.vademecum.es"},
    {"label": "DrugBank",   "url": "https://go.drugbank.com"},
]


# ─────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────

class CompatRequest(BaseModel):
    drug_name: str
    patient_text: str
    symptom_text: str = ""
    lang: str = "es"   # "es" | "en"


# ─────────────────────────────────────────
# OPENFDA — FETCH
# ─────────────────────────────────────────

async def fetch_openfda_raw(query: str) -> Optional[dict]:
    """
    Busca en OpenFDA. Traduce nombres europeos/españoles/internacionales a inglés (FDA).
    Usa fuzzy matching para tolerar errores tipográficos y grafías alternativas.
    Intenta: nombre resuelto → nombre original → brand name → substance name.
    """
    q_lower = query.lower().strip()
    resolved = fuzzy_resolve_drug_name(q_lower)

    # Construir lista de términos a probar (sin duplicados)
    terms = [resolved]
    if resolved.lower() != q_lower:
        terms.append(query)  # también probar el original por si acaso

    searches = []
    for term in terms:
        t = term.strip()
        searches += [
            f'openfda.generic_name:"{t}"',
            f'openfda.brand_name:"{t}"',
            f'openfda.substance_name:"{t}"',
        ]

    async with httpx.AsyncClient(timeout=12.0) as client:
        for search in searches:
            try:
                resp = await client.get(OPENFDA_URL, params={"search": search, "limit": 1})
                if resp.status_code == 200:
                    results = resp.json().get("results", [])
                    if results:
                        return results[0]
            except Exception:
                continue
    return None


# ─────────────────────────────────────────
# OPENFDA — TEXT HELPERS
# ─────────────────────────────────────────

def _first(lst: Optional[list], max_chars: int = 800) -> str:
    if lst and isinstance(lst, list) and lst[0]:
        return lst[0][:max_chars].strip()
    return ""


def _split_to_list(text: str, max_items: int = 8) -> List[str]:
    """Divide texto libre (efectos adversos, contraindicaciones) en lista de items."""
    if not text:
        return []
    # Intentar separar por bullets, guiones, números de lista o doble salto
    items = re.split(r'\n\s*[\u2022\-\*•]\s*|\n\s*\d+[\.\)]\s*|\n{2,}', text)
    items = [i.strip().rstrip('.').rstrip(',') for i in items if len(i.strip()) > 12]
    if len(items) <= 1:
        # fallback: separar por punto seguido de mayúscula
        items = re.split(r'\.\s+(?=[A-Z])', text)
        items = [i.strip() for i in items if len(i.strip()) > 12]
    return [i[:200] for i in items[:max_items]]


def _drug_class(openfda: dict) -> str:
    for key in ("pharm_class_epc", "pharm_class_cs", "pharm_class_moa"):
        classes = openfda.get(key, [])
        if classes:
            return re.sub(r'\s*\[.*?\]', '', classes[0]).strip()
    return "Medicamento"


def _emoji(drug_class: str) -> str:
    c = drug_class.lower()
    if any(k in c for k in ["anti-inflammatory", "nsaid", "analgesic", "pain", "antipyretic"]):
        return "💊"
    if any(k in c for k in ["antibiotic", "antibacterial", "antimicrobial", "penicillin", "macrolide"]):
        return "🟡"
    if any(k in c for k in ["antidiabetic", "hypoglycemic", "biguanide", "insulin"]):
        return "🔴"
    if any(k in c for k in ["proton pump", "antacid", "h2 blocker", "gastric"]):
        return "🟣"
    if any(k in c for k in ["anticoagulant", "antithrombotic", "antiplatelet"]):
        return "🩸"
    if any(k in c for k in ["antihypertensive", "cardiovascular", "beta blocker", "ace inhibitor"]):
        return "❤️"
    if any(k in c for k in ["antidepressant", "antianxiety", "psychiatric", "psychotropic", "ssri"]):
        return "🧠"
    if any(k in c for k in ["antiviral", "antiretroviral"]):
        return "🔬"
    if any(k in c for k in ["corticosteroid", "steroid"]):
        return "⚗️"
    return "💊"


def _infer_verdict(text: str) -> str:
    """Infiere un verdict de compatibilidad a partir del texto del label FDA."""
    if not text:
        return "uncertain"
    t = text.lower()
    not_rec = ["contraindicated", "must not be used", "should not be used",
               "do not use", "do not administer", "is prohibited", "is not recommended"]
    risky_kw = ["use with caution", "caution", "caution should be exercised",
                "monitor", "reduce dose", "dose reduction", "adjust dose",
                "not recommended", "avoid if possible", "may worsen",
                "increased risk", "use caution", "carefully"]
    suitable_kw = ["no dose adjustment", "not necessary to adjust", "considered safe",
                   "no special precautions", "well tolerated", "no clinically significant"]
    if any(k in t for k in not_rec):
        return "not-recommended"
    if any(k in t for k in suitable_kw):
        return "suitable"
    if any(k in t for k in risky_kw):
        return "risky"
    # Si se menciona la condición pero sin clasificación clara → precaución
    return "risky"


def _extract_section_for(text: str, keywords: List[str], max_chars: int = 400) -> str:
    """Extrae la frase/párrafo más relevante de un texto libre para una condición dada."""
    if not text:
        return ""
    pattern = '(' + '|'.join(keywords) + r')[\s\S]{0,350}'
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(0)[:max_chars].strip() if match else ""


# ─────────────────────────────────────────
# OPENFDA → FORMATO ESTÁNDAR
# ─────────────────────────────────────────

def openfda_to_drug(raw: dict) -> dict:
    """
    Transforma un resultado crudo de OpenFDA al formato que espera el frontend:
    {name, class, emoji, dosage, uses, sideEffects[], restrictions[], notFor[], fact, sources[], compat{}}
    """
    openfda = raw.get("openfda", {})

    # Nombre
    name = (
        _first(openfda.get("brand_name")) or
        _first(openfda.get("generic_name")) or
        _first(openfda.get("substance_name")) or
        "Unknown"
    )
    generic_name = _first(openfda.get("generic_name")) or name

    # Clase y emoji
    drug_class = _drug_class(openfda)
    emoji = _emoji(drug_class)

    # Dosificación — primera línea del campo
    dosage_raw = _first(raw.get("dosage_and_administration"), 500)
    dosage = (dosage_raw.split('\n')[0] or dosage_raw.split('.')[0])[:250].strip()

    # Indicaciones
    uses = (
        _first(raw.get("indications_and_usage"), 700) or
        _first(raw.get("purpose"), 700) or
        "Consult the official package leaflet for complete indications."
    )

    # Efectos adversos
    adverse_text = _first(raw.get("adverse_reactions"), 2000)
    side_effects = _split_to_list(adverse_text) or [
        "No significant side effects recorded for this medication.",
        "Consult the package leaflet for the complete list of adverse effects.",
    ]

    # Contraindicaciones
    contra_text = _first(raw.get("contraindications"), 2000)
    restrictions = _split_to_list(contra_text) or [
        "No important restrictions identified for this medication.",
        "Consult the package leaflet for the complete list of contraindications.",
    ]

    # Cuándo no usar — advertencias
    warnings_text = (
        _first(raw.get("warnings_and_cautions"), 2000) or
        _first(raw.get("warnings"), 2000)
    )
    not_for = _split_to_list(warnings_text)[:6] or restrictions[:3]

    # Fuentes
    sources = [
        {"label": "OpenFDA",  "url": f"https://api.fda.gov/drug/label.json?search=openfda.generic_name:{generic_name}&limit=1"},
        {"label": "DailyMed", "url": f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?query={generic_name}"},
        {"label": "FDA",      "url": "https://www.fda.gov/drugs"},
    ]

    # ── COMPAT — extraído de secciones específicas del label FDA ──
    compat = {}

    # Embarazo
    preg_text = (
        _first(raw.get("pregnancy"), 600) or
        _first(raw.get("teratogenic_effects"), 600) or
        _extract_section_for(warnings_text, ["pregnant", "pregnancy", "fetal", "teratogen"])
    )
    if preg_text:
        compat["pregnancy"] = {"verdict": _infer_verdict(preg_text), "note": preg_text[:350]}

    # Pediatría
    ped_text = (
        _first(raw.get("pediatric_use"), 600) or
        _extract_section_for(warnings_text, ["pediatric", "children", "child", "neonates", "infants"])
    )
    if ped_text:
        compat["child"] = {"verdict": _infer_verdict(ped_text), "note": ped_text[:350]}

    # Geriatría
    ger_text = (
        _first(raw.get("geriatric_use"), 600) or
        _extract_section_for(warnings_text, ["geriatric", "elderly", "older adults", "aged"])
    )
    if ger_text:
        compat["elderly"] = {"verdict": _infer_verdict(ger_text), "note": ger_text[:350]}

    # Insuficiencia renal
    renal_text = (
        _first(raw.get("renal_impairment"), 600) or
        _extract_section_for(warnings_text or contra_text, ["renal", "kidney", "renal impairment", "renal failure"])
    )
    if renal_text:
        compat["renal"] = {"verdict": _infer_verdict(renal_text), "note": renal_text[:350]}

    # Insuficiencia hepática
    hep_text = (
        _first(raw.get("hepatic_impairment"), 600) or
        _extract_section_for(warnings_text or contra_text, ["hepatic", "liver", "hepatic impairment", "hepatic failure"])
    )
    if hep_text:
        compat["hepatic"] = {"verdict": _infer_verdict(hep_text), "note": hep_text[:350]}

    # Gastrointestinal
    gi_text = _extract_section_for(
        warnings_text or contra_text,
        ["gastrointestinal", "gastric", "stomach", "ulcer", "GI bleeding", "peptic"]
    )
    if gi_text:
        compat["gastric"] = {"verdict": _infer_verdict(gi_text), "note": gi_text[:350]}

    # Alergia a AINEs (para NSAIDs)
    nsaid_text = _extract_section_for(
        contra_text or warnings_text,
        ["aspirin", "nsaid", "nonsteroidal", "hypersensitivity", "allergic"]
    )
    if nsaid_text:
        compat["allergy_nsaid"] = {"verdict": _infer_verdict(nsaid_text), "note": nsaid_text[:350]}

    compat["alternatives"] = []

    return {
        "name": name,
        "class": drug_class,
        "emoji": emoji,
        "dosage": dosage or "Consultar prospecto.",
        "uses": uses,
        "sideEffects": side_effects,
        "restrictions": restrictions,
        "notFor": not_for,
        "fact": "",
        "sources": sources,
        "compat": compat,
    }


# ─────────────────────────────────────────
# LÓGICA DE COMPATIBILIDAD (igual que antes,
# ahora funciona con datos reales de OpenFDA)
# ─────────────────────────────────────────

def parse_patient(text: str) -> dict:
    t = text.lower()
    return {
        "pregnant":           bool(re.search(r"embara|gestaci|pregnant|primer trimestre|segundo trimestre|tercer trimestre", t)),
        "trimester3":         bool(re.search(r"tercer trimestre|3.*trimestre|trimestre.*3", t)),
        "child":              bool(re.search(r"niñ|infant|bebé|bebe|pediatr|[0-9]+\s*mes|años.*([0-9]|1[0-5])\b|\b([0-9]|1[0-5])\s*años", t)),
        "elderly":            bool(re.search(r"ancian|mayor.*65|65.*años|[7-9][0-9]\s*años|vejez|geriatr", t)),
        "allergy_nsaid":      bool(re.search(r"alergi.*aine|alergi.*ibuprofen|alergi.*aspirina|alergi.*nsaid|hipersensib.*aine", t)),
        "allergy_penicillin": bool(re.search(r"alergi.*penicil|alergi.*amoxicil|alergi.*betalact", t)),
        "gastric":            bool(re.search(r"gastritis|úlcera|ulcera|reflujo|erge|estómago|estomago|dispepsia|gástrico|gastr", t)),
        "renal":              bool(re.search(r"renal|riñón|riñon|insuficiencia.*renal|dialisis|diálisis", t)),
        "hepatic":            bool(re.search(r"hepatic|hígado|higado|cirrosis|hepatitis|insuficiencia.*hepática", t)),
        "cardiac":            bool(re.search(r"cardíac|cardiaco|cardiac|corazón|corazon|arritmia|taquicardia|hipertens", t)),
        "diabetic":           bool(re.search(r"diabet|glucosa|insulin|glucem", t)),
    }


def analyze_compat(med: dict, patient_text: str, symptom_text: str) -> dict:
    p = parse_patient(patient_text + " " + symptom_text)
    c = med.get("compat", {})
    flags = []

    mapping = [
        (p["pregnant"],           "pregnancy",    "Embarazo"),
        (p["trimester3"] and not p["pregnant"], "pregnancy", "Tercer trimestre"),
        (p["allergy_nsaid"],      "allergy_nsaid","Alergia a AINEs"),
        (p["gastric"],            "gastric",      "Patología gástrica"),
        (p["renal"],              "renal",        "Insuficiencia renal"),
        (p["hepatic"],            "hepatic",      "Hepatopatía"),
        (p["child"],              "child",        "Paciente pediátrico"),
        (p["elderly"],            "elderly",      "Paciente anciano"),
    ]

    for condition, key, label in mapping:
        if condition and key in c:
            flags.append({"key": key, "label": label, **c[key]})

    # Alergia a penicilinas (caso especial)
    if p["allergy_penicillin"] and "penicillin" in med.get("class", "").lower():
        flags.append({
            "key": "allergy_pen", "label": "Alergia a penicilinas",
            "verdict": "not-recommended",
            "note": "Contraindicada en pacientes con alergia a penicilinas. Riesgo de anafilaxia."
        })

    verdict = "suitable"
    if any(f["verdict"] == "not-recommended" for f in flags):
        verdict = "not-recommended"
    elif any(f["verdict"] == "risky" for f in flags):
        verdict = "risky"

    return {"verdict": verdict, "flags": flags, "alternatives": c.get("alternatives", [])}


def suitability_text(med: dict, patient_text: str) -> dict:
    t = patient_text.lower()
    uses_lower = med.get("uses", "").lower()

    cond_map = {
        "dolor":       ["dolor", "pain", "cefalea", "headache", "muscular"],
        "fiebre":      ["fiebre", "fever", "temperatura"],
        "infección":   ["infección", "infeccion", "bacteria", "amigdal", "faringit", "sinusit", "otitis", "neumonia"],
        "diabetes":    ["diabet", "glucosa", "azúcar", "azucar"],
        "gastritis":   ["gastrit", "reflujo", "úlcera", "ulcera", "estomago", "gástrico"],
        "inflamación": ["inflamac", "artritis", "lumbal", "rodilla"],
    }

    matched = [c for c, kws in cond_map.items()
               if any(k in t for k in kws) and c.split("/")[0] in uses_lower]

    if matched:
        return {"match": True, "text": f"{med['name']} está indicado para {', '.join(matched)}, lo cual corresponde con la información del paciente proporcionada."}
    return {"match": None, "text": f"{med['name']} se usa principalmente para: {med['uses'].split('.')[0][:200]}."}


def build_explanation(verdict: str, med_name: str, suit_text: str) -> str:
    if verdict == "suitable":
        return (f"Basándonos en la información disponible (OpenFDA), {med_name} parece adecuado para este caso. "
                f"{suit_text} No se han identificado contraindicaciones absolutas con las condiciones descritas. "
                "Confirmar siempre con el médico tratante.")
    if verdict == "risky":
        return (f"{med_name} puede ser útil para la condición descrita, pero existen factores de riesgo que requieren precaución. "
                f"{suit_text} Se recomienda supervisión médica y posible ajuste de dosis.")
    if verdict == "not-recommended":
        return (f"Existe al menos una contraindicación relevante para usar {med_name} en este paciente según la ficha FDA. "
                f"{suit_text} Se recomienda buscar alternativas y consultar con el médico.")
    return (f"Información insuficiente para evaluar completamente {med_name} en este caso. "
            "Consultar con un profesional sanitario.")


# ─────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────

@app.get("/api/drugs/search")
async def search_drug(query: str = Query(..., min_length=1)):
    """
    Busca un medicamento en OpenFDA y devuelve su ficha estructurada.
    """
    raw = await fetch_openfda_raw(query)
    if raw:
        return {"found": True, "drug": openfda_to_drug(raw)}
    return {"found": False, "drug": None}


@app.post("/api/drugs/compatibility")
async def drug_compatibility(req: CompatRequest):
    """
    Analiza la compatibilidad de un medicamento con el perfil del paciente.
    Obtiene los datos del medicamento desde OpenFDA y aplica lógica de compatibilidad.
    """
    raw = await fetch_openfda_raw(req.drug_name)

    if not raw:
        # Medicamento no encontrado en OpenFDA — análisis genérico
        p = parse_patient(req.patient_text)
        risks = []
        if p["pregnant"]:  risks.append("embarazo (precaución general con cualquier medicamento)")
        if p["child"]:     risks.append("edad pediátrica (verificar dosis y contraindicaciones específicas)")
        if p["elderly"]:   risks.append("edad avanzada (mayor sensibilidad a efectos adversos)")
        if p["renal"]:     risks.append("función renal comprometida (posible ajuste de dosis)")
        if p["hepatic"]:   risks.append("función hepática comprometida (posible ajuste de dosis)")

        return {
            "found": False,
            "drug_name": req.drug_name,
            "verdict": "risky" if risks else "uncertain",
            "flags": [],
            "generic_risks": risks,
            "alternatives": [],
            "suitability": {"match": None, "text": f"No se encontró '{req.drug_name}' en OpenFDA."},
            "explanation": f"No se encontró información sobre '{req.drug_name}' en OpenFDA. Evaluación basada en perfil del paciente.",
            "sources": DEFAULT_SOURCES,
        }

    med = openfda_to_drug(raw)
    compat = analyze_compat(med, req.patient_text, req.symptom_text)
    suit = suitability_text(med, req.patient_text + " " + req.symptom_text)
    explanation = build_explanation(compat["verdict"], med["name"], suit["text"])

    return {
        "found": True,
        "drug_name": med["name"],
        "verdict": compat["verdict"],
        "flags": compat["flags"],
        "generic_risks": [],
        "alternatives": compat["alternatives"],
        "suitability": suit,
        "explanation": explanation,
        "sources": med["sources"],
    }


@app.get("/api/drugs/external")
async def external_drug_info(query: str = Query(..., min_length=1)):
    """
    Devuelve el resultado crudo de OpenFDA para inspección/debug.
    """
    raw = await fetch_openfda_raw(query)
    if not raw:
        return {"found": False, "source": "OpenFDA"}
    openfda = raw.get("openfda", {})
    return {
        "found": True,
        "source": "OpenFDA",
        "brand_name":       _first(openfda.get("brand_name")),
        "generic_name":     _first(openfda.get("generic_name")),
        "manufacturer":     _first(openfda.get("manufacturer_name")),
        "route":            _first(openfda.get("route")),
        "product_type":     _first(openfda.get("product_type")),
        "pharm_class":      _first(openfda.get("pharm_class_epc")),
        "indications":      _first(raw.get("indications_and_usage"), 600),
        "warnings":         _first(raw.get("warnings") or raw.get("warnings_and_cautions"), 600),
        "dosage_forms":     _first(raw.get("dosage_and_administration"), 400),
        "contraindications":_first(raw.get("contraindications"), 600),
        "adverse_reactions":_first(raw.get("adverse_reactions"), 600),
        "pregnancy":        _first(raw.get("pregnancy"), 400),
        "pediatric_use":    _first(raw.get("pediatric_use"), 400),
        "geriatric_use":    _first(raw.get("geriatric_use"), 400),
    }


@app.post("/api/drugs/gemini-compatibility")
async def gemini_compatibility(req: CompatRequest):
    """
    Genera un informe de compatibilidad con el paciente usando Google Gemini.
    Primero obtiene datos reales del medicamento desde OpenFDA, luego
    los envía a Gemini junto con el perfil del paciente para generar un
    informe médico estructurado en español.
    """
    # 1. Obtener info real del medicamento desde OpenFDA
    raw = await fetch_openfda_raw(req.drug_name)
    drug_context = ""
    drug_name_display = req.drug_name

    if raw:
        med = openfda_to_drug(raw)
        drug_name_display = med["name"]
        drug_context = f"""
Información oficial del medicamento (fuente: OpenFDA / FDA):
- Nombre: {med['name']}
- Clase farmacológica: {med['class']}
- Dosificación: {med['dosage']}
- Indicaciones: {med['uses'][:500]}
- Efectos adversos conocidos: {'; '.join(med['sideEffects'][:5])}
- Contraindicaciones: {'; '.join(med['restrictions'][:5])}
"""
    else:
        drug_context = f"Medicamento: {req.drug_name} (no encontrado en OpenFDA, usar conocimiento general)."

    # 2. Construir el prompt para Gemini
    lang_instr = "Respond entirely in English." if req.lang == "en" else "Responde completamente en español."
    prompt = f"""Eres un sistema experto de análisis farmacéutico clínico.
Analiza la compatibilidad del siguiente medicamento con el perfil del paciente y genera un informe médico detallado.

{drug_context}

Información del paciente:
{req.patient_text or 'No especificada.'}

Síntomas / motivo de consulta:
{req.symptom_text or req.drug_name}

{lang_instr}"""

    # Schema JSON que Gemini debe respetar estrictamente
    response_schema = {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["suitable", "risky", "not-recommended", "uncertain"],
                "description": "Veredicto global de compatibilidad"
            },
            "resumen": {
                "type": "string",
                "description": "Frase corta que resume la evaluación (máx 120 caracteres)"
            },
            "indicado_para": {
                "type": "string",
                "description": "Si el medicamento es adecuado para los síntomas descritos (1-2 frases)"
            },
            "factores_riesgo": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "factor":      {"type": "string", "description": "Nombre del factor de riesgo"},
                        "nivel":       {"type": "string", "enum": ["alto", "medio", "bajo"]},
                        "explicacion": {"type": "string", "description": "Explicación clínica breve"}
                    },
                    "required": ["factor", "nivel", "explicacion"]
                }
            },
            "explicacion_general": {
                "type": "string",
                "description": "Evaluación clínica global en 2-3 frases"
            },
            "recomendaciones": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Lista de recomendaciones para el paciente"
            },
            "alternativas": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Medicamentos alternativos si el veredicto es risky o not-recommended"
            },
            "advertencia_critica": {
                "type": "string",
                "description": "Contraindicación absoluta crítica si existe, cadena vacía si no hay"
            }
        },
        "required": ["verdict", "resumen", "indicado_para", "factores_riesgo",
                     "explicacion_general", "recomendaciones", "alternativas", "advertencia_critica"]
    }

    # 3. Llamar a Gemini con JSON Schema nativo
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(GEMINI_URL,
                headers={"X-goog-api-key": GEMINI_KEY, "Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "maxOutputTokens": 7500,
                        "responseMimeType": "application/json",
                        "responseJsonSchema": response_schema
                    }
                }
            )
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e!r}"}

    if resp.status_code != 200:
        return {"error": f"Gemini respondió con status {resp.status_code}", "detail": resp.text[:300]}

    try:
        gemini_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        report = json.loads(gemini_text)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        return {"error": f"Error procesando respuesta de Gemini: {str(e)}", "detail": resp.text[:300]}

    report["drug_name"] = drug_name_display
    report["sources"] = med["sources"] if raw else DEFAULT_SOURCES
    return report

@app.post("/api/drugs/gemini-sheet")
async def gemini_sheet(req: CompatRequest):
    """
    Genera una ficha enriquecida de medicamento usando Gemini AI.
    Combina datos reales de OpenFDA con análisis de Gemini.
    """
    raw = await fetch_openfda_raw(req.drug_name)
    drug_name_display = req.drug_name
    drug_context = ""
    med = None

    if raw:
        med = openfda_to_drug(raw)
        drug_name_display = med["name"]
        drug_context = f"""Información oficial del medicamento (fuente: OpenFDA / FDA):
- Nombre: {med['name']}
- Clase farmacológica: {med['class']}
- Dosificación: {med['dosage']}
- Indicaciones: {med['uses'][:600]}
- Efectos adversos conocidos: {'; '.join(med['sideEffects'][:6])}
- Contraindicaciones: {'; '.join(med['restrictions'][:5])}
- Advertencias: {'; '.join(med['notFor'][:5])}
"""
    else:
        drug_context = f"Medicamento: {req.drug_name} (usar conocimiento general de farmacología)."

    lang_instr = "Respond entirely in English." if req.lang == "en" else "Responde completamente en español."
    prompt = f"""Eres un sistema experto de información farmacéutica clínica.
Genera una ficha técnica completa y detallada del siguiente medicamento.
Proporciona información precisa, útil y bien estructurada.

{drug_context}

Medicamento consultado por el usuario: {req.drug_name}

{lang_instr}"""

    response_schema = {
        "type": "object",
        "properties": {
            "nombre":              {"type": "string", "description": "Nombre oficial del medicamento"},
            "clase_farmacologica": {"type": "string", "description": "Clase terapéutica o farmacológica"},
            "emoji":               {"type": "string", "description": "Un único emoji representativo (ej: 💊 🩺 ❤️)"},
            "resumen":             {"type": "string", "description": "1 sola frase corta, máx 90 caracteres"},
            "indicaciones":        {"type": "array", "items": {"type": "string"},
                                    "description": "Lista de condiciones/usos (4-7 elementos, cada uno máx 3 palabras, ej: 'Dolor de cabeza', 'Fiebre', 'Inflamación articular')"},
            "como_funciona":       {"type": "string", "description": "Mecanismo de acción, máx 75 caracteres, muy breve"},
            "dosificacion_tipica": {"type": "string", "description": "Pauta estándar adultos, máx 60 caracteres"},
            "efectos_secundarios": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "efecto":     {"type": "string", "description": "Nombre del efecto, máx 4 palabras"},
                        "frecuencia": {"type": "string", "enum": ["muy frecuente", "frecuente", "poco frecuente", "raro"]},
                        "gravedad":   {"type": "string", "enum": ["leve", "moderado", "grave"]}
                    },
                    "required": ["efecto", "frecuencia", "gravedad"]
                },
                "description": "Máx 8 efectos secundarios"
            },
            "contraindicaciones":        {"type": "array", "items": {"type": "string"},
                                          "description": "Máx 5 contraindicaciones, cada una máx 5 palabras"},
            "advertencias_importantes":  {"type": "array", "items": {"type": "string"},
                                          "description": "Máx 4 advertencias clave, cada una máx 6 palabras"},
            "interacciones_destacadas":  {"type": "array", "items": {"type": "string"},
                                          "description": "Máx 4 interacciones, cada una máx 5 palabras"},
            "poblaciones_especiales": {
                "type": "object",
                "properties": {
                    "embarazo":              {"type": "string", "description": "máx 50 caracteres"},
                    "ninos":                 {"type": "string", "description": "máx 50 caracteres"},
                    "ancianos":              {"type": "string", "description": "máx 50 caracteres"},
                    "insuficiencia_renal":   {"type": "string", "description": "máx 50 caracteres"},
                    "insuficiencia_hepatica":{"type": "string", "description": "máx 50 caracteres"}
                }
            },
            "dato_curioso":       {"type": "string", "description": "Dato curioso breve, máx 110 caracteres"},
            "consejos_practicos": {"type": "array", "items": {"type": "string"},
                                   "description": "3-4 consejos, cada uno máx 8 palabras"}
        },
        "required": ["nombre", "clase_farmacologica", "emoji", "resumen", "indicaciones",
                     "como_funciona", "dosificacion_tipica", "efectos_secundarios",
                     "contraindicaciones", "advertencias_importantes", "interacciones_destacadas",
                     "poblaciones_especiales", "dato_curioso", "consejos_practicos"]
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(GEMINI_URL,
                headers={"X-goog-api-key": GEMINI_KEY, "Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "maxOutputTokens": 7500,
                        "responseMimeType": "application/json",
                        "responseJsonSchema": response_schema
                    }
                }
            )
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e!r}"}

    if resp.status_code != 200:
        return {"error": f"Gemini respondió con status {resp.status_code}", "detail": resp.text[:300]}

    try:
        gemini_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        report = json.loads(gemini_text)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        return {"error": f"Error procesando respuesta de Gemini: {str(e)}", "detail": resp.text[:300]}

    report["sources"] = med["sources"] if med else DEFAULT_SOURCES
    return report

@app.get("/")
async def root():
    return {
        "app": "PharmaCheck API",
        "version": "2.0.0",
        "data_source": "OpenFDA Drug Label API (open.fda.gov)",
        "endpoints": [
            "GET  /api/drugs/search?query=ibuprofen",
            "POST /api/drugs/compatibility  {drug_name, patient_text, symptom_text}",
            "GET  /api/drugs/external?query=ibuprofen",
            "GET  /docs  (Swagger UI)",
        ],
    }

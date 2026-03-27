"""
PharmaCheck — Backend (FastAPI) v2.0
Fuente principal de datos: OpenFDA Drug Label API
https://open.fda.gov/apis/drug/label/
"""

import os
import re
import json
import html
import asyncio
import httpx
from difflib import get_close_matches
from typing import Optional, List
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel

app = FastAPI(title="PharmaCheck API", version="2.0.0")

# ─────────────────────────────────────────
# TRADUCCIÓN — deep-translator (Google Translate, sin API key)
# ─────────────────────────────────────────

_lt_ready = False

try:
    from deep_translator import GoogleTranslator
    _lt_ready = True
except ImportError:
    GoogleTranslator = None


def _init_libretranslate():
    if _lt_ready:
        print("[Translate] ✓ deep-translator (Google) listo")
    else:
        print("[Translate] deep-translator no disponible — se devuelve texto original.")


def translate_en_es(text: str) -> str:
    """Traduce texto de inglés a español usando Google Translate (deep-translator)."""
    if not _lt_ready or not text:
        return text
    try:
        return GoogleTranslator(source="en", target="es").translate(text)
    except Exception:
        return text


def translate_text(text: str, lang: str) -> str:
    """Traduce texto de inglés al idioma indicado (deep-translator)."""
    if not _lt_ready or not text or lang == "en":
        return text
    try:
        return GoogleTranslator(source="en", target=lang).translate(text)
    except Exception:
        return text


# ── OPTIMIZACIÓN 1: caché en memoria ──────────────────────────────────────────
# Clave: "{query_lower}_{lang}" → {"data": <resultado completo>, "hits": int}
# El contador NO se reinicia al refrescar; refresco cada _CACHE_REFRESH_EVERY hits.
_DRUG_CACHE: dict = {}
_CACHE_REFRESH_EVERY: int = 12


def _cache_get(key: str):
    """Incrementa el contador y devuelve los datos cacheados, o None si hay que refrescar."""
    entry = _DRUG_CACHE.get(key)
    if entry is None:
        return None
    entry["hits"] += 1
    if entry["hits"] % _CACHE_REFRESH_EVERY == 0:
        return None          # toca refrescar; el contador sigue subiendo
    return entry["data"]


def _cache_set(key: str, data: dict) -> None:
    """Guarda o actualiza el caché sin reiniciar el contador."""
    if key in _DRUG_CACHE:
        _DRUG_CACHE[key]["data"] = data
    else:
        _DRUG_CACHE[key] = {"data": data, "hits": 1}


# ── OPTIMIZACIÓN 3: CIMA completo en paralelo con OpenFDA ─────────────────────
async def _fetch_cima_full(query: str):
    """
    Ejecuta fetch_cima_data y fetch_cima_ficha en secuencia dentro de esta
    corutina, para que el caller pueda lanzarla en paralelo con fetch_openfda_raw.
    Devuelve (cima_meta, ficha).
    """
    meta = await fetch_cima_data(query)
    if not meta or not meta.get("nregistro"):
        return meta, {}
    ficha = await fetch_cima_ficha(meta["nregistro"])
    return meta, ficha


# ── OPTIMIZACIÓN 2: traducciones en paralelo ──────────────────────────────────
# Envía todos los textos a traducir en una sola llamada a Google Translate,
# separados por un marcador numérico que el traductor no toca.
_TRANS_SEP = " [[[|||]]] "


async def _translate_fields_parallel(drug: dict, lang: str) -> None:
    """
    Traduce uses, dosage, restrictions, notFor y sideEffects usando DOS
    requests paralelos a Google Translate para reducir la latencia total.
    - Batch A: uses + dosage + restrictions
    - Batch B: notFor + sideEffects
    Modifica `drug` in-place. Solo actúa si _lt_ready y lang no es en/es.
    """
    if not _lt_ready or lang in ("en", "es"):
        return

    r_list = list(drug.get("restrictions", []))
    n_list = list(drug.get("notFor", []))
    s_list = list(drug.get("sideEffects", []))

    # Batch A: campos principales (uses, dosage, restrictions)
    texts_a = [drug.get("uses", ""), drug.get("dosage", "")] + r_list
    # Batch B: campos secundarios (notFor, sideEffects)
    texts_b = n_list + s_list

    ne_a = [(i, t) for i, t in enumerate(texts_a) if t and t.strip()]
    ne_b = [(i, t) for i, t in enumerate(texts_b) if t and t.strip()]

    if not ne_a and not ne_b:
        return

    async def _do_batch(ne, texts, tgt):
        if not ne:
            return
        combined = _TRANS_SEP.join(t for _, t in ne)
        try:
            result = await asyncio.to_thread(
                GoogleTranslator(source="en", target=tgt).translate, combined
            )
            parts = [p.strip() for p in result.split("[[[|||]]]")]
            for li, (orig_idx, _) in enumerate(ne):
                if li < len(parts):
                    texts[orig_idx] = parts[li]
        except Exception:
            pass  # texto original intacto

    # Ambos batches corren en paralelo
    await asyncio.gather(
        _do_batch(ne_a, texts_a, lang),
        _do_batch(ne_b, texts_b, lang),
    )

    drug["uses"]         = texts_a[0]
    drug["dosage"]       = texts_a[1]
    drug["restrictions"] = texts_a[2 : 2 + len(r_list)]
    drug["notFor"]       = texts_b[: len(n_list)]
    drug["sideEffects"]  = texts_b[len(n_list) :]


@app.on_event("startup")
async def startup_event():
    _init_libretranslate()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENFDA_URL = "https://api.fda.gov/drug/label.json"
CIMA_SEARCH_URL = "https://cima.aemps.es/cima/rest/medicamentos"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent"

# Nombres europeos/españoles → nombre FDA (inglés)
NAME_TRANSLATIONS = {
    # ── Analgésicos / Antipiréticos ──────────────────────────────────────────
    "paracetamol":                    "acetaminophen",
    "acetaminofén":                   "acetaminophen",
    "gelocatil":                      "acetaminophen",
    "efferalgan":                     "acetaminophen",
    "termalgín":                      "acetaminophen",
    "doliprane":                      "acetaminophen",  # FR
    "tachipirina":                    "acetaminophen",  # IT
    "dafalgan":                       "acetaminophen",  # FR/CH
    "panadol":                        "acetaminophen",  # marca intl
    "calpol":                         "acetaminophen",  # UK
    "tylenol":                        "acetaminophen",  # US
    "febrectal":                      "acetaminophen",  # ES pediátrico
    "apiretal":                       "acetaminophen",  # ES pediátrico
    # ── AINEs ────────────────────────────────────────────────────────────────
    "ibuprofeno":                     "ibuprofen",
    "ibuprofène":                     "ibuprofen",      # FR
    "ibuprofen":                      "ibuprofen",
    "nurofen":                        "ibuprofen",      # marca EU
    "advil":                          "ibuprofen",      # marca intl
    "brufen":                         "ibuprofen",      # marca EU
    "espidifen":                      "ibuprofen",      # ES
    "dalsy":                          "ibuprofen",      # ES pediátrico
    "algiasdin":                      "ibuprofen",      # ES
    "aspirina":                       "aspirin",
    "aspegic":                        "aspirin",        # FR marca
    "ácido acetilsalicílico":         "aspirin",
    "acido acetilsalicilico":         "aspirin",
    "acetylsalicylsäure":             "aspirin",        # DE
    "acide acétylsalicylique":        "aspirin",        # FR
    "acido acetilsalicilico":         "aspirin",        # IT
    "diclofenaco":                    "diclofenac",
    "diclofénac":                     "diclofenac",     # FR
    "voltaren":                       "diclofenac",     # marca EU
    "dicloflex":                      "diclofenac",     # UK
    "naproxeno":                      "naproxen",
    "naproxène":                      "naproxen",       # FR
    "naprosyn":                       "naproxen",       # marca
    "aleve":                          "naproxen",       # marca US
    "naproxen":                       "naproxen",
    "celecoxib":                      "celecoxib",
    "celebrex":                       "celecoxib",      # marca
    "etoricoxib":                     "etoricoxib",
    "arcoxia":                        "etoricoxib",     # marca
    "meloxicam":                      "meloxicam",
    "mobic":                          "meloxicam",      # marca
    "metamizol":                      "metamizole",
    "dipirona":                       "metamizole",
    "nolotil":                        "metamizole",     # marca ES
    "novalgina":                      "metamizole",     # PT/IT
    "ketorolaco":                     "ketorolac",
    "toradol":                        "ketorolac",      # marca
    "tramadol":                       "tramadol",
    "tramal":                         "tramadol",       # marca EU
    "adolonta":                       "tramadol",       # ES
    "codeína":                        "codeine",
    "codeina":                        "codeine",
    "codéine":                        "codeine",        # FR
    # ── Antibióticos ─────────────────────────────────────────────────────────
    "amoxicilina":                    "amoxicillin",
    "amoxicilline":                   "amoxicillin",    # FR
    "amoxil":                         "amoxicillin",    # marca
    "azitromicina":                   "azithromycin",
    "azithromycine":                  "azithromycin",   # FR
    "zithromax":                      "azithromycin",   # marca
    "claritromicina":                 "clarithromycin",
    "klacid":                         "clarithromycin", # marca EU
    "biaxin":                         "clarithromycin", # marca US
    "ciprofloxacino":                 "ciprofloxacin",
    "ciprofloxacine":                 "ciprofloxacin",  # FR
    "cipro":                          "ciprofloxacin",  # marca
    "levofloxacino":                  "levofloxacin",
    "levofloxacine":                  "levofloxacin",   # FR
    "tavanic":                        "levofloxacin",   # marca EU
    "doxiciclina":                    "doxycycline",
    "doxycycline":                    "doxycycline",
    "vibramycin":                     "doxycycline",    # marca
    "cefalexina":                     "cephalexin",
    "cefalexine":                     "cephalexin",     # FR
    "keflex":                         "cephalexin",     # marca
    "cefuroxima":                     "cefuroxime",
    "zinnat":                         "cefuroxime",     # marca EU
    "ceftriaxona":                    "ceftriaxone",
    "rocephin":                       "ceftriaxone",    # marca
    "amoxicilina clavulánico":        "amoxicillin clavulanate",
    "amoxicilina clavulanato":        "amoxicillin clavulanate",
    "augmentine":                     "amoxicillin clavulanate",
    "augmentin":                      "amoxicillin clavulanate", # marca intl
    "amoxicilline acide clavulanique":"amoxicillin clavulanate", # FR
    "metronidazol":                   "metronidazole",
    "flagyl":                         "metronidazole",  # marca
    "trimetoprim sulfametoxazol":     "trimethoprim sulfamethoxazole",
    "cotrimoxazol":                   "trimethoprim sulfamethoxazole",
    "septrin":                        "trimethoprim sulfamethoxazole", # ES
    "bactrim":                        "trimethoprim sulfamethoxazole", # marca
    "nitrofurantoína":                "nitrofurantoin",
    "nitrofurantoina":                "nitrofurantoin",
    "macrobid":                       "nitrofurantoin", # marca
    "fosfomicina":                    "fosfomycin",
    "monurol":                        "fosfomycin",     # marca
    "vancomicina":                    "vancomycin",
    "meropenem":                      "meropenem",
    "linezolid":                      "linezolid",
    "zyvox":                          "linezolid",      # marca
    "clindamicina":                   "clindamycin",
    "dalacin":                        "clindamycin",    # marca EU
    # ── Antifúngicos ─────────────────────────────────────────────────────────
    "fluconazol":                     "fluconazole",
    "diflucan":                       "fluconazole",    # marca
    "itraconazol":                    "itraconazole",
    "voriconazol":                    "voriconazole",
    "terbinafina":                    "terbinafine",
    "lamisil":                        "terbinafine",    # marca
    # ── Antivirales ──────────────────────────────────────────────────────────
    "aciclovir":                      "acyclovir",
    "aciclovire":                     "acyclovir",      # IT
    "zovirax":                        "acyclovir",      # marca
    "valaciclovir":                   "valacyclovir",
    "valtrex":                        "valacyclovir",   # marca
    "oseltamivir":                    "oseltamivir",
    "tamiflu":                        "oseltamivir",    # marca
    # ── Antidiabéticos ───────────────────────────────────────────────────────
    "metformina":                     "metformin",
    "metformine":                     "metformin",      # FR
    "glucophage":                     "metformin",      # marca
    "sitagliptina":                   "sitagliptin",
    "januvia":                        "sitagliptin",    # marca
    "empagliflozina":                 "empagliflozin",
    "jardiance":                      "empagliflozin",  # marca
    "dapagliflozina":                 "dapagliflozin",
    "forxiga":                        "dapagliflozin",  # marca EU
    "farxiga":                        "dapagliflozin",  # marca US
    "canagliflozina":                 "canagliflozin",
    "invokana":                       "canagliflozin",  # marca
    "liraglutida":                    "liraglutide",
    "victoza":                        "liraglutide",    # marca
    "semaglutida":                    "semaglutide",
    "ozempic":                        "semaglutide",    # marca
    "wegovy":                         "semaglutide",    # marca
    "glibenclamida":                  "glyburide",
    "glipizida":                      "glipizide",
    "gliclazida":                     "gliclazide",
    "diamicron":                      "gliclazide",     # marca EU
    "pioglitazona":                   "pioglitazone",
    "actos":                          "pioglitazone",   # marca
    "insulina glargina":              "insulin glargine",
    "lantus":                         "insulin glargine", # marca
    "insulina aspart":                "insulin aspart",
    "novorapid":                      "insulin aspart", # marca EU
    "insulina lispro":                "insulin lispro",
    "humalog":                        "insulin lispro", # marca
    # ── Gastrointestinal ─────────────────────────────────────────────────────
    "omeprazol":                      "omeprazole",
    "oméprazole":                     "omeprazole",     # FR
    "losec":                          "omeprazole",     # marca EU
    "prilosec":                       "omeprazole",     # marca US
    "pantoprazol":                    "pantoprazole",
    "pantoprazole":                   "pantoprazole",
    "pantoc":                         "pantoprazole",   # marca
    "lansoprazol":                    "lansoprazole",
    "prevacid":                       "lansoprazole",   # marca US
    "esomeprazol":                    "esomeprazole",
    "nexium":                         "esomeprazole",   # marca
    "rabeprazol":                     "rabeprazole",
    "ranitidina":                     "ranitidine",
    "zantac":                         "ranitidine",     # marca
    "famotidina":                     "famotidine",
    "pepcid":                         "famotidine",     # marca
    "metoclopramida":                 "metoclopramide",
    "primperan":                      "metoclopramide", # marca EU
    "ondansetrón":                    "ondansetron",
    "ondansetron":                    "ondansetron",
    "zofran":                         "ondansetron",    # marca
    "loperamida":                     "loperamide",
    "imodium":                        "loperamide",     # marca
    "domperidona":                    "domperidone",
    "motilium":                       "domperidone",    # marca EU
    "mesalazina":                     "mesalamine",
    "budesonida rectal":              "budesonide",
    "lactulose":                      "lactulose",
    "lactulosa":                      "lactulose",
    # ── Cardiovascular ───────────────────────────────────────────────────────
    "atorvastatina":                  "atorvastatin",
    "atorvastatine":                  "atorvastatin",   # FR
    "lipitor":                        "atorvastatin",   # marca
    "simvastatina":                   "simvastatin",
    "simvastatine":                   "simvastatin",    # FR
    "zocor":                          "simvastatin",    # marca
    "rosuvastatina":                  "rosuvastatin",
    "crestor":                        "rosuvastatin",   # marca
    "pravastatina":                   "pravastatin",
    "amlodipino":                     "amlodipine",
    "amlodipine":                     "amlodipine",
    "norvasc":                        "amlodipine",     # marca
    "enalapril":                      "enalapril",
    "renitec":                        "enalapril",      # marca EU
    "lisinopril":                     "lisinopril",
    "zestril":                        "lisinopril",     # marca
    "ramipril":                       "ramipril",
    "tritace":                        "ramipril",       # marca EU
    "perindopril":                    "perindopril",
    "coversyl":                       "perindopril",    # marca
    "losartán":                       "losartan",
    "losartan":                       "losartan",
    "cozaar":                         "losartan",       # marca
    "valsartán":                      "valsartan",
    "valsartan":                      "valsartan",
    "diovan":                         "valsartan",      # marca
    "irbesartán":                     "irbesartan",
    "irbesartan":                     "irbesartan",
    "aprovel":                        "irbesartan",     # marca EU
    "candesartán":                    "candesartan",
    "candesartan":                    "candesartan",
    "bisoprolol":                     "bisoprolol",
    "concor":                         "bisoprolol",     # marca EU
    "metoprolol":                     "metoprolol",
    "lopresor":                       "metoprolol",     # marca
    "carvedilol":                     "carvedilol",
    "dilatrend":                      "carvedilol",     # marca EU
    "nebivolol":                      "nebivolol",
    "bystolic":                       "nebivolol",      # marca US
    "furosemida":                     "furosemide",
    "furosémide":                     "furosemide",     # FR
    "lasix":                          "furosemide",     # marca
    "hidroclorotiazida":              "hydrochlorothiazide",
    "hidrochlorothiazide":            "hydrochlorothiazide",
    "espironolactona":                "spironolactone",
    "aldactone":                      "spironolactone", # marca
    "eplerenona":                     "eplerenone",
    "inspra":                         "eplerenone",     # marca
    "digoxina":                       "digoxin",
    "lanoxin":                        "digoxin",        # marca
    "amiodarona":                     "amiodarone",
    "cordarone":                      "amiodarone",     # marca
    "clopidogrel":                    "clopidogrel",
    "plavix":                         "clopidogrel",    # marca
    "ticagrelor":                     "ticagrelor",
    "brilinta":                       "ticagrelor",     # marca
    "prasugrel":                      "prasugrel",
    "efient":                         "prasugrel",      # marca EU
    "nitroglicerina":                 "nitroglycerin",
    "nitrato de isosorbida":          "isosorbide dinitrate",
    "mononitrato de isosorbida":      "isosorbide mononitrate",
    "ivabradina":                     "ivabradine",
    "procoralan":                     "ivabradine",     # marca EU
    "sacubitrilo valsartán":          "sacubitril valsartan",
    "entresto":                       "sacubitril valsartan", # marca
    # ── Anticoagulantes ──────────────────────────────────────────────────────
    "acenocumarol":                   "acenocoumarol",
    "sintrom":                        "acenocoumarol",  # marca ES
    "warfarina":                      "warfarin",
    "warfarine":                      "warfarin",       # FR
    "coumadin":                       "warfarin",       # marca
    "apixabán":                       "apixaban",
    "apixaban":                       "apixaban",
    "eliquis":                        "apixaban",       # marca
    "rivaroxabán":                    "rivaroxaban",
    "rivaroxaban":                    "rivaroxaban",
    "xarelto":                        "rivaroxaban",    # marca
    "dabigatrán":                     "dabigatran",
    "dabigatran":                     "dabigatran",
    "pradaxa":                        "dabigatran",     # marca
    "edoxabán":                       "edoxaban",
    "edoxaban":                       "edoxaban",
    "lixiana":                        "edoxaban",       # marca EU
    "heparina":                       "heparin",
    "enoxaparina":                    "enoxaparin",
    "clexane":                        "enoxaparin",     # marca EU
    "lovenox":                        "enoxaparin",     # marca US
    # ── Psiquiátricos / Neurológicos ─────────────────────────────────────────
    "alprazolam":                     "alprazolam",
    "xanax":                          "alprazolam",     # marca
    "lorazepam":                      "lorazepam",
    "orfidal":                        "lorazepam",      # marca ES
    "diazepam":                       "diazepam",
    "valium":                         "diazepam",       # marca
    "clonazepam":                     "clonazepam",
    "rivotril":                       "clonazepam",     # marca EU
    "bromazepam":                     "bromazepam",
    "lexatin":                        "bromazepam",     # marca ES
    "sertralina":                     "sertraline",
    "sertraline":                     "sertraline",
    "zoloft":                         "sertraline",     # marca
    "fluoxetina":                     "fluoxetine",
    "fluoxétine":                     "fluoxetine",     # FR
    "prozac":                         "fluoxetine",     # marca
    "escitalopram":                   "escitalopram",
    "lexapro":                        "escitalopram",   # marca US
    "cipralex":                       "escitalopram",   # marca EU
    "citalopram":                     "citalopram",
    "celexa":                         "citalopram",     # marca US
    "paroxetina":                     "paroxetine",
    "paroxétine":                     "paroxetine",     # FR
    "paxil":                          "paroxetine",     # marca US
    "seroxat":                        "paroxetine",     # marca EU
    "venlafaxina":                    "venlafaxine",
    "venlafaxine":                    "venlafaxine",
    "effexor":                        "venlafaxine",    # marca
    "duloxetina":                     "duloxetine",
    "cymbalta":                       "duloxetine",     # marca
    "mirtazapina":                    "mirtazapine",
    "remeron":                        "mirtazapine",    # marca
    "trazodona":                      "trazodone",
    "amitriptilina":                  "amitriptyline",
    "pregabalina":                    "pregabalin",
    "pregabaline":                    "pregabalin",     # FR
    "lyrica":                         "pregabalin",     # marca
    "gabapentina":                    "gabapentin",
    "gabapentine":                    "gabapentin",     # FR
    "neurontin":                      "gabapentin",     # marca
    "quetiapina":                     "quetiapine",
    "seroquel":                       "quetiapine",     # marca
    "olanzapina":                     "olanzapine",
    "zyprexa":                        "olanzapine",     # marca
    "risperidona":                    "risperidone",
    "risperdal":                      "risperidone",    # marca
    "aripiprazol":                    "aripiprazole",
    "abilify":                        "aripiprazole",   # marca
    "haloperidol":                    "haloperidol",
    "haldol":                         "haloperidol",    # marca
    "litio":                          "lithium",
    "carbonate de lithium":           "lithium",        # FR
    "carbonato de litio":             "lithium",
    "carbamazepina":                  "carbamazepine",
    "tegretol":                       "carbamazepine",  # marca
    "valproato":                      "valproate",
    "ácido valproico":                "valproate",
    "acido valproico":                "valproate",
    "depakote":                       "valproate",      # marca US
    "depakine":                       "valproate",      # marca EU
    "levetiracetam":                  "levetiracetam",
    "keppra":                         "levetiracetam",  # marca
    "lamotrigina":                    "lamotrigine",
    "lamictal":                       "lamotrigine",    # marca
    "topiramato":                     "topiramate",
    "topamax":                        "topiramate",     # marca
    "fenitoína":                      "phenytoin",
    "fenitoina":                      "phenytoin",
    "dilantin":                       "phenytoin",      # marca US
    "fenobarbital":                   "phenobarbital",
    "zolpidem":                       "zolpidem",
    "stilnox":                        "zolpidem",       # marca EU
    "melatonina":                     "melatonin",
    "melatonine":                     "melatonin",      # FR
    "donepezilo":                     "donepezil",
    "aricept":                        "donepezil",      # marca
    "memantina":                      "memantine",
    "ebixa":                          "memantine",      # marca EU
    "methylfenidato":                 "methylphenidate",
    "metilfenidato":                  "methylphenidate",
    "ritalin":                        "methylphenidate", # marca
    # ── Respiratorio ─────────────────────────────────────────────────────────
    "salbutamol":                     "albuterol",
    "ventolin":                       "albuterol",      # marca
    "albuterol":                      "albuterol",
    "terbutalina":                    "terbutaline",
    "bricanyl":                       "terbutaline",    # marca EU
    "formoterol":                     "formoterol",
    "salmeterol":                     "salmeterol",
    "seretide":                       "salmeterol fluticasone", # marca EU combo
    "symbicort":                      "budesonide formoterol",  # marca combo
    "budesonida":                     "budesonide",
    "pulmicort":                      "budesonide",     # marca
    "fluticasona":                    "fluticasone",
    "flixotide":                      "fluticasone",    # marca EU
    "beclometasona":                  "beclomethasone",
    "clenil":                         "beclomethasone", # marca EU
    "tiotropio":                      "tiotropium",
    "spiriva":                        "tiotropium",     # marca
    "umeclidinio":                    "umeclidinium",
    "montelukast":                    "montelukast",
    "singulair":                      "montelukast",    # marca
    "teofilina":                      "theophylline",
    "ipratropio":                     "ipratropium",
    "atrovent":                       "ipratropium",    # marca
    "roflumilast":                    "roflumilast",
    "daxas":                          "roflumilast",    # marca EU
    # ── Hormonas ─────────────────────────────────────────────────────────────
    "levotiroxina":                   "levothyroxine",
    "levothyroxine":                  "levothyroxine",
    "eutirox":                        "levothyroxine",  # marca ES
    "synthroid":                      "levothyroxine",  # marca US
    "prednisona":                     "prednisone",
    "prednisolona":                   "prednisolone",
    "dexametasona":                   "dexamethasone",
    "dexaméthasone":                  "dexamethasone",  # FR
    "metilprednisolona":              "methylprednisolone",
    "urbason":                        "methylprednisolone", # marca EU
    "hidrocortisona":                 "hydrocortisone",
    "cortisol":                       "hydrocortisone",
    "fludrocortisona":                "fludrocortisone",
    "testosterona":                   "testosterone",
    "estradiol":                      "estradiol",
    "progesterona":                   "progesterone",
    "utrogestan":                     "progesterone",   # marca EU
    "acetato de medroxiprogesterona": "medroxyprogesterone",
    "depo-provera":                   "medroxyprogesterone", # marca
    # ── Oncología / Inmunomoduladores ────────────────────────────────────────
    "metotrexato":                    "methotrexate",
    "methotrexate":                   "methotrexate",
    "ciclofosfamida":                 "cyclophosphamide",
    "azatioprina":                    "azathioprine",
    "imurel":                         "azathioprine",   # marca EU
    "micofenolato":                   "mycophenolate",
    "cellcept":                       "mycophenolate",  # marca
    "tacrolimus":                     "tacrolimus",
    "prograf":                        "tacrolimus",     # marca
    "ciclosporina":                   "cyclosporine",
    "neoral":                         "cyclosporine",   # marca EU
    "hidroxicloroquina":              "hydroxychloroquine",
    "plaquenil":                      "hydroxychloroquine", # marca
    # ── Dermatología ─────────────────────────────────────────────────────────
    "isotretinoína":                  "isotretinoin",
    "isotretinoina":                  "isotretinoin",
    "roaccutane":                     "isotretinoin",   # marca EU
    "tretinoína":                     "tretinoin",
    "tretinoina":                     "tretinoin",
    "retin-a":                        "tretinoin",      # marca
    "finasterida":                    "finasteride",
    "propecia":                       "finasteride",    # marca
    "minoxidilo":                     "minoxidil",
    "rogaine":                        "minoxidil",      # marca
    # ── Osteoporosis / Reumatología ──────────────────────────────────────────
    "alendronato":                    "alendronate",
    "fosamax":                        "alendronate",    # marca
    "ibandronato":                    "ibandronate",
    "bondronat":                      "ibandronate",    # marca EU
    "risedronato":                    "risedronate",
    "actonel":                        "risedronate",    # marca
    "denosumab":                      "denosumab",
    "prolia":                         "denosumab",      # marca
    "calcio carbonato":               "calcium carbonate",
    "vitamina d":                     "vitamin d",
    "colecalciferol":                 "cholecalciferol",
    "calcitriol":                     "calcitriol",
    # ── Urología ─────────────────────────────────────────────────────────────
    "tamsulosina":                    "tamsulosin",
    "omnic":                          "tamsulosin",     # marca EU
    "dutasterida":                    "dutasteride",
    "avodart":                        "dutasteride",    # marca
    "solifenacina":                   "solifenacin",
    "vesicare":                       "solifenacin",    # marca
    "sildenafilo":                    "sildenafil",
    "viagra":                         "sildenafil",     # marca
    "tadalafilo":                     "tadalafil",
    "cialis":                         "tadalafil",      # marca
    # ── Oftalmología ─────────────────────────────────────────────────────────
    "timolol":                        "timolol",
    "latanoprost":                    "latanoprost",
    "xalatan":                        "latanoprost",    # marca
    "dorzolamida":                    "dorzolamide",
    "trusopt":                        "dorzolamide",    # marca EU
    # ── Nombres propios RO (rumano) ───────────────────────────────────────────
    "amoxicilină":                    "amoxicillin",    # RO
    "metformină":                     "metformin",      # RO
    # ── Nombres propios CA (catalán) ─────────────────────────────────────────
    "ibuprofèn":                      "ibuprofen",      # CA
    "amoxicil·lina":                  "amoxicillin",    # CA
    # ── Nombres propios PT (portugués) ───────────────────────────────────────
    "cetorolaco":                     "ketorolac",      # PT
    "anlodipino":                     "amlodipine",     # PT
}

_ALL_KNOWN_NAMES = list(NAME_TRANSLATIONS.keys())


def fuzzy_resolve_drug_name(query: str) -> str:
    """
    Resuelve nombres de medicamentos tolerando faltas de ortografía,
    nombres en otros idiomas y variantes de escritura.
    Estrategia:
    1. Coincidencia exacta en NAME_TRANSLATIONS
    2. Coincidencia parcial (prefijo/substring)
    3. Fuzzy estricto (cutoff 0.72)
    4. Fuzzy permisivo (cutoff 0.60)
    5. Fallback: devuelve el original
    """
    q = query.lower().strip()

    # 1. Exacto
    if q in NAME_TRANSLATIONS:
        return NAME_TRANSLATIONS[q]

    # 2. Parcial — el query es prefijo o substring de una clave conocida
    for key, fda_name in NAME_TRANSLATIONS.items():
        if len(q) >= 4 and (key.startswith(q) or q.startswith(key[:max(4, len(key) - 2)])):
            return fda_name

    # 3. Fuzzy estricto
    matches = get_close_matches(q, _ALL_KNOWN_NAMES, n=1, cutoff=0.72)
    if matches:
        return NAME_TRANSLATIONS[matches[0]]

    # 4. Fuzzy permisivo
    matches = get_close_matches(q, _ALL_KNOWN_NAMES, n=1, cutoff=0.60)
    if matches:
        return NAME_TRANSLATIONS[matches[0]]

    # 5. Fallback: OpenFDA puede entenderlo directamente
    return query


# FDA generic name → nombre español preferido
SPANISH_NAMES: dict[str, str] = {
    "acetaminophen":            "Paracetamol",
    "ibuprofen":                "Ibuprofeno",
    "aspirin":                  "Aspirina",
    "naproxen":                 "Naproxeno",
    "diclofenac":               "Diclofenaco",
    "celecoxib":                "Celecoxib",
    "etoricoxib":               "Etoricoxib",
    "meloxicam":                "Meloxicam",
    "ketorolac":                "Ketorolaco",
    "metamizole":               "Metamizol",
    "tramadol":                 "Tramadol",
    "codeine":                  "Codeína",
    "morphine":                 "Morfina",
    "amoxicillin":              "Amoxicilina",
    "amoxicillin clavulanate":  "Amoxicilina-Clavulánico",
    "azithromycin":             "Azitromicina",
    "clarithromycin":           "Claritromicina",
    "ciprofloxacin":            "Ciprofloxacino",
    "levofloxacin":             "Levofloxacino",
    "doxycycline":              "Doxiciclina",
    "cephalexin":               "Cefalexina",
    "cefuroxime":               "Cefuroxima",
    "ceftriaxone":              "Ceftriaxona",
    "metronidazole":            "Metronidazol",
    "trimethoprim sulfamethoxazole": "Cotrimoxazol",
    "nitrofurantoin":           "Nitrofurantoína",
    "clindamycin":              "Clindamicina",
    "vancomycin":               "Vancomicina",
    "fluconazole":              "Fluconazol",
    "itraconazole":             "Itraconazol",
    "terbinafine":              "Terbinafina",
    "acyclovir":                "Aciclovir",
    "valacyclovir":             "Valaciclovir",
    "oseltamivir":              "Oseltamivir",
    "metformin":                "Metformina",
    "sitagliptin":              "Sitagliptina",
    "empagliflozin":            "Empagliflozina",
    "dapagliflozin":            "Dapagliflozina",
    "liraglutide":              "Liraglutida",
    "semaglutide":              "Semaglutida",
    "glipizide":                "Glipizida",
    "gliclazide":               "Gliclazida",
    "pioglitazone":             "Pioglitazona",
    "insulin glargine":         "Insulina Glargina",
    "insulin aspart":           "Insulina Aspart",
    "insulin lispro":           "Insulina Lispro",
    "omeprazole":               "Omeprazol",
    "pantoprazole":             "Pantoprazol",
    "lansoprazole":             "Lansoprazol",
    "esomeprazole":             "Esomeprazol",
    "famotidine":               "Famotidina",
    "metoclopramide":           "Metoclopramida",
    "ondansetron":              "Ondansetrón",
    "loperamide":               "Loperamida",
    "lactulose":                "Lactulosa",
    "atorvastatin":             "Atorvastatina",
    "simvastatin":              "Simvastatina",
    "rosuvastatin":             "Rosuvastatina",
    "pravastatin":              "Pravastatina",
    "amlodipine":               "Amlodipino",
    "enalapril":                "Enalapril",
    "lisinopril":               "Lisinopril",
    "ramipril":                 "Ramipril",
    "losartan":                 "Losartán",
    "valsartan":                "Valsartán",
    "bisoprolol":               "Bisoprolol",
    "metoprolol":               "Metoprolol",
    "carvedilol":               "Carvedilol",
    "furosemide":               "Furosemida",
    "hydrochlorothiazide":      "Hidroclorotiazida",
    "spironolactone":           "Espironolactona",
    "digoxin":                  "Digoxina",
    "amiodarone":               "Amiodarona",
    "clopidogrel":              "Clopidogrel",
    "ticagrelor":               "Ticagrelor",
    "acenocoumarol":            "Acenocumarol",
    "warfarin":                 "Warfarina",
    "apixaban":                 "Apixabán",
    "rivaroxaban":              "Rivaroxabán",
    "dabigatran":               "Dabigatrán",
    "enoxaparin":               "Enoxaparina",
    "heparin":                  "Heparina",
    "alprazolam":               "Alprazolam",
    "lorazepam":                "Lorazepam",
    "diazepam":                 "Diazepam",
    "clonazepam":               "Clonazepam",
    "sertraline":               "Sertralina",
    "fluoxetine":               "Fluoxetina",
    "escitalopram":             "Escitalopram",
    "citalopram":               "Citalopram",
    "paroxetine":               "Paroxetina",
    "venlafaxine":              "Venlafaxina",
    "duloxetine":               "Duloxetina",
    "mirtazapine":              "Mirtazapina",
    "amitriptyline":            "Amitriptilina",
    "pregabalin":               "Pregabalina",
    "gabapentin":               "Gabapentina",
    "quetiapine":               "Quetiapina",
    "olanzapine":               "Olanzapina",
    "risperidone":              "Risperidona",
    "aripiprazole":             "Aripiprazol",
    "haloperidol":              "Haloperidol",
    "lithium":                  "Litio",
    "carbamazepine":            "Carbamazepina",
    "valproate":                "Valproato",
    "levetiracetam":            "Levetiracetam",
    "lamotrigine":              "Lamotrigina",
    "topiramate":               "Topiramato",
    "phenytoin":                "Fenitoína",
    "zolpidem":                 "Zolpidem",
    "melatonin":                "Melatonina",
    "methylphenidate":          "Metilfenidato",
    "albuterol":                "Salbutamol",
    "budesonide":               "Budesonida",
    "fluticasone":              "Fluticasona",
    "tiotropium":               "Tiotropio",
    "montelukast":              "Montelukast",
    "levothyroxine":            "Levotiroxina",
    "prednisone":               "Prednisona",
    "prednisolone":             "Prednisolona",
    "dexamethasone":            "Dexametasona",
    "methylprednisolone":       "Metilprednisolona",
    "hydrocortisone":           "Hidrocortisona",
    "methotrexate":             "Metotrexato",
    "azathioprine":             "Azatioprina",
    "hydroxychloroquine":       "Hidroxicloroquina",
    "isotretinoin":             "Isotretinoína",
    "finasteride":              "Finasterida",
    "sildenafil":               "Sildenafilo",
    "tadalafil":                "Tadalafilo",
    "alendronate":              "Alendronato",
    "calcium carbonate":        "Carbonato de calcio",
    "cholecalciferol":          "Colecalciferol",
    "vitamin d":                "Vitamina D",
}

# Clases farmacológicas en español (orden importa: más específico primero)
CLASS_TRANSLATIONS_ES: list[tuple[str, str]] = [
    ("nonsteroidal anti-inflammatory", "Antiinflamatorio no esteroideo (AINE)"),
    ("proton pump inhibitor",          "Inhibidor de la bomba de protones"),
    ("h2 blocker",                     "Bloqueante H2"),
    ("angiotensin receptor blocker",   "Antagonista del receptor de angiotensina II"),
    ("ace inhibitor",                  "Inhibidor de la ECA"),
    ("beta blocker",                   "Betabloqueante"),
    ("calcium channel blocker",        "Bloqueante de los canales de calcio"),
    ("diuretic",                       "Diurético"),
    ("anticoagulant",                  "Anticoagulante"),
    ("antithrombotic",                 "Antitrombótico"),
    ("antiplatelet",                   "Antiagregante plaquetario"),
    ("antihypertensive",               "Antihipertensivo"),
    ("statin",                         "Estatina (inhibidor de la HMG-CoA reductasa)"),
    ("hmg-coa reductase inhibitor",    "Estatina (inhibidor de la HMG-CoA reductasa)"),
    ("antidiabetic",                   "Antidiabético"),
    ("hypoglycemic",                   "Hipoglucemiante"),
    ("biguanide",                      "Biguanida"),
    ("insulin",                        "Insulina"),
    ("glp-1",                          "Agonista del receptor GLP-1"),
    ("sglt2",                          "Inhibidor SGLT2"),
    ("ssri",                           "ISRS (inhibidor selectivo de la recaptación de serotonina)"),
    ("serotonin-norepinephrine",       "ISRSN (inhibidor de la recaptación de serotonina-noradrenalina)"),
    ("antidepressant",                 "Antidepresivo"),
    ("antianxiety",                    "Ansiolítico"),
    ("benzodiazepine",                 "Benzodiacepina"),
    ("antipsychotic",                  "Antipsicótico"),
    ("mood stabilizer",                "Estabilizador del estado de ánimo"),
    ("anticonvulsant",                 "Anticonvulsivante"),
    ("antiepileptic",                  "Antiepiléptico"),
    ("opioid",                         "Opioide"),
    ("analgesic",                      "Analgésico"),
    ("antipyretic",                    "Antipirético"),
    ("antibiotic",                     "Antibiótico"),
    ("antibacterial",                  "Antibacteriano"),
    ("antimicrobial",                  "Antimicrobiano"),
    ("macrolide",                      "Macrólido"),
    ("penicillin",                     "Penicilina"),
    ("cephalosporin",                  "Cefalosporina"),
    ("fluoroquinolone",                "Fluoroquinolona"),
    ("tetracycline",                   "Tetraciclina"),
    ("antifungal",                     "Antifúngico"),
    ("antiviral",                      "Antiviral"),
    ("antiretroviral",                 "Antirretroviral"),
    ("corticosteroid",                 "Corticoesteroide"),
    ("steroid",                        "Corticoesteroide"),
    ("bronchodilator",                 "Broncodilatador"),
    ("antihistamine",                  "Antihistamínico"),
    ("immunosuppressant",              "Inmunosupresor"),
    ("thyroid hormone",                "Hormona tiroidea"),
    ("hypnotic",                       "Hipnótico"),
    ("sedative",                       "Sedante"),
    ("antiparkinsonian",               "Antiparkinsónico"),
    ("antineoplastic",                 "Antineoplásico"),
    ("cardiovascular agent",           "Agente cardiovascular"),
    ("pain reliever",                  "Analgésico"),
    ("pain",                           "Analgésico"),
    ("fever reducer",                  "Antipirético"),
]


def translate_class_to_es(drug_class: str) -> str:
    """Traduce la clase farmacológica al español usando el diccionario estático."""
    c = drug_class.lower()
    for en_key, es_val in CLASS_TRANSLATIONS_ES:
        if en_key in c:
            return es_val
    return drug_class


CLASS_TRANSLATIONS_FR: list[tuple[str, str]] = [
    ("nonsteroidal anti-inflammatory", "Anti-inflammatoire non stéroïdien (AINS)"),
    ("proton pump inhibitor",          "Inhibiteur de la pompe à protons"),
    ("h2 blocker",                     "Antihistaminique H2"),
    ("angiotensin receptor blocker",   "Antagoniste des récepteurs de l'angiotensine II"),
    ("ace inhibitor",                  "Inhibiteur de l'ECA"),
    ("beta blocker",                   "Bêtabloquant"),
    ("calcium channel blocker",        "Inhibiteur calcique"),
    ("diuretic",                       "Diurétique"),
    ("anticoagulant",                  "Anticoagulant"),
    ("antiplatelet",                   "Antiplaquettaire"),
    ("antihypertensive",               "Antihypertenseur"),
    ("statin",                         "Statine"),
    ("hmg-coa reductase inhibitor",    "Statine"),
    ("antidiabetic",                   "Antidiabétique"),
    ("biguanide",                      "Biguanide"),
    ("insulin",                        "Insuline"),
    ("glp-1",                          "Agoniste du récepteur GLP-1"),
    ("sglt2",                          "Inhibiteur SGLT2"),
    ("ssri",                           "ISRS"),
    ("serotonin-norepinephrine",       "IRSNa"),
    ("antidepressant",                 "Antidépresseur"),
    ("benzodiazepine",                 "Benzodiazépine"),
    ("antipsychotic",                  "Antipsychotique"),
    ("anticonvulsant",                 "Anticonvulsivant"),
    ("antiepileptic",                  "Antiépileptique"),
    ("opioid",                         "Opioïde"),
    ("analgesic",                      "Analgésique"),
    ("antipyretic",                    "Antipyrétique"),
    ("antibiotic",                     "Antibiotique"),
    ("antibacterial",                  "Antibactérien"),
    ("macrolide",                      "Macrolide"),
    ("penicillin",                     "Pénicilline"),
    ("cephalosporin",                  "Céphalosporine"),
    ("fluoroquinolone",                "Fluoroquinolone"),
    ("antifungal",                     "Antifongique"),
    ("antiviral",                      "Antiviral"),
    ("corticosteroid",                 "Corticostéroïde"),
    ("bronchodilator",                 "Bronchodilatateur"),
    ("antihistamine",                  "Antihistaminique"),
    ("immunosuppressant",              "Immunosuppresseur"),
    ("thyroid hormone",                "Hormone thyroïdienne"),
    ("pain reliever",                  "Analgésique"),
    ("pain",                           "Analgésique"),
]

CLASS_TRANSLATIONS_IT: list[tuple[str, str]] = [
    ("nonsteroidal anti-inflammatory", "Farmaco antinfiammatorio non steroideo (FANS)"),
    ("proton pump inhibitor",          "Inibitore della pompa protonica"),
    ("h2 blocker",                     "Antagonista H2"),
    ("angiotensin receptor blocker",   "Antagonista del recettore dell'angiotensina II"),
    ("ace inhibitor",                  "Inibitore dell'ECA"),
    ("beta blocker",                   "Betabloccante"),
    ("calcium channel blocker",        "Calcio-antagonista"),
    ("diuretic",                       "Diuretico"),
    ("anticoagulant",                  "Anticoagulante"),
    ("antiplatelet",                   "Antiaggregante piastrinico"),
    ("antihypertensive",               "Antipertensivo"),
    ("statin",                         "Statina"),
    ("hmg-coa reductase inhibitor",    "Statina"),
    ("antidiabetic",                   "Antidiabetico"),
    ("biguanide",                      "Biguanide"),
    ("insulin",                        "Insulina"),
    ("glp-1",                          "Agonista del recettore GLP-1"),
    ("sglt2",                          "Inibitore SGLT2"),
    ("ssri",                           "SSRI"),
    ("serotonin-norepinephrine",       "SNRI"),
    ("antidepressant",                 "Antidepressivo"),
    ("benzodiazepine",                 "Benzodiazepina"),
    ("antipsychotic",                  "Antipsicotico"),
    ("anticonvulsant",                 "Anticonvulsivante"),
    ("antiepileptic",                  "Antiepilettico"),
    ("opioid",                         "Oppioide"),
    ("analgesic",                      "Analgesico"),
    ("antipyretic",                    "Antipiretico"),
    ("antibiotic",                     "Antibiotico"),
    ("antibacterial",                  "Antibatterico"),
    ("macrolide",                      "Macrolide"),
    ("penicillin",                     "Penicillina"),
    ("cephalosporin",                  "Cefalosporina"),
    ("fluoroquinolone",                "Fluorochinolone"),
    ("antifungal",                     "Antimicotico"),
    ("antiviral",                      "Antivirale"),
    ("corticosteroid",                 "Corticosteroide"),
    ("bronchodilator",                 "Broncodilatatore"),
    ("antihistamine",                  "Antistaminico"),
    ("immunosuppressant",              "Immunosoppressore"),
    ("thyroid hormone",                "Ormone tiroideo"),
    ("pain reliever",                  "Analgesico"),
    ("pain",                           "Analgesico"),
]

CLASS_TRANSLATIONS_DE: list[tuple[str, str]] = [
    ("nonsteroidal anti-inflammatory", "Nichtsteroidales Antirheumatikum (NSAR)"),
    ("proton pump inhibitor",          "Protonenpumpenhemmer"),
    ("h2 blocker",                     "H2-Antagonist"),
    ("angiotensin receptor blocker",   "Angiotensin-II-Rezeptorblocker"),
    ("ace inhibitor",                  "ACE-Hemmer"),
    ("beta blocker",                   "Betablocker"),
    ("calcium channel blocker",        "Calciumkanalblocker"),
    ("diuretic",                       "Diuretikum"),
    ("anticoagulant",                  "Antikoagulans"),
    ("antiplatelet",                   "Thrombozytenaggregationshemmer"),
    ("antihypertensive",               "Antihypertensivum"),
    ("statin",                         "Statin"),
    ("hmg-coa reductase inhibitor",    "Statin"),
    ("antidiabetic",                   "Antidiabetikum"),
    ("biguanide",                      "Biguanid"),
    ("insulin",                        "Insulin"),
    ("glp-1",                          "GLP-1-Rezeptoragonist"),
    ("sglt2",                          "SGLT2-Hemmer"),
    ("ssri",                           "SSRI"),
    ("serotonin-norepinephrine",       "SNRI"),
    ("antidepressant",                 "Antidepressivum"),
    ("benzodiazepine",                 "Benzodiazepin"),
    ("antipsychotic",                  "Antipsychotikum"),
    ("anticonvulsant",                 "Antikonvulsivum"),
    ("antiepileptic",                  "Antiepileptikum"),
    ("opioid",                         "Opioid"),
    ("analgesic",                      "Analgetikum"),
    ("antipyretic",                    "Antipyretikum"),
    ("antibiotic",                     "Antibiotikum"),
    ("antibacterial",                  "Antibakterielles Mittel"),
    ("macrolide",                      "Makrolid"),
    ("penicillin",                     "Penicillin"),
    ("cephalosporin",                  "Cephalosporin"),
    ("fluoroquinolone",                "Fluorchinolon"),
    ("antifungal",                     "Antimykotikum"),
    ("antiviral",                      "Antivirales Mittel"),
    ("corticosteroid",                 "Kortikosteroid"),
    ("bronchodilator",                 "Bronchodilatator"),
    ("antihistamine",                  "Antihistaminikum"),
    ("immunosuppressant",              "Immunsuppressivum"),
    ("thyroid hormone",                "Schilddrüsenhormon"),
    ("pain reliever",                  "Analgetikum"),
    ("pain",                           "Analgetikum"),
]

CLASS_TRANSLATIONS_PT: list[tuple[str, str]] = [
    ("nonsteroidal anti-inflammatory", "Anti-inflamatório não esteroidal (AINE)"),
    ("proton pump inhibitor",          "Inibidor da bomba de protões"),
    ("h2 blocker",                     "Bloqueador H2"),
    ("angiotensin receptor blocker",   "Antagonista do receptor da angiotensina II"),
    ("ace inhibitor",                  "Inibidor da ECA"),
    ("beta blocker",                   "Betabloqueador"),
    ("calcium channel blocker",        "Bloqueador dos canais de cálcio"),
    ("diuretic",                       "Diurético"),
    ("anticoagulant",                  "Anticoagulante"),
    ("antiplatelet",                   "Antiagregante plaquetário"),
    ("antihypertensive",               "Anti-hipertensivo"),
    ("statin",                         "Estatina"),
    ("hmg-coa reductase inhibitor",    "Estatina"),
    ("antidiabetic",                   "Antidiabético"),
    ("biguanide",                      "Biguanida"),
    ("insulin",                        "Insulina"),
    ("glp-1",                          "Agonista do receptor GLP-1"),
    ("sglt2",                          "Inibidor SGLT2"),
    ("ssri",                           "ISRS"),
    ("serotonin-norepinephrine",       "IRSN"),
    ("antidepressant",                 "Antidepressivo"),
    ("benzodiazepine",                 "Benzodiazepina"),
    ("antipsychotic",                  "Antipsicótico"),
    ("anticonvulsant",                 "Anticonvulsivante"),
    ("antiepileptic",                  "Antiepiléptico"),
    ("opioid",                         "Opioide"),
    ("analgesic",                      "Analgésico"),
    ("antipyretic",                    "Antipirético"),
    ("antibiotic",                     "Antibiótico"),
    ("antibacterial",                  "Antibacteriano"),
    ("macrolide",                      "Macrólido"),
    ("penicillin",                     "Penicilina"),
    ("cephalosporin",                  "Cefalosporina"),
    ("fluoroquinolone",                "Fluoroquinolona"),
    ("antifungal",                     "Antifúngico"),
    ("antiviral",                      "Antiviral"),
    ("corticosteroid",                 "Corticosteroide"),
    ("bronchodilator",                 "Broncodilatador"),
    ("antihistamine",                  "Anti-histamínico"),
    ("immunosuppressant",              "Imunossupressor"),
    ("thyroid hormone",                "Hormona tiroideia"),
    ("pain reliever",                  "Analgésico"),
    ("pain",                           "Analgésico"),
]

CLASS_TRANSLATIONS_CA: list[tuple[str, str]] = [
    ("nonsteroidal anti-inflammatory", "Antiinflamatori no esteroidal (AINE)"),
    ("proton pump inhibitor",          "Inhibidor de la bomba de protons"),
    ("h2 blocker",                     "Bloqueant H2"),
    ("angiotensin receptor blocker",   "Antagonista del receptor de l'angiotensina II"),
    ("ace inhibitor",                  "Inhibidor de l'ECA"),
    ("beta blocker",                   "Betabloqueant"),
    ("calcium channel blocker",        "Bloqueant dels canals de calci"),
    ("diuretic",                       "Diürètic"),
    ("anticoagulant",                  "Anticoagulant"),
    ("antiplatelet",                   "Antiagregant plaquetari"),
    ("antihypertensive",               "Antihipertensiu"),
    ("statin",                         "Estatina"),
    ("hmg-coa reductase inhibitor",    "Estatina"),
    ("antidiabetic",                   "Antidiabètic"),
    ("biguanide",                      "Biguanida"),
    ("insulin",                        "Insulina"),
    ("glp-1",                          "Agonista del receptor GLP-1"),
    ("sglt2",                          "Inhibidor SGLT2"),
    ("ssri",                           "ISRS"),
    ("serotonin-norepinephrine",       "IRSN"),
    ("antidepressant",                 "Antidepressiu"),
    ("benzodiazepine",                 "Benzodiazepina"),
    ("antipsychotic",                  "Antipsicòtic"),
    ("anticonvulsant",                 "Anticonvulsivant"),
    ("antiepileptic",                  "Antiepilèptic"),
    ("opioid",                         "Opioide"),
    ("analgesic",                      "Analgèsic"),
    ("antipyretic",                    "Antipirètic"),
    ("antibiotic",                     "Antibiòtic"),
    ("antibacterial",                  "Antibacterià"),
    ("macrolide",                      "Macròlid"),
    ("penicillin",                     "Penicil·lina"),
    ("cephalosporin",                  "Cefalosporina"),
    ("fluoroquinolone",                "Fluoroquinolona"),
    ("antifungal",                     "Antifúngic"),
    ("antiviral",                      "Antiviral"),
    ("corticosteroid",                 "Corticosteroide"),
    ("bronchodilator",                 "Broncodilatador"),
    ("antihistamine",                  "Antihistamínic"),
    ("immunosuppressant",              "Immunosupressor"),
    ("thyroid hormone",                "Hormona tiroïdal"),
    ("pain reliever",                  "Analgèsic"),
    ("pain",                           "Analgèsic"),
]

CLASS_TRANSLATIONS_PL: list[tuple[str, str]] = [
    ("nonsteroidal anti-inflammatory", "Niesteroidowy lek przeciwzapalny (NLPZ)"),
    ("proton pump inhibitor",          "Inhibitor pompy protonowej"),
    ("h2 blocker",                     "Antagonista H2"),
    ("angiotensin receptor blocker",   "Antagonista receptora angiotensyny II"),
    ("ace inhibitor",                  "Inhibitor ACE"),
    ("beta blocker",                   "Beta-bloker"),
    ("calcium channel blocker",        "Bloker kanałów wapniowych"),
    ("diuretic",                       "Diuretyk"),
    ("anticoagulant",                  "Antykoagulant"),
    ("antiplatelet",                   "Lek przeciwpłytkowy"),
    ("antihypertensive",               "Lek hipotensyjny"),
    ("statin",                         "Statyna"),
    ("hmg-coa reductase inhibitor",    "Statyna"),
    ("antidiabetic",                   "Lek przeciwcukrzycowy"),
    ("biguanide",                      "Biguanid"),
    ("insulin",                        "Insulina"),
    ("glp-1",                          "Agonista receptora GLP-1"),
    ("sglt2",                          "Inhibitor SGLT2"),
    ("ssri",                           "SSRI"),
    ("serotonin-norepinephrine",       "SNRI"),
    ("antidepressant",                 "Lek przeciwdepresyjny"),
    ("benzodiazepine",                 "Benzodiazepin"),
    ("antipsychotic",                  "Lek przeciwpsychotyczny"),
    ("anticonvulsant",                 "Lek przeciwdrgawkowy"),
    ("antiepileptic",                  "Lek przeciwpadaczkowy"),
    ("opioid",                         "Opioid"),
    ("analgesic",                      "Lek przeciwbólowy"),
    ("antipyretic",                    "Lek przeciwgorączkowy"),
    ("antibiotic",                     "Antybiotyk"),
    ("antibacterial",                  "Lek przeciwbakteryjny"),
    ("macrolide",                      "Makrolid"),
    ("penicillin",                     "Penicylina"),
    ("cephalosporin",                  "Cefalosporyna"),
    ("fluoroquinolone",                "Fluorochinolon"),
    ("antifungal",                     "Lek przeciwgrzybiczny"),
    ("antiviral",                      "Lek przeciwwirusowy"),
    ("corticosteroid",                 "Kortykosteroid"),
    ("bronchodilator",                 "Bronchodilatator"),
    ("antihistamine",                  "Lek przeciwhistaminowy"),
    ("immunosuppressant",              "Immunosupresant"),
    ("thyroid hormone",                "Hormon tarczycy"),
    ("pain reliever",                  "Lek przeciwbólowy"),
    ("pain",                           "Lek przeciwbólowy"),
]

CLASS_TRANSLATIONS_FI: list[tuple[str, str]] = [
    ("nonsteroidal anti-inflammatory", "Tulehduskipulääke (NSAID)"),
    ("proton pump inhibitor",          "Protonipumpun estäjä"),
    ("h2 blocker",                     "H2-salpaaja"),
    ("angiotensin receptor blocker",   "Angiotensiinireseptorin salpaaja"),
    ("ace inhibitor",                  "ACE:n estäjä"),
    ("beta blocker",                   "Beetasalpaaja"),
    ("calcium channel blocker",        "Kalsiumkanavan salpaaja"),
    ("diuretic",                       "Diureetti"),
    ("anticoagulant",                  "Antikoagulantti"),
    ("antiplatelet",                   "Verihiutaleiden aggregaation estäjä"),
    ("antihypertensive",               "Verenpainelääke"),
    ("statin",                         "Statiini"),
    ("hmg-coa reductase inhibitor",    "Statiini"),
    ("antidiabetic",                   "Diabeteslääke"),
    ("biguanide",                      "Biguanidi"),
    ("insulin",                        "Insuliini"),
    ("glp-1",                          "GLP-1-reseptoriagonisti"),
    ("sglt2",                          "SGLT2:n estäjä"),
    ("ssri",                           "SSRI"),
    ("serotonin-norepinephrine",       "SNRI"),
    ("antidepressant",                 "Masennuslääke"),
    ("benzodiazepine",                 "Bentsodiatsepiini"),
    ("antipsychotic",                  "Psykoosilääke"),
    ("anticonvulsant",                 "Epilepsialääke"),
    ("antiepileptic",                  "Epilepsialääke"),
    ("opioid",                         "Opioidi"),
    ("analgesic",                      "Kipulääke"),
    ("antipyretic",                    "Kuumetta alentava lääke"),
    ("antibiotic",                     "Antibiootti"),
    ("antibacterial",                  "Antibakteerinen lääke"),
    ("macrolide",                      "Makrolidi"),
    ("penicillin",                     "Penisilliini"),
    ("cephalosporin",                  "Kefalosporiini"),
    ("fluoroquinolone",                "Fluorokinoloni"),
    ("antifungal",                     "Sienilääke"),
    ("antiviral",                      "Viruslääke"),
    ("corticosteroid",                 "Kortikosteroidi"),
    ("bronchodilator",                 "Keuhkoputkia laajentava lääke"),
    ("antihistamine",                  "Antihistamiini"),
    ("immunosuppressant",              "Immunosuppressiivinen lääke"),
    ("thyroid hormone",                "Kilpirauhashormoni"),
    ("pain reliever",                  "Kipulääke"),
    ("pain",                           "Kipulääke"),
]

CLASS_TRANSLATIONS_RO: list[tuple[str, str]] = [
    ("nonsteroidal anti-inflammatory", "Antiinflamator nesteroidian (AINS)"),
    ("proton pump inhibitor",          "Inhibitor al pompei de protoni"),
    ("h2 blocker",                     "Antagonist H2"),
    ("angiotensin receptor blocker",   "Antagonist al receptorilor angiotensinei II"),
    ("ace inhibitor",                  "Inhibitor ECA"),
    ("beta blocker",                   "Betablocant"),
    ("calcium channel blocker",        "Blocant al canalelor de calciu"),
    ("diuretic",                       "Diuretic"),
    ("anticoagulant",                  "Anticoagulant"),
    ("antiplatelet",                   "Antiagregant plachetar"),
    ("antihypertensive",               "Antihipertensiv"),
    ("statin",                         "Statină"),
    ("hmg-coa reductase inhibitor",    "Statină"),
    ("antidiabetic",                   "Antidiabetic"),
    ("biguanide",                      "Biguanidă"),
    ("insulin",                        "Insulină"),
    ("glp-1",                          "Agonist al receptorului GLP-1"),
    ("sglt2",                          "Inhibitor SGLT2"),
    ("ssri",                           "ISRS"),
    ("serotonin-norepinephrine",       "IRSN"),
    ("antidepressant",                 "Antidepresiv"),
    ("benzodiazepine",                 "Benzodiazepină"),
    ("antipsychotic",                  "Antipsihotic"),
    ("anticonvulsant",                 "Anticonvulsivant"),
    ("antiepileptic",                  "Antiepileptic"),
    ("opioid",                         "Opioid"),
    ("analgesic",                      "Analgezic"),
    ("antipyretic",                    "Antipiretic"),
    ("antibiotic",                     "Antibiotic"),
    ("antibacterial",                  "Antibacterian"),
    ("macrolide",                      "Macrolidă"),
    ("penicillin",                     "Penicilină"),
    ("cephalosporin",                  "Cefalosporină"),
    ("fluoroquinolone",                "Fluorochinolonă"),
    ("antifungal",                     "Antifungic"),
    ("antiviral",                      "Antiviral"),
    ("corticosteroid",                 "Corticosteroid"),
    ("bronchodilator",                 "Bronhodilatator"),
    ("antihistamine",                  "Antihistaminic"),
    ("immunosuppressant",              "Imunosupresor"),
    ("thyroid hormone",                "Hormon tiroidian"),
    ("pain reliever",                  "Analgezic"),
    ("pain",                           "Analgezic"),
]

CLASS_TRANSLATIONS_NO: list[tuple[str, str]] = [
    ("nonsteroidal anti-inflammatory", "Ikke-steroide antiinflammatoriske midler (NSAID)"),
    ("proton pump inhibitor",          "Protonpumpehemmer"),
    ("h2 blocker",                     "H2-antagonist"),
    ("angiotensin receptor blocker",   "Angiotensin II-reseptorantagonist"),
    ("ace inhibitor",                  "ACE-hemmer"),
    ("beta blocker",                   "Betablokker"),
    ("calcium channel blocker",        "Kalsiumkanalblokker"),
    ("diuretic",                       "Diuretikum"),
    ("anticoagulant",                  "Antikoagulasjonsmiddel"),
    ("antiplatelet",                   "Blodplatehemmende middel"),
    ("antihypertensive",               "Blodtrykksenkende middel"),
    ("statin",                         "Statin"),
    ("hmg-coa reductase inhibitor",    "Statin"),
    ("antidiabetic",                   "Antidiabetikum"),
    ("biguanide",                      "Biguanid"),
    ("insulin",                        "Insulin"),
    ("glp-1",                          "GLP-1-reseptoragonist"),
    ("sglt2",                          "SGLT2-hemmer"),
    ("ssri",                           "SSRI"),
    ("serotonin-norepinephrine",       "SNRI"),
    ("antidepressant",                 "Antidepressivum"),
    ("benzodiazepine",                 "Benzodiazepin"),
    ("antipsychotic",                  "Antipsykotikum"),
    ("anticonvulsant",                 "Antikonvulsivum"),
    ("antiepileptic",                  "Antiepileptikum"),
    ("opioid",                         "Opioid"),
    ("analgesic",                      "Smertestillende middel"),
    ("antipyretic",                    "Febernedsettende middel"),
    ("antibiotic",                     "Antibiotikum"),
    ("antibacterial",                  "Antibakterielt middel"),
    ("macrolide",                      "Makrolid"),
    ("penicillin",                     "Penicillin"),
    ("cephalosporin",                  "Cefalosporin"),
    ("fluoroquinolone",                "Fluorokinolon"),
    ("antifungal",                     "Soppmiddel"),
    ("antiviral",                      "Antiviralt middel"),
    ("corticosteroid",                 "Kortikosteroid"),
    ("bronchodilator",                 "Bronkodilatator"),
    ("antihistamine",                  "Antihistamin"),
    ("immunosuppressant",              "Immunsuppressivum"),
    ("thyroid hormone",                "Skjoldbruskkjertelhormon"),
    ("pain reliever",                  "Smertestillende middel"),
    ("pain",                           "Smertestillende middel"),
]

# Localized drug display names by language (key = FDA generic name lowercase)
LOCALIZED_NAMES: dict[str, dict[str, str]] = {
    "fr": {
        "acetaminophen": "Paracétamol", "ibuprofen": "Ibuprofène",
        "aspirin": "Aspirine", "naproxen": "Naproxène",
        "diclofenac": "Diclofénac", "celecoxib": "Célécoxib",
        "meloxicam": "Méloxicam", "ketorolac": "Kétorolac",
        "metamizole": "Métamizole", "tramadol": "Tramadol",
        "codeine": "Codéine", "morphine": "Morphine",
        "amoxicillin": "Amoxicilline",
        "amoxicillin clavulanate": "Amoxicilline-acide clavulanique",
        "azithromycin": "Azithromycine", "clarithromycin": "Clarithromycine",
        "ciprofloxacin": "Ciprofloxacine", "levofloxacin": "Lévofloxacine",
        "doxycycline": "Doxycycline", "cephalexin": "Céfalexine",
        "metronidazole": "Métronidazole",
        "trimethoprim sulfamethoxazole": "Cotrimoxazole",
        "nitrofurantoin": "Nitrofurantoïne", "clindamycin": "Clindamycine",
        "fluconazole": "Fluconazole", "terbinafine": "Terbinafine",
        "acyclovir": "Aciclovir", "oseltamivir": "Oseltamivir",
        "metformin": "Metformine", "sitagliptin": "Sitagliptine",
        "empagliflozin": "Empagliflozine", "liraglutide": "Liraglutide",
        "semaglutide": "Sémaglutide", "insulin glargine": "Insuline glargine",
        "omeprazole": "Oméprazole", "pantoprazole": "Pantoprazole",
        "lansoprazole": "Lansoprazole", "esomeprazole": "Ésoméprazole",
        "famotidine": "Famotidine", "ondansetron": "Ondansétron",
        "metoclopramide": "Métoclopramide", "loperamide": "Lopéramide",
        "atorvastatin": "Atorvastatine", "simvastatin": "Simvastatine",
        "rosuvastatin": "Rosuvastatine", "amlodipine": "Amlodipine",
        "enalapril": "Énalapril", "lisinopril": "Lisinopril",
        "ramipril": "Ramipril", "losartan": "Losartan",
        "bisoprolol": "Bisoprolol", "metoprolol": "Métoprolol",
        "furosemide": "Furosémide", "spironolactone": "Spironolactone",
        "warfarin": "Warfarine", "apixaban": "Apixaban",
        "rivaroxaban": "Rivaroxaban", "clopidogrel": "Clopidogrel",
        "alprazolam": "Alprazolam", "lorazepam": "Lorazépam",
        "diazepam": "Diazépam", "sertraline": "Sertraline",
        "fluoxetine": "Fluoxétine", "escitalopram": "Escitalopram",
        "venlafaxine": "Venlafaxine", "duloxetine": "Duloxétine",
        "quetiapine": "Quétiapine", "pregabalin": "Prégabaline",
        "gabapentin": "Gabapentine", "levothyroxine": "Lévothyroxine",
        "prednisone": "Prednisone", "prednisolone": "Prednisolone",
        "albuterol": "Salbutamol", "budesonide": "Budésonide",
        "methotrexate": "Méthotrexate", "hydroxychloroquine": "Hydroxychloroquine",
        "sildenafil": "Sildénafil", "tadalafil": "Tadalafil",
    },
    "it": {
        "acetaminophen": "Paracetamolo", "ibuprofen": "Ibuprofene",
        "aspirin": "Aspirina", "naproxen": "Naprossene",
        "diclofenac": "Diclofenac", "celecoxib": "Celecoxib",
        "meloxicam": "Meloxicam", "ketorolac": "Ketorolac",
        "metamizole": "Metamizolo", "tramadol": "Tramadolo",
        "codeine": "Codeina", "morphine": "Morfina",
        "amoxicillin": "Amoxicillina",
        "amoxicillin clavulanate": "Amoxicillina-acido clavulanico",
        "azithromycin": "Azitromicina", "clarithromycin": "Claritromicina",
        "ciprofloxacin": "Ciprofloxacina", "levofloxacin": "Levofloxacina",
        "doxycycline": "Doxiciclina", "cephalexin": "Cefalexina",
        "metronidazole": "Metronidazolo",
        "trimethoprim sulfamethoxazole": "Cotrimossazolo",
        "nitrofurantoin": "Nitrofurantoina", "clindamycin": "Clindamicina",
        "fluconazole": "Fluconazolo", "terbinafine": "Terbinafina",
        "acyclovir": "Aciclovir", "oseltamivir": "Oseltamivir",
        "metformin": "Metformina", "sitagliptin": "Sitagliptin",
        "empagliflozin": "Empagliflozin", "liraglutide": "Liraglutide",
        "semaglutide": "Semaglutide", "insulin glargine": "Insulina glargine",
        "omeprazole": "Omeprazolo", "pantoprazole": "Pantoprazolo",
        "lansoprazole": "Lansoprazolo", "esomeprazole": "Esomeprazolo",
        "famotidine": "Famotidina", "ondansetron": "Ondansetron",
        "metoclopramide": "Metoclopramide", "loperamide": "Loperamide",
        "atorvastatin": "Atorvastatina", "simvastatin": "Simvastatina",
        "rosuvastatin": "Rosuvastatina", "amlodipine": "Amlodipina",
        "enalapril": "Enalapril", "lisinopril": "Lisinopril",
        "ramipril": "Ramipril", "losartan": "Losartan",
        "bisoprolol": "Bisoprololo", "metoprolol": "Metoprololo",
        "furosemide": "Furosemide", "spironolactone": "Spironolattone",
        "warfarin": "Warfarin", "apixaban": "Apixaban",
        "rivaroxaban": "Rivaroxaban", "clopidogrel": "Clopidogrel",
        "alprazolam": "Alprazolam", "lorazepam": "Lorazepam",
        "diazepam": "Diazepam", "sertraline": "Sertralina",
        "fluoxetine": "Fluoxetina", "escitalopram": "Escitalopram",
        "venlafaxine": "Venlafaxina", "duloxetine": "Duloxetina",
        "quetiapine": "Quetiapina", "pregabalin": "Pregabalin",
        "gabapentin": "Gabapentin", "levothyroxine": "Levotiroxina",
        "prednisone": "Prednisone", "prednisolone": "Prednisolone",
        "albuterol": "Salbutamolo", "budesonide": "Budesonide",
        "methotrexate": "Metotrexato", "hydroxychloroquine": "Idrossiclorochina",
        "sildenafil": "Sildenafil", "tadalafil": "Tadalafil",
    },
    "de": {
        "acetaminophen": "Paracetamol", "ibuprofen": "Ibuprofen",
        "aspirin": "Acetylsalicylsäure", "naproxen": "Naproxen",
        "diclofenac": "Diclofenac", "celecoxib": "Celecoxib",
        "meloxicam": "Meloxicam", "ketorolac": "Ketorolac",
        "metamizole": "Metamizol", "tramadol": "Tramadol",
        "codeine": "Codein", "morphine": "Morphin",
        "amoxicillin": "Amoxicillin",
        "amoxicillin clavulanate": "Amoxicillin-Clavulansäure",
        "azithromycin": "Azithromycin", "clarithromycin": "Clarithromycin",
        "ciprofloxacin": "Ciprofloxacin", "levofloxacin": "Levofloxacin",
        "doxycycline": "Doxycyclin", "cephalexin": "Cefalexin",
        "metronidazole": "Metronidazol",
        "trimethoprim sulfamethoxazole": "Cotrimoxazol",
        "nitrofurantoin": "Nitrofurantoin", "clindamycin": "Clindamycin",
        "fluconazole": "Fluconazol", "terbinafine": "Terbinafin",
        "acyclovir": "Aciclovir", "oseltamivir": "Oseltamivir",
        "metformin": "Metformin", "sitagliptin": "Sitagliptin",
        "empagliflozin": "Empagliflozin", "liraglutide": "Liraglutid",
        "semaglutide": "Semaglutid", "insulin glargine": "Insulin glargin",
        "omeprazole": "Omeprazol", "pantoprazole": "Pantoprazol",
        "lansoprazole": "Lansoprazol", "esomeprazole": "Esomeprazol",
        "famotidine": "Famotidin", "ondansetron": "Ondansetron",
        "metoclopramide": "Metoclopramid", "loperamide": "Loperamid",
        "atorvastatin": "Atorvastatin", "simvastatin": "Simvastatin",
        "rosuvastatin": "Rosuvastatin", "amlodipine": "Amlodipin",
        "enalapril": "Enalapril", "lisinopril": "Lisinopril",
        "ramipril": "Ramipril", "losartan": "Losartan",
        "bisoprolol": "Bisoprolol", "metoprolol": "Metoprolol",
        "furosemide": "Furosemid", "spironolactone": "Spironolacton",
        "warfarin": "Warfarin", "apixaban": "Apixaban",
        "rivaroxaban": "Rivaroxaban", "clopidogrel": "Clopidogrel",
        "alprazolam": "Alprazolam", "lorazepam": "Lorazepam",
        "diazepam": "Diazepam", "sertraline": "Sertralin",
        "fluoxetine": "Fluoxetin", "escitalopram": "Escitalopram",
        "venlafaxine": "Venlafaxin", "duloxetine": "Duloxetin",
        "quetiapine": "Quetiapin", "pregabalin": "Pregabalin",
        "gabapentin": "Gabapentin", "levothyroxine": "Levothyroxin",
        "prednisone": "Prednison", "prednisolone": "Prednisolon",
        "albuterol": "Salbutamol", "budesonide": "Budesonid",
        "methotrexate": "Methotrexat", "hydroxychloroquine": "Hydroxychloroquin",
        "sildenafil": "Sildenafil", "tadalafil": "Tadalafil",
    },
    "pt": {
        "acetaminophen": "Paracetamol", "ibuprofen": "Ibuprofeno",
        "aspirin": "Aspirina", "naproxen": "Naproxeno",
        "diclofenac": "Diclofenaco", "celecoxib": "Celecoxib",
        "meloxicam": "Meloxicam", "ketorolac": "Cetorolaco",
        "metamizole": "Metamizol", "tramadol": "Tramadol",
        "codeine": "Codeína", "morphine": "Morfina",
        "amoxicillin": "Amoxicilina",
        "amoxicillin clavulanate": "Amoxicilina-ácido clavulânico",
        "azithromycin": "Azitromicina", "clarithromycin": "Claritromicina",
        "ciprofloxacin": "Ciprofloxacina", "levofloxacin": "Levofloxacina",
        "doxycycline": "Doxiciclina", "cephalexin": "Cefalexina",
        "metronidazole": "Metronidazol",
        "trimethoprim sulfamethoxazole": "Cotrimoxazol",
        "nitrofurantoin": "Nitrofurantoína", "clindamycin": "Clindamicina",
        "fluconazole": "Fluconazol", "terbinafine": "Terbinafina",
        "acyclovir": "Aciclovir", "oseltamivir": "Oseltamivir",
        "metformin": "Metformina", "sitagliptin": "Sitagliptina",
        "empagliflozin": "Empagliflozina", "liraglutide": "Liraglutida",
        "semaglutide": "Semaglutida", "insulin glargine": "Insulina glargina",
        "omeprazole": "Omeprazol", "pantoprazole": "Pantoprazol",
        "lansoprazole": "Lansoprazol", "esomeprazole": "Esomeprazol",
        "famotidine": "Famotidina", "ondansetron": "Ondansetron",
        "metoclopramide": "Metoclopramida", "loperamide": "Loperamida",
        "atorvastatin": "Atorvastatina", "simvastatin": "Simvastatina",
        "rosuvastatin": "Rosuvastatina", "amlodipine": "Anlodipino",
        "enalapril": "Enalapril", "lisinopril": "Lisinopril",
        "ramipril": "Ramipril", "losartan": "Losartan",
        "bisoprolol": "Bisoprolol", "metoprolol": "Metoprolol",
        "furosemide": "Furosemida", "spironolactone": "Espironolactona",
        "warfarin": "Varfarina", "apixaban": "Apixabano",
        "rivaroxaban": "Rivaroxabano", "clopidogrel": "Clopidogrel",
        "alprazolam": "Alprazolam", "lorazepam": "Lorazepam",
        "diazepam": "Diazepam", "sertraline": "Sertralina",
        "fluoxetine": "Fluoxetina", "escitalopram": "Escitalopram",
        "venlafaxine": "Venlafaxina", "duloxetine": "Duloxetina",
        "quetiapine": "Quetiapina", "pregabalin": "Pregabalina",
        "gabapentin": "Gabapentina", "levothyroxine": "Levotiroxina",
        "prednisone": "Prednisona", "prednisolone": "Prednisolona",
        "albuterol": "Salbutamol", "budesonide": "Budesonida",
        "methotrexate": "Metotrexato", "hydroxychloroquine": "Hidroxicloroquina",
        "sildenafil": "Sildenafila", "tadalafil": "Tadalafila",
    },
    "ca": {
        "acetaminophen": "Paracetamol", "ibuprofen": "Ibuprofèn",
        "aspirin": "Aspirina", "naproxen": "Naproxè",
        "diclofenac": "Diclofenac", "celecoxib": "Celecoxib",
        "meloxicam": "Meloxicam", "ketorolac": "Ketorolac",
        "metamizole": "Metamizol", "tramadol": "Tramadol",
        "codeine": "Codeïna", "morphine": "Morfina",
        "amoxicillin": "Amoxicil·lina",
        "amoxicillin clavulanate": "Amoxicil·lina-àcid clavulànic",
        "azithromycin": "Azitromicina", "clarithromycin": "Claritromicina",
        "ciprofloxacin": "Ciprofloxacina", "levofloxacin": "Levofloxacina",
        "doxycycline": "Doxiciclina", "cephalexin": "Cefalexina",
        "metronidazole": "Metronidazol",
        "trimethoprim sulfamethoxazole": "Cotrimoxazol",
        "nitrofurantoin": "Nitrofurantoïna", "clindamycin": "Clindamicina",
        "fluconazole": "Fluconazol", "terbinafine": "Terbinafina",
        "acyclovir": "Aciclovir", "oseltamivir": "Oseltamivir",
        "metformin": "Metformina", "sitagliptin": "Sitagliptina",
        "empagliflozin": "Empagliflozina", "liraglutide": "Liraglutida",
        "semaglutide": "Semaglutida", "insulin glargine": "Insulina glargina",
        "omeprazole": "Omeprazol", "pantoprazole": "Pantoprazol",
        "lansoprazole": "Lansoprazol", "esomeprazole": "Esomeprazol",
        "famotidine": "Famotidina", "ondansetron": "Ondansetró",
        "metoclopramide": "Metoclopramida", "loperamide": "Loperamida",
        "atorvastatin": "Atorvastatina", "simvastatin": "Simvastatina",
        "rosuvastatin": "Rosuvastatina", "amlodipine": "Amlodipina",
        "enalapril": "Enalapril", "lisinopril": "Lisinopril",
        "ramipril": "Ramipril", "losartan": "Losartan",
        "bisoprolol": "Bisoprolol", "metoprolol": "Metoprolol",
        "furosemide": "Furosemida", "spironolactone": "Espironolactona",
        "warfarin": "Warfarina", "apixaban": "Apixaban",
        "rivaroxaban": "Rivaroxaban", "clopidogrel": "Clopidogrel",
        "alprazolam": "Alprazolam", "lorazepam": "Lorazepam",
        "diazepam": "Diazepam", "sertraline": "Sertralina",
        "fluoxetine": "Fluoxetina", "escitalopram": "Escitalopram",
        "venlafaxine": "Venlafaxina", "duloxetine": "Duloxetina",
        "quetiapine": "Quetiapina", "pregabalin": "Pregabalina",
        "gabapentin": "Gabapentina", "levothyroxine": "Levotiroxina",
        "prednisone": "Prednisona", "prednisolone": "Prednisolona",
        "albuterol": "Salbutamol", "budesonide": "Budesonida",
        "methotrexate": "Metotrexat", "hydroxychloroquine": "Hidroxicloroquina",
        "sildenafil": "Sildenafil", "tadalafil": "Tadalafil",
    },
    "pl": {
        "acetaminophen": "Paracetamol", "ibuprofen": "Ibuprofen",
        "aspirin": "Aspiryna", "naproxen": "Naproksen",
        "diclofenac": "Diklofenak", "celecoxib": "Celekoksyb",
        "meloxicam": "Meloksykam", "ketorolac": "Ketorolak",
        "metamizole": "Metamizol", "tramadol": "Tramadol",
        "codeine": "Kodeina", "morphine": "Morfina",
        "amoxicillin": "Amoksycylina",
        "amoxicillin clavulanate": "Amoksycylina-kwas klawulanowy",
        "azithromycin": "Azytromycyna", "clarithromycin": "Klarytromycyna",
        "ciprofloxacin": "Cyprofloksacyna", "levofloxacin": "Lewofloksacyna",
        "doxycycline": "Doksycyklina", "cephalexin": "Cefaleksyna",
        "metronidazole": "Metronidazol",
        "trimethoprim sulfamethoxazole": "Kotrimoksazol",
        "nitrofurantoin": "Nitrofurantoina", "clindamycin": "Klindamycyna",
        "fluconazole": "Flukonazol", "terbinafine": "Terbinafina",
        "acyclovir": "Acyklowir", "oseltamivir": "Oseltamiwir",
        "metformin": "Metformina", "sitagliptin": "Sitagliptyna",
        "empagliflozin": "Empagliflozyna", "liraglutide": "Liraglutyd",
        "semaglutide": "Semaglutyd", "insulin glargine": "Insulina glargine",
        "omeprazole": "Omeprazol", "pantoprazole": "Pantoprazol",
        "lansoprazole": "Lansoprazol", "esomeprazole": "Esomeprazol",
        "famotidine": "Famotydyna", "ondansetron": "Ondansetron",
        "metoclopramide": "Metoklopramid", "loperamide": "Loperamid",
        "atorvastatin": "Atorwastatyna", "simvastatin": "Simwastatyna",
        "rosuvastatin": "Rozuwastatyna", "amlodipine": "Amlodypina",
        "enalapril": "Enalapril", "lisinopril": "Lizynopryl",
        "ramipril": "Ramipril", "losartan": "Losartan",
        "bisoprolol": "Bisoprolol", "metoprolol": "Metoprolol",
        "furosemide": "Furosemid", "spironolactone": "Spironolakton",
        "warfarin": "Warfaryna", "apixaban": "Apiksaban",
        "rivaroxaban": "Rywaroksaban", "clopidogrel": "Klopidogrel",
        "alprazolam": "Alprazolam", "lorazepam": "Lorazepam",
        "diazepam": "Diazepam", "sertraline": "Sertralina",
        "fluoxetine": "Fluoksetyna", "escitalopram": "Escitalopram",
        "venlafaxine": "Wenlafaksyna", "duloxetine": "Duloksetyna",
        "quetiapine": "Kwetiapina", "pregabalin": "Pregabalina",
        "gabapentin": "Gabapentyna", "levothyroxine": "Lewotyroksyna",
        "prednisone": "Prednizon", "prednisolone": "Prednizolon",
        "albuterol": "Salbutamol", "budesonide": "Budezonid",
        "methotrexate": "Metotreksat", "hydroxychloroquine": "Hydroksychlorochina",
        "sildenafil": "Sildenafil", "tadalafil": "Tadalafil",
    },
    "fi": {
        "acetaminophen": "Parasetamoli", "ibuprofen": "Ibuprofeeni",
        "aspirin": "Aspiriini", "naproxen": "Naprokseeni",
        "diclofenac": "Diklofenaakki", "celecoxib": "Selekoksibi",
        "meloxicam": "Meloksikaami", "ketorolac": "Ketorolaakki",
        "metamizole": "Metamitsoli", "tramadol": "Tramadoli",
        "codeine": "Kodeiini", "morphine": "Morfiini",
        "amoxicillin": "Amoksisilliini",
        "amoxicillin clavulanate": "Amoksisilliini-klavulaanihappo",
        "azithromycin": "Atsitromysiini", "clarithromycin": "Klaritromysiini",
        "ciprofloxacin": "Siprofloksasiini", "levofloxacin": "Levofloksasiini",
        "doxycycline": "Doksisykliini", "cephalexin": "Kefaleksiini",
        "metronidazole": "Metronidatsoli",
        "trimethoprim sulfamethoxazole": "Kotrimoksatsoli",
        "nitrofurantoin": "Nitrofurantoiini", "clindamycin": "Klindamysiini",
        "fluconazole": "Flukonatsoli", "terbinafine": "Terbinafiini",
        "acyclovir": "Asikloviiri", "oseltamivir": "Oseltamiviiri",
        "metformin": "Metformiini", "sitagliptin": "Sitagliptiini",
        "empagliflozin": "Empagliflotsiini", "liraglutide": "Liraglutiidi",
        "semaglutide": "Semaglutiidi", "insulin glargine": "Insuliini glargiini",
        "omeprazole": "Omepratsoli", "pantoprazole": "Pantopratsoli",
        "lansoprazole": "Lansoprotsoli", "esomeprazole": "Esomepratsoli",
        "famotidine": "Famotidiini", "ondansetron": "Ondansetroni",
        "metoclopramide": "Metoklopramidi", "loperamide": "Loperamidi",
        "atorvastatin": "Atorvastatiini", "simvastatin": "Simvastatiini",
        "rosuvastatin": "Rosuvastatiini", "amlodipine": "Amlodipiini",
        "enalapril": "Enalapriili", "lisinopril": "Lisinopriili",
        "ramipril": "Ramipriili", "losartan": "Losartaani",
        "bisoprolol": "Bisoprololi", "metoprolol": "Metoprololi",
        "furosemide": "Furosemidi", "spironolactone": "Spironolaktoni",
        "warfarin": "Varfariini", "apixaban": "Apiksabaani",
        "rivaroxaban": "Rivaroksabaani", "clopidogrel": "Klopidogreeli",
        "alprazolam": "Alpratsolaami", "lorazepam": "Loratsepaaami",
        "diazepam": "Diatsepaami", "sertraline": "Sertraliini",
        "fluoxetine": "Fluoksetiini", "escitalopram": "Essitalopraami",
        "venlafaxine": "Venlafaksiini", "duloxetine": "Duloksetiini",
        "quetiapine": "Ketiapiini", "pregabalin": "Pregabaliini",
        "gabapentin": "Gabapentiini", "levothyroxine": "Levotyroksiini",
        "prednisone": "Prednisoni", "prednisolone": "Prednisoloni",
        "albuterol": "Salbutamoli", "budesonide": "Budesonidi",
        "methotrexate": "Metotreksaatti", "hydroxychloroquine": "Hydroksiklorokiini",
        "sildenafil": "Sildenafiili", "tadalafil": "Tadalafiili",
    },
    "ro": {
        "acetaminophen": "Paracetamol", "ibuprofen": "Ibuprofen",
        "aspirin": "Aspirină", "naproxen": "Naproxen",
        "diclofenac": "Diclofenac", "celecoxib": "Celecoxib",
        "meloxicam": "Meloxicam", "ketorolac": "Ketorolac",
        "metamizole": "Metamizol", "tramadol": "Tramadol",
        "codeine": "Codeină", "morphine": "Morfină",
        "amoxicillin": "Amoxicilină",
        "amoxicillin clavulanate": "Amoxicilină-acid clavulanic",
        "azithromycin": "Azitromicină", "clarithromycin": "Claritromicină",
        "ciprofloxacin": "Ciprofloxacină", "levofloxacin": "Levofloxacină",
        "doxycycline": "Doxiciclină", "cephalexin": "Cefalexină",
        "metronidazole": "Metronidazol",
        "trimethoprim sulfamethoxazole": "Cotrimoxazol",
        "nitrofurantoin": "Nitrofurantoină", "clindamycin": "Clindamicină",
        "fluconazole": "Fluconazol", "terbinafine": "Terbinafină",
        "acyclovir": "Aciclovir", "oseltamivir": "Oseltamivir",
        "metformin": "Metformină", "sitagliptin": "Sitagliptină",
        "empagliflozin": "Empagliflozină", "liraglutide": "Liraglutidă",
        "semaglutide": "Semaglutidă", "insulin glargine": "Insulină glargine",
        "omeprazole": "Omeprazol", "pantoprazole": "Pantoprazol",
        "lansoprazole": "Lansoprazol", "esomeprazole": "Esomeprazol",
        "famotidine": "Famotidină", "ondansetron": "Ondansetron",
        "metoclopramide": "Metoclopramidă", "loperamide": "Loperamidă",
        "atorvastatin": "Atorvastatină", "simvastatin": "Simvastatină",
        "rosuvastatin": "Rosuvastatină", "amlodipine": "Amlodipină",
        "enalapril": "Enalapril", "lisinopril": "Lisinopril",
        "ramipril": "Ramipril", "losartan": "Losartan",
        "bisoprolol": "Bisoprolol", "metoprolol": "Metoprolol",
        "furosemide": "Furosemidă", "spironolactone": "Spironolactonă",
        "warfarin": "Warfarină", "apixaban": "Apixaban",
        "rivaroxaban": "Rivaroxaban", "clopidogrel": "Clopidogrel",
        "alprazolam": "Alprazolam", "lorazepam": "Lorazepam",
        "diazepam": "Diazepam", "sertraline": "Sertralină",
        "fluoxetine": "Fluoxetină", "escitalopram": "Escitalopram",
        "venlafaxine": "Venlafaxină", "duloxetine": "Duloxetină",
        "quetiapine": "Quetiapină", "pregabalin": "Pregabalină",
        "gabapentin": "Gabapentină", "levothyroxine": "Levotiroxină",
        "prednisone": "Prednison", "prednisolone": "Prednisolon",
        "albuterol": "Salbutamol", "budesonide": "Budesonidă",
        "methotrexate": "Metotrexat", "hydroxychloroquine": "Hidroxiclorochină",
        "sildenafil": "Sildenafil", "tadalafil": "Tadalafil",
    },
    "no": {
        "acetaminophen": "Paracetamol", "ibuprofen": "Ibuprofen",
        "aspirin": "Aspirin", "naproxen": "Naproxen",
        "diclofenac": "Diklofenak", "celecoxib": "Celekoksib",
        "meloxicam": "Meloksikam", "ketorolac": "Ketorolak",
        "metamizole": "Metamizol", "tramadol": "Tramadol",
        "codeine": "Kodein", "morphine": "Morfin",
        "amoxicillin": "Amoksicillin",
        "amoxicillin clavulanate": "Amoksicillin-klavulansyre",
        "azithromycin": "Azitromycin", "clarithromycin": "Klaritromycin",
        "ciprofloxacin": "Ciprofloksacin", "levofloxacin": "Levofloksacin",
        "doxycycline": "Doksysyklin", "cephalexin": "Cefaleksin",
        "metronidazole": "Metronidazol",
        "trimethoprim sulfamethoxazole": "Kotrimoksazol",
        "nitrofurantoin": "Nitrofurantoin", "clindamycin": "Klindamycin",
        "fluconazole": "Flukonazol", "terbinafine": "Terbinafin",
        "acyclovir": "Aciklovir", "oseltamivir": "Oseltamivir",
        "metformin": "Metformin", "sitagliptin": "Sitagliptin",
        "empagliflozin": "Empagliflozin", "liraglutide": "Liraglutid",
        "semaglutide": "Semaglutid", "insulin glargine": "Insulin glargin",
        "omeprazole": "Omeprazol", "pantoprazole": "Pantoprazol",
        "lansoprazole": "Lansoprazol", "esomeprazole": "Esomeprazol",
        "famotidine": "Famotidin", "ondansetron": "Ondansetron",
        "metoclopramide": "Metoklopramid", "loperamide": "Loperamid",
        "atorvastatin": "Atorvastatin", "simvastatin": "Simvastatin",
        "rosuvastatin": "Rosuvastatin", "amlodipine": "Amlodipin",
        "enalapril": "Enalapril", "lisinopril": "Lisinopril",
        "ramipril": "Ramipril", "losartan": "Losartan",
        "bisoprolol": "Bisoprolol", "metoprolol": "Metoprolol",
        "furosemide": "Furosemid", "spironolactone": "Spironolakton",
        "warfarin": "Warfarin", "apixaban": "Apixaban",
        "rivaroxaban": "Rivaroksaban", "clopidogrel": "Klopidogrel",
        "alprazolam": "Alprazolam", "lorazepam": "Lorazepam",
        "diazepam": "Diazepam", "sertraline": "Sertralin",
        "fluoxetine": "Fluoksetin", "escitalopram": "Escitalopram",
        "venlafaxine": "Venlafaksin", "duloxetine": "Duloksetin",
        "quetiapine": "Kvetiapin", "pregabalin": "Pregabalin",
        "gabapentin": "Gabapentin", "levothyroxine": "Levotyroksin",
        "prednisone": "Prednisolon", "prednisolone": "Prednisolon",
        "albuterol": "Salbutamol", "budesonide": "Budesonid",
        "methotrexate": "Metotreksat", "hydroxychloroquine": "Hydroksyklorokin",
        "sildenafil": "Sildenafil", "tadalafil": "Tadalafil",
    },
}


def translate_class(drug_class: str, lang: str) -> str:
    """Traduce la clase farmacológica al idioma indicado."""
    if lang == "en":
        return drug_class
    if lang == "es":
        return translate_class_to_es(drug_class)
    tables = {
        "fr": CLASS_TRANSLATIONS_FR,
        "it": CLASS_TRANSLATIONS_IT,
        "de": CLASS_TRANSLATIONS_DE,
        "pt": CLASS_TRANSLATIONS_PT,
        "ca": CLASS_TRANSLATIONS_CA,
        "ro": CLASS_TRANSLATIONS_RO,
        "no": CLASS_TRANSLATIONS_NO,
    }
    table = tables.get(lang, [])
    c = drug_class.lower()
    for en_key, loc_val in table:
        if en_key in c:
            return loc_val
    return drug_class


DEFAULT_SOURCES = [
    {
        "label": "CIMA AEMPS",
        "url": "https://cima.aemps.es"
    },
    {
        "label": "Vademecum",
        "url": "https://www.vademecum.es"
    },
    {
        "label": "DrugBank",
        "url": "https://go.drugbank.com"
    },
]

# ─────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────


class CompatRequest(BaseModel):
    drug_name: str
    patient_text: str
    symptom_text: str = ""
    lang: str = "es"


# ─────────────────────────────────────────
# OPENFDA — FETCH
# ─────────────────────────────────────────


async def enrich_drug_data(med: dict, lang: str) -> dict:
    """
    Enriquece la ficha con Gemini (solo texto libre + dato curioso).
    Nombre y clase ya están traducidos estáticamente antes de llamar aquí.
    """
    if not GEMINI_KEY:
        return med

    drug_name = med.get("name", "this drug")

    if lang == "es":
        payload = {
            "uses":   med.get("uses", "")[:500],
            "dosage": med.get("dosage", "")[:200],
        }
        prompt = (
            f"Eres un traductor médico. Traduce al español (terminología precisa). "
            f"Añade 'funFact': dato curioso REAL sobre {drug_name} en español (1-2 frases). "
            f"Devuelve SOLO JSON con los mismos campos más 'funFact'.\n\n"
            + json.dumps(payload, ensure_ascii=False)
        )
    else:
        prompt = (
            f"Pharmaceutical expert: write a real, verified fun fact about {drug_name} "
            f"in English (1-2 sentences). Return ONLY JSON: {{\"funFact\": \"...\"}}"
        )

    try:
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(
                GEMINI_URL,
                headers={"X-goog-api-key": GEMINI_KEY, "Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.4,
                        "maxOutputTokens": 800,
                        "responseMimeType": "application/json",
                    }
                }
            )
        if resp.status_code == 200:
            result = json.loads(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
            med = {**med}
            if lang == "es":
                for key in ["uses", "dosage"]:
                    if result.get(key):
                        med[key] = result[key]
            if result.get("funFact"):
                med["fact"] = result["funFact"]
    except Exception:
        pass

    return med


async def fetch_cima_data(query: str) -> Optional[dict]:
    """
    Busca en CIMA (AEMPS). Devuelve metadatos del primer resultado relevante o None.
    Prefiere resultados cuyo principio activo (vtm) coincide exactamente con la búsqueda.
    """
    def _parse_item(item: dict) -> dict:
        vtm_info = item.get("vtm") or {}
        vias = item.get("viasAdministracion") or []
        forma = item.get("formaFarmaceutica") or {}
        return {
            "nregistro":   str(item.get("nregistro", "")),
            "nombre":      item.get("nombre", ""),
            "vtm":         vtm_info.get("nombre", ""),
            "via":         vias[0].get("nombre", "") if vias else "",
            "forma":       forma.get("nombre", ""),
            "laboratorio": item.get("labtitular", ""),
        }

    q_lower = query.lower().strip()

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Try with up to 5 results so we can prefer exact vtm match
        for search_term in [query, fuzzy_resolve_drug_name(q_lower)]:
            try:
                resp = await client.get(CIMA_SEARCH_URL,
                                        params={"nombre": search_term, "pageSize": 5})
                if resp.status_code != 200:
                    continue
                items = resp.json().get("resultados", [])
                if not items:
                    continue
                # Priority 1: exact vtm match (prevents omeprazol → esomeprazol etc.)
                for item in items:
                    vtm = (item.get("vtm") or {}).get("nombre", "").lower()
                    if vtm and vtm == q_lower:
                        return _parse_item(item)
                # Priority 2: nombre starts with query (e.g. "IBUPROFENO CINFA…")
                for item in items:
                    nombre = item.get("nombre", "").lower()
                    if nombre.startswith(q_lower + " ") or nombre.startswith(q_lower):
                        return _parse_item(item)
                # No confident match — let OpenFDA handle it
                return None
            except Exception:
                continue
    return None


async def fetch_cima_ficha(nregistro: str) -> dict:
    """
    Descarga la ficha técnica HTML de CIMA y extrae las secciones clínicas
    en español: 4.1 indicaciones, 4.2 posología, 4.3 contraindicaciones,
    4.8 reacciones adversas.
    """
    url = (f"https://cima.aemps.es/cima/dochtml/ft/{nregistro}"
           f"/FT_{nregistro}.html")
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {}

            # Parse HTML: inline elements → space (preserve word flow),
            # block elements → newline, then unescape entities.
            _inline = re.compile(
                r'</?(?:span|a|strong|em|b|i|u|sup|sub|abbr|acronym|cite|'
                r'code|dfn|kbd|q|samp|time|var)[^>]*>', re.IGNORECASE)
            src = html.unescape(resp.text)
            src = _inline.sub(' ', src)          # inline → space
            text = re.sub(r'<[^>]+>', '\n', src)  # block  → newline
            text = re.sub(r'[ \t]{2,}', ' ', text)
            text = re.sub(r'\n[ \t]*\n', '\n\n', text)
            text = re.sub(r'\n{3,}', '\n\n', text).strip()

            def section(start: str, end: str) -> str:
                """Extract text of a numbered section, skipping the title line.
                Only matches section headers (number at start of line)."""
                m = re.search(rf'(?m)^ *{re.escape(start)}\b', text)
                if not m:
                    return ""
                rest = text[m.end():]
                # Skip the title line (first non-blank line after the section number)
                lines = rest.split('\n')
                i = 0
                while i < len(lines) and not lines[i].strip():
                    i += 1  # skip leading blank lines
                i += 1      # skip title line itself
                while i < len(lines) and not lines[i].strip():
                    i += 1  # skip blank lines after title
                content = '\n'.join(lines[i:])
                m2 = re.search(rf'(?m)^ *{re.escape(end)}\b', content)
                return (content[:m2.start()].strip() if m2 else content[:2000].strip())[:2000]

            def clean(s: str) -> str:
                """Remove blank/whitespace-only lines and collapse spacing."""
                lines = [ln.rstrip() for ln in s.split('\n')]
                lines = [ln for ln in lines if ln.strip()]
                return '\n'.join(lines)

            return {
                "indicaciones":        clean(section("4.1", "4.2")),
                "posologia":           clean(section("4.2", "4.3")),
                "contraindicaciones":  clean(section("4.3", "4.4")),
                "reacciones_adversas": clean(section("4.8", "4.9")),
            }
        except Exception:
            return {}


async def fetch_openfda_raw(query: str) -> Optional[dict]:
    """
    Busca en OpenFDA. Traduce nombres europeos/españoles a inglés (FDA) si es necesario.
    Intenta: nombre traducido → nombre original → brand name → substance name.
    """
    q_lower = query.lower().strip()
    translated = fuzzy_resolve_drug_name(q_lower)

    # Construir lista de términos a probar (sin duplicados)
    terms = [translated]
    if translated.lower() != q_lower:
        terms.append(query)  # también probar el original por si acaso

    searches = []
    for term in terms:
        searches += [
            f'openfda.generic_name:"{term}"',
            f'openfda.brand_name:"{term}"',
            f'openfda.substance_name:"{term}"',
        ]

    async with httpx.AsyncClient(timeout=12.0) as client:
        for search in searches:
            try:
                resp = await client.get(OPENFDA_URL,
                                        params={
                                            "search": search,
                                            "limit": 1
                                        })
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

    def _clean(s: str) -> str:
        return re.sub(r'^[\s\u2022\-\*•◦▸\d.)]+', '', s).strip().rstrip('.,;')

    # 1. Bullet / numbered list
    parts = re.split(r'\n\s*[\u2022\-\*•◦]\s*|\n\s*\d+[.)]\s+', text)
    parts = [_clean(p) for p in parts if len(_clean(p)) > 12]
    if len(parts) > 1:
        return [p[:200] for p in parts[:max_items]]

    # 2. Doble salto de línea
    parts = re.split(r'\n{2,}', text)
    parts = [_clean(p) for p in parts if len(_clean(p)) > 12]
    if len(parts) > 1:
        return [p[:200] for p in parts[:max_items]]

    # 3. Salto de línea simple
    parts = [_clean(p) for p in text.split('\n') if len(_clean(p)) > 12]
    if len(parts) > 1:
        return [p[:200] for p in parts[:max_items]]

    # 4. Sentencias (punto + mayúscula)
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    parts = [p.strip() for p in parts if len(p.strip()) > 12]
    return [p[:200] for p in parts[:max_items]]


def _extract_side_effects(raw: dict) -> List[str]:
    """
    Extrae efectos adversos del label FDA.
    - Medicamentos Rx: campo adverse_reactions → busca patrón 'most common … are X, Y'
      y porcentajes, luego split genérico.
    - Medicamentos OTC: campos when_using + stop_use + warnings (patrón 'include:').
    """
    # ── Rx: adverse_reactions ──────────────────────────────────────────────────
    adverse_text = _first(raw.get("adverse_reactions"), 3000)
    if adverse_text:
        # Patrón "most common … are/include X, Y, Z"
        m = re.search(
            r'most\s+common[^:\n]{0,100}(?:are|include|were)[:\s]+(.+?)\.(?=\s+[A-Z]|\s*$)',
            adverse_text, re.IGNORECASE
        )
        if m:
            segment = re.sub(r'\(\s*[\d.\s]+\)', '', m.group(1))  # quitar refs "( 6.1 )"
            items = [
                s.strip().rstrip('.,;')
                for s in re.split(r',\s*(?:and\s+)?|;\s*', segment)
                if len(s.strip()) > 3
            ]
            if len(items) >= 2:
                return [i[:120] for i in items[:10]]

        # Patrón porcentaje: "nausea (3-9%)" o "nausea (0.7%)"
        pct_items = re.findall(
            r'([a-z][a-z\s\-/]{2,40})\s*\(\s*[\d.]+(?:\s*-\s*[\d.]+)?\s*%\s*\)',
            adverse_text, re.IGNORECASE
        )
        if len(pct_items) >= 2:
            return [i.strip()[:120] for i in pct_items[:10]]

        # Limpieza y split genérico
        clean = re.sub(r'^\s*\d+\s+ADVERSE REACTIONS\b\s*', '', adverse_text)
        clean = re.sub(r'\[see [^\]]+\]', '', clean)
        clean = re.sub(r'\(\s*[\d.]+\s*\)', '', clean)
        items = _split_to_list(clean, max_items=8)
        if items:
            return items

    # ── OTC: when_using ────────────────────────────────────────────────────────
    items: List[str] = []
    when_text = _first(raw.get("when_using"), 1000)
    if when_text:
        items = _split_to_list(when_text, max_items=5)

    # OTC: stop_use (señales de alarma)
    stop_text = _first(raw.get("stop_use"), 1200)
    if stop_text:
        # Buscar lista después de "include:" o "following:"
        m = re.search(r'(?:following|include)[^:]*:\s*(.+)', stop_text, re.IGNORECASE | re.DOTALL)
        if m:
            segment = m.group(1)[:600]
            extra = _split_to_list(segment, max_items=6)
        else:
            extra = _split_to_list(stop_text, max_items=5)
        items += [i for i in extra if i not in items]

    # OTC: warnings → "Symptoms may include: rash facial swelling ..."
    if len(items) < 3:
        warn_text = _first(raw.get("warnings"), 2000)
        m = re.search(r'(?:symptoms?\s+may\s+include|symptoms?\s+include)[^:]*:\s*(.+?)(?:\n|If an|$)',
                      warn_text, re.IGNORECASE | re.DOTALL)
        if m:
            segment = m.group(1).strip()
            # Palabras/frases separadas por espacios o comas
            parts = re.split(r'[\n,]+', segment)
            extra = [p.strip().rstrip('.,;') for p in parts if 3 < len(p.strip()) < 80]
            items += [i for i in extra if i not in items]

    return [i[:200] for i in items[:10]]


def _extract_contraindications(raw: dict) -> List[str]:
    """
    Extrae contraindicaciones del label FDA.
    - Medicamentos Rx: campo contraindications → limpia encabezados y refs.
    - Medicamentos OTC: campo do_not_use → split genérico.
    """
    # ── Rx: contraindications ──────────────────────────────────────────────────
    contra_text = _first(raw.get("contraindications"), 2500)
    if contra_text:
        clean = re.sub(r'^\s*\d+\s+CONTRAINDICATIONS\b\s*', '', contra_text)
        clean = re.sub(r'\[see [^\]]+\]', '', clean)
        clean = re.sub(r'\(\s*[\d.\s]+\)', '', clean)
        # Normalizar separadores: cada punto seguido de mayúscula es un item nuevo
        clean = re.sub(r'\.\s+(?=[A-Z])', '.\n', clean)
        items = _split_to_list(clean, max_items=6)
        if items:
            return items

    # ── OTC: do_not_use ───────────────────────────────────────────────────────
    do_not = _first(raw.get("do_not_use"), 1000)
    if do_not:
        items = _split_to_list(do_not, max_items=6)
        if items:
            return items

    # ── OTC: ask_doctor (precauciones como contraindications adicionales) ──────
    ask_text = _first(raw.get("ask_doctor"), 1000)
    if ask_text:
        return _split_to_list(ask_text, max_items=5)

    return []


def _drug_class(openfda: dict) -> str:
    for key in ("pharm_class_epc", "pharm_class_cs", "pharm_class_moa"):
        classes = openfda.get(key, [])
        if classes:
            return re.sub(r'\s*\[.*?\]', '', classes[0]).strip()
    return "Medicamento"


def _emoji(drug_class: str) -> str:
    c = drug_class.lower()
    if any(k in c for k in
           ["anti-inflammatory", "nsaid", "analgesic", "pain", "antipyretic"]):
        return "💊"
    if any(k in c for k in [
            "antibiotic", "antibacterial", "antimicrobial", "penicillin",
            "macrolide"
    ]):
        return "🟡"
    if any(k in c
           for k in ["antidiabetic", "hypoglycemic", "biguanide", "insulin"]):
        return "🔴"
    if any(k in c
           for k in ["proton pump", "antacid", "h2 blocker", "gastric"]):
        return "🟣"
    if any(k in c
           for k in ["anticoagulant", "antithrombotic", "antiplatelet"]):
        return "🩸"
    if any(k in c for k in [
            "antihypertensive", "cardiovascular", "beta blocker",
            "ace inhibitor"
    ]):
        return "❤️"
    if any(k in c for k in [
            "antidepressant", "antianxiety", "psychiatric", "psychotropic",
            "ssri"
    ]):
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
    not_rec = [
        "contraindicated", "must not be used", "should not be used",
        "do not use", "do not administer", "is prohibited",
        "is not recommended"
    ]
    risky_kw = [
        "use with caution", "caution", "caution should be exercised",
        "monitor", "reduce dose", "dose reduction", "adjust dose",
        "not recommended", "avoid if possible", "may worsen", "increased risk",
        "use caution", "carefully"
    ]
    suitable_kw = [
        "no dose adjustment", "not necessary to adjust", "considered safe",
        "no special precautions", "well tolerated", "no clinically significant"
    ]
    if any(k in t for k in not_rec):
        return "not-recommended"
    if any(k in t for k in suitable_kw):
        return "suitable"
    if any(k in t for k in risky_kw):
        return "risky"
    # Si se menciona la condición pero sin clasificación clara → precaución
    return "risky"


def _extract_section_for(text: str,
                         keywords: List[str],
                         max_chars: int = 400) -> str:
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
    name = (_first(openfda.get("brand_name"))
            or _first(openfda.get("generic_name"))
            or _first(openfda.get("substance_name")) or "Desconocido")
    generic_name = _first(openfda.get("generic_name")) or name

    # Clase y emoji
    drug_class = _drug_class(openfda)
    emoji = _emoji(drug_class)

    # Dosificación — primera línea del campo
    dosage_raw = _first(raw.get("dosage_and_administration"), 500)
    dosage = (dosage_raw.split('\n')[0]
              or dosage_raw.split('.')[0])[:250].strip()

    # Indicaciones
    uses = (_first(raw.get("indications_and_usage"), 700)
            or _first(raw.get("purpose"), 700)
            or "")

    # Efectos adversos
    side_effects = _extract_side_effects(raw)

    # Contraindicaciones
    restrictions = _extract_contraindications(raw)

    # Cuándo no usar — advertencias
    warnings_text = (_first(raw.get("warnings_and_cautions"), 2000)
                     or _first(raw.get("warnings"), 2000))
    not_for = _split_to_list(warnings_text)[:6] or restrictions[:3]

    # Texto crudo de contraindicaciones (para compat — búsquedas de sección)
    _contra_raw = (_first(raw.get("contraindications"), 2000)
                   or _first(raw.get("do_not_use"), 1000)
                   or "")

    # Fuentes
    sources = [
        {
            "label":
            "OpenFDA",
            "url":
            f"https://api.fda.gov/drug/label.json?search=openfda.generic_name:{generic_name}&limit=1"
        },
        {
            "label":
            "DailyMed",
            "url":
            f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?query={generic_name}"
        },
        {
            "label": "FDA",
            "url": "https://www.fda.gov/drugs"
        },
    ]

    # ── COMPAT — extraído de secciones específicas del label FDA ──
    compat = {}

    # Embarazo
    preg_text = (_first(raw.get("pregnancy"), 600) or _first(
        raw.get("teratogenic_effects"), 600) or _extract_section_for(
            warnings_text, ["pregnant", "pregnancy", "fetal", "teratogen"]))
    if preg_text:
        compat["pregnancy"] = {
            "verdict": _infer_verdict(preg_text),
            "note": preg_text[:350]
        }

    # Pediatría
    ped_text = (_first(raw.get("pediatric_use"), 600) or _extract_section_for(
        warnings_text,
        ["pediatric", "children", "child", "neonates", "infants"]))
    if ped_text:
        compat["child"] = {
            "verdict": _infer_verdict(ped_text),
            "note": ped_text[:350]
        }

    # Geriatría
    ger_text = (_first(raw.get("geriatric_use"), 600) or _extract_section_for(
        warnings_text, ["geriatric", "elderly", "older adults", "aged"]))
    if ger_text:
        compat["elderly"] = {
            "verdict": _infer_verdict(ger_text),
            "note": ger_text[:350]
        }

    # Insuficiencia renal
    renal_text = (_first(raw.get("renal_impairment"), 600)
                  or _extract_section_for(warnings_text or _contra_raw, [
                      "renal", "kidney", "renal impairment", "renal failure"
                  ]))
    if renal_text:
        compat["renal"] = {
            "verdict": _infer_verdict(renal_text),
            "note": renal_text[:350]
        }

    # Insuficiencia hepática
    hep_text = (_first(raw.get("hepatic_impairment"), 600)
                or _extract_section_for(warnings_text or _contra_raw, [
                    "hepatic", "liver", "hepatic impairment", "hepatic failure"
                ]))
    if hep_text:
        compat["hepatic"] = {
            "verdict": _infer_verdict(hep_text),
            "note": hep_text[:350]
        }

    # Gastrointestinal
    gi_text = _extract_section_for(warnings_text or _contra_raw, [
        "gastrointestinal", "gastric", "stomach", "ulcer", "GI bleeding",
        "peptic"
    ])
    if gi_text:
        compat["gastric"] = {
            "verdict": _infer_verdict(gi_text),
            "note": gi_text[:350]
        }

    # Alergia a AINEs (para NSAIDs)
    nsaid_text = _extract_section_for(
        _contra_raw or warnings_text,
        ["aspirin", "nsaid", "nonsteroidal", "hypersensitivity", "allergic"])
    if nsaid_text:
        compat["allergy_nsaid"] = {
            "verdict": _infer_verdict(nsaid_text),
            "note": nsaid_text[:350]
        }

    compat["alternatives"] = []

    return {
        "name": name,
        "class": drug_class,
        "emoji": emoji,
        "dosage": dosage or "",
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
        "pregnant":
        bool(
            re.search(
                r"embara|gestaci|pregnant|primer trimestre|segundo trimestre|tercer trimestre",
                t)),
        "trimester3":
        bool(re.search(r"tercer trimestre|3.*trimestre|trimestre.*3", t)),
        "child":
        bool(
            re.search(
                r"niñ|infant|bebé|bebe|pediatr|[0-9]+\s*mes|años.*([0-9]|1[0-5])\b|\b([0-9]|1[0-5])\s*años",
                t)),
        "elderly":
        bool(
            re.search(
                r"ancian|mayor.*65|65.*años|[7-9][0-9]\s*años|vejez|geriatr",
                t)),
        "allergy_nsaid":
        bool(
            re.search(
                r"alergi.*aine|alergi.*ibuprofen|alergi.*aspirina|alergi.*nsaid|hipersensib.*aine",
                t)),
        "allergy_penicillin":
        bool(re.search(r"alergi.*penicil|alergi.*amoxicil|alergi.*betalact",
                       t)),
        "gastric":
        bool(
            re.search(
                r"gastritis|úlcera|ulcera|reflujo|erge|estómago|estomago|dispepsia|gástrico|gastr",
                t)),
        "renal":
        bool(
            re.search(
                r"renal|riñón|riñon|insuficiencia.*renal|dialisis|diálisis",
                t)),
        "hepatic":
        bool(
            re.search(
                r"hepatic|hígado|higado|cirrosis|hepatitis|insuficiencia.*hepática",
                t)),
        "cardiac":
        bool(
            re.search(
                r"cardíac|cardiaco|cardiac|corazón|corazon|arritmia|taquicardia|hipertens",
                t)),
        "diabetic":
        bool(re.search(r"diabet|glucosa|insulin|glucem", t)),
    }


def analyze_compat(med: dict, patient_text: str, symptom_text: str) -> dict:
    p = parse_patient(patient_text + " " + symptom_text)
    c = med.get("compat", {})
    flags = []

    mapping = [
        (p["pregnant"], "pregnancy", "Embarazo"),
        (p["trimester3"]
         and not p["pregnant"], "pregnancy", "Tercer trimestre"),
        (p["allergy_nsaid"], "allergy_nsaid", "Alergia a AINEs"),
        (p["gastric"], "gastric", "Patología gástrica"),
        (p["renal"], "renal", "Insuficiencia renal"),
        (p["hepatic"], "hepatic", "Hepatopatía"),
        (p["child"], "child", "Paciente pediátrico"),
        (p["elderly"], "elderly", "Paciente anciano"),
    ]

    for condition, key, label in mapping:
        if condition and key in c:
            flags.append({"key": key, "label": label, **c[key]})

    # Alergia a penicilinas (caso especial)
    if p["allergy_penicillin"] and "penicillin" in med.get("class",
                                                           "").lower():
        flags.append({
            "key":
            "allergy_pen",
            "label":
            "Alergia a penicilinas",
            "verdict":
            "not-recommended",
            "note":
            "Contraindicada en pacientes con alergia a penicilinas. Riesgo de anafilaxia."
        })

    verdict = "suitable"
    if any(f["verdict"] == "not-recommended" for f in flags):
        verdict = "not-recommended"
    elif any(f["verdict"] == "risky" for f in flags):
        verdict = "risky"

    return {
        "verdict": verdict,
        "flags": flags,
        "alternatives": c.get("alternatives", [])
    }


def suitability_text(med: dict, patient_text: str) -> dict:
    t = patient_text.lower()
    uses_lower = med.get("uses", "").lower()

    cond_map = {
        "dolor": ["dolor", "pain", "cefalea", "headache", "muscular"],
        "fiebre": ["fiebre", "fever", "temperatura"],
        "infección": [
            "infección", "infeccion", "bacteria", "amigdal", "faringit",
            "sinusit", "otitis", "neumonia"
        ],
        "diabetes": ["diabet", "glucosa", "azúcar", "azucar"],
        "gastritis":
        ["gastrit", "reflujo", "úlcera", "ulcera", "estomago", "gástrico"],
        "inflamación": ["inflamac", "artritis", "lumbal", "rodilla"],
    }

    matched = [
        c for c, kws in cond_map.items()
        if any(k in t for k in kws) and c.split("/")[0] in uses_lower
    ]

    if matched:
        return {
            "match":
            True,
            "text":
            f"{med['name']} está indicado para {', '.join(matched)}, lo cual corresponde con la información del paciente proporcionada."
        }
    return {
        "match":
        None,
        "text":
        f"{med['name']} se usa principalmente para: {med['uses'].split('.')[0][:200]}."
    }


def build_explanation(verdict: str, med_name: str, suit_text: str) -> str:
    if verdict == "suitable":
        return (
            f"Basándonos en la información disponible (OpenFDA), {med_name} parece adecuado para este caso. "
            f"{suit_text} No se han identificado contraindicaciones absolutas con las condiciones descritas. "
            "Confirmar siempre con el médico tratante.")
    if verdict == "risky":
        return (
            f"{med_name} puede ser útil para la condición descrita, pero existen factores de riesgo que requieren precaución. "
            f"{suit_text} Se recomienda supervisión médica y posible ajuste de dosis."
        )
    if verdict == "not-recommended":
        return (
            f"Existe al menos una contraindicación relevante para usar {med_name} en este paciente según la ficha FDA. "
            f"{suit_text} Se recomienda buscar alternativas y consultar con el médico."
        )
    return (
        f"Información insuficiente para evaluar completamente {med_name} en este caso. "
        "Consultar con un profesional sanitario.")


# ─────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────


@app.get("/api/drugs/search")
async def search_drug(query: str = Query(..., min_length=1), lang: str = Query("es")):
    """
    Busca un medicamento y devuelve su ficha estructurada.
    - lang=es: CIMA (AEMPS) como fuente primaria; OpenFDA para compat.
    - lang=fr/it/de/pt/ca/no/ro: OpenFDA + deep-translator al idioma correspondiente.
    - lang=en: sólo OpenFDA, sin traducción.
    """
    # ── OPTIMIZACIÓN 1: caché ─────────────────────────────────────────────────
    # Se cachea todo EXCEPTO el funFact de Gemini (siempre se recalcula).
    _ck = f"{query.lower().strip()}_{lang}"
    cached = _cache_get(_ck)
    if cached is not None:
        drug_cached = {**cached["drug"]}
        drug_cached = await enrich_drug_data(drug_cached, lang)
        return {"found": cached["found"], "drug": drug_cached}
    # ─────────────────────────────────────────────────────────────────────────

    if lang == "es":
        # ── OPTIMIZACIÓN 3: OpenFDA + CIMA completo en paralelo ───────────────
        raw, (cima_meta, ficha_pre) = await asyncio.gather(
            fetch_openfda_raw(query),
            _fetch_cima_full(query),
        )
    else:
        raw = await fetch_openfda_raw(query)
        cima_meta = None
        ficha_pre = {}

    if not raw and not cima_meta:
        return {"found": False, "drug": None}

    if raw:
        drug = openfda_to_drug(raw)
    else:
        drug = {
            "name":         (cima_meta.get("vtm") or cima_meta.get("nombre") or query).title(),
            "class":        "Medicamento",
            "emoji":        "💊",
            "dosage":       "",
            "uses":         "",
            "sideEffects":  [],
            "restrictions": [],
            "notFor":       [],
            "fact":         "",
            "sources":      [],
            "compat":       {},
        }

    if lang != "en":
        # ── 1. Nombre ─────────────────────────────────────────────────────────
        openfda_section = (raw or {}).get("openfda", {})
        generic_fda = (openfda_section.get("generic_name") or [""])[0].lower().strip()
        loc_names = LOCALIZED_NAMES.get(lang, SPANISH_NAMES if lang == "es" else {})

        if lang == "es" and cima_meta:
            vtm = cima_meta.get("vtm", "")
            drug["name"] = vtm.title() if vtm else cima_meta.get("nombre", drug["name"]).title()
        elif generic_fda in loc_names:
            drug["name"] = loc_names[generic_fda]
        else:
            # Fallback 1: substance_name (OTC products a veces no tienen generic_name)
            sub_fda = (openfda_section.get("substance_name") or [""])[0].lower().strip()
            if sub_fda and sub_fda in loc_names:
                drug["name"] = loc_names[sub_fda]
            else:
                # Fallback 2: query → NAME_TRANSLATIONS → loc_names
                q_lower = query.lower().strip()
                fda_name = NAME_TRANSLATIONS.get(q_lower)
                if fda_name and fda_name in loc_names:
                    drug["name"] = loc_names[fda_name]
                elif lang == "es" and q_lower in NAME_TRANSLATIONS:
                    drug["name"] = query.strip().title()

        # ── 2. Clase farmacológica ─────────────────────────────────────────────
        drug["class"] = translate_class(drug["class"], lang)

        # ── 3. Contenido clínico ───────────────────────────────────────────────
        # ficha_pre ya fue obtenida en paralelo con OpenFDA (OPTIMIZACIÓN 3)
        ficha: dict = ficha_pre

        if ficha.get("indicaciones"):
            drug["uses"] = ficha["indicaciones"]
        if ficha.get("posologia"):
            for _line in ficha["posologia"].split('\n'):
                _line = _line.strip()
                if _line and not re.match(r'^\d+\.\d+\.', _line):
                    drug["dosage"] = _line[:250]
                    break
        if ficha.get("contraindicaciones"):
            drug["restrictions"] = _split_to_list(ficha["contraindicaciones"], 6)
            drug["notFor"] = drug["restrictions"][:3]
        if ficha.get("reacciones_adversas"):
            drug["sideEffects"] = _split_to_list(ficha["reacciones_adversas"], 8)

        # ── OPTIMIZACIÓN 2: traducciones en batch ─────────────────────────────
        if _lt_ready and lang not in ("en", "es"):
            # Idiomas no-ES: un solo request a Google Translate para todos los campos
            await _translate_fields_parallel(drug, lang)
        elif _lt_ready and lang == "es":
            # ES: batch solo para campos no cubiertos por CIMA
            _need_uses   = not ficha.get("indicaciones") and bool(drug.get("uses"))
            _need_dosage = not ficha.get("posologia")    and bool(drug.get("dosage"))
            _need_restr  = not ficha.get("contraindicaciones")
            _need_se     = not ficha.get("reacciones_adversas")

            r_list = drug.get("restrictions", []) if _need_restr else []
            n_list = drug.get("notFor", [])       if _need_restr else []
            s_list = drug.get("sideEffects", [])  if _need_se    else []

            all_texts = (
                [drug.get("uses", "") if _need_uses else "",
                 drug.get("dosage", "") if _need_dosage else ""]
                + list(r_list) + list(n_list) + list(s_list)
            )
            non_empty = [(i, t) for i, t in enumerate(all_texts) if t and t.strip()]
            if non_empty:
                combined = _TRANS_SEP.join(t for _, t in non_empty)
                try:
                    translated = await asyncio.to_thread(
                        GoogleTranslator(source="en", target="es").translate, combined
                    )
                    parts = [p.strip() for p in translated.split("[[[|||]]]")]
                    for li, (orig_idx, _) in enumerate(non_empty):
                        if li < len(parts):
                            all_texts[orig_idx] = parts[li]
                except Exception:
                    pass

                if _need_uses:   drug["uses"]   = all_texts[0]
                if _need_dosage: drug["dosage"] = all_texts[1]
                offset = 2
                if _need_restr:
                    drug["restrictions"] = all_texts[offset:offset+len(r_list)]; offset += len(r_list)
                    drug["notFor"]       = all_texts[offset:offset+len(n_list)]; offset += len(n_list)
                if _need_se:
                    drug["sideEffects"]  = all_texts[offset:offset+len(s_list)]
        # ─────────────────────────────────────────────────────────────────────

        # ── 4. Fuente CIMA si fue usada ────────────────────────────────────────
        if cima_meta and cima_meta.get("nregistro"):
            nreg = cima_meta["nregistro"]
            drug["sources"] = [{
                "label": "CIMA AEMPS",
                "url":   f"https://cima.aemps.es/cima/publico/detalle.html?nregistro={nreg}"
            }] + drug.get("sources", [])

    # ── 5. funFact vía Gemini ─────────────────────────────────────────────────
    drug = await enrich_drug_data(drug, lang)

    result = {"found": True, "drug": drug}
    # ── OPTIMIZACIÓN 1: guardar en caché ──────────────────────────────────────
    _cache_set(_ck, result)
    # ─────────────────────────────────────────────────────────────────────────
    return result


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
        if p["pregnant"]:
            risks.append(
                "embarazo (precaución general con cualquier medicamento)")
        if p["child"]:
            risks.append(
                "edad pediátrica (verificar dosis y contraindicaciones específicas)"
            )
        if p["elderly"]:
            risks.append(
                "edad avanzada (mayor sensibilidad a efectos adversos)")
        if p["renal"]:
            risks.append(
                "función renal comprometida (posible ajuste de dosis)")
        if p["hepatic"]:
            risks.append(
                "función hepática comprometida (posible ajuste de dosis)")

        return {
            "found": False,
            "drug_name": req.drug_name,
            "verdict": "risky" if risks else "uncertain",
            "flags": [],
            "generic_risks": risks,
            "alternatives": [],
            "suitability": {
                "match": None,
                "text": f"No se encontró '{req.drug_name}' en OpenFDA."
            },
            "explanation":
            f"No se encontró información sobre '{req.drug_name}' en OpenFDA. Evaluación basada en perfil del paciente.",
            "sources": DEFAULT_SOURCES,
        }

    med = openfda_to_drug(raw)
    compat = analyze_compat(med, req.patient_text, req.symptom_text)
    suit = suitability_text(med, req.patient_text + " " + req.symptom_text)
    explanation = build_explanation(compat["verdict"], med["name"],
                                    suit["text"])

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
async def external_drug_info(query: str = Query(..., min_length=1), lang: str = Query("es")):
    """
    Devuelve el resultado crudo de OpenFDA para inspección/debug.
    """
    raw = await fetch_openfda_raw(query)
    if not raw:
        return {"found": False, "source": "OpenFDA"}
    openfda = raw.get("openfda", {})

    def tr(text: str) -> str:
        return translate_text(text, lang) if lang != "en" else text

    return {
        "found":        True,
        "source":       "OpenFDA",
        "brand_name":   _first(openfda.get("brand_name")),
        "generic_name": _first(openfda.get("generic_name")),
        "manufacturer": _first(openfda.get("manufacturer_name")),
        "route":        _first(openfda.get("route")),
        "product_type": _first(openfda.get("product_type")),
        "pharm_class":  _first(openfda.get("pharm_class_epc")),
        "indications":       tr(_first(raw.get("indications_and_usage"), 600)),
        "warnings":          tr(_first(raw.get("warnings") or raw.get("warnings_and_cautions"), 600)),
        "dosage_forms":      tr(_first(raw.get("dosage_and_administration"), 400)),
        "contraindications": tr(_first(raw.get("contraindications"), 600)),
        "adverse_reactions": tr(_first(raw.get("adverse_reactions"), 600)),
        "pregnancy":         tr(_first(raw.get("pregnancy"), 400)),
        "pediatric_use":     tr(_first(raw.get("pediatric_use"), 400)),
        "geriatric_use":     tr(_first(raw.get("geriatric_use"), 400)),
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
    lang_instruction = (
        "Analiza y responde COMPLETAMENTE EN ESPAÑOL."
        if req.lang == "es" else
        "Analyze and respond COMPLETELY IN ENGLISH."
    )

    prompt = f"""You are an expert clinical pharmaceutical analysis system.
Analyze the compatibility of the following medication with the patient profile and generate a detailed medical report.

{drug_context}

Patient information:
{req.patient_text or 'Not specified.'}

Symptoms / reason for consultation:
{req.symptom_text or req.drug_name}

{lang_instruction}"""

    # Schema JSON que Gemini debe respetar estrictamente
    response_schema = {
        "type":
        "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["suitable", "risky", "not-recommended", "uncertain"],
                "description": "Veredicto global de compatibilidad"
            },
            "resumen": {
                "type":
                "string",
                "description":
                "Frase corta que resume la evaluación (máx 120 caracteres)"
            },
            "indicado_para": {
                "type":
                "string",
                "description":
                "Si el medicamento es adecuado para los síntomas descritos (1-2 frases)"
            },
            "factores_riesgo": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "factor": {
                            "type": "string",
                            "description": "Nombre del factor de riesgo"
                        },
                        "nivel": {
                            "type": "string",
                            "enum": ["alto", "medio", "bajo"]
                        },
                        "explicacion": {
                            "type": "string",
                            "description": "Explicación clínica breve"
                        }
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
                "items": {
                    "type": "string"
                },
                "description": "Lista de recomendaciones para el paciente"
            },
            "alternativas": {
                "type":
                "array",
                "items": {
                    "type": "string"
                },
                "description":
                "Medicamentos alternativos si el veredicto es risky o not-recommended"
            },
            "advertencia_critica": {
                "type":
                "string",
                "description":
                "Contraindicación absoluta crítica si existe, cadena vacía si no hay"
            }
        },
        "required": [
            "verdict", "resumen", "indicado_para", "factores_riesgo",
            "explicacion_general", "recomendaciones", "alternativas",
            "advertencia_critica"
        ]
    }

    # 3. Llamar a Gemini con JSON Schema nativo
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(GEMINI_URL,
                                     headers={
                                         "X-goog-api-key": GEMINI_KEY,
                                         "Content-Type": "application/json"
                                     },
                                     json={
                                         "contents": [{
                                             "parts": [{
                                                 "text": prompt
                                             }]
                                         }],
                                         "generationConfig": {
                                             "temperature": 0.2,
                                             "maxOutputTokens": 7500,
                                             "responseMimeType":
                                             "application/json",
                                             "responseJsonSchema":
                                             response_schema
                                         }
                                     })
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e!r}"}

    if resp.status_code != 200:
        return {
            "error": f"Gemini respondió con status {resp.status_code}",
            "detail": resp.text[:300]
        }

    try:
        gemini_text = resp.json(
        )["candidates"][0]["content"]["parts"][0]["text"]
        report = json.loads(gemini_text)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        return {
            "error": f"Error procesando respuesta de Gemini: {str(e)}",
            "detail": resp.text[:300]
        }

    report["drug_name"] = drug_name_display
    report["sources"] = med["sources"] if raw else DEFAULT_SOURCES
    return report

@app.get("/api")
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
        ]
    }

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if _FRONTEND_DIR.exists():
    app.mount("/",
              StaticFiles(directory=str(_FRONTEND_DIR), html=True),
              name="frontend")

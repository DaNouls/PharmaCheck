"""
PharmaCheck — Backend (FastAPI) v2.0
Fuente principal de datos: OpenFDA Drug Label API
https://open.fda.gov/apis/drug/label/
"""

import os
import re
import json
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
# TRADUCCIÓN — stub ligero (sin dependencias pesadas)
# ─────────────────────────────────────────

_lt_ready = False


def _init_libretranslate():
    print("[Translate] Traducción local desactivada — se devuelve texto original.")


def translate_en_es(text: str) -> str:
    """Devuelve el texto sin traducir (stub ligero)."""
    return text


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
    # Intentar separar por bullets, guiones, números de lista o doble salto
    items = re.split(r'\n\s*[\u2022\-\*•]\s*|\n\s*\d+[\.\)]\s*|\n{2,}', text)
    items = [
        i.strip().rstrip('.').rstrip(',') for i in items if len(i.strip()) > 12
    ]
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

    # Efectos adversos — lista vacía si no hay datos (el frontend pone el fallback traducido)
    adverse_text = _first(raw.get("adverse_reactions"), 2000)
    side_effects = _split_to_list(adverse_text)

    # Contraindicaciones — lista vacía si no hay datos (el frontend pone el fallback traducido)
    contra_text = _first(raw.get("contraindications"), 2000)
    restrictions = _split_to_list(contra_text)

    # Cuándo no usar — advertencias
    warnings_text = (_first(raw.get("warnings_and_cautions"), 2000)
                     or _first(raw.get("warnings"), 2000))
    not_for = _split_to_list(warnings_text)[:6] or restrictions[:3]

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
                  or _extract_section_for(warnings_text or contra_text, [
                      "renal", "kidney", "renal impairment", "renal failure"
                  ]))
    if renal_text:
        compat["renal"] = {
            "verdict": _infer_verdict(renal_text),
            "note": renal_text[:350]
        }

    # Insuficiencia hepática
    hep_text = (_first(raw.get("hepatic_impairment"), 600)
                or _extract_section_for(warnings_text or contra_text, [
                    "hepatic", "liver", "hepatic impairment", "hepatic failure"
                ]))
    if hep_text:
        compat["hepatic"] = {
            "verdict": _infer_verdict(hep_text),
            "note": hep_text[:350]
        }

    # Gastrointestinal
    gi_text = _extract_section_for(warnings_text or contra_text, [
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
        contra_text or warnings_text,
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
    Busca un medicamento en OpenFDA y devuelve su ficha estructurada.
    - Nombre y clase se traducen con diccionarios estáticos (siempre fiable).
    - uses/dosage y funFact se enriquecen con Gemini cuando está disponible.
    """
    raw = await fetch_openfda_raw(query)
    if not raw:
        return {"found": False, "drug": None}

    drug = openfda_to_drug(raw)

    if lang == "es":
        # 1. Nombre: diccionario estático
        openfda_section = raw.get("openfda", {})
        generic_fda = (openfda_section.get("generic_name") or [""])[0].lower().strip()
        if generic_fda in SPANISH_NAMES:
            drug["name"] = SPANISH_NAMES[generic_fda]
        elif query.lower().strip() in NAME_TRANSLATIONS:
            drug["name"] = query.strip().title()

        # 2. Clase farmacológica: diccionario estático
        drug["class"] = translate_class_to_es(drug["class"])

        # 3. uses / dosage / sideEffects / restrictions / notFor: LibreTranslate local
        if _lt_ready:
            if drug.get("uses"):
                drug["uses"] = translate_en_es(drug["uses"])
            if drug.get("dosage"):
                drug["dosage"] = translate_en_es(drug["dosage"])
            drug["sideEffects"]  = [translate_en_es(e) for e in drug.get("sideEffects", [])]
            drug["restrictions"] = [translate_en_es(e) for e in drug.get("restrictions", [])]
            drug["notFor"]       = [translate_en_es(e) for e in drug.get("notFor", [])]

    # 4. funFact vía Gemini (opcional, falla silenciosamente)
    drug = await enrich_drug_data(drug, lang)

    return {"found": True, "drug": drug}


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
        return translate_en_es(text) if lang == "es" else text

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

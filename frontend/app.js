/**
 * PharmaCheck — Frontend
 * Toda la lógica de datos y análisis vive en el backend (Python/FastAPI).
 * Este archivo solo maneja UI, rendering y llamadas a la API.
 */

const API_BASE = '';
const AI_DAILY_LIMIT = 20;

let compatMode = false;
let currentLang = localStorage.getItem('pharma_lang') || 'es';

// ─────────────────────────────────────────
// THEME
// ─────────────────────────────────────────

let currentTheme = localStorage.getItem('pharma_theme') || 'light';

function applyTheme() {
  document.documentElement.setAttribute('data-theme', currentTheme);
  const btn = document.getElementById('theme-btn');
  if (btn) btn.textContent = currentTheme === 'dark' ? '🌙' : '☀️';
}

function toggleTheme() {
  currentTheme = currentTheme === 'light' ? 'dark' : 'light';
  localStorage.setItem('pharma_theme', currentTheme);
  applyTheme();
}

applyTheme();

// ─────────────────────────────────────────
// I18N
// ─────────────────────────────────────────

const i18n = {
  es: {
    hero_title:       'Evaluación de medicamentos',
    hero_sub:         'Consulta la ficha técnica de cualquier fármaco o analiza su compatibilidad con un paciente en segundos.',
    label_med:        '💊 Medicamento',
    ph_med:           'Nombre del medicamento',
    label_patient:    '🧑‍⚕️ Información del paciente',
    ph_patient:       'síntomas, condiciones, edad, embarazo, alergias…',
    toggle_label:     'Concordancia',
    btn_sheet:        'Ficha de medicamento',
    btn_compat:       'Análisis de concordancia',
    btn_back_sheet:   '← Otro medicamento',
    btn_back_compat:  '← Otro caso',
    err_empty:        'Por favor ingresa el nombre de un medicamento.',
    err_server:       '⚠️ No se pudo conectar con el servidor. Verifica que el backend esté corriendo.',
    loading_sheet:    'Consultando base de datos médica…',
    loading_compat:   'Generando informe con Gemini AI…',
    v_suitable:       'Adecuado',
    v_risky:          'Potencialmente arriesgado',
    v_not_rec:        'No recomendado',
    v_uncertain:      'Incierto',
    sources_label:    '📚 Fuentes:',
    ext_title:        '🌐 Datos OpenFDA (oficial)',
    ext_brand:        'Nombre comercial:',
    ext_generic:      'Nombre genérico:',
    ext_manufacturer: 'Fabricante:',
    ext_route:        'Vía:',
    ext_indications:  'Indicaciones (FDA):',
    ext_warnings:     'Advertencias (FDA):',
    s_uses:           '🎯 Para qué se usa',
    s_effects:        '⚠️ Efectos secundarios',
    s_when_not:       '🚫 Cuándo NO usar',
    s_restrictions:   '⚙️ Restricciones',
    s_official_info:  'Informaciones oficiales',
    s_fun_fact:       '💡 Dato curioso:',
    unknown_class:    'Medicamento — clase no identificada',
    unknown_dosage:   'Consultar prospecto o profesional sanitario',
    unknown_section:  'ℹ️ Información no disponible',
    unknown_body:     'no ha sido reconocido en la base de datos local. Consulta las fuentes oficiales para información precisa.',
    gemini_ai_title:  'Análisis IA:',
    gemini_badge:     '✨ Gemini AI',
    gemini_sub:       'Informe generado por inteligencia artificial · Solo orientativo',
    gemini_summary:   '📋 Resumen',
    gemini_suit:      '🎯 Idoneidad para la condición',
    gemini_risks:     '🛡️ Factores de riesgo identificados',
    gemini_eval:      '📄 Evaluación clínica',
    gemini_recs:      '✅ Recomendaciones',
    gemini_alts:      '🔄 Alternativas posibles',
    no_side_effects:  'No se han identificado efectos secundarios relevantes.',
    no_restrictions:  'No se han identificado contraindicaciones relevantes.',
    consult_leaflet:  'Consultar el prospecto oficial para información completa.',
    gemini_no_risks:  'No se identificaron factores de riesgo específicos para este paciente.',
    gemini_def_recs:  'Seguir las indicaciones del prospecto oficial.',
    gemini_err_title:    'Error de Gemini',
    gemini_overloaded:   '⚠️ Error 503: Gemini está sobrecargado, inténtalo en otro momento.',
    gemini_retrying:     '🔄 Gemini tardando, reintentando…',
    risk_alto:        'ALTO',
    risk_medio:       'MEDIO',
    risk_bajo:        'BAJO',
    compat_title:     'Análisis de concordancia:',
    compat_sub:       'Evaluación para el perfil de paciente descrito',
    compat_suit:      '🎯 Idoneidad para la condición',
    compat_safety:    '🛡️ Seguridad para el paciente',
    compat_expl:      '📋 Explicación',
    compat_alts:      '🔄 Alternativas posibles',
    compat_alts_desc: 'Las siguientes alternativas podrían ser más adecuadas. Haz clic para ver su ficha.',
    compat_no_risks:  'No se identificaron factores de riesgo específicos en la información del paciente.',
    compat_gen_risks: 'Factores de riesgo generales identificados:',
    ai_label:         '✨ IA',
  },
  en: {
    hero_title:       'Drug Evaluation',
    hero_sub:         'Look up any drug information sheet or analyze its compatibility with a patient profile in seconds.',
    label_med:        '💊 Medication',
    ph_med:           'Medication name',
    label_patient:    '🧑‍⚕️ Patient information',
    ph_patient:       'symptoms, conditions, age, pregnancy, allergies…',
    toggle_label:     'Compatibility',
    btn_sheet:        'Drug sheet',
    btn_compat:       'Compatibility analysis',
    btn_back_sheet:   '← Another medication',
    btn_back_compat:  '← Another case',
    err_empty:        'Please enter a medication name.',
    err_server:       '⚠️ Could not connect to the server. Make sure the backend is running.',
    loading_sheet:    'Querying medical database…',
    loading_compat:   'Generating AI report with Gemini…',
    v_suitable:       'Suitable',
    v_risky:          'Potentially risky',
    v_not_rec:        'Not recommended',
    v_uncertain:      'Uncertain',
    sources_label:    '📚 Sources:',
    ext_title:        '🌐 OpenFDA Data (official)',
    ext_brand:        'Brand name:',
    ext_generic:      'Generic name:',
    ext_manufacturer: 'Manufacturer:',
    ext_route:        'Route:',
    ext_indications:  'Indications (FDA):',
    ext_warnings:     'Warnings (FDA):',
    s_uses:           '🎯 What it is used for',
    s_effects:        '⚠️ Side effects',
    s_when_not:       '🚫 When NOT to use',
    s_restrictions:   '⚙️ Restrictions',
    s_official_info:  'Official information',
    s_fun_fact:       '💡 Fun fact:',
    unknown_class:    'Medication — unidentified class',
    unknown_dosage:   'Consult the leaflet or a healthcare professional',
    unknown_section:  'ℹ️ Information not available',
    unknown_body:     'was not recognized in the database. Consult official sources for accurate information.',
    gemini_ai_title:  'AI Analysis:',
    gemini_badge:     '✨ Gemini AI',
    gemini_sub:       'Report generated by artificial intelligence · For guidance only',
    gemini_summary:   '📋 Summary',
    gemini_suit:      '🎯 Suitability for the condition',
    gemini_risks:     '🛡️ Identified risk factors',
    gemini_eval:      '📄 Clinical evaluation',
    gemini_recs:      '✅ Recommendations',
    gemini_alts:      '🔄 Possible alternatives',
    no_side_effects:  'No relevant side effects have been identified.',
    no_restrictions:  'No relevant contraindications have been identified.',
    consult_leaflet:  'Consult the official leaflet for complete information.',
    gemini_no_risks:  'No specific risk factors identified for this patient.',
    gemini_def_recs:  'Follow the instructions in the official leaflet.',
    gemini_err_title:  'Gemini Error',
    gemini_overloaded: '⚠️ Error 503: Gemini is overloaded, please try again later.',
    gemini_retrying:   '🔄 Gemini taking long, retrying…',
    risk_alto:        'HIGH',
    risk_medio:       'MEDIUM',
    risk_bajo:        'LOW',
    compat_title:     'Compatibility analysis:',
    compat_sub:       'Evaluation for the described patient profile',
    compat_suit:      '🎯 Suitability for the condition',
    compat_safety:    '🛡️ Patient safety',
    compat_expl:      '📋 Explanation',
    compat_alts:      '🔄 Possible alternatives',
    compat_alts_desc: 'The following alternatives might be more suitable. Click to view their sheet.',
    compat_no_risks:  'No specific risk factors identified in the patient information.',
    compat_gen_risks: 'General risk factors identified:',
    ai_label:         '✨ AI',
  },
  fr: {
    hero_title:       'Évaluation des médicaments',
    hero_sub:         'Consultez la fiche technique de tout médicament ou analysez sa compatibilité avec un patient en quelques secondes.',
    label_med:        '💊 Médicament',
    ph_med:           'Nom du médicament',
    label_patient:    '🧑‍⚕️ Informations du patient',
    ph_patient:       'symptômes, conditions, âge, grossesse, allergies…',
    toggle_label:     'Compatibilité',
    btn_sheet:        'Fiche médicament',
    btn_compat:       'Analyse de compatibilité',
    btn_back_sheet:   '← Autre médicament',
    btn_back_compat:  '← Autre cas',
    err_empty:        "Veuillez saisir le nom d'un médicament.",
    err_server:       '⚠️ Impossible de se connecter au serveur.',
    loading_sheet:    'Consultation de la base de données médicale…',
    loading_compat:   'Génération du rapport avec Gemini AI…',
    v_suitable:       'Approprié',
    v_risky:          'Potentiellement risqué',
    v_not_rec:        'Déconseillé',
    v_uncertain:      'Incertain',
    sources_label:    '📚 Sources :',
    ext_title:        '🌐 Données OpenFDA (officielles)',
    ext_brand:        'Nom commercial :',
    ext_generic:      'Nom générique :',
    ext_manufacturer: 'Fabricant :',
    ext_route:        'Voie :',
    ext_indications:  'Indications (FDA) :',
    ext_warnings:     'Mises en garde (FDA) :',
    s_uses:           '🎯 Indications thérapeutiques',
    s_effects:        '⚠️ Effets secondaires',
    s_when_not:       '🚫 Quand NE PAS utiliser',
    s_restrictions:   '⚙️ Restrictions',
    s_official_info:  'Informations officielles',
    s_fun_fact:       '💡 Le saviez-vous ?',
    unknown_class:    'Médicament — classe non identifiée',
    unknown_dosage:   'Consulter la notice ou un professionnel de santé',
    unknown_section:  'ℹ️ Information non disponible',
    unknown_body:     "n'a pas été reconnu dans la base de données. Consultez les sources officielles.",
    gemini_ai_title:  'Analyse IA :',
    gemini_badge:     '✨ Gemini AI',
    gemini_sub:       'Rapport généré par intelligence artificielle · À titre indicatif seulement',
    gemini_summary:   '📋 Résumé',
    gemini_suit:      '🎯 Adéquation pour la condition',
    gemini_risks:     '🛡️ Facteurs de risque identifiés',
    gemini_eval:      '📄 Évaluation clinique',
    gemini_recs:      '✅ Recommandations',
    gemini_alts:      '🔄 Alternatives possibles',
    no_side_effects:  'Aucun effet secondaire significatif identifié.',
    no_restrictions:  'Aucune contre-indication significative identifiée.',
    consult_leaflet:  'Consulter la notice officielle pour des informations complètes.',
    gemini_no_risks:  'Aucun facteur de risque spécifique identifié pour ce patient.',
    gemini_def_recs:  'Suivre les instructions de la notice officielle.',
    gemini_err_title:  'Erreur Gemini',
    gemini_overloaded: '⚠️ Erreur 503 : Gemini est surchargé, veuillez réessayer plus tard.',
    gemini_retrying:   '🔄 Gemini tarde, nouvelle tentative…',
    risk_alto:        'ÉLEVÉ',
    risk_medio:       'MOYEN',
    risk_bajo:        'FAIBLE',
    compat_title:     'Analyse de compatibilité :',
    compat_sub:       'Évaluation pour le profil patient décrit',
    compat_suit:      '🎯 Adéquation pour la condition',
    compat_safety:    '🛡️ Sécurité du patient',
    compat_expl:      '📋 Explication',
    compat_alts:      '🔄 Alternatives possibles',
    compat_alts_desc: 'Les alternatives suivantes pourraient être plus adaptées. Cliquez pour voir leur fiche.',
    compat_no_risks:  'Aucun facteur de risque spécifique identifié.',
    compat_gen_risks: 'Facteurs de risque généraux identifiés :',
    ai_label:         '✨ IA',
  },
  it: {
    hero_title:       'Valutazione dei farmaci',
    hero_sub:         'Consulta la scheda tecnica di qualsiasi farmaco o analizza la sua compatibilità con un paziente in pochi secondi.',
    label_med:        '💊 Farmaco',
    ph_med:           'Nome del farmaco',
    label_patient:    '🧑‍⚕️ Informazioni del paziente',
    ph_patient:       'sintomi, condizioni, età, gravidanza, allergie…',
    toggle_label:     'Compatibilità',
    btn_sheet:        'Scheda farmaco',
    btn_compat:       'Analisi di compatibilità',
    btn_back_sheet:   '← Altro farmaco',
    btn_back_compat:  '← Altro caso',
    err_empty:        'Inserire il nome di un farmaco.',
    err_server:       '⚠️ Impossibile connettersi al server.',
    loading_sheet:    'Consultazione della banca dati medica…',
    loading_compat:   'Generazione del report con Gemini AI…',
    v_suitable:       'Adatto',
    v_risky:          'Potenzialmente rischioso',
    v_not_rec:        'Non raccomandato',
    v_uncertain:      'Incerto',
    sources_label:    '📚 Fonti:',
    ext_title:        '🌐 Dati OpenFDA (ufficiali)',
    ext_brand:        'Nome commerciale:',
    ext_generic:      'Nome generico:',
    ext_manufacturer: 'Produttore:',
    ext_route:        'Via:',
    ext_indications:  'Indicazioni (FDA):',
    ext_warnings:     'Avvertenze (FDA):',
    s_uses:           '🎯 A cosa serve',
    s_effects:        '⚠️ Effetti indesiderati',
    s_when_not:       '🚫 Quando NON usare',
    s_restrictions:   '⚙️ Restrizioni',
    s_official_info:  'Informazioni ufficiali',
    s_fun_fact:       '💡 Lo sapevi?',
    unknown_class:    'Farmaco — classe non identificata',
    unknown_dosage:   'Consultare il foglietto illustrativo o un professionista sanitario',
    unknown_section:  'ℹ️ Informazione non disponibile',
    unknown_body:     'non è stato riconosciuto nel database. Consulta le fonti ufficiali.',
    gemini_ai_title:  'Analisi IA:',
    gemini_badge:     '✨ Gemini AI',
    gemini_sub:       'Report generato da intelligenza artificiale · Solo orientativo',
    gemini_summary:   '📋 Riepilogo',
    gemini_suit:      '🎯 Adeguatezza per la condizione',
    gemini_risks:     '🛡️ Fattori di rischio identificati',
    gemini_eval:      '📄 Valutazione clinica',
    gemini_recs:      '✅ Raccomandazioni',
    gemini_alts:      '🔄 Alternative possibili',
    no_side_effects:  'Nessun effetto indesiderato rilevante identificato.',
    no_restrictions:  'Nessuna controindicazione rilevante identificata.',
    consult_leaflet:  'Consultare il foglietto illustrativo ufficiale per informazioni complete.',
    gemini_no_risks:  'Nessun fattore di rischio specifico identificato per questo paziente.',
    gemini_def_recs:  'Seguire le istruzioni del foglietto illustrativo ufficiale.',
    gemini_err_title:  'Errore Gemini',
    gemini_overloaded: '⚠️ Errore 503: Gemini è sovraccarico, riprova più tardi.',
    gemini_retrying:   '🔄 Gemini impiega tempo, nuovo tentativo…',
    risk_alto:        'ALTO',
    risk_medio:       'MEDIO',
    risk_bajo:        'BASSO',
    compat_title:     'Analisi di compatibilità:',
    compat_sub:       'Valutazione per il profilo paziente descritto',
    compat_suit:      '🎯 Adeguatezza per la condizione',
    compat_safety:    '🛡️ Sicurezza del paziente',
    compat_expl:      '📋 Spiegazione',
    compat_alts:      '🔄 Alternative possibili',
    compat_alts_desc: 'Le seguenti alternative potrebbero essere più adatte. Clicca per vedere la scheda.',
    compat_no_risks:  'Nessun fattore di rischio specifico identificato.',
    compat_gen_risks: 'Fattori di rischio generali identificati:',
    ai_label:         '✨ IA',
  },
  de: {
    hero_title:       'Medikamentenbewertung',
    hero_sub:         'Rufen Sie das Datenblatt eines Medikaments ab oder analysieren Sie die Verträglichkeit mit einem Patientenprofil in Sekunden.',
    label_med:        '💊 Medikament',
    ph_med:           'Medikamentenname',
    label_patient:    '🧑‍⚕️ Patienteninformationen',
    ph_patient:       'Symptome, Erkrankungen, Alter, Schwangerschaft, Allergien…',
    toggle_label:     'Verträglichkeit',
    btn_sheet:        'Medikamentenblatt',
    btn_compat:       'Verträglichkeitsanalyse',
    btn_back_sheet:   '← Anderes Medikament',
    btn_back_compat:  '← Anderer Fall',
    err_empty:        'Bitte geben Sie einen Medikamentennamen ein.',
    err_server:       '⚠️ Verbindung zum Server fehlgeschlagen.',
    loading_sheet:    'Medizinische Datenbank wird abgefragt…',
    loading_compat:   'Bericht mit Gemini AI wird erstellt…',
    v_suitable:       'Geeignet',
    v_risky:          'Potenziell riskant',
    v_not_rec:        'Nicht empfohlen',
    v_uncertain:      'Ungewiss',
    sources_label:    '📚 Quellen:',
    ext_title:        '🌐 OpenFDA-Daten (offiziell)',
    ext_brand:        'Handelsname:',
    ext_generic:      'Wirkstoffname:',
    ext_manufacturer: 'Hersteller:',
    ext_route:        'Verabreichungsweg:',
    ext_indications:  'Indikationen (FDA):',
    ext_warnings:     'Warnhinweise (FDA):',
    s_uses:           '🎯 Anwendungsgebiete',
    s_effects:        '⚠️ Nebenwirkungen',
    s_when_not:       '🚫 Wann NICHT anwenden',
    s_restrictions:   '⚙️ Einschränkungen',
    s_official_info:  'Offizielle Informationen',
    s_fun_fact:       '💡 Wussten Sie schon?',
    unknown_class:    'Medikament — Klasse nicht identifiziert',
    unknown_dosage:   'Beipackzettel oder Fachpersonal konsultieren',
    unknown_section:  'ℹ️ Information nicht verfügbar',
    unknown_body:     'wurde nicht in der Datenbank erkannt. Konsultieren Sie offizielle Quellen.',
    gemini_ai_title:  'KI-Analyse:',
    gemini_badge:     '✨ Gemini AI',
    gemini_sub:       'Bericht von künstlicher Intelligenz erstellt · Nur zur Orientierung',
    gemini_summary:   '📋 Zusammenfassung',
    gemini_suit:      '🎯 Eignung für die Erkrankung',
    gemini_risks:     '🛡️ Identifizierte Risikofaktoren',
    gemini_eval:      '📄 Klinische Bewertung',
    gemini_recs:      '✅ Empfehlungen',
    gemini_alts:      '🔄 Mögliche Alternativen',
    no_side_effects:  'Keine relevanten Nebenwirkungen identifiziert.',
    no_restrictions:  'Keine relevanten Kontraindikationen identifiziert.',
    consult_leaflet:  'Beipackzettel für vollständige Informationen konsultieren.',
    gemini_no_risks:  'Keine spezifischen Risikofaktoren für diesen Patienten identifiziert.',
    gemini_def_recs:  'Anweisungen im offiziellen Beipackzettel befolgen.',
    gemini_err_title:  'Gemini-Fehler',
    gemini_overloaded: '⚠️ Fehler 503: Gemini ist überlastet, bitte später erneut versuchen.',
    gemini_retrying:   '🔄 Gemini braucht lange, erneuter Versuch…',
    risk_alto:        'HOCH',
    risk_medio:       'MITTEL',
    risk_bajo:        'NIEDRIG',
    compat_title:     'Verträglichkeitsanalyse:',
    compat_sub:       'Bewertung für das beschriebene Patientenprofil',
    compat_suit:      '🎯 Eignung für die Erkrankung',
    compat_safety:    '🛡️ Patientensicherheit',
    compat_expl:      '📋 Erklärung',
    compat_alts:      '🔄 Mögliche Alternativen',
    compat_alts_desc: 'Die folgenden Alternativen könnten besser geeignet sein. Klicken Sie für das Datenblatt.',
    compat_no_risks:  'Keine spezifischen Risikofaktoren in den Patientendaten identifiziert.',
    compat_gen_risks: 'Allgemeine Risikofaktoren identifiziert:',
    ai_label:         '✨ KI',
  },
  ca: {
    hero_title:       'Avaluació de medicaments',
    hero_sub:         'Consulta la fitxa tècnica de qualsevol fàrmac o analitza la seva compatibilitat amb un pacient en segons.',
    label_med:        '💊 Medicament',
    ph_med:           'Nom del medicament',
    label_patient:    '🧑‍⚕️ Informació del pacient',
    ph_patient:       'símptomes, condicions, edat, embaràs, al·lèrgies…',
    toggle_label:     'Concordança',
    btn_sheet:        'Fitxa del medicament',
    btn_compat:       'Anàlisi de concordança',
    btn_back_sheet:   '← Altre medicament',
    btn_back_compat:  '← Altre cas',
    err_empty:        'Si us plau, introdueix el nom d\'un medicament.',
    err_server:       '⚠️ No s\'ha pogut connectar amb el servidor.',
    loading_sheet:    'Consultant la base de dades mèdica…',
    loading_compat:   'Generant l\'informe amb Gemini AI…',
    v_suitable:       'Adequat',
    v_risky:          'Potencialment arriscat',
    v_not_rec:        'No recomanat',
    v_uncertain:      'Incert',
    sources_label:    '📚 Fonts:',
    ext_title:        '🌐 Dades OpenFDA (oficials)',
    ext_brand:        'Nom comercial:',
    ext_generic:      'Nom genèric:',
    ext_manufacturer: 'Fabricant:',
    ext_route:        'Via:',
    ext_indications:  'Indicacions (FDA):',
    ext_warnings:     'Advertències (FDA):',
    s_uses:           '🎯 Per a què serveix',
    s_effects:        '⚠️ Efectes secundaris',
    s_when_not:       '🚫 Quan NO usar',
    s_restrictions:   '⚙️ Restriccions',
    s_official_info:  'Informació oficial',
    s_fun_fact:       '💡 Sabies que…?',
    unknown_class:    'Medicament — classe no identificada',
    unknown_dosage:   'Consultar el prospecte o un professional sanitari',
    unknown_section:  'ℹ️ Informació no disponible',
    unknown_body:     'no ha estat reconegut a la base de dades. Consulta les fonts oficials.',
    gemini_ai_title:  'Anàlisi IA:',
    gemini_badge:     '✨ Gemini AI',
    gemini_sub:       'Informe generat per intel·ligència artificial · Només orientatiu',
    gemini_summary:   '📋 Resum',
    gemini_suit:      '🎯 Idoneïtat per a la condició',
    gemini_risks:     '🛡️ Factors de risc identificats',
    gemini_eval:      '📄 Avaluació clínica',
    gemini_recs:      '✅ Recomanacions',
    gemini_alts:      '🔄 Alternatives possibles',
    no_side_effects:  'No s\'han identificat efectes secundaris rellevants.',
    no_restrictions:  'No s\'han identificat contraindicacions rellevants.',
    consult_leaflet:  'Consultar el prospecte oficial per a informació completa.',
    gemini_no_risks:  'No s\'han identificat factors de risc específics per a aquest pacient.',
    gemini_def_recs:  'Seguir les indicacions del prospecte oficial.',
    gemini_err_title:  'Error de Gemini',
    gemini_overloaded: '⚠️ Error 503: Gemini està sobrecarregat, torna-ho a intentar més tard.',
    gemini_retrying:   '🔄 Gemini tarda, reintentant…',
    risk_alto:        'ALT',
    risk_medio:       'MITJÀ',
    risk_bajo:        'BAIX',
    compat_title:     'Anàlisi de concordança:',
    compat_sub:       'Avaluació per al perfil de pacient descrit',
    compat_suit:      '🎯 Idoneïtat per a la condició',
    compat_safety:    '🛡️ Seguretat del pacient',
    compat_expl:      '📋 Explicació',
    compat_alts:      '🔄 Alternatives possibles',
    compat_alts_desc: 'Les alternatives següents podrien ser més adequades. Fes clic per veure la fitxa.',
    compat_no_risks:  'No s\'han identificat factors de risc específics en la informació del pacient.',
    compat_gen_risks: 'Factors de risc generals identificats:',
    ai_label:         '✨ IA',
  },
  pt: {
    hero_title:       'Avaliação de medicamentos',
    hero_sub:         'Consulte a ficha técnica de qualquer fármaco ou analise a sua compatibilidade com um paciente em segundos.',
    label_med:        '💊 Medicamento',
    ph_med:           'Nome do medicamento',
    label_patient:    '🧑‍⚕️ Informação do paciente',
    ph_patient:       'sintomas, condições, idade, gravidez, alergias…',
    toggle_label:     'Concordância',
    btn_sheet:        'Ficha do medicamento',
    btn_compat:       'Análise de concordância',
    btn_back_sheet:   '← Outro medicamento',
    btn_back_compat:  '← Outro caso',
    err_empty:        'Por favor, introduza o nome de um medicamento.',
    err_server:       '⚠️ Não foi possível ligar ao servidor.',
    loading_sheet:    'A consultar a base de dados médica…',
    loading_compat:   'A gerar o relatório com Gemini AI…',
    v_suitable:       'Adequado',
    v_risky:          'Potencialmente arriscado',
    v_not_rec:        'Não recomendado',
    v_uncertain:      'Incerto',
    sources_label:    '📚 Fontes:',
    ext_title:        '🌐 Dados OpenFDA (oficiais)',
    ext_brand:        'Nome comercial:',
    ext_generic:      'Nome genérico:',
    ext_manufacturer: 'Fabricante:',
    ext_route:        'Via:',
    ext_indications:  'Indicações (FDA):',
    ext_warnings:     'Advertências (FDA):',
    s_uses:           '🎯 Para que serve',
    s_effects:        '⚠️ Efeitos secundários',
    s_when_not:       '🚫 Quando NÃO usar',
    s_restrictions:   '⚙️ Restrições',
    s_official_info:  'Informação oficial',
    s_fun_fact:       '💡 Sabia que…?',
    unknown_class:    'Medicamento — classe não identificada',
    unknown_dosage:   'Consultar o folheto ou um profissional de saúde',
    unknown_section:  'ℹ️ Informação não disponível',
    unknown_body:     'não foi reconhecido na base de dados. Consulte as fontes oficiais.',
    gemini_ai_title:  'Análise IA:',
    gemini_badge:     '✨ Gemini AI',
    gemini_sub:       'Relatório gerado por inteligência artificial · Apenas orientativo',
    gemini_summary:   '📋 Resumo',
    gemini_suit:      '🎯 Adequação para a condição',
    gemini_risks:     '🛡️ Fatores de risco identificados',
    gemini_eval:      '📄 Avaliação clínica',
    gemini_recs:      '✅ Recomendações',
    gemini_alts:      '🔄 Alternativas possíveis',
    no_side_effects:  'Não foram identificados efeitos secundários relevantes.',
    no_restrictions:  'Não foram identificadas contraindicações relevantes.',
    consult_leaflet:  'Consultar o folheto oficial para informação completa.',
    gemini_no_risks:  'Não foram identificados fatores de risco específicos para este paciente.',
    gemini_def_recs:  'Seguir as indicações do folheto oficial.',
    gemini_err_title:  'Erro Gemini',
    gemini_overloaded: '⚠️ Erro 503: Gemini está sobrecarregado, tente novamente mais tarde.',
    gemini_retrying:   '🔄 Gemini a demorar, a tentar novamente…',
    risk_alto:        'ALTO',
    risk_medio:       'MÉDIO',
    risk_bajo:        'BAIXO',
    compat_title:     'Análise de concordância:',
    compat_sub:       'Avaliação para o perfil de paciente descrito',
    compat_suit:      '🎯 Adequação para a condição',
    compat_safety:    '🛡️ Segurança do paciente',
    compat_expl:      '📋 Explicação',
    compat_alts:      '🔄 Alternativas possíveis',
    compat_alts_desc: 'As alternativas seguintes poderão ser mais adequadas. Clique para ver a ficha.',
    compat_no_risks:  'Não foram identificados fatores de risco específicos na informação do paciente.',
    compat_gen_risks: 'Fatores de risco gerais identificados:',
    ai_label:         '✨ IA',
  },
  no: {
    hero_title:       'Legemiddelvurdering',
    hero_sub:         'Slå opp teknisk informasjon om ethvert legemiddel eller analyser kompatibiliteten med en pasient på sekunder.',
    label_med:        '💊 Legemiddel',
    ph_med:           'Legemiddelnavn',
    label_patient:    '🧑‍⚕️ Pasientinformasjon',
    ph_patient:       'symptomer, tilstander, alder, graviditet, allergier…',
    toggle_label:     'Kompatibilitet',
    btn_sheet:        'Legemiddelark',
    btn_compat:       'Kompatibilitetsanalyse',
    btn_back_sheet:   '← Annet legemiddel',
    btn_back_compat:  '← Annet tilfelle',
    err_empty:        'Vennligst skriv inn et legemiddelnavn.',
    err_server:       '⚠️ Kunne ikke koble til serveren.',
    loading_sheet:    'Spørrer medisinsk database…',
    loading_compat:   'Genererer rapport med Gemini AI…',
    v_suitable:       'Egnet',
    v_risky:          'Potensielt risikabelt',
    v_not_rec:        'Ikke anbefalt',
    v_uncertain:      'Usikkert',
    sources_label:    '📚 Kilder:',
    ext_title:        '🌐 OpenFDA-data (offisielt)',
    ext_brand:        'Handelsnavn:',
    ext_generic:      'Generisk navn:',
    ext_manufacturer: 'Produsent:',
    ext_route:        'Administrasjonsvei:',
    ext_indications:  'Indikasjoner (FDA):',
    ext_warnings:     'Advarsler (FDA):',
    s_uses:           '🎯 Hva det brukes til',
    s_effects:        '⚠️ Bivirkninger',
    s_when_not:       '🚫 Når du IKKE skal bruke det',
    s_restrictions:   '⚙️ Begrensninger',
    s_official_info:  'Offisiell informasjon',
    s_fun_fact:       '💡 Visste du at…?',
    unknown_class:    'Legemiddel — klasse ikke identifisert',
    unknown_dosage:   'Konsulter pakningsvedlegget eller helsepersonell',
    unknown_section:  'ℹ️ Informasjon ikke tilgjengelig',
    unknown_body:     'ble ikke gjenkjent i databasen. Konsulter offisielle kilder.',
    gemini_ai_title:  'KI-analyse:',
    gemini_badge:     '✨ Gemini AI',
    gemini_sub:       'Rapport generert av kunstig intelligens · Kun veiledende',
    gemini_summary:   '📋 Sammendrag',
    gemini_suit:      '🎯 Egnethet for tilstanden',
    gemini_risks:     '🛡️ Identifiserte risikofaktorer',
    gemini_eval:      '📄 Klinisk vurdering',
    gemini_recs:      '✅ Anbefalinger',
    gemini_alts:      '🔄 Mulige alternativer',
    no_side_effects:  'Ingen relevante bivirkninger identifisert.',
    no_restrictions:  'Ingen relevante kontraindikasjoner identifisert.',
    consult_leaflet:  'Se pakningsvedlegget for fullstendig informasjon.',
    gemini_no_risks:  'Ingen spesifikke risikofaktorer identifisert for denne pasienten.',
    gemini_def_recs:  'Følg anvisningene i pakningsvedlegget.',
    gemini_err_title:  'Gemini-feil',
    gemini_overloaded: '⚠️ Feil 503: Gemini er overbelastet, prøv igjen senere.',
    gemini_retrying:   '🔄 Gemini tar lang tid, prøver på nytt…',
    risk_alto:        'HØY',
    risk_medio:       'MIDDELS',
    risk_bajo:        'LAV',
    compat_title:     'Kompatibilitetsanalyse:',
    compat_sub:       'Vurdering for det beskrevne pasientprofilen',
    compat_suit:      '🎯 Egnethet for tilstanden',
    compat_safety:    '🛡️ Pasientsikkerhet',
    compat_expl:      '📋 Forklaring',
    compat_alts:      '🔄 Mulige alternativer',
    compat_alts_desc: 'Følgende alternativer kan være mer egnet. Klikk for å se arket.',
    compat_no_risks:  'Ingen spesifikke risikofaktorer identifisert i pasientinformasjonen.',
    compat_gen_risks: 'Generelle risikofaktorer identifisert:',
    ai_label:         '✨ KI',
  },
  ro: {
    hero_title:       'Evaluarea medicamentelor',
    hero_sub:         'Consultați fișa tehnică a oricărui medicament sau analizați compatibilitatea cu un pacient în câteva secunde.',
    label_med:        '💊 Medicament',
    ph_med:           'Numele medicamentului',
    label_patient:    '🧑‍⚕️ Informații pacient',
    ph_patient:       'simptome, condiții, vârstă, sarcină, alergii…',
    toggle_label:     'Concordanță',
    btn_sheet:        'Fișa medicamentului',
    btn_compat:       'Analiză de concordanță',
    btn_back_sheet:   '← Alt medicament',
    btn_back_compat:  '← Alt caz',
    err_empty:        'Vă rugăm să introduceți numele unui medicament.',
    err_server:       '⚠️ Nu s-a putut conecta la server.',
    loading_sheet:    'Se consultă baza de date medicală…',
    loading_compat:   'Se generează raportul cu Gemini AI…',
    v_suitable:       'Adecvat',
    v_risky:          'Potențial riscant',
    v_not_rec:        'Nerecomandат',
    v_uncertain:      'Incert',
    sources_label:    '📚 Surse:',
    ext_title:        '🌐 Date OpenFDA (oficiale)',
    ext_brand:        'Nume comercial:',
    ext_generic:      'Denumire generică:',
    ext_manufacturer: 'Producător:',
    ext_route:        'Cale de administrare:',
    ext_indications:  'Indicații (FDA):',
    ext_warnings:     'Avertismente (FDA):',
    s_uses:           '🎯 La ce se folosește',
    s_effects:        '⚠️ Efecte secundare',
    s_when_not:       '🚫 Când să NU se folosească',
    s_restrictions:   '⚙️ Restricții',
    s_official_info:  'Informații oficiale',
    s_fun_fact:       '💡 Știați că…?',
    unknown_class:    'Medicament — clasă neidentificată',
    unknown_dosage:   'Consultați prospectul sau un profesionist din domeniul sănătății',
    unknown_section:  'ℹ️ Informație indisponibilă',
    unknown_body:     'nu a fost recunoscut în baza de date. Consultați sursele oficiale.',
    gemini_ai_title:  'Analiză IA:',
    gemini_badge:     '✨ Gemini AI',
    gemini_sub:       'Raport generat de inteligență artificială · Doar orientativ',
    gemini_summary:   '📋 Rezumat',
    gemini_suit:      '🎯 Adecvare pentru condiție',
    gemini_risks:     '🛡️ Factori de risc identificați',
    gemini_eval:      '📄 Evaluare clinică',
    gemini_recs:      '✅ Recomandări',
    gemini_alts:      '🔄 Alternative posibile',
    no_side_effects:  'Nu au fost identificate efecte secundare relevante.',
    no_restrictions:  'Nu au fost identificate contraindicații relevante.',
    consult_leaflet:  'Consultați prospectul oficial pentru informații complete.',
    gemini_no_risks:  'Nu au fost identificați factori de risc specifici pentru acest pacient.',
    gemini_def_recs:  'Urmați instrucțiunile din prospectul oficial.',
    gemini_err_title:  'Eroare Gemini',
    gemini_overloaded: '⚠️ Eroare 503: Gemini este supraîncărcat, încercați mai târziu.',
    gemini_retrying:   '🔄 Gemini întârzie, se reîncearcă…',
    risk_alto:        'RIDICAT',
    risk_medio:       'MEDIU',
    risk_bajo:        'SCĂZUT',
    compat_title:     'Analiză de concordanță:',
    compat_sub:       'Evaluare pentru profilul de pacient descris',
    compat_suit:      '🎯 Adecvare pentru condiție',
    compat_safety:    '🛡️ Siguranța pacientului',
    compat_expl:      '📋 Explicație',
    compat_alts:      '🔄 Alternative posibile',
    compat_alts_desc: 'Alternativele de mai jos ar putea fi mai potrivite. Faceți clic pentru a vedea fișa.',
    compat_no_risks:  'Nu au fost identificați factori de risc specifici în informațiile pacientului.',
    compat_gen_risks: 'Factori de risc generali identificați:',
    ai_label:         '✨ IA',
  },
};

function t(key) {
  return (i18n[currentLang] || i18n.es)[key] || key;
}

function applyLang() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  document.documentElement.lang = currentLang;
  document.querySelectorAll('.lang-option').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.lang === currentLang);
  });
  updateActionBtn();
}

function setLang(lang) {
  currentLang = lang;
  localStorage.setItem('pharma_lang', currentLang);
  applyLang();
}

function updateActionBtn() {
  const actionBtn = document.getElementById('action-btn');
  if (!actionBtn) return;
  if (compatMode) {
    actionBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg> ${t('btn_compat')}`;
  } else {
    actionBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/></svg> ${t('btn_sheet')}`;
  }
}

// ─────────────────────────────────────────
// AI USAGE COUNTER
// ─────────────────────────────────────────

function getAiUsage() {
  const today = new Date().toISOString().slice(0, 10);
  const stored = JSON.parse(localStorage.getItem('ai_usage') || '{}');
  if (stored.date !== today) return { date: today, used: 0 };
  return stored;
}

function incrementAiUsage() {
  const usage = getAiUsage();
  usage.used = Math.min(usage.used + 1, AI_DAILY_LIMIT);
  localStorage.setItem('ai_usage', JSON.stringify(usage));
  renderAiCounter();
}

function renderAiCounter() {
  const { used } = getAiUsage();
  const remaining = AI_DAILY_LIMIT - used;
  const pct = (remaining / AI_DAILY_LIMIT) * 100;

  document.getElementById('ai-count').textContent = remaining;
  document.getElementById('ai-bar-fill').style.width = pct + '%';

  const el = document.getElementById('ai-counter');
  el.classList.remove('low', 'empty');
  if (remaining === 0) el.classList.add('empty');
  else if (remaining <= 5) el.classList.add('low');
}

renderAiCounter();

// ─────────────────────────────────────────
// API CALLS
// ─────────────────────────────────────────

async function apiSearchDrug(query) {
  const res = await fetch(`${API_BASE}/api/drugs/search?query=${encodeURIComponent(query)}&lang=${currentLang}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function apiCompatibility(drugName, patientText, symptomText = '') {
  const res = await fetch(`${API_BASE}/api/drugs/compatibility`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ drug_name: drugName, patient_text: patientText, symptom_text: symptomText, lang: currentLang }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function apiGeminiCompatibility(drugName, patientText, symptomText = '') {
  const res = await fetch(`${API_BASE}/api/drugs/gemini-compatibility`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ drug_name: drugName, patient_text: patientText, symptom_text: symptomText, lang: currentLang }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function apiExternalDrug(query) {
  const res = await fetch(`${API_BASE}/api/drugs/external?query=${encodeURIComponent(query)}&lang=${currentLang}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ─────────────────────────────────────────
// RENDER HELPERS
// ─────────────────────────────────────────

function verdictBadge(verdict) {
  const map = {
    'suitable':        { cls: 'suitable',       icon: '✅', key: 'v_suitable' },
    'risky':           { cls: 'risky',           icon: '⚠️', key: 'v_risky' },
    'not-recommended': { cls: 'not-recommended', icon: '🚫', key: 'v_not_rec' },
    'uncertain':       { cls: 'uncertain',       icon: '❓', key: 'v_uncertain' },
  };
  const v = map[verdict] || map['uncertain'];
  return `<span class="verdict-badge ${v.cls}">${v.icon} ${t(v.key)}</span>`;
}

function sectionColor(verdict) {
  return { suitable: 'green', risky: 'orange', 'not-recommended': 'red', uncertain: 'gray' }[verdict] || 'gray';
}

function indicatorClass(verdict) {
  return sectionColor(verdict);
}

function sourcesHtml(sources) {
  return `<div class="sources-bar">
    <span>${t('sources_label')}</span>
    ${sources.map(s => `<a class="source-link" href="${s.url}" target="_blank" rel="noopener">🔗 ${s.label}</a>`).join('')}
  </div>`;
}

function externalBoxHtml(ext) {
  if (!ext || !ext.found) return '';
  const rows = [
    ext.brand_name   && `<p><strong>${t('ext_brand')}</strong> ${ext.brand_name}</p>`,
    ext.generic_name && `<p><strong>${t('ext_generic')}</strong> ${ext.generic_name}</p>`,
    ext.manufacturer && `<p><strong>${t('ext_manufacturer')}</strong> ${ext.manufacturer}</p>`,
    ext.route        && `<p><strong>${t('ext_route')}</strong> ${ext.route}</p>`,
    ext.indications  && `<p><strong>${t('ext_indications')}</strong> ${ext.indications}</p>`,
    ext.warnings     && `<p><strong>${t('ext_warnings')}</strong> ${ext.warnings}</p>`,
  ].filter(Boolean).join('');
  if (!rows) return '';
  return `<div class="external-box"><h4>${t('ext_title')}</h4>${rows}</div>`;
}

// ─────────────────────────────────────────
// MODE 1: RENDER MED SHEET
// ─────────────────────────────────────────

function renderMedSheet(med, externalData = null) {
  return `
  <div class="med-card">
    <div class="med-card-header">
      <div class="med-icon-wrap">${med.emoji}</div>
      <div class="med-header-info">
        <h2>${med.name}</h2>
        <div class="med-class">${med.class}</div>
        <div class="med-dosage">📏 ${med.dosage}</div>
      </div>
    </div>
    <div class="med-body">
      <div class="med-section">
        <h3 class="green">${t('s_uses')}</h3>
        <p>${med.uses}</p>
      </div>
      <div class="med-section">
        <h3 class="orange">${t('s_effects')}</h3>
        ${med.sideEffects.length
          ? `<ul>${med.sideEffects.map(e => `<li>${e}</li>`).join('')}</ul>`
          : `<p class="no-data-note">${t('no_side_effects')}</p>`
        }
        <p class="consult-note">${t('consult_leaflet')}</p>
      </div>
      <div class="med-section">
        <h3 class="red">${t('s_when_not')}</h3>
        <ul>${med.notFor.length ? med.notFor.map(e => `<li>${e}</li>`).join('') : `<li>${t('consult_leaflet')}</li>`}</ul>
      </div>
      <div class="med-section">
        <h3 class="blue">${t('s_restrictions')}</h3>
        ${med.restrictions.length
          ? `<ul>${med.restrictions.map(e => `<li>${e}</li>`).join('')}</ul>`
          : `<p class="no-data-note">${t('no_restrictions')}</p>`
        }
        <p class="consult-note">${t('consult_leaflet')}</p>
      </div>
      <div class="fact-box">
        <div class="fact-icon">ℹ️</div>
        <div>
          <p class="fact-section-label"><strong>${t('s_official_info')}</strong></p>
          ${med.fact ? `<p class="fact-text"><em>${t('s_fun_fact')}</em> ${med.fact}</p>` : ''}
        </div>
      </div>
    </div>
    ${externalBoxHtml(externalData)}
    ${sourcesHtml(med.sources)}
    <div class="card-footer">
      <button class="btn-secondary" onclick="resetToMain(false)">${t('btn_back_sheet')}</button>
    </div>
  </div>`;
}

function renderUnknownMedSheet(medName, externalData = null) {
  const sources = [
    { label: 'CIMA AEMPS', url: 'https://cima.aemps.es' },
    { label: 'Vademecum',  url: 'https://www.vademecum.es' },
    { label: 'DrugBank',   url: 'https://go.drugbank.com' },
  ];
  const namePrefixMap = { es:'El nombre', en:'The name', fr:'Le nom', it:'Il nome', de:'Der Name', ca:'El nom', pt:'O nome', no:'Navnet', ro:'Numele' };
  const namePrefix = namePrefixMap[currentLang] || 'The name';
  return `
  <div class="med-card">
    <div class="med-card-header">
      <div class="med-icon-wrap">💊</div>
      <div class="med-header-info">
        <h2>${medName}</h2>
        <div class="med-class">${t('unknown_class')}</div>
        <div class="med-dosage">📏 ${t('unknown_dosage')}</div>
      </div>
    </div>
    <div class="med-body">
      <div class="med-section" style="grid-column:1/-1">
        <h3 class="gray">${t('unknown_section')}</h3>
        <p>${namePrefix} "<strong>${medName}</strong>" ${t('unknown_body')}</p>
      </div>
    </div>
    ${externalBoxHtml(externalData)}
    ${sourcesHtml(sources)}
    <div class="card-footer">
      <button class="btn-secondary" onclick="resetToMain(false)">${t('btn_back_sheet')}</button>
    </div>
  </div>`;
}

// ─────────────────────────────────────────
// MODE 2A: RENDER GEMINI REPORT
// ─────────────────────────────────────────

function renderGeminiReport(data) {
  if (data.error) {
    const msg = data.error === 'gemini_overloaded' ? t('gemini_overloaded') : data.error;
    return `<div class="compat-card">
      <div class="compat-header">
        <div class="compat-header-left"><h2>${t('gemini_err_title')}</h2><p>${msg}</p></div>
      </div>
      <div class="card-footer"><button class="btn-secondary" onclick="resetToMain(true)">${t('btn_back_compat')}</button></div>
    </div>`;
  }

  const { drug_name, verdict, resumen, indicado_para, factores_riesgo = [],
          explicacion_general, recomendaciones = [], alternativas = [],
          advertencia_critica, sources = [] } = data;

  const riskLevelMap = { alto: t('risk_alto'), medio: t('risk_medio'), bajo: t('risk_bajo') };

  const riskHtml = factores_riesgo.length
    ? factores_riesgo.map(f => `
        <div class="risk-row">
          <div class="risk-dot ${f.nivel}"></div>
          <div class="risk-content">
            <strong>${f.factor} <span class="risk-tag ${f.nivel}">${riskLevelMap[f.nivel] || f.nivel.toUpperCase()}</span></strong>
            <p>${f.explicacion}</p>
          </div>
        </div>`).join('')
    : `<p>${t('gemini_no_risks')}</p>`;

  const recsHtml = recomendaciones.length
    ? `<ul>${recomendaciones.map(r => `<li>${r}</li>`).join('')}</ul>`
    : `<p>${t('gemini_def_recs')}</p>`;

  const altsHtml = alternativas.length && (verdict === 'risky' || verdict === 'not-recommended')
    ? `<div class="gemini-section">
        <h3 class="blue">${t('gemini_alts')}</h3>
        <div class="alt-list">
          ${alternativas.map(a => `<span class="alt-pill" onclick="goToMedSheet('${a}')">💊 ${a}</span>`).join('')}
        </div>
      </div>`
    : '';

  const criticalHtml = advertencia_critica
    ? `<div class="critical-warning">⛔ ${advertencia_critica}</div>`
    : '';

  return `
  <div class="gemini-card">
    <div class="gemini-header">
      <div class="gemini-header-left">
        <h2>${t('gemini_ai_title')} <span style="color:var(--blue)">${drug_name}</span></h2>
        <p>
          <span class="gemini-badge">${t('gemini_badge')}</span>
          ${t('gemini_sub')}
        </p>
      </div>
      ${verdictBadge(verdict)}
    </div>

    ${criticalHtml ? `<div style="padding: 16px 36px 0">${criticalHtml}</div>` : ''}

    <div class="gemini-body">
      <div class="gemini-section">
        <h3 class="${verdict === 'suitable' ? 'green' : verdict === 'not-recommended' ? 'red' : 'orange'}">
          ${t('gemini_summary')}
        </h3>
        <p><strong>${resumen}</strong></p>
      </div>

      <div class="gemini-section">
        <h3 class="blue">${t('gemini_suit')}</h3>
        <p>${indicado_para}</p>
      </div>

      <div class="gemini-section">
        <h3 class="orange">${t('gemini_risks')}</h3>
        ${riskHtml}
      </div>

      <div class="gemini-section">
        <h3 class="blue">${t('gemini_eval')}</h3>
        <p>${explicacion_general}</p>
      </div>

      <div class="gemini-section">
        <h3 class="green">${t('gemini_recs')}</h3>
        ${recsHtml}
      </div>

      ${altsHtml}
    </div>

    ${sourcesHtml(sources)}

    <div class="card-footer">
      <button class="btn-secondary" onclick="resetToMain(true)">${t('btn_back_compat')}</button>
    </div>
  </div>`;
}

// ─────────────────────────────────────────
// MODE 2B: RENDER COMPAT RESULT (fallback)
// ─────────────────────────────────────────

function renderCompat(data) {
  const { drug_name, verdict, flags, generic_risks, alternatives, suitability, explanation, sources, found } = data;
  const col = sectionColor(verdict);

  let safetyHtml;
  if (flags.length === 0 && generic_risks.length === 0) {
    safetyHtml = `<p>${t('compat_no_risks')}</p>`;
  } else if (flags.length > 0) {
    safetyHtml = flags.map(f => `
      <div class="suitability-row" style="margin-bottom:10px; align-items:flex-start">
        <div class="suit-indicator ${indicatorClass(f.verdict)}" style="margin-top:6px"></div>
        <div>
          <strong style="font-size:0.88rem; color:#374151">${f.label}</strong>
          <p style="margin-top:3px">${f.note}</p>
        </div>
      </div>`).join('');
  } else {
    safetyHtml = `<p>${t('compat_gen_risks')}</p>
      <ul style="margin-top:10px; padding-left:18px; font-size:0.92rem; color:#374151; line-height:1.7">
        ${generic_risks.map(r => `<li>${r}</li>`).join('')}
      </ul>`;
  }

  let altsHtml = '';
  if ((verdict === 'risky' || verdict === 'not-recommended') && alternatives.length > 0) {
    altsHtml = `
    <div class="compat-section">
      <h3 class="blue">${t('compat_alts')}</h3>
      <p style="margin-bottom:12px">${t('compat_alts_desc')}</p>
      <div class="alt-list">
        ${alternatives.map(a => `<span class="alt-pill" onclick="goToMedSheet('${a}')">💊 ${a}</span>`).join('')}
      </div>
    </div>`;
  }

  const defaultSources = [
    { label: 'CIMA AEMPS', url: 'https://cima.aemps.es' },
    { label: 'Vademecum',  url: 'https://www.vademecum.es' },
    { label: 'DrugBank',   url: 'https://go.drugbank.com' },
  ];

  return `
  <div class="compat-card">
    <div class="compat-header">
      <div class="compat-header-left">
        <h2>${t('compat_title')} <span style="color:var(--blue)">${drug_name}</span></h2>
        <p>${t('compat_sub')}</p>
      </div>
      ${verdictBadge(verdict)}
    </div>
    <div class="compat-sections">
      <div class="compat-section">
        <h3 class="${suitability.match ? 'green' : 'gray'}">${t('compat_suit')}</h3>
        <div class="suitability-row">
          <div class="suit-indicator ${suitability.match ? 'green' : 'gray'}"></div>
          <p>${suitability.text}</p>
        </div>
      </div>
      <div class="compat-section">
        <h3 class="${col}">${t('compat_safety')}</h3>
        ${safetyHtml}
      </div>
      <div class="compat-section">
        <h3 class="blue">${t('compat_expl')}</h3>
        <p>${explanation}</p>
      </div>
      ${altsHtml}
    </div>
    ${sourcesHtml(sources || defaultSources)}
    <div class="card-footer">
      <button class="btn-secondary" onclick="resetToMain(true)">${t('btn_back_compat')}</button>
    </div>
  </div>`;
}

// ─────────────────────────────────────────
// NAVIGATION HELPERS
// ─────────────────────────────────────────

function resetToMain(keepCompatMode) {
  document.getElementById('initial-screen').style.display = '';
  document.getElementById('result-section').style.display = 'none';
  document.getElementById('result-section').innerHTML = '';
  document.getElementById('med-input').value = '';
  document.getElementById('patient-input').value = '';
  if (!keepCompatMode && compatMode) toggleMode();
  document.getElementById('med-input').focus();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function goToMedSheet(medName) {
  if (compatMode) toggleMode();
  document.getElementById('initial-screen').style.display = '';
  document.getElementById('result-section').style.display = 'none';
  document.getElementById('result-section').innerHTML = '';
  document.getElementById('med-input').value = medName;
  window.scrollTo({ top: 0, behavior: 'smooth' });
  setTimeout(() => handleAction(), 200);
}

// ─────────────────────────────────────────
// TOGGLE MODE
// ─────────────────────────────────────────

function toggleMode() {
  compatMode = !compatMode;
  const btn = document.getElementById('toggle-btn');
  const patientWrap = document.getElementById('patient-wrap');
  const medInput = document.getElementById('med-group');

  btn.classList.toggle('active', compatMode);
  btn.setAttribute('aria-pressed', compatMode);
  patientWrap.classList.toggle('visible', compatMode);
  document.getElementById('input-row').classList.toggle('compat-active', compatMode);
  document.getElementById('toggle-label-text').textContent = t('toggle_label');

  updateActionBtn();
  if (compatMode) {
    medInput.querySelector('label').textContent = t('label_med');
  }
}

// ─────────────────────────────────────────
// MAIN ACTION
// ─────────────────────────────────────────

async function handleAction() {
  const medQuery = document.getElementById('med-input').value.trim();
  const patientText = document.getElementById('patient-input').value.trim();
  const errorBox = document.getElementById('error-box');
  const apiBanner = document.getElementById('api-error-banner');

  if (!medQuery) {
    errorBox.textContent = t('err_empty');
    errorBox.style.display = 'block';
    document.getElementById('med-input').focus();
    setTimeout(() => { errorBox.style.display = 'none'; }, 3000);
    return;
  }
  errorBox.style.display = 'none';
  apiBanner.style.display = 'none';

  document.getElementById('initial-screen').style.display = 'none';
  const resultSection = document.getElementById('result-section');
  resultSection.style.display = 'block';
  const loadingMsg = compatMode ? t('loading_compat') : t('loading_sheet');
  resultSection.innerHTML = `<div class="loading-wrap"><div class="spinner"></div><p>${loadingMsg}</p></div>`;
  window.scrollTo({ top: 0, behavior: 'smooth' });

  let retryNotifTimer = null;
  if (compatMode) {
    retryNotifTimer = setTimeout(() => {
      const notif = document.getElementById('retry-notif');
      if (notif) { notif.textContent = t('gemini_retrying'); notif.classList.add('visible'); }
    }, 20000);
  }

  try {
    let html;

    if (compatMode) {
      const geminiData = await apiGeminiCompatibility(medQuery, patientText, medQuery);
      incrementAiUsage();
      html = renderGeminiReport(geminiData);
    } else {
      const [searchData, externalData] = await Promise.allSettled([
        apiSearchDrug(medQuery),
        apiExternalDrug(medQuery),
      ]);

      const local = searchData.status === 'fulfilled' ? searchData.value : null;
      const ext   = externalData.status === 'fulfilled' ? externalData.value : null;

      if (local && local.found) {
        html = renderMedSheet(local.drug, ext);
      } else {
        html = renderUnknownMedSheet(medQuery, ext);
      }
    }

    clearTimeout(retryNotifTimer);
    const notif = document.getElementById('retry-notif');
    if (notif) notif.classList.remove('visible');
    resultSection.innerHTML = html;
  } catch (err) {
    clearTimeout(retryNotifTimer);
    const notif = document.getElementById('retry-notif');
    if (notif) notif.classList.remove('visible');
    resultSection.innerHTML = '';
    document.getElementById('initial-screen').style.display = '';
    apiBanner.textContent = t('err_server');
    apiBanner.style.display = 'block';
    setTimeout(() => { apiBanner.style.display = 'none'; }, 6000);
  }
}

// ─────────────────────────────────────────
// EVENT LISTENERS
// ─────────────────────────────────────────

document.getElementById('toggle-btn').addEventListener('click', toggleMode);
document.getElementById('action-btn').addEventListener('click', handleAction);
const langGlobeBtn = document.getElementById('lang-globe-btn');
const langDropdown = document.getElementById('lang-dropdown');

langGlobeBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  langDropdown.classList.toggle('open');
});

document.querySelectorAll('.lang-option').forEach(btn => {
  btn.addEventListener('click', () => {
    setLang(btn.dataset.lang);
    langDropdown.classList.remove('open');
  });
});

document.addEventListener('click', () => {
  langDropdown.classList.remove('open');
});
document.getElementById('theme-btn').addEventListener('click', toggleTheme);

document.getElementById('med-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !compatMode) handleAction();
  if (e.key === 'Enter' && compatMode && e.ctrlKey) handleAction();
});
document.getElementById('patient-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.ctrlKey) handleAction();
});

// Init
applyLang();

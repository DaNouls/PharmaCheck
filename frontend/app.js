/**
 * PharmaCheck — Frontend
 * Toda la lógica de datos y análisis vive en el backend (Python/FastAPI).
 * Este archivo maneja UI, rendering, traducciones y llamadas a la API.
 */

const API_BASE = 'http://localhost:8000';
const AI_DAILY_LIMIT = 20;

let compatMode = false;
let currentLang = 'es'; // Siempre empieza en español
let lastRender = null;  // { fn, args } — solo para resultados estándar (sin Gemini)
let lastQuery   = null; // { medQuery, patientText } — para re-fetch al cambiar idioma
let renderCache = {};   // { 'es': html, 'en': html } — caché para no gastar 2 usos IA

// ─────────────────────────────────────────
// TRANSLATIONS
// ─────────────────────────────────────────

const LANGS = {
  es: {
    heroTitle:          'Evaluación de medicamentos',
    heroSub:            'Consulta la ficha técnica de cualquier fármaco o analiza su compatibilidad con un paciente en segundos.',
    medLabel:           '💊 Medicamento',
    medPlaceholder:     'Nombre del medicamento',
    patientLabel:       '🧑‍⚕️ Información del paciente',
    patientPlaceholder: 'síntomas, receta, enfermedad; peso, altura, embarazo, alergias…',
    concordanceLabel:   'Concordancia',
    btnSheet:           'Ficha de medicamento',
    btnCompat:          'Análisis de concordancia',
    errorEmpty:         'Por favor ingresa el nombre de un medicamento.',
    errorServer:        '⚠️ No se pudo conectar con el servidor. Verifica que el backend esté corriendo en',
    loadingGeminiCompat:'Generando informe con Gemini AI…',
    loadingGeminiSheet: 'Generando ficha con Gemini AI…',
    loadingStandard:    'Consultando base de datos médica…',
    sourcesLabel:       '📚 Fuentes:',
    btnBack:            '← Otro medicamento',
    btnBackCompat:      '← Otro caso',
    // Section titles — Gemini sheet
    secIndicatedFor:    '🎯 Indicado para',
    secSideEffects:     '⚠️ Efectos secundarios',
    secContraind:       '🚫 Contraindicaciones',
    secWarnings:        '⚡ Advertencias',
    secPopulations:     '👥 Poblaciones especiales',
    secInteractions:    '🔗 Interacciones',
    secTips:            '✅ Consejos',
    secMechanism:       'Mecanismo',
    secDosage:          'Dosis típica',
    secCurious:         '¿Sabías que…?',
    // Section titles — standard sheet
    secUsedFor:         '🎯 Para qué se usa',
    secWhenNot:         '🚫 Cuándo NO usar',
    secRestrictions:    '⚙️ Restricciones',
    // Section titles — compat report
    secResumen:         '📋 Resumen',
    secSuitability:     '🎯 Idoneidad para la condición',
    secRisks:           '🛡️ Factores de riesgo identificados',
    secEvaluation:      '📄 Evaluación clínica',
    secRecommendations: '✅ Recomendaciones',
    secAlternatives:    '🔄 Alternativas posibles',
    altSubtext:         'Las siguientes alternativas podrían ser más adecuadas. Haz clic para ver su ficha.',
    // Verdict badges
    verdictSuitable:    'Adecuado',
    verdictRisky:       'Potencialmente arriesgado',
    verdictNotRec:      'No recomendado',
    verdictUncertain:   'Incierto',
    // No-data fallbacks
    noSideEffects:      'No hay efectos secundarios importantes registrados.',
    noSideEffectsSub:   'Consultar el prospecto oficial para la lista completa.',
    noRestrictions:     'No se han identificado restricciones importantes.',
    noWarnings:         'Sin advertencias especiales destacadas.',
    noRisks:            'No se identificaron factores de riesgo específicos para este paciente.',
    followLeaflet:      'Seguir las indicaciones del prospecto oficial.',
    // Population labels
    popPregnancy: 'Embarazo',
    popChildren:  'Niños',
    popElderly:   'Ancianos',
    popRenal:     'Ins. renal',
    popHepatic:   'Ins. hepática',
    // Unknown med
    unknownClass:   'Medicamento — clase no identificada',
    unknownDosage:  'Consultar prospecto o profesional sanitario',
    unknownTitle:   'ℹ️ Información no disponible',
    unknownText:    'no ha sido reconocido en la base de datos local. Consulta las fuentes oficiales para información precisa.',
    // Gemini labels
    geminiAI:        '✨ Gemini AI',
    geminiSubtitle:  'Informe generado por inteligencia artificial · Solo orientativo',
    geminiAnalysis:  'Análisis IA:',
    geminiEvalFor:   'Evaluación para el perfil de paciente descrito',
    geminiError:     'Error de Gemini',
    // External box
    extTitle:   '🌐 Datos OpenFDA (oficial)',
    extBrand:   'Nombre comercial:',
    extGeneric: 'Nombre genérico:',
    extMfr:     'Fabricante:',
    extRoute:   'Vía:',
    extInd:     'Indicaciones (FDA):',
    extWarn:    'Advertencias (FDA):',
    // Enums de Gemini (frecuencia, gravedad, nivel)
    frecMuyFrecuente:  'muy frecuente',
    frecFrecuente:     'frecuente',
    frecPocoFrecuente: 'poco frecuente',
    frecRaro:          'raro',
    gravLeve:          'leve',
    gravModerado:      'moderado',
    gravGrave:         'grave',
    nivelAlto:         'ALTO',
    nivelMedio:        'MEDIO',
    nivelBajo:         'BAJO',
  },
  en: {
    heroTitle:          'Medication Evaluation',
    heroSub:            'Look up any drug profile or analyze its compatibility with a patient in seconds.',
    medLabel:           '💊 Medication',
    medPlaceholder:     'Medication name',
    patientLabel:       '🧑‍⚕️ Patient information',
    patientPlaceholder: 'symptoms, prescription, condition; weight, height, pregnancy, allergies…',
    concordanceLabel:   'Compatibility',
    btnSheet:           'Drug profile',
    btnCompat:          'Compatibility analysis',
    errorEmpty:         'Please enter a medication name.',
    errorServer:        '⚠️ Could not connect to the server. Make sure the backend is running at',
    loadingGeminiCompat:'Generating report with Gemini AI…',
    loadingGeminiSheet: 'Generating profile with Gemini AI…',
    loadingStandard:    'Looking up medical database…',
    sourcesLabel:       '📚 Sources:',
    btnBack:            '← Another medication',
    btnBackCompat:      '← Another case',
    secIndicatedFor:    '🎯 Indicated for',
    secSideEffects:     '⚠️ Side effects',
    secContraind:       '🚫 Contraindications',
    secWarnings:        '⚡ Warnings',
    secPopulations:     '👥 Special populations',
    secInteractions:    '🔗 Interactions',
    secTips:            '✅ Tips',
    secMechanism:       'Mechanism',
    secDosage:          'Typical dose',
    secCurious:         'Did you know…?',
    secUsedFor:         '🎯 What it is used for',
    secWhenNot:         '🚫 When NOT to use',
    secRestrictions:    '⚙️ Restrictions',
    secResumen:         '📋 Summary',
    secSuitability:     '🎯 Suitability for the condition',
    secRisks:           '🛡️ Identified risk factors',
    secEvaluation:      '📄 Clinical evaluation',
    secRecommendations: '✅ Recommendations',
    secAlternatives:    '🔄 Possible alternatives',
    altSubtext:         'The following alternatives may be more suitable. Click to view their profile.',
    verdictSuitable:    'Suitable',
    verdictRisky:       'Potentially risky',
    verdictNotRec:      'Not recommended',
    verdictUncertain:   'Uncertain',
    noSideEffects:      'No significant side effects recorded for this medication.',
    noSideEffectsSub:   'Check the official package leaflet for the complete list.',
    noRestrictions:     'No important restrictions identified.',
    noWarnings:         'No special warnings highlighted.',
    noRisks:            'No specific risk factors identified for this patient.',
    followLeaflet:      'Follow the instructions in the official package leaflet.',
    popPregnancy: 'Pregnancy',
    popChildren:  'Children',
    popElderly:   'Elderly',
    popRenal:     'Renal insuf.',
    popHepatic:   'Hepatic insuf.',
    unknownClass:   'Medication — class not identified',
    unknownDosage:  'Consult package leaflet or healthcare professional',
    unknownTitle:   'ℹ️ Information not available',
    unknownText:    'was not recognised in the local database. Please check official sources for accurate information.',
    geminiAI:        '✨ Gemini AI',
    geminiSubtitle:  'Report generated by artificial intelligence · For guidance only',
    geminiAnalysis:  'AI Analysis:',
    geminiEvalFor:   'Evaluation for the described patient profile',
    geminiError:     'Gemini Error',
    extTitle:   '🌐 OpenFDA data (official)',
    extBrand:   'Brand name:',
    extGeneric: 'Generic name:',
    extMfr:     'Manufacturer:',
    extRoute:   'Route:',
    extInd:     'Indications (FDA):',
    extWarn:    'Warnings (FDA):',
    // Gemini enums translated
    frecMuyFrecuente:  'very common',
    frecFrecuente:     'common',
    frecPocoFrecuente: 'uncommon',
    frecRaro:          'rare',
    gravLeve:          'mild',
    gravModerado:      'moderate',
    gravGrave:         'severe',
    nivelAlto:         'HIGH',
    nivelMedio:        'MEDIUM',
    nivelBajo:         'LOW',
  },
};

function t(key) {
  return (LANGS[currentLang] || LANGS.es)[key] || key;
}

// Traduce valores enum que vienen del backend (frecuencia, gravedad, nivel)
const FREC_KEYS  = { 'muy frecuente': 'frecMuyFrecuente', 'frecuente': 'frecFrecuente', 'poco frecuente': 'frecPocoFrecuente', 'raro': 'frecRaro' };
const GRAV_KEYS  = { 'leve': 'gravLeve', 'moderado': 'gravModerado', 'grave': 'gravGrave' };
const NIVEL_KEYS = { 'alto': 'nivelAlto', 'medio': 'nivelMedio', 'bajo': 'nivelBajo' };
function tEnum(map, val) { const k = map[(val || '').toLowerCase()]; return k ? t(k) : val; }

function setLang(lang) {
  currentLang = lang;
  document.getElementById('lang-es').classList.toggle('active', lang === 'es');
  document.getElementById('lang-en').classList.toggle('active', lang === 'en');
  updateStaticUI();
  renderAiCounter();
  const resultSection = document.getElementById('result-section');
  if (!resultSection.innerHTML || resultSection.style.display === 'none') return;

  if (renderCache[lang]) {
    // Resultado Gemini ya cacheado en este idioma — sin coste
    resultSection.innerHTML = renderCache[lang];
  } else if (lastRender) {
    // Resultado estándar (sin Gemini) — los datos no cambian, solo los labels
    resultSection.innerHTML = lastRender.fn(...lastRender.args);
  } else if (lastQuery) {
    // Resultado Gemini no cacheado en este idioma — re-fetch con nuevo idioma
    document.getElementById('med-input').value = lastQuery.medQuery;
    document.getElementById('patient-input').value = lastQuery.patientText;
    handleAction();
  }
}

function updateStaticUI() {
  document.getElementById('hero-title').textContent = t('heroTitle');
  document.getElementById('hero-sub').textContent   = t('heroSub');

  const medGroup = document.getElementById('med-group');
  medGroup.querySelector('label').textContent = t('medLabel');
  document.getElementById('med-input').placeholder = t('medPlaceholder');

  const patientLabel = document.querySelector('#patient-wrap .input-group label');
  if (patientLabel) patientLabel.textContent = t('patientLabel');
  document.getElementById('patient-input').placeholder = t('patientPlaceholder');

  document.querySelector('.toggle-label').textContent = t('concordanceLabel');
  document.getElementById('error-box').textContent    = t('errorEmpty');

  // Re-render action button text (keeping the SVG icon)
  const actionBtn = document.getElementById('action-btn');
  const svgSheet = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>`;
  const svgCompat = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>`;
  actionBtn.innerHTML = compatMode
    ? `${svgCompat} ${t('btnCompat')}`
    : `${svgSheet} ${t('btnSheet')}`;
}

// ─────────────────────────────────────────
// AI USAGE COUNTER
// ─────────────────────────────────────────

function getAiUsage() {
  const today = new Date().toISOString().slice(0, 10);
  const stored = JSON.parse(localStorage.getItem('pharmacheck_ai') || '{}');
  if (stored.date !== today) return { date: today, used: 0 };
  return stored;
}

function getAiRemaining() {
  return AI_DAILY_LIMIT - getAiUsage().used;
}

function incrementAiUsage() {
  const usage = getAiUsage();
  usage.used = Math.min(usage.used + 1, AI_DAILY_LIMIT);
  localStorage.setItem('pharmacheck_ai', JSON.stringify(usage));
  renderAiCounter();
}

function renderAiCounter() {
  const remaining = getAiRemaining();
  const el = document.getElementById('ai-counter');
  if (!el) return;
  const cls = remaining > 10 ? 'green' : remaining > 5 ? 'orange' : 'red';
  el.className = `ai-counter ${cls}`;
  el.innerHTML = `<span class="ai-counter-icon">✨</span><span class="ai-counter-text">${remaining}/${AI_DAILY_LIMIT} IA</span>`;
}

// ─────────────────────────────────────────
// API CALLS
// ─────────────────────────────────────────

async function apiSearchDrug(query) {
  const res = await fetch(`${API_BASE}/api/drugs/search?query=${encodeURIComponent(query)}`);
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

async function apiGeminiSheet(drugName) {
  const res = await fetch(`${API_BASE}/api/drugs/gemini-sheet`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ drug_name: drugName, patient_text: '', symptom_text: '', lang: currentLang }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function apiExternalDrug(query) {
  const res = await fetch(`${API_BASE}/api/drugs/external?query=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ─────────────────────────────────────────
// RENDER HELPERS
// ─────────────────────────────────────────

function verdictBadge(verdict) {
  const map = {
    'suitable':        { cls: 'suitable',        icon: '✅', text: t('verdictSuitable') },
    'risky':           { cls: 'risky',            icon: '⚠️', text: t('verdictRisky') },
    'not-recommended': { cls: 'not-recommended',  icon: '🚫', text: t('verdictNotRec') },
    'uncertain':       { cls: 'uncertain',        icon: '❓', text: t('verdictUncertain') },
  };
  const v = map[verdict] || map['uncertain'];
  return `<span class="verdict-badge ${v.cls}">${v.icon} ${v.text}</span>`;
}

function sectionColor(verdict) {
  return { suitable: 'green', risky: 'orange', 'not-recommended': 'red', uncertain: 'gray' }[verdict] || 'gray';
}

function indicatorClass(verdict) { return sectionColor(verdict); }

function sourcesHtml(sources) {
  return `<div class="sources-bar">
    <span>${t('sourcesLabel')}</span>
    ${sources.map(s => `<a class="source-link" href="${s.url}" target="_blank" rel="noopener">🔗 ${s.label}</a>`).join('')}
  </div>`;
}

function externalBoxHtml(ext) {
  if (!ext || !ext.found) return '';
  const rows = [
    ext.brand_name   && `<p><strong>${t('extBrand')}</strong> ${ext.brand_name}</p>`,
    ext.generic_name && `<p><strong>${t('extGeneric')}</strong> ${ext.generic_name}</p>`,
    ext.manufacturer && `<p><strong>${t('extMfr')}</strong> ${ext.manufacturer}</p>`,
    ext.route        && `<p><strong>${t('extRoute')}</strong> ${ext.route}</p>`,
    ext.indications  && `<p><strong>${t('extInd')}</strong> ${ext.indications}</p>`,
    ext.warnings     && `<p><strong>${t('extWarn')}</strong> ${ext.warnings}</p>`,
  ].filter(Boolean).join('');
  if (!rows) return '';
  return `<div class="external-box"><h4>${t('extTitle')}</h4>${rows}</div>`;
}

function toChips(items, color) {
  return `<div class="kw-chips">${items.map(text => {
    const short = text.length > 72 ? text.slice(0, 72) + '…' : text;
    return `<span class="kw-chip ${color}">${short}</span>`;
  }).join('')}</div>`;
}

// ─────────────────────────────────────────
// MODE 1A: RENDER GEMINI DRUG SHEET
// ─────────────────────────────────────────

function renderGeminiSheet(data) {
  const {
    nombre, clase_farmacologica, emoji, resumen,
    indicaciones = [], como_funciona, dosificacion_tipica,
    efectos_secundarios = [], contraindicaciones = [],
    advertencias_importantes = [], interacciones_destacadas = [],
    poblaciones_especiales = {}, dato_curioso, consejos_practicos = [],
    sources = [],
  } = data;

  const indicHtml = indicaciones.length
    ? `<div class="kw-chips">${indicaciones.map(i => `<span class="kw-chip green">${i}</span>`).join('')}</div>`
    : '';

  const efectosHtml = efectos_secundarios.length
    ? `<div class="gs-effects-grid">
        ${efectos_secundarios.map(e => `
          <div class="gs-effect-chip ${e.gravedad}">
            <span class="gs-effect-name">${e.efecto}</span>
            <div class="gs-effect-tags">
              <span class="gs-effect-tag freq">${tEnum(FREC_KEYS, e.frecuencia)}</span>
              <span class="gs-effect-tag grav-${e.gravedad}">${tEnum(GRAV_KEYS, e.gravedad)}</span>
            </div>
          </div>`).join('')}
      </div>`
    : `<p class="no-data-note">${t('noSideEffects')}</p>
       <p class="no-data-sub">${t('noSideEffectsSub')}</p>`;

  const contraHtml = contraindicaciones.length
    ? `<div class="kw-chips">${contraindicaciones.map(c => `<span class="kw-chip red">✕ ${c}</span>`).join('')}</div>`
    : `<p class="no-data-note">${t('noRestrictions')}</p>`;

  const advHtml = advertencias_importantes.length
    ? `<div class="kw-chips">${advertencias_importantes.map(a => `<span class="kw-chip orange">! ${a}</span>`).join('')}</div>`
    : `<p class="no-data-sub">${t('noWarnings')}</p>`;

  const intHtml = interacciones_destacadas.length
    ? `<div class="kw-chips">${interacciones_destacadas.map(i => `<span class="kw-chip amber">⚡ ${i}</span>`).join('')}</div>`
    : '';

  const pops = [
    { icon: '🤰', label: t('popPregnancy'), val: poblaciones_especiales.embarazo },
    { icon: '👶', label: t('popChildren'),  val: poblaciones_especiales.ninos },
    { icon: '👴', label: t('popElderly'),   val: poblaciones_especiales.ancianos },
    { icon: '🫘', label: t('popRenal'),     val: poblaciones_especiales.insuficiencia_renal },
    { icon: '🫀', label: t('popHepatic'),   val: poblaciones_especiales.insuficiencia_hepatica },
  ].filter(p => p.val);

  const popHtml = pops.map(p => `
    <div class="gs-pop-card">
      <div class="gs-pop-header"><span class="gs-pop-icon">${p.icon}</span>${p.label}</div>
      <div class="gs-pop-body">${p.val}</div>
    </div>`).join('');

  const consejosHtml = consejos_practicos.length
    ? `<div class="kw-chips">${consejos_practicos.map(c => `<span class="kw-chip green-soft">✓ ${c}</span>`).join('')}</div>`
    : '';

  const fallbackSources = [
    { label: 'OpenFDA', url: 'https://open.fda.gov' },
    { label: 'FDA',     url: 'https://www.fda.gov/drugs' },
  ];

  return `
  <div class="gs-card">
    <div class="gs-header">
      <div class="gs-header-top">
        <div class="gs-emoji-wrap">${emoji || '💊'}</div>
        <div class="gs-header-info">
          <h2 class="gs-title">${nombre}</h2>
          <span class="gs-class-pill">${clase_farmacologica}</span>
        </div>
        <span class="gs-ai-badge">${t('geminiAI')}</span>
      </div>
      <p class="gs-resumen">${resumen}</p>
    </div>

    <div class="gs-info-row">
      <div class="gs-info-pill">
        <span class="gs-info-pill-icon">⚙️</span>
        <div class="gs-info-pill-text">
          <div class="gs-info-pill-label">${t('secMechanism')}</div>
          <div class="gs-info-pill-value">${como_funciona}</div>
        </div>
      </div>
      <div class="gs-info-pill">
        <span class="gs-info-pill-icon">📏</span>
        <div class="gs-info-pill-text">
          <div class="gs-info-pill-label">${t('secDosage')}</div>
          <div class="gs-info-pill-value">${dosificacion_tipica}</div>
        </div>
      </div>
    </div>

    <div class="gs-body">
      ${indicHtml ? `
      <div class="gs-section">
        <div class="gs-section-title green">${t('secIndicatedFor')}</div>
        ${indicHtml}
      </div>` : ''}

      <div class="gs-section">
        <div class="gs-section-title orange">${t('secSideEffects')}</div>
        ${efectosHtml}
      </div>

      <div class="gs-two-col">
        <div class="gs-section">
          <div class="gs-section-title red">${t('secContraind')}</div>
          ${contraHtml}
        </div>
        <div class="gs-section">
          <div class="gs-section-title orange">${t('secWarnings')}</div>
          ${advHtml}
        </div>
      </div>

      ${pops.length ? `
      <div class="gs-section">
        <div class="gs-section-title blue">${t('secPopulations')}</div>
        <div class="gs-pop-grid">${popHtml}</div>
      </div>` : ''}

      ${intHtml ? `
      <div class="gs-section">
        <div class="gs-section-title amber">${t('secInteractions')}</div>
        ${intHtml}
      </div>` : ''}

      ${consejosHtml ? `
      <div class="gs-section">
        <div class="gs-section-title green">${t('secTips')}</div>
        ${consejosHtml}
      </div>` : ''}
    </div>

    ${dato_curioso ? `
    <div class="gs-curious-box">
      <span class="gs-curious-icon">💡</span>
      <div class="gs-curious-text">
        <strong>${t('secCurious')}</strong>
        <p>${dato_curioso}</p>
      </div>
    </div>` : ''}

    ${sourcesHtml(sources.length ? sources : fallbackSources)}
    <div class="card-footer">
      <button class="btn-secondary" onclick="resetToMain(false)">${t('btnBack')}</button>
    </div>
  </div>`;
}

// ─────────────────────────────────────────
// MODE 1B: RENDER MED SHEET (fallback)
// ─────────────────────────────────────────

function renderMedSheet(med, externalData = null) {
  const usesShort = med.uses.split(/\.\s+/)[0].slice(0, 180);

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
        <h3 class="green">${t('secUsedFor')}</h3>
        <p class="med-uses-text">${usesShort}.</p>
      </div>
      <div class="med-section">
        <h3 class="orange">${t('secSideEffects')}</h3>
        ${toChips(med.sideEffects, 'orange-soft')}
      </div>
      <div class="med-section">
        <h3 class="red">${t('secWhenNot')}</h3>
        ${toChips(med.notFor, 'red-soft')}
      </div>
      <div class="med-section">
        <h3 class="blue">${t('secRestrictions')}</h3>
        ${toChips(med.restrictions, 'blue-soft')}
      </div>
    </div>
    ${externalBoxHtml(externalData)}
    ${sourcesHtml(med.sources)}
    <div class="card-footer">
      <button class="btn-secondary" onclick="resetToMain(false)">${t('btnBack')}</button>
    </div>
  </div>`;
}

function renderUnknownMedSheet(medName, externalData = null) {
  const sources = [
    { label: 'CIMA AEMPS', url: 'https://cima.aemps.es' },
    { label: 'Vademecum',  url: 'https://www.vademecum.es' },
    { label: 'DrugBank',   url: 'https://go.drugbank.com' },
  ];
  return `
  <div class="med-card">
    <div class="med-card-header">
      <div class="med-icon-wrap">💊</div>
      <div class="med-header-info">
        <h2>${medName}</h2>
        <div class="med-class">${t('unknownClass')}</div>
        <div class="med-dosage">📏 ${t('unknownDosage')}</div>
      </div>
    </div>
    <div class="med-body">
      <div class="med-section" style="grid-column:1/-1">
        <h3 class="gray">${t('unknownTitle')}</h3>
        <p>"<strong>${medName}</strong>" ${t('unknownText')}</p>
      </div>
    </div>
    ${externalBoxHtml(externalData)}
    ${sourcesHtml(sources)}
    <div class="card-footer">
      <button class="btn-secondary" onclick="resetToMain(false)">${t('btnBack')}</button>
    </div>
  </div>`;
}

// ─────────────────────────────────────────
// MODE 2A: RENDER GEMINI REPORT
// ─────────────────────────────────────────

function renderGeminiReport(data) {
  if (data.error) {
    return `<div class="compat-card">
      <div class="compat-header">
        <div class="compat-header-left"><h2>${t('geminiError')}</h2><p>${data.error}</p></div>
      </div>
      <div class="card-footer"><button class="btn-secondary" onclick="resetToMain(true)">${t('btnBackCompat')}</button></div>
    </div>`;
  }

  const { drug_name, verdict, resumen, indicado_para, factores_riesgo = [],
          explicacion_general, recomendaciones = [], alternativas = [],
          advertencia_critica, sources = [] } = data;

  const riskHtml = factores_riesgo.length
    ? factores_riesgo.map(f => `
        <div class="risk-row">
          <div class="risk-dot ${f.nivel}"></div>
          <div class="risk-content">
            <strong>${f.factor} <span class="risk-tag ${f.nivel}">${tEnum(NIVEL_KEYS, f.nivel)}</span></strong>
            <p>${f.explicacion}</p>
          </div>
        </div>`).join('')
    : `<p>${t('noRisks')}</p>`;

  const recsHtml = recomendaciones.length
    ? `<ul>${recomendaciones.map(r => `<li>${r}</li>`).join('')}</ul>`
    : `<p>${t('followLeaflet')}</p>`;

  const altsHtml = alternativas.length && (verdict === 'risky' || verdict === 'not-recommended')
    ? `<div class="gemini-section">
        <h3 class="blue">${t('secAlternatives')}</h3>
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
        <h2>${t('geminiAnalysis')} <span style="color:var(--blue)">${drug_name}</span></h2>
        <p><span class="gemini-badge">${t('geminiAI')}</span> ${t('geminiSubtitle')}</p>
      </div>
      ${verdictBadge(verdict)}
    </div>

    ${criticalHtml ? `<div style="padding: 16px 36px 0">${criticalHtml}</div>` : ''}

    <div class="gemini-body">
      <div class="gemini-section">
        <h3 class="${verdict === 'suitable' ? 'green' : verdict === 'not-recommended' ? 'red' : 'orange'}">${t('secResumen')}</h3>
        <p><strong>${resumen}</strong></p>
      </div>
      <div class="gemini-section">
        <h3 class="blue">${t('secSuitability')}</h3>
        <p>${indicado_para}</p>
      </div>
      <div class="gemini-section">
        <h3 class="orange">${t('secRisks')}</h3>
        ${riskHtml}
      </div>
      <div class="gemini-section">
        <h3 class="blue">${t('secEvaluation')}</h3>
        <p>${explicacion_general}</p>
      </div>
      <div class="gemini-section">
        <h3 class="green">${t('secRecommendations')}</h3>
        ${recsHtml}
      </div>
      ${altsHtml}
    </div>

    ${sourcesHtml([...sources, { label: 'Gemini AI', url: 'https://deepmind.google/technologies/gemini/' }])}
    <div class="card-footer">
      <button class="btn-secondary" onclick="resetToMain(true)">${t('btnBackCompat')}</button>
    </div>
  </div>`;
}

// ─────────────────────────────────────────
// MODE 2B: RENDER COMPAT RESULT (fallback)
// ─────────────────────────────────────────

function renderCompat(data) {
  const { drug_name, verdict, flags, generic_risks, alternatives, suitability, explanation, sources } = data;
  const col = sectionColor(verdict);

  let safetyHtml;
  if (flags.length === 0 && generic_risks.length === 0) {
    safetyHtml = `<p>${t('noRisks')}</p>`;
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
    safetyHtml = `<ul style="margin-top:10px; padding-left:18px; font-size:0.92rem; color:#374151; line-height:1.7">
      ${generic_risks.map(r => `<li>${r}</li>`).join('')}
    </ul>`;
  }

  let altsHtml = '';
  if ((verdict === 'risky' || verdict === 'not-recommended') && alternatives.length > 0) {
    altsHtml = `
    <div class="compat-section">
      <h3 class="blue">${t('secAlternatives')}</h3>
      <p style="margin-bottom:12px">${t('altSubtext')}</p>
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
        <h2>${t('geminiAnalysis').replace(':', '')} <span style="color:var(--blue)">${drug_name}</span></h2>
        <p>${t('geminiEvalFor')}</p>
      </div>
      ${verdictBadge(verdict)}
    </div>
    <div class="compat-sections">
      <div class="compat-section">
        <h3 class="${suitability.match ? 'green' : 'gray'}">${t('secSuitability')}</h3>
        <div class="suitability-row">
          <div class="suit-indicator ${suitability.match ? 'green' : 'gray'}"></div>
          <p>${suitability.text}</p>
        </div>
      </div>
      <div class="compat-section">
        <h3 class="${col}">${t('secRisks')}</h3>
        ${safetyHtml}
      </div>
      <div class="compat-section">
        <h3 class="blue">${t('secEvaluation')}</h3>
        <p>${explanation}</p>
      </div>
      ${altsHtml}
    </div>
    ${sourcesHtml(sources || defaultSources)}
    <div class="card-footer">
      <button class="btn-secondary" onclick="resetToMain(true)">${t('btnBackCompat')}</button>
    </div>
  </div>`;
}

// ─────────────────────────────────────────
// NAVIGATION HELPERS
// ─────────────────────────────────────────

function resetToMain(keepCompatMode) {
  lastRender  = null;
  lastQuery   = null;
  renderCache = {};
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
  const btn        = document.getElementById('toggle-btn');
  const patientWrap = document.getElementById('patient-wrap');

  btn.classList.toggle('active', compatMode);
  btn.setAttribute('aria-pressed', compatMode);
  patientWrap.classList.toggle('visible', compatMode);

  updateStaticUI();
}

// ─────────────────────────────────────────
// MAIN ACTION
// ─────────────────────────────────────────

async function handleAction() {
  const medQuery    = document.getElementById('med-input').value.trim();
  const patientText = document.getElementById('patient-input').value.trim();
  const errorBox    = document.getElementById('error-box');
  const apiBanner   = document.getElementById('api-error-banner');

  if (!medQuery) {
    errorBox.style.display = 'block';
    document.getElementById('med-input').focus();
    setTimeout(() => { errorBox.style.display = 'none'; }, 3000);
    return;
  }
  errorBox.style.display = 'none';
  apiBanner.style.display = 'none';

  // Guardar query y limpiar caché solo si es una nueva búsqueda
  if (!lastQuery || lastQuery.medQuery !== medQuery || lastQuery.patientText !== patientText) {
    lastQuery   = { medQuery, patientText };
    renderCache = {};
    lastRender  = null;
  }

  const useGeminiForSheet = !compatMode && getAiRemaining() > 5;

  document.getElementById('initial-screen').style.display = 'none';
  const resultSection = document.getElementById('result-section');
  resultSection.style.display = 'block';
  const loadingMsg = compatMode
    ? t('loadingGeminiCompat')
    : useGeminiForSheet
      ? t('loadingGeminiSheet')
      : t('loadingStandard');
  resultSection.innerHTML = `<div class="loading-wrap"><div class="spinner"></div><p>${loadingMsg}</p></div>`;
  window.scrollTo({ top: 0, behavior: 'smooth' });

  try {
    let html;

    if (compatMode) {
      incrementAiUsage();
      const geminiData = await apiGeminiCompatibility(medQuery, patientText, medQuery);
      lastRender = null;
      html = renderGeminiReport(geminiData);
      renderCache[currentLang] = html;
      // Pre-cache the other language in background (no extra AI counter: included in session)
      prefetchOtherLang(() => apiGeminiCompatibility(medQuery, patientText, medQuery), renderGeminiReport);

    } else if (useGeminiForSheet) {
      incrementAiUsage();
      const geminiSheetData = await apiGeminiSheet(medQuery);

      if (!geminiSheetData.error) {
        lastRender = null;
        html = renderGeminiSheet(geminiSheetData);
        renderCache[currentLang] = html;
        // Pre-cache the other language in background
        prefetchOtherLang(() => apiGeminiSheet(medQuery), renderGeminiSheet);
      } else {
        const [searchData, externalData] = await Promise.allSettled([
          apiSearchDrug(medQuery),
          apiExternalDrug(medQuery),
        ]);
        const local = searchData.status === 'fulfilled' ? searchData.value : null;
        const ext   = externalData.status === 'fulfilled' ? externalData.value : null;
        if (local && local.found) {
          lastRender = { fn: renderMedSheet, args: [local.drug, ext] };
          html = renderMedSheet(local.drug, ext);
        } else {
          lastRender = { fn: renderUnknownMedSheet, args: [medQuery, ext] };
          html = renderUnknownMedSheet(medQuery, ext);
        }
      }

    } else {
      const [searchData, externalData] = await Promise.allSettled([
        apiSearchDrug(medQuery),
        apiExternalDrug(medQuery),
      ]);
      const local = searchData.status === 'fulfilled' ? searchData.value : null;
      const ext   = externalData.status === 'fulfilled' ? externalData.value : null;
      if (local && local.found) {
        lastRender = { fn: renderMedSheet, args: [local.drug, ext] };
        html = renderMedSheet(local.drug, ext);
      } else {
        lastRender = { fn: renderUnknownMedSheet, args: [medQuery, ext] };
        html = renderUnknownMedSheet(medQuery, ext);
      }
    }

    resultSection.innerHTML = html;
  } catch (err) {
    resultSection.innerHTML = '';
    document.getElementById('initial-screen').style.display = '';
    apiBanner.textContent = `${t('errorServer')} ${API_BASE}`;
    apiBanner.style.display = 'block';
    setTimeout(() => { apiBanner.style.display = 'none'; }, 6000);
  }
}

// ─────────────────────────────────────────
// EVENT LISTENERS
// ─────────────────────────────────────────

document.getElementById('toggle-btn').addEventListener('click', toggleMode);
document.getElementById('action-btn').addEventListener('click', handleAction);

document.getElementById('med-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !compatMode) handleAction();
  if (e.key === 'Enter' && compatMode && e.ctrlKey) handleAction();
});
document.getElementById('patient-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.ctrlKey) handleAction();
});

// Init
setLang(currentLang);
renderAiCounter();

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
    gemini_err_title: 'Error de Gemini',
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
    lang_btn:         'EN',
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
    gemini_err_title: 'Gemini Error',
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
    lang_btn:         'ES',
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
  const langBtn = document.getElementById('lang-btn');
  if (langBtn) langBtn.textContent = t('lang_btn');
  document.documentElement.lang = currentLang;
  updateActionBtn();
}

function toggleLang() {
  currentLang = currentLang === 'es' ? 'en' : 'es';
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
  const namePrefix = currentLang === 'es' ? 'El nombre' : 'The name';
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
    return `<div class="compat-card">
      <div class="compat-header">
        <div class="compat-header-left"><h2>${t('gemini_err_title')}</h2><p>${data.error}</p></div>
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

    resultSection.innerHTML = html;
  } catch (err) {
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
document.getElementById('lang-btn').addEventListener('click', toggleLang);
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

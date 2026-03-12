/**
 * PharmaCheck — Frontend
 * Toda la lógica de datos y análisis vive en el backend (Python/FastAPI).
 * Este archivo solo maneja UI, rendering y llamadas a la API.
 */

const API_BASE = 'http://localhost:8000';

let compatMode = false;

// ─────────────────────────────────────────
// API CALLS
// ─────────────────────────────────────────

async function apiSearchDrug(query) {
  const res = await fetch(`${API_BASE}/api/drugs/search?query=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function apiCompatibility(drugName, patientText, symptomText = '') {
  const res = await fetch(`${API_BASE}/api/drugs/compatibility`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ drug_name: drugName, patient_text: patientText, symptom_text: symptomText }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function apiGeminiCompatibility(drugName, patientText, symptomText = '') {
  const res = await fetch(`${API_BASE}/api/drugs/gemini-compatibility`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ drug_name: drugName, patient_text: patientText, symptom_text: symptomText }),
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
    'suitable':        { cls: 'suitable',        icon: '✅', text: 'Adecuado' },
    'risky':           { cls: 'risky',            icon: '⚠️', text: 'Potencialmente arriesgado' },
    'not-recommended': { cls: 'not-recommended',  icon: '🚫', text: 'No recomendado' },
    'uncertain':       { cls: 'uncertain',        icon: '❓', text: 'Incierto' },
  };
  const v = map[verdict] || map['uncertain'];
  return `<span class="verdict-badge ${v.cls}">${v.icon} ${v.text}</span>`;
}

function sectionColor(verdict) {
  return { suitable: 'green', risky: 'orange', 'not-recommended': 'red', uncertain: 'gray' }[verdict] || 'gray';
}

function indicatorClass(verdict) {
  return sectionColor(verdict);
}

function sourcesHtml(sources) {
  return `<div class="sources-bar">
    <span>📚 Fuentes:</span>
    ${sources.map(s => `<a class="source-link" href="${s.url}" target="_blank" rel="noopener">🔗 ${s.label}</a>`).join('')}
  </div>`;
}

function externalBoxHtml(ext) {
  if (!ext || !ext.found) return '';
  const rows = [
    ext.brand_name     && `<p><strong>Nombre comercial:</strong> ${ext.brand_name}</p>`,
    ext.generic_name   && `<p><strong>Nombre genérico:</strong> ${ext.generic_name}</p>`,
    ext.manufacturer   && `<p><strong>Fabricante:</strong> ${ext.manufacturer}</p>`,
    ext.route          && `<p><strong>Vía:</strong> ${ext.route}</p>`,
    ext.indications    && `<p><strong>Indicaciones (FDA):</strong> ${ext.indications}</p>`,
    ext.warnings       && `<p><strong>Advertencias (FDA):</strong> ${ext.warnings}</p>`,
  ].filter(Boolean).join('');
  if (!rows) return '';
  return `<div class="external-box"><h4>🌐 Datos OpenFDA (oficial)</h4>${rows}</div>`;
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
        <h3 class="green">🎯 Para qué se usa</h3>
        <p>${med.uses}</p>
      </div>
      <div class="med-section">
        <h3 class="orange">⚠️ Efectos secundarios</h3>
        <ul>${med.sideEffects.map(e => `<li>${e}</li>`).join('')}</ul>
      </div>
      <div class="med-section">
        <h3 class="red">🚫 Cuándo NO usar</h3>
        <ul>${med.notFor.map(e => `<li>${e}</li>`).join('')}</ul>
      </div>
      <div class="med-section">
        <h3 class="blue">⚙️ Restricciones</h3>
        <ul>${med.restrictions.map(e => `<li>${e}</li>`).join('')}</ul>
      </div>
      <div class="fact-box">
        <div class="fact-icon">💡</div>
        <p><strong>Dato curioso: </strong>${med.fact}</p>
      </div>
    </div>
    ${externalBoxHtml(externalData)}
    ${sourcesHtml(med.sources)}
    <div class="card-footer">
      <button class="btn-secondary" onclick="resetToMain(false)">← Otro medicamento</button>
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
        <div class="med-class">Medicamento — clase no identificada</div>
        <div class="med-dosage">📏 Consultar prospecto o profesional sanitario</div>
      </div>
    </div>
    <div class="med-body">
      <div class="med-section" style="grid-column:1/-1">
        <h3 class="gray">ℹ️ Información no disponible</h3>
        <p>El nombre "<strong>${medName}</strong>" no ha sido reconocido en la base de datos local. Consulta las fuentes oficiales para información precisa.</p>
      </div>
    </div>
    ${externalBoxHtml(externalData)}
    ${sourcesHtml(sources)}
    <div class="card-footer">
      <button class="btn-secondary" onclick="resetToMain(false)">← Otro medicamento</button>
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
        <div class="compat-header-left"><h2>Error de Gemini</h2><p>${data.error}</p></div>
      </div>
      <div class="card-footer"><button class="btn-secondary" onclick="resetToMain(true)">← Otro caso</button></div>
    </div>`;
  }

  const { drug_name, verdict, resumen, indicado_para, factores_riesgo = [],
          explicacion_general, recomendaciones = [], alternativas = [],
          advertencia_critica, sources = [] } = data;

  // Factores de riesgo
  const riskHtml = factores_riesgo.length
    ? factores_riesgo.map(f => `
        <div class="risk-row">
          <div class="risk-dot ${f.nivel}"></div>
          <div class="risk-content">
            <strong>${f.factor} <span class="risk-tag ${f.nivel}">${f.nivel.toUpperCase()}</span></strong>
            <p>${f.explicacion}</p>
          </div>
        </div>`).join('')
    : '<p>No se identificaron factores de riesgo específicos para este paciente.</p>';

  // Recomendaciones
  const recsHtml = recomendaciones.length
    ? `<ul>${recomendaciones.map(r => `<li>${r}</li>`).join('')}</ul>`
    : '<p>Seguir las indicaciones del prospecto oficial.</p>';

  // Alternativas
  const altsHtml = alternativas.length && (verdict === 'risky' || verdict === 'not-recommended')
    ? `<div class="gemini-section">
        <h3 class="blue">🔄 Alternativas posibles</h3>
        <div class="alt-list">
          ${alternativas.map(a => `<span class="alt-pill" onclick="goToMedSheet('${a}')">💊 ${a}</span>`).join('')}
        </div>
      </div>`
    : '';

  // Advertencia crítica
  const criticalHtml = advertencia_critica
    ? `<div class="critical-warning">⛔ ${advertencia_critica}</div>`
    : '';

  return `
  <div class="gemini-card">
    <div class="gemini-header">
      <div class="gemini-header-left">
        <h2>Análisis IA: <span style="color:var(--blue)">${drug_name}</span></h2>
        <p>
          <span class="gemini-badge">✨ Gemini AI</span>
          Informe generado por inteligencia artificial · Solo orientativo
        </p>
      </div>
      ${verdictBadge(verdict)}
    </div>

    ${criticalHtml ? `<div style="padding: 16px 36px 0">${criticalHtml}</div>` : ''}

    <div class="gemini-body">
      <div class="gemini-section">
        <h3 class="${verdict === 'suitable' ? 'green' : verdict === 'not-recommended' ? 'red' : 'orange'}">
          📋 Resumen
        </h3>
        <p><strong>${resumen}</strong></p>
      </div>

      <div class="gemini-section">
        <h3 class="blue">🎯 Idoneidad para la condición</h3>
        <p>${indicado_para}</p>
      </div>

      <div class="gemini-section">
        <h3 class="orange">🛡️ Factores de riesgo identificados</h3>
        ${riskHtml}
      </div>

      <div class="gemini-section">
        <h3 class="blue">📄 Evaluación clínica</h3>
        <p>${explicacion_general}</p>
      </div>

      <div class="gemini-section">
        <h3 class="green">✅ Recomendaciones</h3>
        ${recsHtml}
      </div>

      ${altsHtml}
    </div>

    ${sourcesHtml([...sources, { label: 'Gemini AI', url: 'https://deepmind.google/technologies/gemini/' }])}

    <div class="card-footer">
      <button class="btn-secondary" onclick="resetToMain(true)">← Otro caso</button>
    </div>
  </div>`;
}

// ─────────────────────────────────────────
// MODE 2B: RENDER COMPAT RESULT (fallback)
// ─────────────────────────────────────────

function renderCompat(data) {
  const { drug_name, verdict, flags, generic_risks, alternatives, suitability, explanation, sources, found } = data;
  const col = sectionColor(verdict);

  // Safety section
  let safetyHtml;
  if (flags.length === 0 && generic_risks.length === 0) {
    safetyHtml = `<p>No se identificaron factores de riesgo específicos en la información del paciente.</p>`;
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
    // generic risks for unknown drug
    safetyHtml = `<p>Factores de riesgo generales identificados:</p>
      <ul style="margin-top:10px; padding-left:18px; font-size:0.92rem; color:#374151; line-height:1.7">
        ${generic_risks.map(r => `<li>${r}</li>`).join('')}
      </ul>`;
  }

  // Alternatives
  let altsHtml = '';
  if ((verdict === 'risky' || verdict === 'not-recommended') && alternatives.length > 0) {
    altsHtml = `
    <div class="compat-section">
      <h3 class="blue">🔄 Alternativas posibles</h3>
      <p style="margin-bottom:12px">Las siguientes alternativas podrían ser más adecuadas. Haz clic para ver su ficha.</p>
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
        <h2>Análisis de concordancia: <span style="color:var(--blue)">${drug_name}</span></h2>
        <p>Evaluación para el perfil de paciente descrito</p>
      </div>
      ${verdictBadge(verdict)}
    </div>
    <div class="compat-sections">
      <div class="compat-section">
        <h3 class="${suitability.match ? 'green' : 'gray'}">🎯 Idoneidad para la condición</h3>
        <div class="suitability-row">
          <div class="suit-indicator ${suitability.match ? 'green' : 'gray'}"></div>
          <p>${suitability.text}</p>
        </div>
      </div>
      <div class="compat-section">
        <h3 class="${col}">🛡️ Seguridad para el paciente</h3>
        ${safetyHtml}
      </div>
      <div class="compat-section">
        <h3 class="blue">📋 Explicación</h3>
        <p>${explanation}</p>
      </div>
      ${altsHtml}
    </div>
    ${sourcesHtml(sources || defaultSources)}
    <div class="card-footer">
      <button class="btn-secondary" onclick="resetToMain(true)">← Otro caso</button>
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
  const actionBtn = document.getElementById('action-btn');
  const medInput = document.getElementById('med-group');

  btn.classList.toggle('active', compatMode);
  btn.setAttribute('aria-pressed', compatMode);
  patientWrap.classList.toggle('visible', compatMode);

  if (compatMode) {
    actionBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg> Análisis de concordancia`;
    medInput.querySelector('label').textContent = '💊 Medicamento';
  } else {
    actionBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/></svg> Ficha de medicamento`;
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
    errorBox.style.display = 'block';
    document.getElementById('med-input').focus();
    setTimeout(() => { errorBox.style.display = 'none'; }, 3000);
    return;
  }
  errorBox.style.display = 'none';
  apiBanner.style.display = 'none';

  // Show loading
  document.getElementById('initial-screen').style.display = 'none';
  const resultSection = document.getElementById('result-section');
  resultSection.style.display = 'block';
  const loadingMsg = compatMode
    ? 'Generando informe con Gemini AI…'
    : 'Consultando base de datos médica…';
  resultSection.innerHTML = `<div class="loading-wrap"><div class="spinner"></div><p>${loadingMsg}</p></div>`;
  window.scrollTo({ top: 0, behavior: 'smooth' });

  try {
    let html;

    if (compatMode) {
      const geminiData = await apiGeminiCompatibility(medQuery, patientText, medQuery);
      html = renderGeminiReport(geminiData);
    } else {
      // Buscar en local y en OpenFDA en paralelo
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
    apiBanner.textContent = `⚠️ No se pudo conectar con el servidor. Verifica que el backend esté corriendo en ${API_BASE}`;
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

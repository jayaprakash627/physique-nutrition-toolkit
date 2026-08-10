/* =============================================================================
 *  app.js — the controller: state, events, and wiring.
 * =============================================================================
 *  Reads the form, calls the API, hands the response to Render, then draws any
 *  charts the new markup contains. Deliberately the only file that touches
 *  global state, so there's one place to look when behaviour is confusing.
 * ========================================================================== */

const State = {
  meta: null,          // /api/meta — option lists and help text
  lastAssessment: null,
  activeClientId: null,
};

/* =============================================================================
 *  Theme
 * ========================================================================== */

function initTheme() {
  // Remembered choice wins; otherwise follow the OS preference.
  const saved = localStorage.getItem('pnt-theme');
  const prefersLight = window.matchMedia?.('(prefers-color-scheme: light)').matches;
  setTheme(saved || (prefersLight ? 'light' : 'dark'));

  document.getElementById('themeToggle').addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('pnt-theme', next);
    // Canvas colours are baked in at draw time, so charts must be repainted.
    Charts.redrawAll();
  });
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.getElementById('themeIcon').textContent = theme === 'dark' ? '☀' : '☾';
}

/* =============================================================================
 *  Tabs
 * ========================================================================== */

function initTabs() {
  const tabs = document.querySelectorAll('.tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.setAttribute('aria-selected', 'false'));
      tab.setAttribute('aria-selected', 'true');

      document.querySelectorAll('.panel').forEach(p => { p.hidden = true; });
      document.getElementById(`panel-${tab.dataset.tab}`).hidden = false;
      window.scrollTo({ top: 0, behavior: 'smooth' });

      // Lazy-load the tabs whose content comes from the API.
      if (tab.dataset.tab === 'sources') loadSources();
      if (tab.dataset.tab === 'learn') loadLearn();
      if (tab.dataset.tab === 'clients') loadClients();

      // A chart inside a hidden panel measures its container as 0 wide, so
      // anything drawn while hidden needs a repaint once it's visible.
      Charts.redrawAll();
    });
  });
}

/* =============================================================================
 *  Bootstrap — populate every dropdown from /api/meta
 * ========================================================================== */

async function loadMeta() {
  try {
    State.meta = await API.meta();
  } catch (e) {
    toast(e.message, true);
    return;
  }
  const m = State.meta;

  const fill = (id, obj, selected) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = Object.entries(obj).map(([k, v]) => {
      const label = typeof v === 'string' ? v : v.label;
      return `<option value="${esc(k)}"${k === selected ? ' selected' : ''}>${esc(label)}</option>`;
    }).join('');
  };

  fill('goal', m.goals, 'cut');
  fill('activity', m.activity_levels, 'moderate');
  fill('diet', m.diets, 'omnivore');
  fill('climate', m.climates, 'hot');
  fill('c_diet', m.diets, 'omnivore');
  fill('c_goal', m.goals, 'cut');

  document.getElementById('disclaimerTop').innerHTML =
    `<strong>Read this first:</strong> ${esc(m.disclaimer)}`;
  document.getElementById('disclaimerBottom').innerHTML =
    `<strong>Not medical advice.</strong> ${esc(m.disclaimer)} <br><br>${esc(m.safeguarding)}`;

  document.getElementById('techniqueHint').textContent = m.measurement_help.technique;

  const g = m.measurement_help.girths;
  document.getElementById('girthHelp').innerHTML =
    `<strong>Neck:</strong> ${esc(g.neck)}<br>
     <strong>Waist:</strong> ${esc(g.waist)}<br>
     <strong>Hip:</strong> ${esc(g.hip)}`;

  const s = m.measurement_help.skinfolds;
  document.getElementById('skinfoldHelp').innerHTML =
    Object.entries(s).map(([k, v]) =>
      `<strong>${esc(k)}:</strong> ${esc(v)}`).join('<br>');

  updateSexDependentUI();
}

/**
 * Show only the fields the chosen sex actually needs.
 *
 * This isn't cosmetic: the Navy equation needs hip circumference for women and
 * not for men, and the JP 3-site equations use different sites per sex. Showing
 * all of them invites people to fill in fields that will be ignored.
 */
function updateSexDependentUI() {
  const sex = segValue('sex');
  const hipField = document.getElementById('hipField');
  if (hipField) {
    hipField.style.display = sex === 'female' ? '' : 'none';
    if (sex === 'female') {
      hipField.querySelector('label').innerHTML = 'Hip (cm) <span style="color:var(--caution)">*</span>';
    }
  }

  // Mark the 3-site skinfolds this sex needs.
  const needed = sex === 'male'
    ? ['s_chest', 's_abdomen', 's_thigh']
    : ['s_triceps', 's_suprailiac', 's_thigh'];
  ['s_chest', 's_abdomen', 's_thigh', 's_triceps', 's_suprailiac'].forEach(id => {
    const label = document.querySelector(`label[for="${id}"]`);
    if (!label) return;
    const base = label.textContent.replace(' ★', '');
    label.textContent = needed.includes(id) ? base + ' ★' : base;
  });
}

/* =============================================================================
 *  Full assessment
 * ========================================================================== */

function assessPayload() {
  const girths = {
    neck: numVal('g_neck'),
    waist: numVal('g_waist'),
    hip: numVal('g_hip'),
  };
  const skinfolds = {
    chest: numVal('s_chest'),
    abdomen: numVal('s_abdomen'),
    thigh: numVal('s_thigh'),
    triceps: numVal('s_triceps'),
    suprailiac: numVal('s_suprailiac'),
    subscapular: numVal('s_subscapular'),
    midaxillary: numVal('s_midaxillary'),
  };

  // Send null rather than an all-null object, so the backend's "did they give me
  // anything?" checks stay simple.
  const anyGirth = Object.values(girths).some(v => v !== null);
  const anySkin = Object.values(skinfolds).some(v => v !== null);

  return {
    sex: segValue('sex'),
    age: numVal('age'),
    weight_kg: numVal('weight'),
    height_cm: numVal('height'),
    goal: document.getElementById('goal').value,
    activity: document.getElementById('activity').value,
    diet: document.getElementById('diet').value,
    climate: document.getElementById('climate').value,
    training_hours: numVal('trainingHours') ?? 0,
    meals: numVal('meals') ?? 4,
    girths: anyGirth ? girths : null,
    skinfolds: anySkin ? skinfolds : null,
    bodyfat_pct: numVal('bodyfatPct'),
    target_bodyfat_pct: numVal('targetBf'),
    contest_prep: document.getElementById('contestPrep').checked,
    pregnant: document.getElementById('pregnant').checked,
    medical_conditions: document.getElementById('medicalConditions').checked,
  };
}

async function runAssessment(e) {
  e.preventDefault();
  const btn = document.getElementById('assessBtn');
  const out = document.getElementById('assessResults');

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Building…';
  out.innerHTML = '<div class="card center"><div class="spinner" style="margin:0 auto"></div></div>';

  try {
    const r = await API.assess(assessPayload());
    State.lastAssessment = r;

    Charts.reset();
    out.innerHTML = Render.assessment(r);

    // Draw the macro donut now that its canvas exists in the DOM.
    const n = r.nutrition;
    Charts.donut(
      document.getElementById('macroDonut'),
      [
        { value: n.protein.kcal, colorVar: '--c-protein' },
        { value: n.fat.kcal, colorVar: '--c-fat' },
        { value: n.carbs.kcal, colorVar: '--c-carbs' },
      ],
      num(n.kcal.number),
      'kcal/day',
    );

    out.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (err) {
    out.innerHTML = `<div class="card"><div class="flag flag--danger">
      <div class="flag__title"><span class="flag__level">error</span>Couldn't build the plan</div>
      <p class="flag__msg">${esc(err.message)}</p>
    </div></div>`;
    toast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Build my plan';
  }
}

/* =============================================================================
 *  Body fat comparison
 * ========================================================================== */

async function runBodyfat(e) {
  e.preventDefault();
  const out = document.getElementById('bfResults');
  out.innerHTML = '<div class="card center"><div class="spinner" style="margin:0 auto"></div></div>';

  const girths = { neck: numVal('bf_neck'), waist: numVal('bf_waist'), hip: numVal('bf_hip') };
  const skinfolds = {
    chest: numVal('bf_s_chest'), abdomen: numVal('bf_s_abdomen'), thigh: numVal('bf_s_thigh'),
    triceps: numVal('bf_s_triceps'), suprailiac: numVal('bf_s_suprailiac'),
    subscapular: numVal('bf_s_subscapular'), midaxillary: numVal('bf_s_midaxillary'),
  };

  try {
    const r = await API.bodyfat({
      sex: segValue('bfSex'),
      age: numVal('bf_age'),
      weight_kg: numVal('bf_weight'),
      height_cm: numVal('bf_height'),
      girths: Object.values(girths).some(v => v !== null) ? girths : null,
      skinfolds: Object.values(skinfolds).some(v => v !== null) ? skinfolds : null,
    });

    if (!r.chosen) {
      out.innerHTML = `<div class="card"><div class="empty">
        <p>No method could run with those inputs. Add neck and waist, or three skinfolds.</p>
      </div></div>`;
      return;
    }
    Charts.reset();
    out.innerHTML = Render.bodyfatCard(r);
  } catch (err) {
    out.innerHTML = `<div class="card"><div class="flag flag--danger">
      <div class="flag__title"><span class="flag__level">error</span>Couldn't compare methods</div>
      <p class="flag__msg">${esc(err.message)}</p></div></div>`;
  }
}

/* =============================================================================
 *  Prep planner
 * ========================================================================== */

async function runPrep(e) {
  e.preventDefault();
  const out = document.getElementById('prepResults');
  out.innerHTML = '<div class="card center"><div class="spinner" style="margin:0 auto"></div></div>';

  try {
    const r = await API.prepPlan({
      sex: segValue('prepSex'),
      weight_kg: numVal('p_weight'),
      current_bodyfat_pct: numVal('p_current'),
      target_bodyfat_pct: numVal('p_target'),
      weeks: numVal('p_weeks'),
    });

    Charts.reset();
    out.innerHTML = Render.prep(r);

    // Two series on one axis: body fat % and weight in kg. Their ranges differ
    // wildly (12–20 vs 75–85), so the chart normalises weight onto the body-fat
    // scale for shape comparison — the table beside it carries exact values.
    const proj = r.plan.projection;
    const bfPoints = proj.map(p => ({ x: p.week, y: p.bodyfat_pct }));
    const wMin = Math.min(...proj.map(p => p.weight_kg));
    const wMax = Math.max(...proj.map(p => p.weight_kg));
    const bMin = Math.min(...bfPoints.map(p => p.y));
    const bMax = Math.max(...bfPoints.map(p => p.y));
    const scaleW = w => (wMax === wMin)
      ? (bMin + bMax) / 2
      : bMin + ((w - wMin) / (wMax - wMin)) * (bMax - bMin);

    Charts.line(
      document.getElementById('prepChart'),
      [
        { label: 'Body fat %', points: bfPoints, colorVar: '--c-carbs' },
        {
          label: 'Weight (scaled)',
          points: proj.map(p => ({ x: p.week, y: scaleW(p.weight_kg) })),
          colorVar: '--c-protein',
          dashed: true,
        },
      ],
      { xLabel: 'Week', yLabel: 'Body fat', yUnit: '%' },
    );
  } catch (err) {
    out.innerHTML = `<div class="card"><div class="flag flag--danger">
      <div class="flag__title"><span class="flag__level">error</span>Couldn't build the projection</div>
      <p class="flag__msg">${esc(err.message)}</p></div></div>`;
  }
}

/* =============================================================================
 *  Strength
 * ========================================================================== */

async function runStrength(e) {
  e.preventDefault();
  const out = document.getElementById('strResults');
  out.innerHTML = '<div class="card center"><div class="spinner" style="margin:0 auto"></div></div>';

  try {
    const r = await API.strength({
      weight: numVal('st_weight'),
      reps: numVal('st_reps'),
      sex: segValue('strSex'),
      bodyweight_kg: numVal('st_bw'),
      total_kg: numVal('st_total'),
    });
    out.innerHTML = Render.strength(r);
  } catch (err) {
    out.innerHTML = `<div class="card"><div class="flag flag--danger">
      <div class="flag__title"><span class="flag__level">error</span>Couldn't calculate</div>
      <p class="flag__msg">${esc(err.message)}</p></div></div>`;
  }
}

/* =============================================================================
 *  Sources tab
 * ========================================================================== */

let _sourcesLoaded = false;
async function loadSources() {
  if (_sourcesLoaded) return;
  try {
    const r = await API.sources();
    document.getElementById('sourceList').innerHTML = Render.sources(r);
    _sourcesLoaded = true;
  } catch (e) {
    document.getElementById('sourceList').innerHTML =
      `<div class="card"><p class="muted">${esc(e.message)}</p></div>`;
  }
}

/* =============================================================================
 *  Micronutrient reference tab
 * ========================================================================== */

async function loadLearn() {
  const sex = segValue('learnSex') || 'male';
  const panel = document.getElementById('learnPanel');
  panel.innerHTML = '<div class="spinner"></div>';
  try {
    const r = await API.micronutrients(sex);
    panel.innerHTML = Render.microRows(r.panel);

    document.getElementById('riskDefs').innerHTML =
      Object.entries(r.risk_definitions).map(([, v]) => `
        <div class="risk-card">
          <div class="risk-card__label">${esc(v.label)}</div>
          <p class="risk-card__why">${esc(v.why)}</p>
          <div class="pills" style="margin-top:var(--sp-3)">
            ${v.watch.map(w => `<span class="chip">${esc(w.replace(/_/g, ' '))}</span>`).join('')}
          </div>
        </div>`).join('');
  } catch (e) {
    panel.innerHTML = `<p class="muted">${esc(e.message)}</p>`;
  }
}

/* =============================================================================
 *  Clients & tracking
 * ========================================================================== */

async function loadClients() {
  try {
    const { clients } = await API.clients();
    document.getElementById('clientList').innerHTML =
      Render.clientList(clients, State.activeClientId);
  } catch (e) {
    toast(e.message, true);
  }
}

async function openClient(id) {
  State.activeClientId = id;
  const out = document.getElementById('clientDetail');
  out.innerHTML = '<div class="card center"><div class="spinner" style="margin:0 auto"></div></div>';

  try {
    const d = await API.client(id);
    Charts.reset();
    out.innerHTML = Render.clientDetail(d);

    // Default the date field to today, so logging is one field less.
    const dateEl = document.getElementById('m_date');
    if (dateEl) dateEl.value = new Date().toISOString().slice(0, 10);

    // Trend chart — x is days since the first measurement, so unevenly spaced
    // weigh-ins plot at their true distance apart rather than evenly.
    if (d.measurements.length >= 2) {
      const t0 = new Date(d.measurements[0].taken_on).getTime();
      const days = m => (new Date(m.taken_on).getTime() - t0) / 86400000;

      const series = [{
        label: 'Weight',
        points: d.measurements.map(m => ({ x: days(m), y: m.weight_kg })),
        colorVar: '--c-protein',
      }];

      const withBf = d.measurements.filter(m => m.bodyfat_pct !== null);
      if (withBf.length >= 2) {
        // Scale body fat onto the weight axis so both fit one chart.
        const wVals = d.measurements.map(m => m.weight_kg);
        const wMin = Math.min(...wVals), wMax = Math.max(...wVals);
        const bVals = withBf.map(m => m.bodyfat_pct);
        const bMin = Math.min(...bVals), bMax = Math.max(...bVals);
        series.push({
          label: 'Body fat (scaled)',
          points: withBf.map(m => ({
            x: days(m),
            y: bMax === bMin ? (wMin + wMax) / 2
              : wMin + ((m.bodyfat_pct - bMin) / (bMax - bMin)) * (wMax - wMin),
          })),
          colorVar: '--c-carbs',
          dashed: true,
        });
      }

      Charts.line(document.getElementById('clientChart'), series,
        { xLabel: 'Days since first measurement', yLabel: 'Weight', yUnit: 'kg' });
    }

    await loadClients();   // refresh the list so the active item highlights
  } catch (e) {
    out.innerHTML = `<div class="card"><p class="muted">${esc(e.message)}</p></div>`;
  }
}

async function createClient(e) {
  e.preventDefault();
  try {
    const c = await API.createClient({
      name: document.getElementById('c_name').value.trim(),
      sex: segValue('cSex'),
      age: numVal('c_age'),
      height_cm: numVal('c_height'),
      diet: document.getElementById('c_diet').value,
      goal: document.getElementById('c_goal').value,
      notes: document.getElementById('c_notes').value.trim() || null,
    });
    document.getElementById('clientForm').reset();
    toast(`${c.name} added`);
    await loadClients();
    await openClient(c.id);
  } catch (err) {
    toast(err.message, true);
  }
}

async function addMeasurement(e) {
  e.preventDefault();
  const id = Number(e.target.dataset.client);
  try {
    await API.addMeasurement(id, {
      taken_on: document.getElementById('m_date').value,
      weight_kg: numVal('m_weight'),
      bodyfat_pct: numVal('m_bf'),
      waist_cm: numVal('m_waist'),
      chest_cm: numVal('m_chest'),
      arm_cm: numVal('m_arm'),
      thigh_cm: numVal('m_thigh'),
      note: document.getElementById('m_note').value.trim() || null,
    });
    toast('Measurement logged');
    await openClient(id);
  } catch (err) {
    toast(err.message, true);
  }
}

/**
 * Delegated click handling for the clients panel.
 *
 * The client list and detail view are both re-rendered wholesale, so binding
 * listeners to individual buttons would mean re-binding after every render.
 * One listener on the panel handles all of them and survives re-renders.
 */
function initClientEvents() {
  document.getElementById('panel-clients').addEventListener('click', async e => {
    const pick = e.target.closest('[data-client]');
    if (pick && !e.target.closest('form')) {
      openClient(Number(pick.dataset.client));
      return;
    }

    const del = e.target.closest('#deleteClientBtn');
    if (del) {
      const name = document.querySelector('#clientDetail h2')?.textContent || 'this client';
      if (!confirm(`Delete ${name} and all their measurements? This can't be undone.`)) return;
      try {
        await API.deleteClient(Number(del.dataset.id));
        State.activeClientId = null;
        document.getElementById('clientDetail').innerHTML =
          '<div class="empty"><p>Client deleted.</p></div>';
        toast('Client deleted');
        await loadClients();
      } catch (err) { toast(err.message, true); }
      return;
    }

    const delMeas = e.target.closest('[data-del-meas]');
    if (delMeas) {
      try {
        await API.deleteMeasurement(Number(delMeas.dataset.delMeas));
        toast('Measurement deleted');
        await openClient(State.activeClientId);
      } catch (err) { toast(err.message, true); }
    }
  });

  // Submit handler for the measurement form, which is also re-rendered.
  document.getElementById('panel-clients').addEventListener('submit', e => {
    if (e.target.id === 'measForm') addMeasurement(e);
  });
}

/* =============================================================================
 *  Init
 * ========================================================================== */

document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  initTabs();

  initSegs((name) => {
    if (name === 'sex') updateSexDependentUI();
    if (name === 'learnSex') loadLearn();
  });

  document.getElementById('assessForm').addEventListener('submit', runAssessment);
  document.getElementById('bfForm').addEventListener('submit', runBodyfat);
  document.getElementById('prepForm').addEventListener('submit', runPrep);
  document.getElementById('strForm').addEventListener('submit', runStrength);
  document.getElementById('clientForm').addEventListener('submit', createClient);
  initClientEvents();

  await loadMeta();
});

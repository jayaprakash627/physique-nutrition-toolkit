/* =============================================================================
 *  app.js — the controller: state, events, and wiring.
 * =============================================================================
 *  Reads the form, calls the API, hands the response to Render, then draws any
 *  charts the new markup contains. Deliberately the only file that touches
 *  global state, so there's one place to look when behaviour is confusing.
 *
 *  Two-step flow on the main tab: a short question card, then results. The form
 *  is replaced rather than sitting beside the answer, because user testing showed
 *  a permanent 20-field sidebar reads as homework and people bounced before ever
 *  seeing a number.
 * ========================================================================== */

const State = {
  meta: null,            // /api/meta — option lists and help text
  lastAssessment: null,
  activeClientId: null,
  detail: 'simple',      // 'simple' | 'full' — how much of the report to show
};

/* =============================================================================
 *  Theme & detail level
 * ========================================================================== */

function initTheme() {
  const saved = localStorage.getItem('pnt-theme');
  const prefersLight = window.matchMedia?.('(prefers-color-scheme: light)').matches;
  setTheme(saved || (prefersLight ? 'light' : 'dark'));

  document.getElementById('themeToggle').addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('pnt-theme', next);
    // Canvas colours are baked in at draw time, so charts need a repaint.
    Charts.redrawAll();
  });
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.getElementById('themeIcon').textContent = theme === 'dark' ? '☀' : '☾';
}

/**
 * Restore the remembered detail level.
 *
 * Defaults to 'simple' for anyone new. Someone who deliberately switched to full
 * detail last time is a coach, and shouldn't have to switch again every visit.
 */
function initDetail() {
  const saved = localStorage.getItem('pnt-detail');
  if (saved === 'full' || saved === 'simple') State.detail = saved;

  document.querySelectorAll('[data-seg="detail"] button').forEach(b => {
    b.setAttribute('aria-pressed', String(b.dataset.value === State.detail));
  });
}

function setDetail(level) {
  State.detail = level;
  localStorage.setItem('pnt-detail', level);
  // Re-render the existing result rather than making them resubmit.
  if (State.lastAssessment) showAssessment(State.lastAssessment);
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

      if (tab.dataset.tab === 'learn') loadLearn();
      // Re-check auth every time rather than caching it, so an expired session
      // shows the login form instead of a workspace of failing requests.
      if (tab.dataset.tab === 'coach') refreshCoachState();

      // A chart inside a hidden panel measures its container as 0 wide, so
      // anything drawn while hidden needs a repaint once it's visible.
      Charts.redrawAll();
    });
  });
}

/* =============================================================================
 *  Bootstrap
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

  fill('climate', m.climates, 'hot');
  fill('c_diet', m.diets, 'omnivore');
  fill('c_goal', m.goals, 'cut');

  document.getElementById('disclaimerTop').innerHTML =
    `${esc(m.disclaimer)}<br><br>${esc(m.safeguarding)}`;
  document.getElementById('disclaimerBottom').innerHTML =
    `<strong>Not medical advice.</strong> ${esc(m.disclaimer)}<br><br>${esc(m.safeguarding)}`;

  const g = m.measurement_help.girths;
  document.getElementById('girthHelp').innerHTML =
    `<strong>Neck:</strong> ${esc(g.neck)}<br>
     <strong>Waist:</strong> ${esc(g.waist)}<br>
     <strong>Hip:</strong> ${esc(g.hip)} <em>(women only — the equation needs it)</em>`;

  const sk = m.measurement_help.skinfolds;
  const skHelp = document.getElementById('skinfoldHelp');
  if (skHelp) {
    skHelp.innerHTML = Object.entries(sk)
      .map(([k, v]) => `<strong>${esc(k)}:</strong> ${esc(v)}`).join('<br>');
  }

  updateSexDependentUI();
}

/**
 * Hip circumference is only used by the female Navy equation, so hide it for
 * men rather than inviting them to fill a field that gets ignored.
 */
function updateSexDependentUI() {
  const hip = document.getElementById('hipField');
  if (hip) hip.style.display = segValue('sex') === 'female' ? '' : 'none';
}

/* =============================================================================
 *  The main flow: short form → results
 * ========================================================================== */

function quickPayload() {
  const girths = {
    neck: numVal('g_neck'),
    waist: numVal('g_waist'),
    hip: numVal('g_hip'),
  };
  const anyGirth = Object.values(girths).some(v => v !== null);

  return {
    sex: segValue('sex'),
    age: numVal('age'),
    weight_kg: numVal('weight'),
    height_cm: numVal('height'),
    goal: segValue('goal'),
    activity: segValue('activity'),
    diet: segValue('diet'),
    // Fine-tune fields, all with sensible defaults so skipping them is fine.
    climate: document.getElementById('climate').value || 'hot',
    training_hours: numVal('trainingHours') ?? 1,
    meals: numVal('meals') ?? 3,
    girths: anyGirth ? girths : null,
    skinfolds: null,            // callipers live in the Extra tools tab
    bodyfat_pct: numVal('bodyfatPct'),
    target_bodyfat_pct: numVal('targetBf'),
    contest_prep: document.getElementById('contestPrep').checked,
    pregnant: document.getElementById('pregnant').checked,
    medical_conditions: document.getElementById('medicalConditions').checked,
  };
}

async function runQuick(e) {
  e.preventDefault();
  const btn = document.getElementById('quickBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Working it out…';

  try {
    const r = await API.assess(quickPayload());
    State.lastAssessment = r;
    showAssessment(r);

    // Swap the form out for the answer.
    document.getElementById('startStep').hidden = true;
    document.getElementById('resultStep').hidden = false;
    window.scrollTo({ top: 0, behavior: 'instant' });
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Show my numbers →';
  }
}

/** Render whichever detail level is active, then draw its charts. */
function showAssessment(r) {
  const out = document.getElementById('planResults');
  document.getElementById('recap').innerHTML = Render.recap(r);

  Charts.reset();
  out.innerHTML = State.detail === 'full' ? Render.assessment(r) : Render.simple(r);

  // The donut only exists in the full view.
  const donut = document.getElementById('macroDonut');
  if (donut) {
    const n = r.nutrition;
    Charts.donut(donut, [
      { value: n.protein.kcal, colorVar: '--c-protein' },
      { value: n.fat.kcal, colorVar: '--c-fat' },
      { value: n.carbs.kcal, colorVar: '--c-carbs' },
    ], num(n.kcal.number), 'kcal/day');
  }
}

/** Go back to the questions, keeping every answer as it was. */
function editInputs() {
  document.getElementById('resultStep').hidden = true;
  document.getElementById('startStep').hidden = false;
  window.scrollTo({ top: 0, behavior: 'instant' });
}

/** From the accuracy prompt: back to the form with the tape fields open. */
function jumpToMeasurements() {
  editInputs();
  const fold = document.getElementById('fineTune');
  fold.open = true;
  const neck = document.getElementById('g_neck');
  fold.scrollIntoView({ behavior: 'smooth', block: 'center' });
  setTimeout(() => neck.focus(), 350);
}

/* =============================================================================
 *  Extra tools
 * ========================================================================== */

async function runBodyfat(e) {
  e.preventDefault();
  const out = document.getElementById('bfResults');
  out.innerHTML = '<div class="center"><div class="spinner" style="margin:0 auto"></div></div>';

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
      out.innerHTML = `<div class="empty">
        <p>No method could run with those inputs. Add neck and waist, or three skinfolds.</p>
      </div>`;
      return;
    }
    Charts.reset();
    out.innerHTML = Render.bodyfatCard(r);
  } catch (err) {
    out.innerHTML = `<div class="flag flag--danger">
      <div class="flag__title"><span class="flag__level">error</span>Couldn't compare methods</div>
      <p class="flag__msg">${esc(err.message)}</p></div>`;
  }
}

async function runPrep(e) {
  e.preventDefault();
  const out = document.getElementById('prepResults');
  out.innerHTML = '<div class="center"><div class="spinner" style="margin:0 auto"></div></div>';

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

    // Body fat % and weight in kg live on wildly different scales, so weight is
    // normalised onto the body-fat axis for shape comparison. The table beside
    // the chart carries the exact values.
    const proj = r.plan.projection;
    const bf = proj.map(p => ({ x: p.week, y: p.bodyfat_pct }));
    const wMin = Math.min(...proj.map(p => p.weight_kg));
    const wMax = Math.max(...proj.map(p => p.weight_kg));
    const bMin = Math.min(...bf.map(p => p.y));
    const bMax = Math.max(...bf.map(p => p.y));
    const scale = w => (wMax === wMin)
      ? (bMin + bMax) / 2
      : bMin + ((w - wMin) / (wMax - wMin)) * (bMax - bMin);

    Charts.line(document.getElementById('prepChart'), [
      { label: 'Body fat %', points: bf, colorVar: '--c-carbs' },
      {
        label: 'Weight (scaled)',
        points: proj.map(p => ({ x: p.week, y: scale(p.weight_kg) })),
        colorVar: '--c-protein', dashed: true,
      },
    ], { xLabel: 'Week', yLabel: 'Body fat', yUnit: '%' });
  } catch (err) {
    out.innerHTML = `<div class="flag flag--danger">
      <div class="flag__title"><span class="flag__level">error</span>Couldn't build the projection</div>
      <p class="flag__msg">${esc(err.message)}</p></div>`;
  }
}

async function runStrength(e) {
  e.preventDefault();
  const out = document.getElementById('strResults');
  out.innerHTML = '<div class="center"><div class="spinner" style="margin:0 auto"></div></div>';
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
    out.innerHTML = `<div class="flag flag--danger">
      <div class="flag__title"><span class="flag__level">error</span>Couldn't calculate</div>
      <p class="flag__msg">${esc(err.message)}</p></div>`;
  }
}

/* =============================================================================
 *  Learn tab
 * ========================================================================== */

let _sourcesLoaded = false;
let _learnLoadedFor = null;

async function loadLearn() {
  const sex = segValue('learnSex') || 'male';

  if (_learnLoadedFor !== sex) {
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
          </div>`).join('');
      _learnLoadedFor = sex;
    } catch (e) {
      panel.innerHTML = `<p class="muted">${esc(e.message)}</p>`;
    }
  }

  if (!_sourcesLoaded) {
    try {
      document.getElementById('sourceList').innerHTML = Render.sources(await API.sources());
      _sourcesLoaded = true;
    } catch (e) {
      document.getElementById('sourceList').innerHTML = `<p class="muted">${esc(e.message)}</p>`;
    }
  }
}

/* =============================================================================
 *  Coach mode: clients & tracking
 * ========================================================================== */

/**
 * Decide which of the three coach states to show: locked (no password set),
 * login, or the workspace.
 *
 * Called whenever the tab opens, so an expired session shows the login form
 * rather than a workspace full of failing requests.
 */
async function refreshCoachState() {
  const locked = document.getElementById('coachLocked');
  const login = document.getElementById('coachLogin');
  const work = document.getElementById('coachWorkspace');
  [locked, login, work].forEach(el => { el.hidden = true; });

  let s;
  try {
    s = await API.session();
  } catch (e) {
    login.hidden = false;
    showLoginError(e.message);
    return;
  }

  if (!s.configured) {
    locked.hidden = false;
    // The hint is a multi-line shell snippet, so the command gets a <pre>.
    const [intro, ...rest] = s.setup_hint.split('\n\n');
    document.getElementById('setupNote').innerHTML =
      `${esc(intro)}<pre>${esc(rest.join('\n\n').trim())}</pre>`;
    return;
  }

  if (!s.logged_in) {
    login.hidden = false;
    return;
  }

  work.hidden = false;
  await Promise.all([loadClients(), loadInvites(), loadIntakes()]);
}

function showLoginError(msg) {
  const el = document.getElementById('loginError');
  el.textContent = msg;
  el.hidden = false;
}

async function doLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('loginBtn');
  const input = document.getElementById('coachPassword');
  document.getElementById('loginError').hidden = true;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Checking…';

  try {
    await API.login(input.value);
    input.value = '';
    await refreshCoachState();
  } catch (err) {
    showLoginError(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Log in';
  }
}

async function doLogout() {
  try { await API.logout(); } catch { /* logging out locally regardless */ }
  State.activeClientId = null;
  document.getElementById('clientDetail').innerHTML =
    '<div class="empty"><p>Logged out.</p></div>';
  await refreshCoachState();
}

/* ---------------------------------------------------------------------------
 *  Onboarding links
 * ------------------------------------------------------------------------ */

async function loadInvites() {
  try {
    const { invites } = await API.invites();
    document.getElementById('inviteList').innerHTML = Render.inviteList(invites);
  } catch (e) {
    document.getElementById('inviteList').innerHTML =
      `<p class="muted small">${esc(e.message)}</p>`;
  }
}

async function createInvite(e) {
  e.preventDefault();
  try {
    const inv = await API.createInvite({
      label: document.getElementById('inviteLabel').value.trim() || null,
      ttl_days: numVal('inviteTtl') ?? 14,
    });
    document.getElementById('inviteLabel').value = '';
    await loadInvites();

    // Put it straight on the clipboard — the next thing you do is paste it into
    // WhatsApp, so saving that step is the whole point.
    try {
      await navigator.clipboard.writeText(inv.url);
      toast('Link created and copied — paste it to your client');
    } catch {
      toast('Link created — use "Copy link" to grab it');
    }
  } catch (err) {
    toast(err.message, true);
  }
}

/* ---------------------------------------------------------------------------
 *  Submitted questionnaires
 * ------------------------------------------------------------------------ */

async function loadIntakes() {
  try {
    const { intakes } = await API.intakes();
    document.getElementById('intakeList').innerHTML = Render.intakeList(intakes);
    // Surface the section when something is waiting to be read.
    if (intakes.length) document.getElementById('intakesTool').open = true;
  } catch (e) {
    document.getElementById('intakeList').innerHTML =
      `<p class="muted small">${esc(e.message)}</p>`;
  }
}

async function openIntake(id) {
  const host = document.getElementById('intakeDetail');
  host.innerHTML = '<div class="center"><div class="spinner" style="margin:0 auto"></div></div>';
  try {
    host.innerHTML = Render.intakeDetail(await API.intake(id));
    host.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    host.innerHTML = `<p class="muted small">${esc(e.message)}</p>`;
  }
}

async function loadClients() {
  try {
    const { clients } = await API.clients();
    document.getElementById('clientList').innerHTML =
      Render.clientList(clients, State.activeClientId);
  } catch (e) {
    // Inline, not a toast. A toast vanishes after three seconds and leaves the
    // panel looking merely empty — so a real failure reads as "no clients yet".
    document.getElementById('clientList').innerHTML = `
      <div class="flag flag--danger">
        <div class="flag__title"><span class="flag__level">error</span>Couldn't load your clients</div>
        <p class="flag__msg">${esc(e.message)}</p>
        <div class="flag__action">
          <strong>Try:</strong> reload the page. If it keeps happening, restart
          the server — the store is a single <code>toolkit.db</code> file in the
          project folder.
        </div>
      </div>`;
    toast('Could not load clients', true);
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

    const dateEl = document.getElementById('m_date');
    if (dateEl) dateEl.value = new Date().toISOString().slice(0, 10);

    // x is days since the first measurement, so unevenly spaced weigh-ins plot
    // at their true distance apart.
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
          colorVar: '--c-carbs', dashed: true,
        });
      }

      Charts.line(document.getElementById('clientChart'), series,
        { xLabel: 'Days since first measurement', yLabel: 'Weight', yUnit: 'kg' });
    }

    await loadClients();
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
 * Delegated events for the coach panel.
 *
 * The client list and detail view are re-rendered wholesale, so per-button
 * listeners would need re-binding after every render. One listener on the panel
 * handles all of them and survives re-renders.
 */
function initClientEvents() {
  const panel = document.getElementById('panel-coach');

  panel.addEventListener('click', async e => {
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

  panel.addEventListener('submit', e => {
    if (e.target.id === 'measForm') addMeasurement(e);
  });

  // ---- Onboarding: links and submissions -------------------------------
  panel.addEventListener('click', async e => {
    const copy = e.target.closest('[data-copy]');
    if (copy) {
      try {
        await navigator.clipboard.writeText(copy.dataset.copy);
        toast('Link copied');
      } catch {
        // Clipboard needs a secure context, so it fails on plain-HTTP LAN
        // access. Select the text instead of leaving them stuck.
        const url = copy.closest('.invite')?.querySelector('.invite__url');
        if (url) {
          const range = document.createRange();
          range.selectNodeContents(url);
          const sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
        }
        toast('Copy blocked by the browser — the link is selected, press Ctrl/Cmd+C', true);
      }
      return;
    }

    const revoke = e.target.closest('[data-revoke]');
    if (revoke) {
      if (!confirm('Cancel this link? Anyone holding it will no longer be able to use it.')) return;
      try {
        await API.revokeInvite(Number(revoke.dataset.revoke));
        toast('Link cancelled');
        await loadInvites();
      } catch (err) { toast(err.message, true); }
      return;
    }

    const delInvite = e.target.closest('[data-del-invite]');
    if (delInvite) {
      try {
        await API.deleteInvite(Number(delInvite.dataset.delInvite));
        await loadInvites();
      } catch (err) { toast(err.message, true); }
      return;
    }

    const openBtn = e.target.closest('[data-open-intake]');
    if (openBtn) { openIntake(Number(openBtn.dataset.openIntake)); return; }

    if (e.target.closest('#closeIntake')) {
      document.getElementById('intakeDetail').innerHTML = '';
      return;
    }

    const convert = e.target.closest('[data-convert]');
    if (convert) {
      try {
        const res = await API.convertIntake(Number(convert.dataset.convert));
        toast(`${res.client.name} added, with their starting weight logged`);
        await Promise.all([loadIntakes(), loadClients()]);
        await openClient(res.client.id);
        document.getElementById('intakeDetail').innerHTML = '';
      } catch (err) { toast(err.message, true); }
      return;
    }

    const delIntake = e.target.closest('[data-del-intake]');
    if (delIntake) {
      if (!confirm(
        'Permanently delete this questionnaire? This is what you use when a '
        + 'client asks you to erase their data — it cannot be undone.'
      )) return;
      try {
        await API.deleteIntake(Number(delIntake.dataset.delIntake));
        document.getElementById('intakeDetail').innerHTML = '';
        toast('Submission deleted');
        await loadIntakes();
      } catch (err) { toast(err.message, true); }
    }
  });
}

/* =============================================================================
 *  Init
 * ========================================================================== */

document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  initDetail();
  initTabs();

  initSegs((name, value) => {
    if (name === 'sex') updateSexDependentUI();
    if (name === 'learnSex') loadLearn();
    if (name === 'detail') setDetail(value);
  });

  document.getElementById('quickForm').addEventListener('submit', runQuick);
  document.getElementById('bfForm').addEventListener('submit', runBodyfat);
  document.getElementById('prepForm').addEventListener('submit', runPrep);
  document.getElementById('strForm').addEventListener('submit', runStrength);
  document.getElementById('clientForm').addEventListener('submit', createClient);
  document.getElementById('loginForm').addEventListener('submit', doLogin);
  document.getElementById('logoutBtn').addEventListener('click', doLogout);
  document.getElementById('inviteForm').addEventListener('submit', createInvite);
  initClientEvents();

  // Buttons that live inside re-rendered markup, handled by delegation.
  document.getElementById('panel-plan').addEventListener('click', e => {
    if (e.target.closest('#editInputs')) editInputs();
    if (e.target.closest('#addMeasurements')) jumpToMeasurements();
    const d = e.target.closest('#showDisclaimer, #showDisclaimer2');
    if (d) {
      const box = document.getElementById(
        d.id === 'showDisclaimer' ? 'disclaimerTop' : 'disclaimerInline');
      box.hidden = !box.hidden;
      d.textContent = box.hidden ? 'Read the full note' : 'Hide';
    }
  });

  await loadMeta();
});

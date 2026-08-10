/* =============================================================================
 *  start.js — the client onboarding questionnaire.
 * =============================================================================
 *  Renders the form from the schema the API returns, one section at a time.
 *
 *  Why one section per screen: the same lesson the main calculator taught. Forty
 *  fields in a single scroll reads as homework and people abandon it. Six short
 *  screens with a progress bar feel like a conversation, and each screen can
 *  carry the "why I'm asking" text without becoming a wall.
 *
 *  Answers are held in memory only — deliberately not localStorage. This is
 *  health information, and persisting it to disk on what might be a shared or
 *  family device is a worse failure than losing a part-finished form. A
 *  beforeunload warning covers the accidental-close case instead.
 * ========================================================================== */

const Intake = {
  token: null,
  schema: null,
  answers: {},
  step: 0,          // index into schema.sections
  submitted: false,
};

/* ---------------------------------------------------------------------------
 *  Theme (mirrors the main app so a client sees one consistent brand)
 * ------------------------------------------------------------------------ */

function initTheme() {
  const saved = localStorage.getItem('pnt-theme');
  const prefersLight = window.matchMedia?.('(prefers-color-scheme: light)').matches;
  setTheme(saved || (prefersLight ? 'light' : 'dark'));
  document.getElementById('themeToggle').addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('pnt-theme', next);
  });
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.getElementById('themeIcon').textContent = theme === 'dark' ? '☀' : '☾';
}

/* ---------------------------------------------------------------------------
 *  Boot
 * ------------------------------------------------------------------------ */

function tokenFromPath() {
  // /start/<token>
  const parts = window.location.pathname.split('/').filter(Boolean);
  return parts[parts.length - 1] || null;
}

async function boot() {
  initTheme();
  Intake.token = tokenFromPath();

  const show = id => { document.getElementById(id).hidden = false; };
  const hide = id => { document.getElementById(id).hidden = true; };

  let data;
  try {
    data = await API.call(`/api/intake/${encodeURIComponent(Intake.token)}`);
  } catch (e) {
    hide('loading');
    show('deadLink');
    document.getElementById('deadLinkMessage').textContent =
      'We couldn\'t load this form. Check your connection and reload, or ask your coach for a new link.';
    return;
  }

  hide('loading');

  if (!data.usable) {
    show('deadLink');
    document.getElementById('deadLinkMessage').textContent = data.message;
    return;
  }

  Intake.schema = data;
  document.getElementById('introHeading').textContent = data.intro.heading;
  document.getElementById('introBody').textContent = data.intro.body.split('\n\n')[0];
  document.getElementById('privacySummary').textContent = data.privacy_summary;
  show('intro');

  document.getElementById('beginBtn').addEventListener('click', begin);
  document.getElementById('nextBtn').addEventListener('click', next);
  document.getElementById('backBtn').addEventListener('click', back);
  document.getElementById('consentBack').addEventListener('click', () => {
    document.getElementById('consentStep').hidden = true;
    document.getElementById('intakeForm').hidden = false;
    Intake.step = Intake.schema.sections.length - 1;
    renderStep();
  });
  document.getElementById('consentBox').addEventListener('change', e => {
    document.getElementById('submitBtn').disabled = !e.target.checked;
  });
  document.getElementById('submitBtn').addEventListener('click', submit);

  // Don't let eight minutes of typing vanish on a stray tab close.
  window.addEventListener('beforeunload', e => {
    if (Object.keys(Intake.answers).length && !Intake.submitted) {
      e.preventDefault();
      e.returnValue = '';
    }
  });
}

function begin() {
  document.getElementById('intro').hidden = true;
  document.getElementById('intakeForm').hidden = false;
  Intake.step = 0;
  renderStep();
}

/* ---------------------------------------------------------------------------
 *  Rendering one section
 * ------------------------------------------------------------------------ */

function fieldHTML(field) {
  const id = `f_${field.key}`;
  const value = Intake.answers[field.key] ?? '';
  const req = field.required ? '<span class="req" title="Required">*</span>' : '';
  const unit = field.unit ? ` <em>${esc(field.unit)}</em>` : '';

  // The "why I'm asking" line. Always visible rather than behind a tap — it's
  // the entire trust mechanism, and a client shouldn't have to hunt for it.
  const why = field.why
    ? `<p class="askwhy"><span class="askwhy__mark">Why I'm asking</span> ${esc(field.why)}</p>`
    : '';

  let control = '';

  if (field.type === 'radio') {
    control = `<div class="cards ${field.options.length > 3 ? 'cards--stack' : ''}"
                    data-field="${esc(field.key)}" role="radiogroup">
      ${field.options.map(o => `
        <button type="button" data-value="${esc(o.value)}"
                aria-pressed="${String(value === o.value)}">
          <strong>${esc(o.label)}</strong>
        </button>`).join('')}
    </div>`;
  } else if (field.type === 'select') {
    control = `<select id="${id}" data-field="${esc(field.key)}">
      <option value="">Choose one…</option>
      ${field.options.map(o => `
        <option value="${esc(o.value)}"${value === o.value ? ' selected' : ''}>${esc(o.label)}</option>`).join('')}
    </select>`;
  } else if (field.type === 'textarea') {
    control = `<textarea id="${id}" data-field="${esc(field.key)}" rows="3"
      placeholder="${esc(field.placeholder || '')}">${esc(value)}</textarea>`;
  } else if (field.type === 'number') {
    control = `<input type="number" id="${id}" data-field="${esc(field.key)}"
      value="${esc(value)}" ${field.min !== undefined ? `min="${field.min}"` : ''}
      ${field.max !== undefined ? `max="${field.max}"` : ''} step="any"
      placeholder="${esc(field.placeholder || '')}" inputmode="decimal" />`;
  } else {
    control = `<input type="text" id="${id}" data-field="${esc(field.key)}"
      value="${esc(value)}" placeholder="${esc(field.placeholder || '')}" />`;
  }

  return `
    <div class="qfield" data-key="${esc(field.key)}">
      <label class="qfield__label" for="${id}">${esc(field.label)}${unit}${req}</label>
      ${why}
      ${control}
    </div>`;
}

function renderStep() {
  const sections = Intake.schema.sections;
  const section = sections[Intake.step];
  const total = sections.length + 1;   // + the consent step

  document.getElementById('progressFill').style.width =
    `${((Intake.step) / total) * 100}%`;
  document.getElementById('progressLabel').textContent =
    `Step ${Intake.step + 1} of ${total} · ${section.title}`;

  document.getElementById('sectionHost').innerHTML = `
    <div class="card">
      <div class="card__head"><h2>${esc(section.title)}</h2></div>
      ${section.intro ? `<p class="card__hint">${esc(section.intro)}</p>` : ''}
      ${section.fields.map(fieldHTML).join('')}
    </div>`;

  document.getElementById('backBtn').style.visibility = Intake.step === 0 ? 'hidden' : 'visible';
  document.getElementById('nextBtn').textContent =
    Intake.step === sections.length - 1 ? 'Review and send →' : 'Next →';
  document.getElementById('stepError').hidden = true;

  wireStepInputs();
  window.scrollTo({ top: 0, behavior: 'instant' });
}

/** Capture answers as they're typed, so navigation never loses them. */
function wireStepInputs() {
  const host = document.getElementById('sectionHost');

  host.querySelectorAll('input, textarea, select').forEach(el => {
    el.addEventListener('input', () => {
      Intake.answers[el.dataset.field] = el.value;
    });
    el.addEventListener('change', () => {
      Intake.answers[el.dataset.field] = el.value;
    });
  });

  host.querySelectorAll('[data-field][role="radiogroup"]').forEach(group => {
    group.addEventListener('click', e => {
      const btn = e.target.closest('button');
      if (!btn) return;
      group.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', 'false'));
      btn.setAttribute('aria-pressed', 'true');
      Intake.answers[group.dataset.field] = btn.dataset.value;
      // Clear any "please answer this" highlight now that it's answered.
      group.closest('.qfield')?.classList.remove('qfield--missing');
    });
  });
}

/* ---------------------------------------------------------------------------
 *  Navigation with per-step validation
 * ------------------------------------------------------------------------ */

function validateStep() {
  const section = Intake.schema.sections[Intake.step];
  const missing = [];

  section.fields.forEach(field => {
    const wrapper = document.querySelector(`.qfield[data-key="${field.key}"]`);
    wrapper?.classList.remove('qfield--missing');
    if (!field.required) return;

    const value = String(Intake.answers[field.key] ?? '').trim();
    if (!value) {
      missing.push(field.label);
      wrapper?.classList.add('qfield--missing');
    }
  });

  const err = document.getElementById('stepError');
  if (missing.length) {
    err.textContent = `Please fill in: ${missing.join(', ')}`;
    err.hidden = false;
    document.querySelector('.qfield--missing')
      ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return false;
  }
  err.hidden = true;
  return true;
}

function next() {
  if (!validateStep()) return;
  if (Intake.step < Intake.schema.sections.length - 1) {
    Intake.step += 1;
    renderStep();
  } else {
    showConsent();
  }
}

function back() {
  if (Intake.step > 0) {
    Intake.step -= 1;
    renderStep();
  }
}

/* ---------------------------------------------------------------------------
 *  Consent & submit
 * ------------------------------------------------------------------------ */

function showConsent() {
  const c = Intake.schema.consent;
  document.getElementById('intakeForm').hidden = true;
  document.getElementById('consentStep').hidden = false;

  document.getElementById('consentTitle').textContent = c.title;
  document.getElementById('consentPoints').innerHTML =
    c.points.map(p => `<li>${esc(p)}</li>`).join('');
  document.getElementById('consentLabel').textContent = c.checkbox_label;
  window.scrollTo({ top: 0, behavior: 'instant' });
}

async function submit() {
  const btn = document.getElementById('submitBtn');
  const err = document.getElementById('submitError');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Sending…';
  err.hidden = true;

  try {
    const result = await API.call(`/api/intake/${encodeURIComponent(Intake.token)}`, {
      method: 'POST',
      body: { answers: Intake.answers, consent: true },
    });
    Intake.submitted = true;      // releases the beforeunload guard
    showDone(result);
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
    btn.disabled = false;
    btn.textContent = 'Send to my coach';
  }
}

function showDone(result) {
  document.getElementById('consentStep').hidden = true;
  document.getElementById('doneStep').hidden = false;

  const closing = result.closing;
  document.getElementById('doneHeading').textContent = closing.heading;
  document.getElementById('doneBody').innerHTML =
    closing.body.split(/\n\s*\n/).map(p => `<p>${esc(p)}</p>`).join('');

  const priorities = result.priorities || [];
  document.getElementById('prioritiesHost').innerHTML = priorities.length
    ? priorities.map((p, i) => `
        <div class="step">
          <span class="step__n">${i + 1}</span>
          <div>
            <div class="step__do">${esc(p.title)}</div>
            <p class="step__how">${esc(p.because)}</p>
          </div>
        </div>`).join('')
    : `<p class="muted small">
         Nothing jumped out as needing special handling — which is good news. We'll
         go through the detail together.
       </p>`;

  document.getElementById('nextStepsHost').innerHTML =
    closing.next_steps.map((s, i) => `
      <div class="step">
        <span class="step__n">${i + 1}</span>
        <div><p class="step__how" style="margin:0">${esc(s)}</p></div>
      </div>`).join('');

  window.scrollTo({ top: 0, behavior: 'instant' });
}

document.addEventListener('DOMContentLoaded', boot);

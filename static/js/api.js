/* =============================================================================
 *  api.js — talking to the backend, plus small shared helpers.
 * =============================================================================
 *  Everything hangs off one global `API` object. No modules, no bundler — this
 *  loads as a plain script, which is the whole point of the no-build-step
 *  constraint.
 * ========================================================================== */

const API = {

  /**
   * One wrapper for every fetch, so error handling exists in exactly one place.
   *
   * FastAPI returns validation errors as {detail: [...]} for 422 and
   * {detail: "..."} for HTTPException — both are unwrapped here into a plain
   * message, so a bad input shows the user what to fix instead of "500".
   */
  async call(path, { method = 'GET', body = null } = {}) {
    const opts = { method, headers: {} };
    if (body) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }

    let res;
    try {
      res = await fetch(path, opts);
    } catch (e) {
      // This is the single most likely error a paying client ever sees, at the
      // worst possible moment: eight minutes of health answers typed on a phone,
      // consent ticked, Send tapped, and the mobile signal drops — or the host's
      // proxy answers while the free instance is still waking up. "Is uvicorn
      // still running?" is a message for the developer, addressed to someone who
      // has never heard the word, and it reads like their answers are gone.
      // They are not: the page still holds them, so say so and let them retry.
      throw new Error(
        'The connection dropped before that could be sent. Nothing is lost — your '
        + 'answers are still on this page. Check your signal and try again.');
    }

    if (!res.ok) {
      let msg = `Request failed (${res.status})`;
      try {
        const err = await res.json();
        if (Array.isArray(err.detail)) {
          // Pydantic validation errors. Two shapes arrive here and they want
          // opposite treatment: a built-in complaint ("Input should be a valid
          // number") is meaningless without knowing which field it's about,
          // while a message written by one of our own validators is already a
          // full explanation — and prefixing that with "fat_100g: Value error,"
          // buries the sentence a coach actually needs to read behind an
          // internal field name.
          msg = err.detail
            .map(d => {
              const text = String(d.msg || '').replace(/^Value error,\s*/, '');
              const written = text.length > 25 && /^[A-Z]/.test(text);
              const field = (d.loc || []).filter(l => l !== 'body').join('.');
              return field && !written ? `${field}: ${text}` : text;
            })
            .join(' ');
        } else if (typeof err.detail === 'string') {
          msg = err.detail;
        }
      } catch { /* response wasn't JSON — keep the status message */ }
      throw new Error(msg);
    }

    return res.json();
  },

  meta:            ()             => API.call('/api/meta'),
  sources:         ()             => API.call('/api/sources'),
  micronutrients:  (sex)          => API.call(`/api/micronutrients?sex=${sex}`),

  assess:   (payload) => API.call('/api/assess',    { method: 'POST', body: payload }),
  bodyfat:  (payload) => API.call('/api/bodyfat',   { method: 'POST', body: payload }),
  prepPlan: (payload) => API.call('/api/prep-plan', { method: 'POST', body: payload }),
  strength: (payload) => API.call('/api/strength',  { method: 'POST', body: payload }),

  // Coach auth
  session:  ()   => API.call('/api/session'),
  login:    (pw) => API.call('/api/login',  { method: 'POST', body: { password: pw } }),
  logout:   ()   => API.call('/api/logout', { method: 'POST' }),

  // Onboarding links & submitted questionnaires
  invites:       ()      => API.call('/api/invites'),
  createInvite:  (p)     => API.call('/api/invites', { method: 'POST', body: p }),
  revokeInvite:  (id)    => API.call(`/api/invites/${id}/revoke`, { method: 'POST' }),
  deleteInvite:  (id)    => API.call(`/api/invites/${id}`, { method: 'DELETE' }),
  intakes:       ()      => API.call('/api/intakes'),
  intake:        (id)    => API.call(`/api/intakes/${id}`),
  convertIntake: (id)    => API.call(`/api/intakes/${id}/convert`, { method: 'POST' }),
  deleteIntake:  (id)    => API.call(`/api/intakes/${id}`, { method: 'DELETE' }),

  // Diet builder — coach only
  mealPlan:           (p)  => API.call('/api/meal-plan', { method: 'POST', body: p }),
  mealPlanFromIntake: (id) => API.call(`/api/intakes/${id}/meal-plan`, { method: 'POST' }),

  // The coach's own foods
  customFoods:      ()    => API.call('/api/foods/custom'),
  addCustomFood:    (p)   => API.call('/api/foods/custom', { method: 'POST', body: p }),
  deleteCustomFood: (key) => API.call(`/api/foods/custom/${key}`, { method: 'DELETE' }),

  // Grocery prices — coach only
  prices:     ()          => API.call('/api/prices'),
  setPrice:   (key, price) => API.call(`/api/prices/${key}`, { method: 'PUT', body: { price } }),
  resetPrice: (key)        => API.call(`/api/prices/${key}`, { method: 'DELETE' }),

  clients:       ()            => API.call('/api/clients'),
  createClient:  (p)           => API.call('/api/clients', { method: 'POST', body: p }),
  client:        (id)          => API.call(`/api/clients/${id}`),
  deleteClient:  (id)          => API.call(`/api/clients/${id}`, { method: 'DELETE' }),
  addMeasurement: (id, p)      => API.call(`/api/clients/${id}/measurements`, { method: 'POST', body: p }),
  deleteMeasurement: (id)      => API.call(`/api/measurements/${id}`, { method: 'DELETE' }),
};


/* =============================================================================
 *  Shared helpers
 * ========================================================================== */

/** Escape user/content text before it goes anywhere near innerHTML. */
function esc(s) {
  if (s === null || s === undefined) return '';
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/**
 * Render the explanation text as paragraphs.
 *
 * The knowledge base writes multi-paragraph strings separated by blank lines,
 * plus bullet lines starting with "•". Escaping happens first, then the light
 * formatting is applied — so content can never inject markup.
 */
function paras(text) {
  if (!text) return '';
  return String(text)
    .split(/\n\s*\n/)
    .map(block => {
      const lines = block.split('\n').map(l => l.trim()).filter(Boolean);
      // A block whose lines are mostly bullets becomes a list.
      const bullets = lines.filter(l => l.startsWith('•'));
      if (bullets.length && bullets.length === lines.filter(l => l.startsWith('•')).length && bullets.length > 0) {
        const lead = lines.filter(l => !l.startsWith('•'));
        const items = bullets.map(l => `<li>${esc(l.replace(/^•\s*/, ''))}</li>`).join('');
        return (lead.length ? `<p>${esc(lead.join(' '))}</p>` : '')
             + `<ul style="margin:0 0 var(--sp-3);padding-left:1.1rem">${items}</ul>`;
      }
      return `<p>${esc(block.replace(/\n/g, ' '))}</p>`;
    })
    .join('');
}

/** Number formatting with thousands separators. */
function num(n, decimals = 0) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return Number(n).toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Map a risk word from the API to a chip modifier class. */
function riskClass(risk) {
  return ({ good: 'good', ok: 'ok', caution: 'caution', danger: 'danger' })[risk] || '';
}

/** Transient message at the bottom of the screen. */
function toast(msg, isError = false) {
  document.querySelectorAll('.toast').forEach(t => t.remove());
  const el = document.createElement('div');
  el.className = 'toast' + (isError ? ' toast--error' : '');
  el.textContent = msg;
  el.setAttribute('role', 'status');
  document.body.appendChild(el);
  setTimeout(() => el.remove(), isError ? 6000 : 3200);
}

/**
 * Read the current value of a segmented control or choice-card group.
 *
 * Accepts either ARIA state, because the two control types correctly use
 * different ones: a toggle group uses aria-pressed, while a group with
 * role="radiogroup" must use role="radio" + aria-checked. Reading both keeps one
 * accessor working for both.
 */
function segValue(name) {
  const btn = document.querySelector(
    `[data-seg="${name}"] button[aria-pressed="true"],`
    + ` [data-seg="${name}"] button[aria-checked="true"]`);
  return btn ? btn.dataset.value : null;
}

/** Set selection state using whichever ARIA attribute this control uses. */
function setSelected(btn, on) {
  const attr = btn.hasAttribute('aria-checked') ? 'aria-checked' : 'aria-pressed';
  btn.setAttribute(attr, String(on));
}

/** Select one option within a group, clearing the others. */
function selectInGroup(group, btn) {
  group.querySelectorAll('button').forEach(b => setSelected(b, false));
  setSelected(btn, true);
}

/** Read a number input, returning null when empty so optional fields stay null. */
function numVal(id) {
  const el = document.getElementById(id);
  if (!el || el.value === '') return null;
  const v = parseFloat(el.value);
  return Number.isNaN(v) ? null : v;
}

/** Wire up every segmented control and choice-card group on the page. */
function initSegs(onChange) {
  document.querySelectorAll('[data-seg]').forEach(seg => {
    seg.addEventListener('click', e => {
      const btn = e.target.closest('button');
      if (!btn) return;
      selectInGroup(seg, btn);
      if (onChange) onChange(seg.dataset.seg, btn.dataset.value);
    });

    // Arrow keys move between options, which is what a screen-reader or
    // keyboard-only user expects from a radio group. Buttons already handle
    // Enter and Space, so this is the piece that was missing.
    seg.addEventListener('keydown', e => {
      if (!['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp'].includes(e.key)) return;
      const buttons = [...seg.querySelectorAll('button')];
      const current = buttons.indexOf(document.activeElement);
      if (current === -1) return;
      e.preventDefault();
      const step = (e.key === 'ArrowRight' || e.key === 'ArrowDown') ? 1 : -1;
      const next = buttons[(current + step + buttons.length) % buttons.length];
      next.focus();
      selectInGroup(seg, next);
      if (onChange) onChange(seg.dataset.seg, next.dataset.value);
    });
  });
}

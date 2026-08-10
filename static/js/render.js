/* =============================================================================
 *  render.js — turning API responses into DOM.
 * =============================================================================
 *  All rendering functions hang off `Render`. They return HTML strings rather
 *  than building nodes: the payloads are read-only snapshots, so one innerHTML
 *  assignment per section is simpler and faster than incremental DOM work.
 *
 *  Every string that came from the API goes through esc() or paras() first.
 *  The knowledge base is trusted content, but treating it as untrusted costs
 *  nothing and means a future user-supplied field can't turn into an XSS hole.
 *
 *  The single most important function here is `why()` — the expandable panel
 *  that carries the explanation for every number. It's used identically for
 *  calories, protein, fat, carbs, fibre and water, which is what makes the
 *  "teach, don't just calculate" promise consistent rather than ad hoc.
 * ========================================================================== */

const Render = {

  /* =========================================================================
   *  THE "WHY THIS NUMBER?" PANEL — the core component
   * ====================================================================== */
  why(block, { tintClass = '' } = {}) {
    const w = block.why;
    if (!w) return '';

    const jobs = (w.what_it_does || []).map(j => `
      <div class="job">
        <div class="job__label">${esc(j.label)}</div>
        <p class="job__text">${esc(j.text)}</p>
      </div>`).join('');

    const lowList  = (w.too_little || []).map(x => `<li>${esc(x)}</li>`).join('');
    const highList = (w.too_much   || []).map(x => `<li>${esc(x)}</li>`).join('');

    return `
    <details class="why ${tintClass}">
      <summary>Why this number?</summary>
      <div class="why__body">

        <div class="why__reason">${paras(w.why_this_much)}</div>

        ${jobs ? `
        <div class="why__section">
          <div class="why__section-title">What it actually does</div>
          <div class="jobs">${jobs}</div>
        </div>` : ''}

        ${(lowList || highList) ? `
        <div class="why__section">
          <div class="why__section-title">What goes wrong</div>
          <div class="risks">
            ${lowList ? `
            <div class="risk-box risk-box--low">
              <div class="risk-box__title">▼ Too little</div>
              <ul>${lowList}</ul>
            </div>` : ''}
            ${highList ? `
            <div class="risk-box risk-box--high">
              <div class="risk-box__title">▲ Too much</div>
              <ul>${highList}</ul>
            </div>` : ''}
          </div>
        </div>` : ''}

        ${this.howToHit(block.how_to_hit)}
        ${this.cites(block.sources)}
      </div>
    </details>`;
  },

  /** "How to hit it" — real food portions, or a breakdown for water. */
  howToHit(h) {
    if (!h || !Object.keys(h).length) return '';
    let inner = '';

    // Protein: "your whole target in one food" for scale
    if (h.single_food_equivalents?.length) {
      inner += `
        <p class="xs muted" style="margin-bottom:var(--sp-2)">
          Your entire daily target, if you got it from one food alone — for scale,
          not as a meal plan:
        </p>
        <div class="foods">
          ${h.single_food_equivalents.map(f => `
            <div class="food-row">
              <div>
                <span class="food-row__name">${esc(f.name)}</span>
                <span class="food-row__portion">${esc(f.household)} · ${f.per_portion_g} g protein each</span>
              </div>
              <span class="food-row__value">×${f.portions}</span>
            </div>`).join('')}
        </div>`;
    }

    // Protein: a realistic mixed day
    if (h.sample_day?.length) {
      inner += `
        <p class="xs muted" style="margin:var(--sp-4) 0 var(--sp-2)">
          One realistic day that gets you there
          ${h.sample_day_total_g ? `— <strong>${h.sample_day_total_g} g total</strong>, ${num(h.sample_day_kcal)} kcal` : ''}:
        </p>
        <div class="foods">
          ${h.sample_day.map(f => `
            <div class="food-row">
              <div>
                <span class="food-row__name">${f.portions} × ${esc(f.name)}</span>
                <span class="food-row__portion">${esc(f.household)}</span>
              </div>
              <span class="food-row__value">${f.protein_g} g</span>
            </div>`).join('')}
        </div>`;
    }

    // Fat / carbs / fibre portion lists
    if (h.portions?.length) {
      const key = 'fat_g' in h.portions[0] ? 'fat_g'
                : 'carb_g' in h.portions[0] ? 'carb_g'
                : 'fibre_g';
      const unit = key === 'fat_g' ? 'g fat' : key === 'carb_g' ? 'g carbs' : 'g fibre';
      inner += `
        <div class="foods">
          ${h.portions.map(f => `
            <div class="food-row">
              <div>
                <span class="food-row__name">${esc(f.name)}</span>
                <span class="food-row__portion">${esc(f.household)} · ${num(f.kcal)} kcal</span>
              </div>
              <span class="food-row__value">${f[key]} ${unit}</span>
            </div>`).join('')}
        </div>`;
    }

    // Water: where the target came from
    if (h.breakdown?.length) {
      inner += `
        <div class="foods">
          ${h.breakdown.filter(b => b.ml > 0).map(b => `
            <div class="food-row">
              <span class="food-row__name">${esc(b.label)}</span>
              <span class="food-row__value">${num(b.ml)} ml</span>
            </div>`).join('')}
        </div>`;
    }

    if (h.note) inner += `<div class="note">${esc(h.note)}</div>`;
    if (!inner) return '';

    return `
      <div class="why__section">
        <div class="why__section-title">How to hit it with real food</div>
        ${inner}
      </div>`;
  },

  /** Citation list. */
  cites(sources) {
    if (!sources?.length) return '';
    return `
      <div class="why__section">
        <div class="why__section-title">Where this comes from</div>
        <div class="cites">
          ${sources.map(s => `
            <div class="cite">
              <span class="cite__org">${esc(s.org)}</span>
              <span class="cite__body">
                <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)}</a>
                <span class="cite__note">${esc(s.note)}</span>
              </span>
            </div>`).join('')}
        </div>
      </div>`;
  },

  /* =========================================================================
   *  A single macro / nutrient target card
   * ====================================================================== */
  target(block, { key, label, icon = '' }) {
    const chips = [];
    if (block.pct_kcal !== undefined) chips.push(`${block.pct_kcal}% of calories`);
    if (block.kcal !== undefined && key !== 'kcal') chips.push(`${num(block.kcal)} kcal`);
    if (block.g_per_kg_bw !== undefined) chips.push(`${block.g_per_kg_bw} g/kg bw`);
    if (block.g_per_kg_lbm !== undefined) chips.push(`${block.g_per_kg_lbm} g/kg lean`);
    if (key === 'kcal' && block.tdee) {
      const d = block.delta;
      chips.push(`TDEE ${num(block.tdee)}`);
      chips.push(`${d > 0 ? '+' : ''}${num(d)} kcal (${block.delta_pct}%)`);
      if (block.rate_kg_per_week) chips.push(`≈${block.rate_kg_per_week} kg/week`);
    }
    if (key === 'water' && block.total_ml) chips.push(`${num(block.total_ml)} ml`);

    // ISSN range badge on protein
    let badge = '';
    if (key === 'protein' && block.in_issn_range !== undefined) {
      badge = block.in_issn_range
        ? `<span class="chip chip--good">Inside ISSN 1.6–2.2 g/kg</span>`
        : `<span class="chip chip--caution">Outside ISSN 1.6–2.2 g/kg — driven by lean mass</span>`;
    }
    if (key === 'fat' && block.below_floor) {
      badge = `<span class="chip chip--caution">Raised to the ${block.floor_g} g safe floor</span>`;
    }

    return `
    <div class="target target--${key}">
      <div class="target__label">${icon ? `<span aria-hidden="true">${icon}</span>` : ''}${esc(label)}</div>
      <div class="target__value">
        ${num(block.number, key === 'water' ? 1 : 0)}<span class="target__unit">${esc(block.unit)}</span>
      </div>
      <div class="target__headline">${esc(block.why?.headline || '')}</div>
      <div class="target__meta">
        ${badge}
        ${chips.map(c => `<span class="chip">${esc(c)}</span>`).join('')}
      </div>
      ${this.why(block)}
    </div>`;
  },

  /* =========================================================================
   *  Safety flags
   * ====================================================================== */
  safety(s) {
    if (!s) return '';
    const icon = { good: '✓', warning: '!', danger: '⚠' }[s.level] || 'i';

    const flags = (s.flags || []).map(fl => `
      <div class="flag flag--${fl.level}">
        <div class="flag__title">
          <span class="flag__level">${esc(fl.level)}</span>
          ${esc(fl.title)}
        </div>
        <p class="flag__msg">${esc(fl.message)}</p>
        <div class="flag__action"><strong>What to do:</strong> ${esc(fl.action)}</div>
      </div>`).join('');

    return `
      <div class="verdict verdict--${s.level}">
        <span class="verdict__icon" aria-hidden="true">${icon}</span>
        <div>
          <div class="verdict__text">${esc(s.verdict)}</div>
          <div class="verdict__sub">
            ${s.counts.danger} critical · ${s.counts.warning} warnings · ${s.counts.info} notes
          </div>
        </div>
      </div>
      ${flags}`;
  },

  /* =========================================================================
   *  RECAP BAR — what you entered, with a way back
   * ====================================================================== */
  recap(r) {
    const i = r.input;
    const goalWords = {
      cut: 'losing fat', aggressive_cut: 'losing fat fast',
      maintain: 'maintaining', bulk: 'building muscle',
    };
    const bits = [
      `${i.sex === 'male' ? 'Male' : 'Female'}, ${i.age}`,
      `${i.weight_kg} kg`,
      `${i.height_cm} cm`,
      goalWords[i.goal] || i.goal,
      i.diet === 'omnivore' ? 'eats everything' : i.diet,
    ];
    return `
      ${bits.map(b => `<span class="chip">${esc(b)}</span>`).join('')}
      <span class="recap__spacer"></span>
      <button class="btn btn--ghost btn--sm no-print" id="editInputs">Change my answers</button>`;
  },

  /* =========================================================================
   *  SIMPLE VIEW — the default
   *
   *  Leads with one number and one sentence. The reasoning is still one click
   *  away on every tile (that's the whole product), but the full report — energy
   *  breakdown, body composition, micronutrient panel, method comparison — is
   *  demoted behind a single "show me everything" fold.
   * ====================================================================== */
  simple(r) {
    const s = r.summary;
    const n = r.nutrition;
    const blocked = r.safety?.blocked;

    // When nothing is flagged, a single quiet line beats a full green banner.
    const safetyBlock = (r.safety.level === 'good')
      ? `<p class="notice-slim" style="text-align:left;margin:0 0 var(--sp-4)">
           ✓ Nothing looks unsafe about these numbers for you.
         </p>`
      : this.safety(r.safety);

    const tile = (block, key, name, forWhat) => `
      <div class="tile tile--${key}">
        <div class="tile__name">${esc(name)}</div>
        <div class="tile__value">${num(block.number, key === 'water' ? 1 : 0)}<small> ${esc(block.unit.replace('/day', ''))}</small></div>
        <p class="tile__for">${esc(forWhat)}</p>
      </div>`;

    return `
      ${safetyBlock}

      ${blocked ? `
        <div class="blocked-notice">
          Please read the warnings above before using these numbers.
        </div>` : ''}

      <!-- The answer -->
      <div class="answer">
        <div class="answer__kcal">${num(n.kcal.number)}</div>
        <span class="answer__unit">calories a day</span>
        <p class="answer__line">${esc(s.headline)}</p>
        <p class="answer__expect">${esc(s.expect)}</p>
      </div>

      <!-- The one thing that matters most -->
      <div class="priority">
        <div class="priority__label">${esc(s.priority.label)}</div>
        <div class="priority__what">${esc(s.priority.what)}</div>
        <p class="priority__why">${esc(s.priority.why)}</p>
      </div>

      <!-- The numbers, small and scannable -->
      <div class="card">
        <div class="card__head">
          <h2>Your day in four numbers</h2>
        </div>
        <div class="tiles">
          ${tile(n.protein, 'protein', 'Protein', 'Builds and protects muscle. The one to get right.')}
          ${tile(n.carbs, 'carbs', 'Carbs', 'Fuel for training. Powers your hard sets.')}
          ${tile(n.fat, 'fat', 'Fat', 'Hormones and vitamin absorption. Not optional.')}
          ${tile(n.fibre, 'fibre', 'Fibre', 'Digestion and staying full. From veg, fruit and dal.')}
        </div>
        <p class="small muted">${esc(s.plate)}</p>

        <div class="stack" style="margin-top:var(--sp-5)">
          ${['protein', 'carbs', 'fat', 'fibre', 'water'].map(k => `
            <div class="target target--${k}" style="padding:var(--sp-4)">
              <div class="target__label" style="margin-bottom:var(--sp-1)">
                ${esc(n[k].why.title)} — ${num(n[k].number, k === 'water' ? 1 : 0)} ${esc(n[k].unit)}
              </div>
              <div class="small muted">${esc(n[k].why.headline)}</div>
              ${this.why(n[k])}
            </div>`).join('')}
        </div>
      </div>

      <!-- What to actually do -->
      <div class="card">
        <div class="card__head"><h2>Three things to do this week</h2></div>
        <div class="steps">
          ${s.steps.map(st => `
            <div class="step">
              <span class="step__n">${st.n}</span>
              <div>
                <div class="step__do">${esc(st.do)}</div>
                <p class="step__how">${esc(st.how)}</p>
              </div>
            </div>`).join('')}
        </div>
        <div class="note">${esc(s.reassurance)}</div>
      </div>

      <!-- Meals -->
      <div class="card">
        <div class="card__head"><h2>Split across your meals</h2></div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>Meal</th><th class="num">Protein</th><th class="num">Carbs</th><th class="num">Fat</th><th class="num">Calories</th></tr>
            </thead>
            <tbody>
              ${n.meal_split.meals.map(m => `
                <tr>
                  <td class="strong">${esc(m.meal)}</td>
                  <td class="num">${m.protein_g} g</td>
                  <td class="num">${m.carb_g} g</td>
                  <td class="num">${m.fat_g} g</td>
                  <td class="num">${num(m.kcal)}</td>
                </tr>`).join('')}
            </tbody>
          </table>
        </div>
        <p class="q__hint">
          A guide, not a rule. Daily totals do most of the work — hitting your
          numbers on a schedule you can actually keep beats a perfect split you
          abandon.
        </p>
      </div>

      ${s.needs_better_measurement ? `
        <div class="upgrade">
          <div class="upgrade__text">
            <strong>Want a sharper estimate?</strong>
            ${esc(s.accuracy_note)}
          </div>
          <button class="btn btn--ghost btn--sm no-print" id="addMeasurements">
            Add a tape measurement
          </button>
        </div>` : `
        <p class="notice-slim" style="text-align:left">${esc(s.accuracy_note)}</p>`}

      <!-- Everything else, demoted -->
      <details class="tool" style="margin-top:var(--sp-5)">
        <summary>
          <span class="tool__title">Show me everything</span>
          <span class="tool__desc">
            Body fat methods, how your calories were worked out, vitamins &amp;
            minerals, body composition — the full coach's report
          </span>
        </summary>
        <div class="tool__body">${this.fullSections(r)}</div>
      </details>

      <div class="actions no-print" style="margin-top:var(--sp-5);justify-content:center">
        <button class="btn btn--ghost" onclick="window.print()">Print or save this plan</button>
      </div>

      <p class="notice-slim">
        Estimates for education, not medical advice.
        <button type="button" class="linkbtn" id="showDisclaimer2">Read the full note</button>
      </p>
      <div class="disclaimer" id="disclaimerInline" hidden>
        ${esc(r.disclaimer)}<br><br>${esc(r.safeguarding)}
      </div>`;
  },

  /* =========================================================================
   *  FULL ASSESSMENT
   * ====================================================================== */
  assessment(r) {
    const n = r.nutrition;
    const c = r.composition;
    const blocked = r.safety?.blocked;

    return `
      ${this.safety(r.safety)}

      ${blocked ? `
        <div class="blocked-notice">
          The numbers below are shown for transparency, but this plan is not
          recommended as calculated. Please read the flags above first.
        </div>` : ''}

      <div class="${blocked ? 'blocked' : ''}">

        <!-- ===== Calories + macro donut ===== -->
        <div class="card">
          <div class="card__head">
            <h2>Your daily targets</h2>
            <button class="btn btn--ghost btn--sm no-print" onclick="window.print()">
              Print / save summary
            </button>
          </div>
          <p class="card__hint">
            Every card below opens into the full reasoning — the physiology, what
            goes wrong at too little or too much, real food portions, and the
            standard behind the number. That's the part most plans leave out.
          </p>

          <div class="grid grid--2">
            <div>${this.target(n.kcal, { key: 'kcal', label: 'Calories', icon: '◉' })}</div>
            <div class="chart-box center">
              <canvas id="macroDonut" aria-label="Macronutrient split chart"></canvas>
              <div class="legend" style="justify-content:center">
                <span class="legend__item">
                  <span class="legend__dot" style="background:var(--c-protein)"></span>
                  Protein ${n.protein.pct_kcal}%
                </span>
                <span class="legend__item">
                  <span class="legend__dot" style="background:var(--c-fat)"></span>
                  Fat ${n.fat.pct_kcal}%
                </span>
                <span class="legend__item">
                  <span class="legend__dot" style="background:var(--c-carbs)"></span>
                  Carbs ${n.carbs.pct_kcal}%
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- ===== The three macros ===== -->
        <div class="stack">
          ${this.target(n.protein, { key: 'protein', label: 'Protein', icon: '◆' })}
          ${this.target(n.fat,     { key: 'fat',     label: 'Fat',     icon: '●' })}
          ${this.target(n.carbs,   { key: 'carbs',   label: 'Carbohydrate', icon: '▲' })}
          ${this.target(n.fibre,   { key: 'fibre',   label: 'Fibre',   icon: '❋' })}
          ${this.target(n.water,   { key: 'water',   label: 'Water',   icon: '≈' })}
        </div>

        <!-- ===== Meal split ===== -->
        <div class="card" style="margin-top:var(--sp-4)">
          <div class="card__head"><h2>Meal-by-meal breakdown</h2></div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Meal</th>
                  <th class="num">Protein</th>
                  <th class="num">Carbs</th>
                  <th class="num">Fat</th>
                  <th class="num">Calories</th>
                </tr>
              </thead>
              <tbody>
                ${n.meal_split.meals.map(m => `
                  <tr>
                    <td class="strong">${esc(m.meal)}</td>
                    <td class="num">${m.protein_g} g</td>
                    <td class="num">${m.carb_g} g</td>
                    <td class="num">${m.fat_g} g</td>
                    <td class="num">${num(m.kcal)}</td>
                  </tr>`).join('')}
                <tr style="background:var(--surface-2)">
                  <td class="strong">Total</td>
                  <td class="num strong">${n.protein.number} g</td>
                  <td class="num strong">${n.carbs.number} g</td>
                  <td class="num strong">${n.fat.number} g</td>
                  <td class="num strong">${num(n.kcal.number)}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <details class="why">
            <summary>Why split it this way?</summary>
            <div class="why__body">
              <div class="why__reason">${paras(n.meal_split.explain)}</div>
              ${this.cites(n.meal_split.sources)}
            </div>
          </details>
        </div>

        ${this.fullSections(r)}

      </div>

      <div class="disclaimer" style="margin-top:var(--sp-5)">
        <strong>Important:</strong> ${esc(r.disclaimer)}
      </div>
      <div class="disclaimer">${esc(r.safeguarding)}</div>`;
  },

  /* =========================================================================
   *  BODY FAT method comparison
   * ====================================================================== */
  /* =========================================================================
   *  THE DEEP SECTIONS — energy, composition, body-fat methods, micronutrients
   *
   *  Extracted so both views share one implementation: the full report renders
   *  them inline, and the simple view tucks the identical markup behind its
   *  "show me everything" fold. The depth can never drift between the two.
   * ====================================================================== */
  fullSections(r) {
    const c = r.composition;
    return `
        <!-- ===== Energy ===== -->
        <div class="card">
          <div class="card__head"><h2>Energy — where the calories came from</h2></div>
          <div class="grid grid--tight">
            <div class="stat">
              <div class="stat__label">BMR · Mifflin–St Jeor</div>
              <div class="stat__value">${num(r.energy.bmr.mifflin)}</div>
              <div class="stat__sub">From total bodyweight</div>
            </div>
            <div class="stat">
              <div class="stat__label">BMR · Katch–McArdle</div>
              <div class="stat__value" style="color:var(--accent)">${num(r.energy.bmr.katch_mcardle)}</div>
              <div class="stat__sub">From lean mass — used here</div>
            </div>
            <div class="stat">
              <div class="stat__label">TDEE</div>
              <div class="stat__value">${num(r.energy.tdee)}</div>
              <div class="stat__sub">×${r.energy.activity.factor} activity</div>
            </div>
            <div class="stat">
              <div class="stat__label">Difference</div>
              <div class="stat__value">${num(r.energy.bmr.difference)}</div>
              <div class="stat__sub">Between the two equations</div>
            </div>
          </div>

          <details class="why">
            <summary>Why two BMR equations, and which to trust?</summary>
            <div class="why__body">
              <div class="why__reason">${paras(r.energy.bmr.why_katch)}</div>
              <div class="why__section">
                <div class="why__section-title">On your activity multiplier</div>
                <div class="why__reason">${paras(r.energy.activity.explain)}</div>
              </div>
              ${this.cites(r.energy.bmr.sources)}
            </div>
          </details>

          <div class="card__head" style="margin-top:var(--sp-5)"><h3>All four goal targets</h3></div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Goal</th><th class="num">Calories</th>
                  <th class="num">vs maintenance</th><th class="num">Rate/week</th>
                </tr>
              </thead>
              <tbody>
                ${Object.entries(r.energy.targets).map(([k, t]) => `
                  <tr>
                    <td class="strong">${esc(k.replace(/_/g, ' '))}</td>
                    <td class="num">${num(t.kcal)}</td>
                    <td class="num">${t.delta > 0 ? '+' : ''}${num(t.delta)}</td>
                    <td class="num">${t.kg_per_week ? `${t.kg_per_week} kg (${t.pct_bw_per_week}%)` : '—'}</td>
                  </tr>`).join('')}
              </tbody>
            </table>
          </div>
          <div class="note">${esc(r.energy.targets_explain)}</div>
        </div>

        <!-- ===== Composition ===== -->
        <div class="card">
          <div class="card__head"><h2>Body composition</h2></div>
          <div class="grid grid--tight">
            <div class="stat">
              <div class="stat__label">Body fat</div>
              <div class="stat__value">${c.bodyfat_pct}%</div>
              <div class="stat__sub">
                <span class="chip chip--${riskClass(c.bodyfat_band.risk)}">${esc(c.bodyfat_band.label)}</span>
              </div>
            </div>
            <div class="stat">
              <div class="stat__label">Lean mass</div>
              <div class="stat__value" style="color:var(--c-protein)">${c.lean_mass_kg} kg</div>
              <div class="stat__sub">Drives protein &amp; BMR</div>
            </div>
            <div class="stat">
              <div class="stat__label">Fat mass</div>
              <div class="stat__value">${c.fat_mass_kg} kg</div>
            </div>
            <div class="stat">
              <div class="stat__label">FFMI (normalised)</div>
              <div class="stat__value" style="color:var(--violet)">${c.ffmi.normalised}</div>
              <div class="stat__sub">${esc(c.ffmi.band)}</div>
            </div>
            ${c.waist_to_height ? `
            <div class="stat">
              <div class="stat__label">Waist : height</div>
              <div class="stat__value">${c.waist_to_height.ratio}</div>
              <div class="stat__sub">
                <span class="chip chip--${riskClass(c.waist_to_height.risk)}">${esc(c.waist_to_height.band)}</span>
              </div>
            </div>` : ''}
            <div class="stat">
              <div class="stat__label">BMI</div>
              <div class="stat__value">${r.bodyfat.bmi}</div>
              <div class="stat__sub">Context only — can't see muscle</div>
            </div>
          </div>

          <div class="note">${esc(c.lean_mass_explain)}</div>

          <details class="why">
            <summary>What FFMI means, and its limits</summary>
            <div class="why__body">
              <div class="why__reason">${paras(c.ffmi.context)}</div>
              <p class="xs muted">Raw FFMI: ${c.ffmi.raw} · normalised to 1.8 m: ${c.ffmi.normalised}</p>
              ${this.cites(c.ffmi.sources)}
            </div>
          </details>

          ${c.waist_to_height ? `
          <details class="why">
            <summary>Why waist-to-height ratio?</summary>
            <div class="why__body">
              <div class="why__reason">${paras(c.waist_to_height.explain)}</div>
              ${this.cites(c.waist_to_height.sources)}
            </div>
          </details>` : ''}

          <div class="card__head" style="margin-top:var(--sp-5)"><h3>What you'd weigh at a goal body fat</h3></div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th class="num">Body fat</th><th class="num">Weight</th><th class="num">Change</th><th>Band</th></tr>
              </thead>
              <tbody>
                ${c.goal_weights.map(g => `
                  <tr>
                    <td class="num strong">${g.bodyfat_pct}%</td>
                    <td class="num">${g.weight_kg} kg</td>
                    <td class="num" style="color:${g.change_kg < 0 ? 'var(--good)' : 'var(--text-muted)'}">
                      ${g.change_kg > 0 ? '+' : ''}${g.change_kg} kg
                    </td>
                    <td>${esc(g.band)}</td>
                  </tr>`).join('')}
              </tbody>
            </table>
          </div>
          <div class="note">${esc(c.goal_weight_note)}</div>
        </div>

        <!-- ===== Body fat methods ===== -->
        ${this.bodyfatCard(r.bodyfat)}

        <!-- ===== Micronutrients ===== -->
        ${this.microCard(r.micronutrients)}
`;
  },

  bodyfatCard(bf) {
    const shown = bf.methods.filter(m => m.method !== 'supplied');
    const maxV = Math.max(...bf.methods.map(m => m.value), 30);

    return `
      <div class="card">
        <div class="card__head">
          <h2>Body fat — four methods compared</h2>
          ${bf.spread ? `<span class="chip chip--${bf.spread > 5 ? 'caution' : 'ok'}">
            ${bf.spread}% spread between methods
          </span>` : ''}
        </div>

        <div class="bars">
          ${bf.methods.map(m => `
            <div class="bar-row">
              <div>
                <strong class="small">${esc(m.name)}</strong>
                ${m.method === bf.chosen.method
                  ? '<span class="chip chip--good" style="margin-left:4px">used</span>' : ''}
              </div>
              <div class="bar-track">
                <div class="bar-fill" style="width:${(m.value / maxV * 100).toFixed(1)}%"></div>
              </div>
              <span class="bar-value">${m.value}%</span>
            </div>`).join('')}
        </div>

        <div class="note">${esc(bf.available_note)}</div>

        <details class="why">
          <summary>Why don't they agree — and which should I trust?</summary>
          <div class="why__body">
            <div class="why__reason">${paras(bf.spread_note)}</div>

            <div class="why__section">
              <div class="why__section-title">Method by method</div>
              <div class="jobs">
                ${bf.methods.map(m => `
                  <div class="job">
                    <div class="job__label">${esc(m.name)} — ${m.value}%</div>
                    <p class="job__text">
                      <strong>How it works:</strong> ${esc(m.how)}<br>
                      <strong>Needs:</strong> ${esc(m.needs)}<br>
                      <strong>Trust level:</strong> ${esc(m.trust)}<br>
                      <strong>Watch out:</strong> ${esc(m.watch)}
                    </p>
                  </div>`).join('')}
              </div>
            </div>

            <div class="why__section">
              <div class="why__section-title">Reference bands</div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Category</th><th class="num">Range</th></tr></thead>
                  <tbody>
                    ${bf.bands.map(b => `
                      <tr>
                        <td><span class="chip chip--${riskClass(b.risk)}">${esc(b.label)}</span></td>
                        <td class="num">${b.min}–${b.max === 100 ? '+' : b.max}%</td>
                      </tr>`).join('')}
                  </tbody>
                </table>
              </div>
            </div>

            ${this.cites(bf.band_source)}
          </div>
        </details>
      </div>`;
  },

  /* =========================================================================
   *  MICRONUTRIENT panel
   * ====================================================================== */
  microCard(m) {
    const risks = (m.risks || []).map(r => `
      <div class="risk-card">
        <div class="risk-card__label">${esc(r.label)}</div>
        <p class="risk-card__why">${esc(r.why)}</p>
      </div>`).join('');

    return `
      <div class="card">
        <div class="card__head">
          <h2>Micronutrients</h2>
          ${m.priority_count ? `<span class="chip chip--caution">
            ${m.priority_count} flagged as priority for you
          </span>` : ''}
        </div>

        <div class="why__reason" style="margin-bottom:var(--sp-5)">${paras(m.explain)}</div>

        ${risks ? `
          <div class="card__head"><h3>Your risk factors</h3></div>
          <div class="grid" style="margin-bottom:var(--sp-5)">${risks}</div>` : ''}

        <div class="note" style="margin-bottom:var(--sp-4)">${esc(m.targets_explain)}</div>

        ${this.microRows(m.panel)}
      </div>`;
  },

  /** The expandable rows — shared between the assessment and the reference tab. */
  microRows(panel) {
    return panel.map(mn => {
      const cls = mn.priority === 'high' ? 'micro--high'
                : mn.priority === 'watch' ? 'micro--watch' : '';
      const target = mn.target_icmr ?? mn.target_western;

      return `
      <details class="micro ${cls}">
        <summary>
          <span class="micro__name">${esc(mn.name)}</span>
          ${mn.priority === 'high' ? '<span class="chip chip--caution">priority</span>' : ''}
          ${mn.flagged_by?.length
            ? `<span class="chip">${esc(mn.flagged_by[0])}${mn.flagged_by.length > 1 ? ` +${mn.flagged_by.length - 1}` : ''}</span>`
            : ''}
          <span class="micro__target">${target ?? '—'} ${esc(mn.unit)}</span>
        </summary>
        <div class="micro__body">

          <div class="targets-2">
            <div class="stat">
              <div class="stat__label">ICMR-NIN (India)</div>
              <div class="stat__value">${mn.target_icmr ?? '—'}</div>
              <div class="stat__sub">${esc(mn.unit)}</div>
            </div>
            <div class="stat">
              <div class="stat__label">IOM / WHO / EFSA</div>
              <div class="stat__value">${mn.target_western ?? '—'}</div>
              <div class="stat__sub">${esc(mn.unit)}</div>
            </div>
          </div>

          <div>
            <div class="micro__block-title">Why the two differ</div>
            <p class="micro__text">${esc(mn.note_on_targets)}</p>
          </div>

          <div>
            <div class="micro__block-title">What it does</div>
            <p class="micro__text">${esc(mn.what_it_does)}</p>
          </div>

          <div>
            <div class="micro__block-title">Why athletes &amp; dieters fall short</div>
            <p class="micro__text">${esc(mn.why_short)}</p>
          </div>

          <div class="risk-box risk-box--low">
            <div class="risk-box__title">Signs of deficiency</div>
            <ul>${mn.deficiency_signs.map(s => `<li>${esc(s)}</li>`).join('')}</ul>
          </div>

          <div class="risk-box risk-box--high">
            <div class="risk-box__title">Upper limit &amp; too much</div>
            <p class="micro__text" style="color:inherit">${esc(mn.upper_limit)}</p>
          </div>

          <div>
            <div class="micro__block-title">Training angle</div>
            <p class="micro__text">${esc(mn.athlete_note)}</p>
          </div>

          <div>
            <div class="micro__block-title">Best food sources for your diet</div>
            ${mn.food_sources?.length ? `
              <div class="foods">
                ${mn.food_sources.map(f => `
                  <div class="food-row">
                    <span class="food-row__name">${esc(f.name)}</span>
                    <span class="food-row__portion">${esc(f.household)}</span>
                  </div>`).join('')}
              </div>`
              : `<div class="note">${esc(mn.no_food_source_note || 'No specific sources listed.')}</div>`}
          </div>

          ${mn.flagged_by?.length ? `
            <div>
              <div class="micro__block-title">Flagged for you because</div>
              <div class="pills">
                ${mn.flagged_by.map(fb => `<span class="chip chip--caution">${esc(fb)}</span>`).join('')}
              </div>
            </div>` : ''}

          ${this.cites(mn.sources)}
        </div>
      </details>`;
    }).join('');
  },

  /* =========================================================================
   *  PREP PLANNER
   * ====================================================================== */
  prep(r) {
    const p = r.plan;
    return `
      ${this.safety(r.safety)}

      <div class="card">
        <div class="card__head">
          <h2>The plan</h2>
          <span class="chip chip--${riskClass(p.risk)}">${esc(p.verdict)}</span>
        </div>

        <div class="grid grid--tight">
          <div class="stat">
            <div class="stat__label">Total to ${esc(p.direction)}</div>
            <div class="stat__value">${p.total_change_kg} kg</div>
            <div class="stat__sub">${p.current_weight_kg} → ${p.goal_weight_kg} kg</div>
          </div>
          <div class="stat">
            <div class="stat__label">Required rate</div>
            <div class="stat__value" style="color:var(--${p.risk === 'danger' ? 'danger' : p.risk === 'caution' ? 'caution' : 'good'})">
              ${p.per_week_kg} kg
            </div>
            <div class="stat__sub">${p.per_week_pct_bw}% of bodyweight/week</div>
          </div>
          <div class="stat">
            <div class="stat__label">At a safe rate</div>
            <div class="stat__value" style="color:var(--accent)">${p.weeks_at_safe_rate} wk</div>
            <div class="stat__sub">vs your ${p.weeks} weeks</div>
          </div>
          <div class="stat">
            <div class="stat__label">Implied daily deficit</div>
            <div class="stat__value">${num(p.implied_daily_kcal_delta)}</div>
            <div class="stat__sub">kcal/day</div>
          </div>
        </div>

        <div class="why__reason" style="margin-top:var(--sp-5)">${paras(r.explain)}</div>
        <div class="note">${esc(r.implied_kcal_note)}</div>
      </div>

      <div class="card">
        <div class="card__head"><h2>Week-by-week projection</h2></div>
        <div class="chart-box">
          <canvas id="prepChart" aria-label="Projected body fat and weight over time"></canvas>
          <div class="legend">
            <span class="legend__item"><span class="legend__dot" style="background:var(--c-carbs)"></span>Body fat %</span>
            <span class="legend__item"><span class="legend__dot" style="background:var(--c-protein)"></span>Weight (kg)</span>
          </div>
        </div>

        <div class="table-wrap" style="margin-top:var(--sp-4);max-height:420px;overflow-y:auto">
          <table>
            <thead>
              <tr>
                <th class="num">Week</th><th class="num">Weight</th>
                <th class="num">Body fat</th><th class="num">Fat mass</th><th class="num">Lean mass</th>
              </tr>
            </thead>
            <tbody>
              ${p.projection.map(w => `
                <tr>
                  <td class="num strong">${w.week}</td>
                  <td class="num">${w.weight_kg}</td>
                  <td class="num">${w.bodyfat_pct}%</td>
                  <td class="num">${w.fat_mass_kg}</td>
                  <td class="num">${w.lean_mass_kg}</td>
                </tr>`).join('')}
            </tbody>
          </table>
        </div>
        <div class="note">
          Lean mass is held constant across the projection — the best case, and
          only achievable with a moderate deficit, protein at the top of its
          range, and hard training throughout.
        </div>
        ${this.cites(r.sources)}
      </div>

      <div class="disclaimer">${esc(r.disclaimer)}</div>`;
  },

  /* =========================================================================
   *  STRENGTH
   * ====================================================================== */
  strength(r) {
    const o = r.one_rm;
    return `
      <div class="card">
        <div class="card__head">
          <h2>Estimated 1RM</h2>
          <span class="chip chip--${o.confidence === 'high' ? 'good' : o.confidence === 'moderate' ? 'ok' : 'caution'}">
            ${esc(o.confidence)} confidence
          </span>
        </div>

        <div class="grid grid--tight">
          <div class="stat">
            <div class="stat__label">Average estimate</div>
            <div class="stat__value" style="color:var(--accent);font-size:2rem">${o.average} kg</div>
            <div class="stat__sub">From ${o.weight} kg × ${o.reps} reps</div>
          </div>
          <div class="stat">
            <div class="stat__label">Epley</div>
            <div class="stat__value">${o.epley} kg</div>
            <div class="stat__sub">${o.reps < 10 ? 'Higher of the two below 10 reps'
              : o.reps === 10 ? 'Both agree at 10 reps' : 'Lower of the two above 10 reps'}</div>
          </div>
          <div class="stat">
            <div class="stat__label">Brzycki</div>
            <div class="stat__value">${o.brzycki} kg</div>
            <div class="stat__sub">${o.reps < 10 ? 'Lower of the two below 10 reps'
              : o.reps === 10 ? 'Both agree at 10 reps' : 'Higher of the two above 10 reps'}</div>
          </div>
        </div>

        <details class="why">
          <summary>How these estimates work</summary>
          <div class="why__body">
            <div class="why__reason">${paras(r.explain)}</div>
            ${this.cites(r.sources)}
          </div>
        </details>
      </div>

      <div class="card">
        <div class="card__head"><h2>Percentage of 1RM — loading table</h2></div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th class="num">%1RM</th><th class="num">Weight</th><th class="num">Plate-rounded</th><th class="num">Reps</th><th>Use it for</th></tr>
            </thead>
            <tbody>
              ${r.table.map(t => `
                <tr>
                  <td class="num strong">${t.pct}%</td>
                  <td class="num">${t.weight} kg</td>
                  <td class="num" style="color:var(--accent)">${t.plate_rounded} kg</td>
                  <td class="num">${esc(t.reps)}</td>
                  <td class="small">${esc(t.use)}</td>
                </tr>`).join('')}
            </tbody>
          </table>
        </div>
        <div class="note">${esc(r.table_explain)}</div>
      </div>

      ${r.scores ? `
      <div class="card">
        <div class="card__head">
          <h2>Bodyweight-adjusted score</h2>
          <span class="chip chip--ok">${esc(r.scores.band)}</span>
        </div>
        <div class="grid grid--tight">
          <div class="stat">
            <div class="stat__label">DOTS</div>
            <div class="stat__value" style="color:var(--accent);font-size:2rem">${r.scores.dots ?? '—'}</div>
            <div class="stat__sub">Modern federation standard</div>
          </div>
          <div class="stat">
            <div class="stat__label">Wilks</div>
            <div class="stat__value">${r.scores.wilks ?? '—'}</div>
            <div class="stat__sub">For comparing historical results</div>
          </div>
        </div>
        <details class="why">
          <summary>What these scores mean</summary>
          <div class="why__body">
            <div class="why__reason">${paras(r.scores.explain)}</div>
            ${this.cites(r.scores.sources)}
          </div>
        </details>
      </div>` : ''}

      <div class="disclaimer">${esc(r.disclaimer)}</div>`;
  },

  /* =========================================================================
   *  SOURCES
   * ====================================================================== */
  sources(r) {
    // Group by organisation so related standards sit together.
    const byOrg = {};
    r.sources.forEach(s => { (byOrg[s.org] ||= []).push(s); });

    return `
      <div class="card">
        <div class="card__head">
          <h2>${r.count} standards</h2>
        </div>
        <div class="note" style="margin-bottom:var(--sp-4)">${esc(r.note)}</div>
        ${Object.entries(byOrg).map(([org, list]) => `
          <div style="margin-bottom:var(--sp-5)">
            <div class="why__section-title">${esc(org)}</div>
            <div class="cites">
              ${list.map(s => `
                <div class="cite">
                  <span class="cite__org mono">${esc(s.key)}</span>
                  <span class="cite__body">
                    <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)}</a>
                    <span class="cite__note">${esc(s.title)}</span>
                    <span class="cite__note">${esc(s.note)}</span>
                  </span>
                </div>`).join('')}
            </div>
          </div>`).join('')}
      </div>`;
  },

  /* =========================================================================
   *  CLIENTS
   * ====================================================================== */
  clientList(clients, activeId) {
    if (!clients.length) return '<p class="muted small">No clients yet. Add one above.</p>';
    return clients.map(c => `
      <button class="btn btn--ghost btn--full" data-client="${c.id}"
              style="justify-content:space-between;margin-bottom:var(--sp-2);
                     ${c.id === activeId ? 'border-color:var(--accent)' : ''}">
        <span>${esc(c.name)}</span>
        <span class="xs muted">
          ${c.measurement_count} log${c.measurement_count === 1 ? '' : 's'}
        </span>
      </button>`).join('');
  },

  clientDetail(d) {
    const c = d.client;
    const p = d.progress;

    return `
      <div class="card">
        <div class="card__head">
          <h2>${esc(c.name)}</h2>
          <div class="actions">
            <span class="chip">${esc(c.sex)} · ${c.age}y · ${c.height_cm} cm</span>
            <span class="chip">${esc(c.diet)}</span>
            <span class="chip">${esc(c.goal)}</span>
            <button class="btn btn--danger btn--sm no-print" id="deleteClientBtn" data-id="${c.id}">Delete</button>
          </div>
        </div>
        ${c.notes ? `<p class="small muted">${esc(c.notes)}</p>` : ''}
      </div>

      <div class="card">
        <div class="card__head"><h2>Log a measurement</h2></div>
        <form id="measForm" data-client="${c.id}">
          <div class="row">
            <div class="field"><label for="m_date">Date</label><input type="date" id="m_date" required /></div>
            <div class="field"><label for="m_weight">Weight (kg)</label><input type="number" id="m_weight" step="0.1" min="25" max="300" required /></div>
            <div class="field"><label for="m_bf">Body fat %</label><input type="number" id="m_bf" step="0.1" min="2" max="70" /></div>
            <div class="field"><label for="m_waist">Waist (cm)</label><input type="number" id="m_waist" step="0.5" min="40" max="200" /></div>
            <div class="field"><label for="m_chest">Chest (cm)</label><input type="number" id="m_chest" step="0.5" min="50" max="200" /></div>
            <div class="field"><label for="m_arm">Arm (cm)</label><input type="number" id="m_arm" step="0.5" min="15" max="80" /></div>
            <div class="field"><label for="m_thigh">Thigh (cm)</label><input type="number" id="m_thigh" step="0.5" min="25" max="110" /></div>
          </div>
          <div class="field">
            <label for="m_note">Note</label>
            <input type="text" id="m_note" maxlength="500" placeholder="e.g. week 4, sleep poor, training good" />
          </div>
          <button type="submit" class="btn btn--primary">Add measurement</button>
        </form>
      </div>

      ${p ? `
      <div class="card">
        <div class="card__head">
          <h2>Progress</h2>
          <span class="chip">${p.entries} entr${p.entries === 1 ? 'y' : 'ies'}</span>
        </div>
        <div class="grid grid--tight">
          <div class="stat">
            <div class="stat__label">Weight change</div>
            <div class="stat__value" style="color:${(p.weight_change_kg ?? 0) < 0 ? 'var(--good)' : 'var(--text)'}">
              ${p.weight_change_kg > 0 ? '+' : ''}${p.weight_change_kg ?? '—'} kg
            </div>
            <div class="stat__sub">${esc(p.first.taken_on)} → ${esc(p.latest.taken_on)}</div>
          </div>
          ${p.bodyfat_change_pct !== null ? `
          <div class="stat">
            <div class="stat__label">Body fat change</div>
            <div class="stat__value" style="color:${p.bodyfat_change_pct < 0 ? 'var(--good)' : 'var(--text)'}">
              ${p.bodyfat_change_pct > 0 ? '+' : ''}${p.bodyfat_change_pct}%
            </div>
          </div>` : ''}
          ${p.fat_mass_change_kg !== null ? `
          <div class="stat">
            <div class="stat__label">Fat mass</div>
            <div class="stat__value" style="color:${p.fat_mass_change_kg < 0 ? 'var(--good)' : 'var(--caution)'}">
              ${p.fat_mass_change_kg > 0 ? '+' : ''}${p.fat_mass_change_kg} kg
            </div>
          </div>
          <div class="stat">
            <div class="stat__label">Lean mass</div>
            <div class="stat__value" style="color:${p.lean_mass_change_kg >= 0 ? 'var(--good)' : 'var(--danger)'}">
              ${p.lean_mass_change_kg > 0 ? '+' : ''}${p.lean_mass_change_kg} kg
            </div>
            <div class="stat__sub">The number that matters most in a cut</div>
          </div>` : ''}
          ${p.waist_change_cm !== null ? `
          <div class="stat">
            <div class="stat__label">Waist</div>
            <div class="stat__value">${p.waist_change_cm > 0 ? '+' : ''}${p.waist_change_cm} cm</div>
          </div>` : ''}
        </div>

        ${p.fat_mass_change_kg !== null ? `
          <div class="note">
            Losing weight is easy to measure and easy to misread. What matters is
            what the loss was <em>made of</em>: fat mass down with lean mass held
            is the goal. Both dropping together means the deficit is too steep,
            protein is too low, or training isn't hard enough to signal your body
            to keep the muscle.
          </div>` : ''}
      </div>

      <div class="card">
        <div class="card__head"><h2>Trend</h2></div>
        <div class="chart-box">
          <canvas id="clientChart" aria-label="Client weight and body fat over time"></canvas>
          <div class="legend">
            <span class="legend__item"><span class="legend__dot" style="background:var(--c-protein)"></span>Weight (kg)</span>
            ${d.measurements.some(m => m.bodyfat_pct) ? `
              <span class="legend__item"><span class="legend__dot" style="background:var(--c-carbs)"></span>Body fat %</span>` : ''}
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card__head"><h2>All measurements</h2></div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Date</th><th class="num">Weight</th><th class="num">BF%</th>
                <th class="num">Waist</th><th class="num">Chest</th><th class="num">Arm</th>
                <th>Note</th><th></th>
              </tr>
            </thead>
            <tbody>
              ${[...d.measurements].reverse().map(m => `
                <tr>
                  <td class="mono small">${esc(m.taken_on)}</td>
                  <td class="num">${m.weight_kg}</td>
                  <td class="num">${m.bodyfat_pct ?? '—'}</td>
                  <td class="num">${m.waist_cm ?? '—'}</td>
                  <td class="num">${m.chest_cm ?? '—'}</td>
                  <td class="num">${m.arm_cm ?? '—'}</td>
                  <td class="small muted">${esc(m.note || '')}</td>
                  <td>
                    <button class="btn btn--ghost btn--sm no-print" data-del-meas="${m.id}"
                            title="Delete this measurement">×</button>
                  </td>
                </tr>`).join('')}
            </tbody>
          </table>
        </div>
      </div>`
      : `
      <div class="card">
        <div class="empty">
          <div class="empty__icon" aria-hidden="true">◕</div>
          <p>No measurements logged yet.</p>
          <p class="xs">Add the first one above — the trend is what tells you if this is working.</p>
        </div>
      </div>`}`;
  },
};

/* =============================================================================
 *  ONBOARDING (coach side) — appended to the Render object.
 * =============================================================================
 *  Kept separate from the object literal above only because it was added later;
 *  same namespace, same conventions.
 * ========================================================================== */

Object.assign(Render, {

  /** The list of onboarding links, newest first. */
  inviteList(invites) {
    if (!invites.length) {
      return `<p class="muted small">
        No links yet. Create one above and send it to your client — it's the whole
        onboarding flow in a single URL.
      </p>`;
    }

    const stateChip = {
      ok: '<span class="chip chip--good">ready to send</span>',
      used: '<span class="chip">filled in</span>',
      expired: '<span class="chip chip--caution">expired</span>',
      revoked: '<span class="chip chip--danger">cancelled</span>',
      missing: '<span class="chip chip--danger">invalid</span>',
    };

    return invites.map(inv => `
      <div class="invite ${inv.state === 'ok' ? '' : 'invite--used'}">
        <div class="invite__main">
          <span class="invite__label">${esc(inv.label || 'Unlabelled link')}</span>
          ${inv.state === 'ok'
            ? `<span class="invite__url">${esc(inv.url)}</span>`
            : `<span class="invite__url">link hidden — ${esc(inv.state)}</span>`}
        </div>
        ${stateChip[inv.state] || ''}
        ${inv.state === 'ok' ? `
          <button class="btn btn--ghost btn--sm" data-copy="${esc(inv.url)}">Copy link</button>
          <button class="btn btn--ghost btn--sm" data-revoke="${inv.id}"
                  title="Stop this link working">Cancel</button>` : `
          <button class="btn btn--ghost btn--sm" data-del-invite="${inv.id}">Remove</button>`}
      </div>`).join('');
  },

  /** The list of submitted questionnaires. */
  intakeList(intakes) {
    if (!intakes.length) {
      return `<p class="muted small">Nothing submitted yet.</p>`;
    }
    return intakes.map(i => `
      <div class="invite">
        <div class="invite__main">
          <span class="invite__label">${esc(i.full_name || 'Unnamed')}</span>
          <span class="invite__url">
            ${esc((i.created_at || '').slice(0, 10))}
            ${i.contact ? ' · ' + esc(i.contact) : ''}
            ${i.client_id ? ' · already a client' : ''}
          </span>
        </div>
        <button class="btn btn--ghost btn--sm" data-open-intake="${i.id}">Read it</button>
      </div>`).join('');
  },

  /**
   * One full submission.
   *
   * Answers are labelled using the same section schema the client filled in, so
   * the coach reads questions rather than database keys — and any answer to a
   * question that has since been reworded still displays under its original label.
   */
  intakeDetail(data) {
    const answers = data.answers || {};

    const labelFor = (section, field) => {
      const raw = answers[field.key];
      if (raw === undefined || raw === null || String(raw).trim() === '') return null;
      // Map stored option values back to the label the client actually saw.
      let shown = String(raw);
      if (field.options) {
        const hit = field.options.find(o => o.value === raw);
        if (hit) shown = hit.label;
      }
      return `<div class="answer-row">
        <dt>${esc(field.label)}</dt>
        <dd>${esc(shown)}${field.unit ? ' ' + esc(field.unit) : ''}</dd>
      </div>`;
    };

    const sections = (data.sections || []).map(section => {
      const rows = section.fields.map(f => labelFor(section, f)).filter(Boolean).join('');
      if (!rows) return '';
      return `
        <div class="card">
          <div class="card__head"><h3>${esc(section.title)}</h3></div>
          <dl class="answer-grid">${rows}</dl>
        </div>`;
    }).join('');

    const priorities = (data.priorities || []).map((p, i) => `
      <div class="step">
        <span class="step__n">${i + 1}</span>
        <div>
          <div class="step__do">${esc(p.title)}</div>
          <p class="step__how">${esc(p.because)}</p>
        </div>
      </div>`).join('');

    return `
      <div class="card" style="margin-top:var(--sp-5)">
        <div class="card__head">
          <h2>${esc(data.full_name || 'Submission')}</h2>
          <div class="actions">
            ${data.client_id
              ? '<span class="chip chip--good">linked to a client</span>'
              : `<button class="btn btn--primary btn--sm" data-convert="${data.id}">
                   Add as a client
                 </button>`}
            <button class="btn btn--danger btn--sm" data-del-intake="${data.id}"
                    title="Permanently delete this submission">Delete</button>
            <button class="btn btn--ghost btn--sm" id="closeIntake">Close</button>
          </div>
        </div>
        <p class="small muted">
          Submitted ${esc((data.created_at || '').replace('T', ' ').slice(0, 16))}
          · consent recorded (${esc(data.consent_version || '—')})
          ${data.contact ? ' · ' + esc(data.contact) : ''}
        </p>
        ${priorities ? `
          <div class="card__head" style="margin-top:var(--sp-5)"><h3>What stands out</h3></div>
          <div class="steps">${priorities}</div>
          <div class="note">
            The client saw these too — it's what convinces them you read their
            answers. Their numbers were deliberately not shown to them.
          </div>` : ''}
      </div>
      ${sections}`;
  },
});

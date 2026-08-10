/* =============================================================================
 *  charts.js — Canvas charts, no libraries.
 * =============================================================================
 *  Three chart types, which is all this app needs:
 *    donut()    macro split
 *    line()     prep projection / client progress over time
 *    grouped()  fat vs lean mass change
 *
 *  Two things every chart here gets right, because they're the usual reasons
 *  hand-rolled canvas looks amateurish:
 *
 *  1. Device pixel ratio. A canvas sized in CSS pixels renders blurry on a
 *     Retina display. `setup()` scales the backing store by devicePixelRatio and
 *     then scales the context back, so one canvas unit = one CSS pixel and the
 *     output is sharp.
 *  2. Theme colours are read from the live CSS custom properties rather than
 *     hardcoded, so a theme toggle recolours the charts. `Charts.redrawAll()`
 *     re-runs every draw call after a theme change — each chart registers its
 *     own redraw closure when it draws.
 * ========================================================================== */

const Charts = {

  /** Every drawn chart registers a redraw closure here for theme switching. */
  _registry: [],

  /** Read a CSS custom property from :root. */
  css(name) {
    return getComputedStyle(document.documentElement)
      .getPropertyValue(name).trim() || '#888';
  },

  /**
   * Prepare a canvas for crisp drawing at a given CSS size.
   * Returns the 2D context with the DPR transform already applied.
   */
  setup(canvas, cssWidth, cssHeight) {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(cssWidth * dpr);
    canvas.height = Math.round(cssHeight * dpr);
    canvas.style.width = cssWidth + 'px';
    canvas.style.height = cssHeight + 'px';
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssWidth, cssHeight);
    return ctx;
  },

  /** Re-run every registered chart's draw closure. Called on theme toggle. */
  redrawAll() {
    this._registry = this._registry.filter(fn => {
      try { return fn() !== false; } catch { return false; }
    });
  },

  /** Drop all registrations — called when a panel's contents are replaced. */
  reset() {
    this._registry = [];
  },

  /* ---------------------------------------------------------------------
   *  DONUT — macro split
   * ------------------------------------------------------------------ */
  donut(canvas, segments, centreLabel, centreSub) {
    const draw = () => {
      // The canvas may have been removed from the DOM by a re-render.
      if (!canvas.isConnected) return false;

      const box = canvas.parentElement.getBoundingClientRect();
      const size = Math.max(180, Math.min(300, box.width - 32));
      const ctx = this.setup(canvas, size, size);

      const cx = size / 2, cy = size / 2;
      const radius = size / 2 - 10;
      const thickness = Math.max(20, size * 0.14);
      const total = segments.reduce((s, x) => s + x.value, 0) || 1;

      // Track behind the segments, so a partial ring still reads as a ring.
      ctx.beginPath();
      ctx.arc(cx, cy, radius - thickness / 2, 0, Math.PI * 2);
      ctx.strokeStyle = this.css('--surface-3');
      ctx.lineWidth = thickness;
      ctx.stroke();

      let angle = -Math.PI / 2;   // start at 12 o'clock
      segments.forEach(seg => {
        const sweep = (seg.value / total) * Math.PI * 2;
        if (sweep <= 0) return;
        ctx.beginPath();
        ctx.arc(cx, cy, radius - thickness / 2, angle, angle + sweep);
        ctx.strokeStyle = this.css(seg.colorVar);
        ctx.lineWidth = thickness;
        ctx.lineCap = 'butt';
        ctx.stroke();
        angle += sweep;
      });

      // Centre text
      ctx.fillStyle = this.css('--text');
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.font = `700 ${Math.round(size * 0.15)}px "JetBrains Mono", monospace`;
      ctx.fillText(centreLabel, cx, cy - (centreSub ? size * 0.05 : 0));

      if (centreSub) {
        ctx.fillStyle = this.css('--text-muted');
        ctx.font = `400 ${Math.round(size * 0.062)}px Inter, sans-serif`;
        ctx.fillText(centreSub, cx, cy + size * 0.09);
      }
      return true;
    };

    draw();
    this._registry.push(draw);
  },

  /* ---------------------------------------------------------------------
   *  LINE — one or more series over an x axis
   *
   *  series: [{ label, points: [{x, y}], colorVar, dashed }]
   * ------------------------------------------------------------------ */
  line(canvas, series, { xLabel = '', yLabel = '', yUnit = '', xTickEvery = null } = {}) {
    const draw = () => {
      if (!canvas.isConnected) return false;

      const box = canvas.parentElement.getBoundingClientRect();
      const w = Math.max(280, box.width - 32);
      const h = Math.min(340, Math.max(200, w * 0.5));
      const ctx = this.setup(canvas, w, h);

      const pad = { top: 16, right: 16, bottom: 38, left: 48 };
      const plotW = w - pad.left - pad.right;
      const plotH = h - pad.top - pad.bottom;

      const all = series.flatMap(s => s.points);
      if (!all.length) return true;

      const xs = all.map(p => p.x), ys = all.map(p => p.y);
      const xMin = Math.min(...xs), xMax = Math.max(...xs);
      let yMin = Math.min(...ys), yMax = Math.max(...ys);

      // Pad the y range by 8% so the line never touches the frame, and guard
      // against a flat series collapsing the scale to zero height.
      const yPad = (yMax - yMin) * 0.08 || Math.max(1, yMax * 0.05);
      yMin -= yPad; yMax += yPad;

      const sx = x => pad.left + ((x - xMin) / ((xMax - xMin) || 1)) * plotW;
      const sy = y => pad.top + plotH - ((y - yMin) / ((yMax - yMin) || 1)) * plotH;

      // --- grid + y labels ---
      ctx.strokeStyle = this.css('--line');
      ctx.fillStyle = this.css('--text-faint');
      ctx.lineWidth = 1;
      ctx.font = '400 10px "JetBrains Mono", monospace';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';

      const ySteps = 5;
      for (let i = 0; i <= ySteps; i++) {
        const val = yMin + ((yMax - yMin) / ySteps) * i;
        const y = sy(val);
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(pad.left + plotW, y);
        ctx.stroke();
        ctx.fillText(val.toFixed(1), pad.left - 8, y);
      }

      // --- x labels ---
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const step = xTickEvery || Math.max(1, Math.ceil((xMax - xMin) / 8));
      for (let x = xMin; x <= xMax; x += step) {
        ctx.fillText(String(Math.round(x)), sx(x), pad.top + plotH + 10);
      }

      // --- axis titles ---
      ctx.fillStyle = this.css('--text-muted');
      ctx.font = '500 10px Inter, sans-serif';
      if (xLabel) ctx.fillText(xLabel, pad.left + plotW / 2, h - 12);
      if (yLabel) {
        ctx.save();
        ctx.translate(12, pad.top + plotH / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(yLabel + (yUnit ? ` (${yUnit})` : ''), 0, 0);
        ctx.restore();
      }

      // --- series ---
      series.forEach(s => {
        if (!s.points.length) return;
        const color = this.css(s.colorVar);

        // Soft fill under a single-series line, for a bit of depth.
        if (series.length === 1) {
          const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + plotH);
          grad.addColorStop(0, color + '38');
          grad.addColorStop(1, color + '00');
          ctx.beginPath();
          ctx.moveTo(sx(s.points[0].x), sy(s.points[0].y));
          s.points.forEach(p => ctx.lineTo(sx(p.x), sy(p.y)));
          ctx.lineTo(sx(s.points[s.points.length - 1].x), pad.top + plotH);
          ctx.lineTo(sx(s.points[0].x), pad.top + plotH);
          ctx.closePath();
          ctx.fillStyle = grad;
          ctx.fill();
        }

        ctx.beginPath();
        ctx.setLineDash(s.dashed ? [5, 4] : []);
        s.points.forEach((p, i) => {
          const x = sx(p.x), y = sy(p.y);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.lineJoin = 'round';
        ctx.stroke();
        ctx.setLineDash([]);

        // Dots — only when the series is sparse enough that they don't merge.
        if (s.points.length <= 30) {
          s.points.forEach(p => {
            ctx.beginPath();
            ctx.arc(sx(p.x), sy(p.y), 3, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();
            ctx.strokeStyle = this.css('--surface');
            ctx.lineWidth = 1.5;
            ctx.stroke();
          });
        }
      });

      return true;
    };

    draw();
    this._registry.push(draw);
  },

  /* ---------------------------------------------------------------------
   *  GROUPED BARS — e.g. fat mass vs lean mass, start vs now
   * ------------------------------------------------------------------ */
  grouped(canvas, groups, { yUnit = 'kg' } = {}) {
    const draw = () => {
      if (!canvas.isConnected) return false;

      const box = canvas.parentElement.getBoundingClientRect();
      const w = Math.max(260, box.width - 32);
      const h = 220;
      const ctx = this.setup(canvas, w, h);

      const pad = { top: 20, right: 12, bottom: 42, left: 44 };
      const plotW = w - pad.left - pad.right;
      const plotH = h - pad.top - pad.bottom;

      const allVals = groups.flatMap(g => g.bars.map(b => b.value));
      const maxV = Math.max(...allVals, 1) * 1.15;

      const sy = v => pad.top + plotH - (v / maxV) * plotH;

      // y grid
      ctx.strokeStyle = this.css('--line');
      ctx.fillStyle = this.css('--text-faint');
      ctx.font = '400 10px "JetBrains Mono", monospace';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      for (let i = 0; i <= 4; i++) {
        const v = (maxV / 4) * i;
        const y = sy(v);
        ctx.beginPath();
        ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + plotW, y);
        ctx.stroke();
        ctx.fillText(v.toFixed(0), pad.left - 6, y);
      }

      const groupW = plotW / groups.length;
      groups.forEach((g, gi) => {
        const barCount = g.bars.length;
        const barW = Math.min(46, (groupW * 0.62) / barCount);
        const groupCentre = pad.left + groupW * gi + groupW / 2;
        const startX = groupCentre - (barW * barCount) / 2;

        g.bars.forEach((b, bi) => {
          const x = startX + bi * barW;
          const y = sy(b.value);
          const barH = pad.top + plotH - y;
          ctx.fillStyle = this.css(b.colorVar);
          ctx.beginPath();
          // Rounded top corners only.
          const r = Math.min(4, barW / 3, barH);
          ctx.moveTo(x, pad.top + plotH);
          ctx.lineTo(x, y + r);
          ctx.quadraticCurveTo(x, y, x + r, y);
          ctx.lineTo(x + barW - r - 2, y);
          ctx.quadraticCurveTo(x + barW - 2, y, x + barW - 2, y + r);
          ctx.lineTo(x + barW - 2, pad.top + plotH);
          ctx.closePath();
          ctx.fill();

          // Value above the bar
          ctx.fillStyle = this.css('--text-muted');
          ctx.font = '600 10px "JetBrains Mono", monospace';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'bottom';
          ctx.fillText(b.value.toFixed(1), x + (barW - 2) / 2, y - 3);
        });

        // Group label
        ctx.fillStyle = this.css('--text-muted');
        ctx.font = '500 11px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(g.label, groupCentre, pad.top + plotH + 10);
      });

      return true;
    };

    draw();
    this._registry.push(draw);
  },
};

/* Redraw on resize — charts are sized from their container, so a window resize
 * or an orientation change needs a repaint. Debounced to avoid thrashing. */
let _resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(_resizeTimer);
  _resizeTimer = setTimeout(() => Charts.redrawAll(), 150);
});

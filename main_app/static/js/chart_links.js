/*
 * Chart.js plugin: make bars and x-axis labels clickable.
 *
 * Enable per chart with options.plugins.labelLinks.href = (index, chart) => url | null.
 * Charts without that option are unaffected.
 */
(function () {
  if (!window.Chart) return;

  const LABEL_PADDING = 4;

  function labelIndexAt(chart, x, y) {
    const scale = chart.scales.x;
    if (!scale || y < chart.chartArea.bottom) return -1;

    const items = typeof scale.getLabelItems === 'function' ? scale.getLabelItems() : null;
    if (!items) {
      // Fallback: nearest tick by x position.
      const value = Math.round(scale.getValueForPixel(x));
      return value >= 0 && value < chart.data.labels.length ? value : -1;
    }

    const ctx = chart.ctx;
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      const opts = item.options || {};
      const [tx, ty] = opts.translation || [0, 0];
      const rotation = opts.rotation || 0;
      const lines = Array.isArray(item.label) ? item.label : [String(item.label)];

      ctx.save();
      ctx.font = item.font.string;
      const width = Math.max(...lines.map((line) => ctx.measureText(line).width));
      ctx.restore();
      const height = item.font.lineHeight * lines.length;

      // Move the pointer into the label's own (unrotated) coordinate space.
      const dx = x - tx;
      const dy = y - ty;
      const cos = Math.cos(-rotation);
      const sin = Math.sin(-rotation);
      const lx = dx * cos - dy * sin;
      const ly = dx * sin + dy * cos - (item.textOffset || 0);

      let left = 0;
      if (opts.textAlign === 'right') left = -width;
      else if (opts.textAlign === 'center') left = -width / 2;
      const top = opts.textBaseline === 'middle' ? -height / 2 : 0;

      if (
        lx >= left - LABEL_PADDING && lx <= left + width + LABEL_PADDING &&
        ly >= top - LABEL_PADDING && ly <= top + height + LABEL_PADDING
      ) {
        return scale.ticks[i] ? scale.ticks[i].value : i;
      }
    }
    return -1;
  }

  function indexAt(chart, event) {
    const bars = chart.getElementsAtEventForMode(event, 'nearest', { intersect: true }, false);
    if (bars.length) return bars[0].index;
    return labelIndexAt(chart, event.x, event.y);
  }

  const plugin = {
    id: 'labelLinks',
    afterEvent(chart, args, options) {
      if (typeof options.href !== 'function') return;
      const event = args.event;
      if (event.type !== 'click' && event.type !== 'mousemove') return;

      const index = indexAt(chart, event);
      const href = index >= 0 ? options.href(index, chart) : null;
      chart.canvas.style.cursor = href ? 'pointer' : '';

      if (href && event.type === 'click') {
        const native = event.native;
        if (native && (native.metaKey || native.ctrlKey)) {
          window.open(href, '_blank', 'noopener');
        } else {
          window.location.href = href;
        }
      }
    },
  };

  window.Chart.register(plugin);

  window.ChartLinks = {
    searchUrl(query, params, base = '/search') {
      const search = new URLSearchParams({ q: query, match_type: '1' });
      Object.entries(params || {}).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') search.set(key, value);
      });
      return `${base}?${search.toString()}`;
    },
  };
})();

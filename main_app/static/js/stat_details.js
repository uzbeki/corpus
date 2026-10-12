/*
 * Clickable statistics cards.
 *
 * Cards are elements with data-stat-key inside a container. Details come from the
 * server (see main_app/stat_details.py) and are attached with:
 *
 *   StatDetails.bind(containerEl, detailsObject)
 *
 * bind() can be called again later (e.g. after an async fetch) to add more details.
 */
(function () {
  const stores = new WeakMap();
  let dialog;
  let pending = null; // card whose dialog is showing "Loading…"

  function safeHref(href) {
    return typeof href === 'string' && href.startsWith('/') && !href.startsWith('//') ? href : null;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function ensureDialog() {
    if (dialog) return dialog;
    dialog = el('dialog', 'stat-dialog');
    dialog.setAttribute('aria-labelledby', 'stat-dialog-title');
    dialog.addEventListener('click', (event) => {
      // Clicking the backdrop (outside the panel) closes the dialog.
      if (event.target === dialog) dialog.close();
    });
    document.body.appendChild(dialog);
    return dialog;
  }

  function renderSection(section) {
    const wrap = el('section', 'stat-dialog__section');
    wrap.appendChild(el('h3', 'stat-dialog__heading', section.heading));

    if (Array.isArray(section.rows)) {
      const list = el('ul', 'stat-dialog__rows');
      section.rows.forEach((row) => {
        const item = el('li', 'stat-dialog__row');
        const href = safeHref(row.href);
        const label = href ? el('a', 'stat-dialog__link', row.label) : el('span', '', row.label);
        if (href) label.href = href;
        item.appendChild(label);
        item.appendChild(el('span', 'stat-dialog__value', row.value));
        list.appendChild(item);
      });
      wrap.appendChild(list);
    }

    if (Array.isArray(section.chips)) {
      const chips = el('div', 'stat-dialog__chips');
      section.chips.forEach((chip) => {
        const href = safeHref(chip.href);
        const node = href ? el('a', 'stat-dialog__chip') : el('span', 'stat-dialog__chip');
        if (href) {
          node.href = href;
          node.title = `Search for "${chip.label}"`;
        }
        node.appendChild(el('span', '', chip.label));
        if (chip.value) node.appendChild(el('span', 'stat-dialog__chip-value', chip.value));
        chips.appendChild(node);
      });
      wrap.appendChild(chips);
    }
    return wrap;
  }

  function open(card, detail) {
    const dlg = ensureDialog();
    dlg.replaceChildren();

    const panel = el('div', 'stat-dialog__panel');
    const header = el('div', 'stat-dialog__header');
    const titleWrap = el('div');
    const label = card.querySelector('p');
    titleWrap.appendChild(el('p', 'stat-dialog__eyebrow', label ? label.textContent : ''));
    const title = el('h2', 'stat-dialog__title', detail ? detail.title : 'Details');
    title.id = 'stat-dialog-title';
    titleWrap.appendChild(title);
    header.appendChild(titleWrap);

    const close = el('button', 'stat-dialog__close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', 'Close');
    close.addEventListener('click', () => dlg.close());
    header.appendChild(close);
    panel.appendChild(header);

    const value = card.querySelector('h4');
    if (value) panel.appendChild(el('p', 'stat-dialog__value-big', value.textContent));

    pending = detail ? null : card;
    if (!detail) {
      panel.appendChild(el('p', 'stat-dialog__text', 'Loading details…'));
    } else {
      if (detail.description) panel.appendChild(el('p', 'stat-dialog__text', detail.description));
      if (detail.formula) panel.appendChild(el('p', 'stat-dialog__formula', detail.formula));
      (detail.sections || []).forEach((section) => panel.appendChild(renderSection(section)));
      if (detail.note) panel.appendChild(el('p', 'stat-dialog__note', detail.note));
    }

    dlg.appendChild(panel);
    if (!dlg.open) dlg.showModal();
    close.focus();
  }

  function bindCard(card, container) {
    if (card.dataset.statBound === '1') return;
    card.dataset.statBound = '1';
    card.classList.add('stat-card');
    card.setAttribute('role', 'button');
    card.setAttribute('tabindex', '0');
    card.setAttribute('aria-haspopup', 'dialog');
    card.title = 'Show details';
    card.appendChild(el('span', 'stat-card__hint', 'Details →'));

    const activate = () => open(card, (stores.get(container) || {})[card.dataset.statKey]);
    card.addEventListener('click', activate);
    card.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        activate();
      }
    });
  }

  function bind(container, details) {
    if (!container) return;
    const store = Object.assign(stores.get(container) || {}, details || {});
    stores.set(container, store);
    container.querySelectorAll('[data-stat-key]').forEach((card) => bindCard(card, container));

    // Refresh an open "Loading…" dialog once its details arrive.
    if (pending && dialog && dialog.open && container.contains(pending)) {
      const detail = store[pending.dataset.statKey];
      if (detail) open(pending, detail);
    }
  }

  window.StatDetails = { bind };
})();

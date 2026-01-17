/* Annotate gendered name markers in article content.

Markers:
- Male: [Mr. Smith]
- Female: ^^Olivera Anna^^

This walks text nodes and replaces markers with <span> tags.
*/

(function () {
  const MALE_RE = /\[([^\[\]]+?)\]/g;
  const FEMALE_RE = /\^\^([\s\S]+?)\^\^/g;
  const COMBINED_RE = /(\[([^\[\]]+?)\])|(\^\^([\s\S]+?)\^\^)/g;

  function shouldSkipNode(node) {
    if (!node || node.nodeType !== Node.TEXT_NODE) return true;
    const parent = node.parentElement;
    if (!parent) return true;
    const tag = parent.tagName;
    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'TEXTAREA') return true;
    if (parent.classList.contains('male-name') || parent.classList.contains('female-name')) return true;
    return false;
  }

  function annotateTextNode(textNode) {
    const text = textNode.nodeValue || '';
    COMBINED_RE.lastIndex = 0;

    let match;
    let lastIndex = 0;
    let changed = false;
    let maleCount = 0;
    let femaleCount = 0;

    const fragment = document.createDocumentFragment();

    while ((match = COMBINED_RE.exec(text)) !== null) {
      const full = match[0];
      const maleName = match[2];
      const femaleName = match[4];

      const start = match.index;
      const end = start + full.length;

      if (start > lastIndex) {
        fragment.appendChild(document.createTextNode(text.slice(lastIndex, start)));
      }

      if (typeof maleName === 'string') {
        const name = maleName.trim();
        if (name) {
          const span = document.createElement('span');
          span.className = 'male-name';
          span.textContent = name;
          fragment.appendChild(span);
          maleCount += 1;
        }
        changed = true;
      } else if (typeof femaleName === 'string') {
        const name = femaleName.trim();
        if (name) {
          const span = document.createElement('span');
          span.className = 'female-name';
          span.textContent = name;
          fragment.appendChild(span);
          femaleCount += 1;
        }
        changed = true;
      } else {
        fragment.appendChild(document.createTextNode(full));
      }

      lastIndex = end;
    }

    if (!changed) return { changed: false, maleCount: 0, femaleCount: 0 };

    if (lastIndex < text.length) {
      fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
    }

    textNode.parentNode.replaceChild(fragment, textNode);
    return { changed: true, maleCount, femaleCount };
  }

  function annotateGenderedNames(rootEl) {
    if (!rootEl) return { maleCount: 0, femaleCount: 0 };

    const walker = document.createTreeWalker(rootEl, NodeFilter.SHOW_TEXT);
    let node;
    let maleCount = 0;
    let femaleCount = 0;

    const textNodes = [];
    while ((node = walker.nextNode())) {
      if (!shouldSkipNode(node)) textNodes.push(node);
    }

    for (const textNode of textNodes) {
      const result = annotateTextNode(textNode);
      maleCount += result.maleCount;
      femaleCount += result.femaleCount;
    }

    return { maleCount, femaleCount };
  }

  function init() {
    const targets = document.querySelectorAll('[data-gender-annotations]');
    for (const el of targets) {
      const counts = annotateGenderedNames(el);
      const targetSelector = el.getAttribute('data-gender-count-target');
      if (targetSelector) {
        const output = document.querySelector(targetSelector);
        if (output) {
            output.textContent = `Male names: ${counts.maleCount} • Female names: ${counts.femaleCount}`;
        }
      }

      // Expose counts on element for other scripts
      el.dataset.maleNameCount = String(counts.maleCount);
      el.dataset.femaleNameCount = String(counts.femaleCount);
    }
  }

  // Expose a small API for other scripts/pages.
  window.GenderAnnotations = {
    annotateGenderedNames,
    MALE_RE,
    FEMALE_RE,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

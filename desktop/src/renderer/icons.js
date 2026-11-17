/**
 * FOXFall icon set — Lucide-derived SVG paths, consistent 24px grid,
 * stroke-based, currentColor. No external dependency.
 */
'use strict';

const ICONS = {
  dashboard: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  download: '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>',
  queue: '<rect x="3" y="4" width="18" height="4" rx="1.5"/><rect x="3" y="10" width="18" height="4" rx="1.5"/><path d="M3 16h18"/><circle cx="19" cy="19" r="2"/>',
  library: '<path d="M4 4h5v16H4z"/><path d="M9 4h5v16H9z"/><path d="m14 5 4 14"/><path d="M19 4h1v16h-1"/>',
  tools: '<path d="M14.7 6.3a4.5 4.5 0 0 0-6.03 5.9L3 17.8V21h3.2l5.6-5.67a4.5 4.5 0 0 0 5.9-6.03L14.7 12l-1.5-1.5z"/><circle cx="17" cy="7" r="1.2"/>',
  history: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 3"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2v2.5M12 19.5V22M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M2 12h2.5M19.5 12H22M4.6 19.4l1.8-1.8M17.6 6.4l1.8-1.8"/>',
  about: '<circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v4h1"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  bell: '<path d="M6 8a6 6 0 1 1 12 0c0 7 2 8 2 8H4s2-1 2-8"/><path d="M10.3 21a2 2 0 0 0 3.4 0"/>',
  play: '<path d="m7 4 13 8-13 8z"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  open: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4L21 8"/><path d="M21 3v5h-5"/>',
  clipboard: '<rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4a3 3 0 0 1 6 0"/>',
  film: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h18M3 16h18"/>',
  music: '<circle cx="6" cy="18" r="2.5"/><circle cx="17" cy="16" r="2.5"/><path d="M8.5 18V6l11-2v10"/>',
  check: '<path d="m5 12 5 5L20 7"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
  alert: '<path d="M12 3 2 20h20z"/><path d="M12 9v5M12 17h.01"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  analyze: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/><path d="M11 8v3l2 2"/>',
  thumb: '<rect x="3" y="5" width="14" height="14" rx="2"/><path d="M17 9h4v10a2 2 0 0 1-2 2h-2z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  trash: '<path d="M4 7h16"/><path d="M10 11v6M14 11v6"/><path d="M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/>',
  shield: '<path d="M12 3 5 6v6c0 4.4 3 8.4 7 9.6 4-1.2 7-5.2 7-9.6V6z"/>',
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
};

/** Render an icon as an inline SVG string. */
function icon(name, size = 18) {
  const body = ICONS[name] || ICONS.about;
  return `<svg class="ic" width="${size}" height="${size}" viewBox="0 0 24 24" ` +
    `fill="none" stroke="currentColor" stroke-width="1.8" ` +
    `stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}

/** Replace all <i data-icon="name"> placeholders in the document. */
function hydrateIcons(root = document) {
  root.querySelectorAll('i[data-icon]').forEach((el) => {
    el.outerHTML = icon(el.dataset.icon, el.dataset.size || 18);
  });
}
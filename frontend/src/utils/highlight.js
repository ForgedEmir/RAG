export function normalize(str) {
  return str.replace(/\s+/g, ' ').trim();
}

/**
 * Find passage in content using whitespace-normalized matching.
 * Returns { before, match, after } mapped back to original string positions, or null.
 */
export function findPassage(content, passage) {
  if (!passage || !content) return null;

  const normContent = normalize(content);
  const normPassage = normalize(passage);
  const idx = normContent.indexOf(normPassage);
  if (idx === -1) return null;

  // Build origPositions[i] = index in `content` corresponding to normContent[i]
  const origPositions = [];
  let ni = 0, prevWasSpace = false;
  for (let oi = 0; oi < content.length; oi++) {
    if (/\s/.test(content[oi])) {
      if (!prevWasSpace && ni > 0) { origPositions[ni] = oi; ni++; }
      prevWasSpace = true;
    } else {
      origPositions[ni] = oi; ni++;
      prevWasSpace = false;
    }
  }

  const startOrig = origPositions[idx] ?? 0;
  const endOrig = origPositions[idx + normPassage.length] ?? content.length;

  return {
    before: content.slice(0, startOrig),
    match:  content.slice(startOrig, endOrig),
    after:  content.slice(endOrig),
  };
}

/**
 * Walk all text nodes inside a DOM element, find the passage via normalized
 * matching, and wrap each matching segment in its own <mark data-passage>.
 * Handles passages that span multiple block elements (p, li, h1…) by creating
 * one <mark> per text node instead of one cross-element surroundContents call.
 * Returns the first <mark> element or null if no match found.
 */
export function injectPassageMark(container, passage) {
  if (!container || !passage) return null;

  container.querySelectorAll('mark[data-passage]').forEach(m => m.replaceWith(...m.childNodes));

  const normPassage = normalize(passage);
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  let node;
  while ((node = walker.nextNode())) textNodes.push(node);
  if (!textNodes.length) return null;

  const normTexts = textNodes.map(n => normalize(n.textContent));
  const fullNorm  = normTexts.join(' ');
  const matchStart = fullNorm.indexOf(normPassage);
  if (matchStart === -1) return null;
  const matchEnd = matchStart + normPassage.length;

  // Compute the start position of each node in the joined string.
  // normTexts.join(' ') puts one space between every node (including empty ones).
  const nodeStarts = [];
  let pos = 0;
  for (let i = 0; i < normTexts.length; i++) {
    nodeStarts.push(pos);
    pos += normTexts[i].length + 1;
  }

  const MARK_STYLE = 'background:rgba(250,204,21,0.45);border-radius:3px;padding:1px 0;color:inherit';
  let firstMark = null;

  for (let i = 0; i < textNodes.length; i++) {
    const ns = nodeStarts[i];
    const ne = ns + normTexts[i].length;
    if (ne <= matchStart || ns >= matchEnd || normTexts[i].length === 0) continue;

    // Overlap in normalized space, relative to this node's start
    const overlapNormStart = Math.max(matchStart, ns) - ns;
    const overlapNormEnd   = Math.min(matchEnd,   ne) - ns;

    // Map back to original-text offsets (approximate; fine for clean text)
    const origLen   = textNodes[i].textContent.length;
    const wrapStart = Math.min(overlapNormStart, origLen);
    const wrapEnd   = Math.min(overlapNormEnd,   origLen);
    if (wrapStart >= wrapEnd) continue;

    try {
      const range = document.createRange();
      range.setStart(textNodes[i], wrapStart);
      range.setEnd(textNodes[i], wrapEnd);
      const mark = document.createElement('mark');
      mark.setAttribute('data-passage', '1');
      mark.style.cssText = MARK_STYLE;
      range.surroundContents(mark);
      if (!firstMark) firstMark = mark;
    } catch (_) {}
  }

  return firstMark;
}

/**
 * Highlight passage text inside a PDF text layer (pdfjs spans).
 *
 * WHY: pdfjs renders each word/glyph in its own <span> so surroundContents()
 * fails across span boundaries. Instead we colour individual spans whose text
 * appears inside the passage, then scroll to the first one.
 *
 * Returns the first highlighted span, or null if nothing matched.
 */
export function highlightPdfLayer(container, passage) {
  if (!container || !passage) return null;

  // Clear previous highlights
  container.querySelectorAll('span[data-pdf-hl]').forEach(s => {
    s.style.background = '';
    s.style.borderRadius = '';
    s.removeAttribute('data-pdf-hl');
  });

  const normPassage = normalize(passage).toLowerCase();
  if (!normPassage) return null;

  // Only select leaf spans (no child spans) to avoid duplicated text from
  // nested span structures used by docx-preview for bold/italic formatting.
  const spans = Array.from(container.querySelectorAll('span')).filter(s => !s.querySelector('span'));
  const texts = spans.map(s => normalize(s.textContent).toLowerCase());
  const full  = texts.join(' ');

  const matchStart = full.indexOf(normPassage);
  if (matchStart === -1) return null;
  const matchEnd = matchStart + normPassage.length;

  // Map each span to its [start, end) range in the concatenated string
  let pos = 0;
  let firstMark = null;
  for (let i = 0; i < spans.length; i++) {
    const len = texts[i].length;
    const spanStart = pos;
    const spanEnd   = pos + len;
    // +1 for the space separator between spans
    pos += len + 1;

    // Span overlaps the match range
    if (spanEnd > matchStart && spanStart < matchEnd && len > 0) {
      spans[i].style.background   = 'rgba(250,204,21,0.55)';
      spans[i].style.borderRadius = '2px';
      spans[i].setAttribute('data-pdf-hl', '1');
      if (!firstMark) firstMark = spans[i];
    }
  }

  return firstMark;
}

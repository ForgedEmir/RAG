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
 * matching, and wrap the match in a <mark data-passage> element.
 * Returns the <mark> element or null if no match found.
 */
export function injectPassageMark(container, passage) {
  if (!container || !passage) return null;

  // Remove previous highlights
  container.querySelectorAll('mark[data-passage]').forEach(m => m.replaceWith(...m.childNodes));

  const normPassage = normalize(passage);
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  let node;
  while ((node = walker.nextNode())) textNodes.push(node);
  if (!textNodes.length) return null;

  // Build per-node info in normalized space
  const nodeInfo = [];
  let npos = 0;
  for (const tn of textNodes) {
    const normText = normalize(tn.textContent);
    const start = npos;
    if (normText.length > 0) {
      npos += normText.length;
      if (nodeInfo.length > 0) npos++; // space separator between nodes
    }
    nodeInfo.push({ node: tn, normStart: start, normLen: normText.length });
  }

  const fullNorm = textNodes.map(n => normalize(n.textContent)).join(' ');
  const matchStart = fullNorm.indexOf(normPassage);
  if (matchStart === -1) return null;
  const matchEnd = matchStart + normPassage.length;

  // Find start and end nodes
  let startNode = null, startOffset = 0, endNode = null, endOffset = 0;
  for (const info of nodeInfo) {
    const ns = info.normStart;
    const ne = ns + info.normLen;
    if (startNode === null && matchStart >= ns && matchStart <= ne) {
      startNode = info.node;
      startOffset = Math.min(matchStart - ns, info.node.textContent.length);
    }
    if (endNode === null && matchEnd >= ns && matchEnd <= ne) {
      endNode = info.node;
      endOffset = Math.min(matchEnd - ns, info.node.textContent.length);
    }
  }

  if (!startNode || !endNode) return null;

  try {
    const range = document.createRange();
    range.setStart(startNode, startOffset);
    range.setEnd(endNode, endOffset);
    const mark = document.createElement('mark');
    mark.setAttribute('data-passage', '1');
    mark.style.cssText = 'background:rgba(250,204,21,0.45);border-radius:3px;padding:1px 0;color:inherit';
    range.surroundContents(mark);
    return mark;
  } catch (_) {
    return null;
  }
}

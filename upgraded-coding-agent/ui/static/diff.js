/**
 * Diff Parser and Line-by-Line Formatter for Upgraded Coding Agent.
 */

function renderUnifiedDiff(diffText) {
  if (!diffText || !diffText.trim()) {
    return '<div class="text-slate-500 italic p-4 text-center">No diff available. Code unchanged or not yet generated.</div>';
  }

  const lines = diffText.split('\n');
  let html = '<div class="diff-container space-y-0.5">';
  let lineOld = 0;
  let lineNew = 0;

  let additions = 0;
  let deletions = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Chunk header @@ -1,4 +1,5 @@
    if (line.startsWith('@@')) {
      const match = line.match(/@@\s+-(\d+),?\d*\s+\+(\d+),?\d*\s+@@/);
      if (match) {
        lineOld = parseInt(match[1], 10) - 1;
        lineNew = parseInt(match[2], 10) - 1;
      }
      html += `<div class="diff-line diff-header"><span class="diff-line-number">...</span><span class="diff-line-content">${escapeHtml(line)}</span></div>`;
      continue;
    }

    if (line.startsWith('---') || line.startsWith('+++')) {
      html += `<div class="diff-line diff-header"><span class="diff-line-number"></span><span class="diff-line-content font-bold">${escapeHtml(line)}</span></div>`;
      continue;
    }

    if (line.startsWith('+')) {
      lineNew++;
      additions++;
      html += `
        <div class="diff-line diff-add">
          <span class="diff-line-number">+${lineNew}</span>
          <span class="diff-line-content">${escapeHtml(line)}</span>
        </div>`;
    } else if (line.startsWith('-')) {
      lineOld++;
      deletions++;
      html += `
        <div class="diff-line diff-delete">
          <span class="diff-line-number">-${lineOld}</span>
          <span class="diff-line-content">${escapeHtml(line)}</span>
        </div>`;
    } else {
      lineOld++;
      lineNew++;
      html += `
        <div class="diff-line diff-context">
          <span class="diff-line-number">${lineNew}</span>
          <span class="diff-line-content">${escapeHtml(line)}</span>
        </div>`;
    }
  }

  html += '</div>';

  // Update diff additions/deletions stats in UI
  const statsElem = document.getElementById('diff-stats');
  if (statsElem) {
    statsElem.innerHTML = `
      <span class="text-emerald-400 font-semibold">+${additions} additions</span>
      <span class="text-rose-400 font-semibold">-${deletions} deletions</span>
    `;
  }

  return html;
}

function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}

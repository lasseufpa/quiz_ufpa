import katex from 'katex';

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderMath(expression, displayMode) {
  try {
    return katex.renderToString(expression, {
      displayMode,
      throwOnError: false,
      output: 'html'
    });
  } catch {
    return escapeHtml(displayMode ? `$$${expression}$$` : `$${expression}$`);
  }
}

export function renderLatexToHtml(value) {
  const text = String(value ?? '');
  if (!text) {
    return '';
  }

  const parts = [];
  const pattern = /\$\$([\s\S]+?)\$\$|(?<!\\)\$([^$\n]+?)\$/g;
  let lastIndex = 0;
  let match;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(escapeHtml(text.slice(lastIndex, match.index)));
    }

    if (match[1] !== undefined) {
      parts.push(renderMath(match[1].trim(), true));
    } else if (match[2] !== undefined) {
      parts.push(renderMath(match[2].trim(), false));
    }

    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(escapeHtml(text.slice(lastIndex)));
  }

  return parts.join('');
}
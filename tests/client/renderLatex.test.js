import { renderLatexToHtml } from '@/lib/renderLatex';

describe('renderLatexToHtml', () => {
  it('returns empty string for empty input', () => {
    expect(renderLatexToHtml('')).toBe('');
  });

  it('escapes HTML outside math', () => {
    const html = renderLatexToHtml('2 < 3');
    expect(html).toContain('2 &lt; 3');
  });

  it('renders inline math', () => {
    const html = renderLatexToHtml('Area $a^2$');
    expect(html).toContain('katex');
  });

  it('renders block math', () => {
    const html = renderLatexToHtml('$$x^2 + y^2$$');
    expect(html).toContain('katex');
  });
});

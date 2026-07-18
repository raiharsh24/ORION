import React from 'react';

interface Props {
  content: string;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderInline(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-zinc-100 font-semibold">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em class="text-zinc-300 italic">$1</em>')
    .replace(/`(.+?)`/g, '<code class="bg-zinc-900 text-cyan-glow/90 px-1.5 py-0.5 rounded text-[11px] font-mono">$1</code>')
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" class="text-cyan-glow underline hover:opacity-80" target="_blank" rel="noopener">$1</a>');
}

export const MarkdownRenderer: React.FC<Props> = ({ content }) => {
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let inCodeBlock = false;
  let codeLang = '';
  let codeLines: string[] = [];
  let codeIndex = 0;

  const flushCode = () => {
    if (codeLines.length === 0) return;
    elements.push(
      <div key={`cb-${codeIndex++}`} className="my-3 rounded-xl overflow-hidden border border-matte-border bg-zinc-950/80">
        {codeLang && (
          <div className="px-4 py-1.5 text-[10px] font-mono text-zinc-500 uppercase tracking-wider border-b border-matte-border bg-black/40">
            {codeLang}
          </div>
        )}
        <pre className="p-4 overflow-x-auto text-xs leading-relaxed font-mono text-zinc-300">
          <code>{codeLines.map((l) => escapeHtml(l)).join('\n')}</code>
        </pre>
      </div>
    );
    codeLines = [];
    codeLang = '';
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith('```')) {
      if (inCodeBlock) {
        flushCode();
        inCodeBlock = false;
      } else {
        flushCode();
        inCodeBlock = true;
        codeLang = line.slice(3).trim();
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    const trimmed = line.trim();

    if (!trimmed) {
      elements.push(<div key={`gap-${i}`} className="h-2" />);
      continue;
    }

    if (trimmed.startsWith('### ')) {
      elements.push(
        <h3 key={`h3-${i}`} className="text-sm font-bold text-zinc-100 mt-4 mb-2">
          {renderInline(escapeHtml(trimmed.slice(4)))}
        </h3>
      );
      continue;
    }

    if (trimmed.startsWith('## ')) {
      elements.push(
        <h2 key={`h2-${i}`} className="text-base font-bold text-zinc-100 mt-5 mb-2">
          {renderInline(escapeHtml(trimmed.slice(3)))}
        </h2>
      );
      continue;
    }

    if (trimmed.startsWith('# ')) {
      elements.push(
        <h1 key={`h1-${i}`} className="text-lg font-bold text-zinc-100 mt-5 mb-3">
          {renderInline(escapeHtml(trimmed.slice(2)))}
        </h1>
      );
      continue;
    }

    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      elements.push(
        <div key={`li-${i}`} className="flex gap-2 text-xs text-zinc-300 ml-2 mb-1 leading-relaxed">
          <span className="text-cyan-glow/60 mt-0.5 shrink-0">&bull;</span>
          <span dangerouslySetInnerHTML={{ __html: renderInline(escapeHtml(trimmed.slice(2))) }} />
        </div>
      );
      continue;
    }

    if (/^\d+\.\s/.test(trimmed)) {
      const content_ = trimmed.replace(/^\d+\.\s/, '');
      elements.push(
        <div key={`ol-${i}`} className="flex gap-2 text-xs text-zinc-300 ml-2 mb-1 leading-relaxed">
          <span className="text-cyan-glow/60 shrink-0 font-mono">{trimmed.match(/^\d+/)?.[0]}.</span>
          <span dangerouslySetInnerHTML={{ __html: renderInline(escapeHtml(content_)) }} />
        </div>
      );
      continue;
    }

    if (trimmed.startsWith('> ')) {
      elements.push(
        <blockquote key={`bq-${i}`} className="border-l-2 border-cyan-border/40 pl-3 my-2 text-xs text-zinc-400 italic">
          <span dangerouslySetInnerHTML={{ __html: renderInline(escapeHtml(trimmed.slice(2))) }} />
        </blockquote>
      );
      continue;
    }

    elements.push(
      <p key={`p-${i}`} className="text-xs text-zinc-300 leading-relaxed mb-1.5">
        <span dangerouslySetInnerHTML={{ __html: renderInline(escapeHtml(trimmed)) }} />
      </p>
    );
  }

  if (inCodeBlock) flushCode();

  return <div className="space-y-0.5">{elements}</div>;
};

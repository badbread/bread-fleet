// Monospace SQL display with basic keyword highlighting.
// SELECT, FROM, WHERE, AND, OR, NOT, EXISTS, LIKE, JOIN in blue.

interface Props {
  sql: string;
}

const KEYWORDS = /\b(SELECT|FROM|WHERE|AND|OR|NOT|EXISTS|LIKE|JOIN|AS|IN|CAST|INTEGER|LIMIT)\b/gi;

function highlight(sql: string): (string | JSX.Element)[] {
  const parts: (string | JSX.Element)[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  const re = new RegExp(KEYWORDS.source, "gi");
  while ((match = re.exec(sql)) !== null) {
    if (match.index > lastIndex) {
      parts.push(sql.slice(lastIndex, match.index));
    }
    parts.push(
      <span key={match.index} className="text-accent font-semibold">
        {match[0]}
      </span>,
    );
    lastIndex = re.lastIndex;
  }
  if (lastIndex < sql.length) {
    parts.push(sql.slice(lastIndex));
  }
  return parts;
}

export default function SqlPreview({ sql }: Props) {
  return (
    <pre className="bg-[#1F1E1B] border border-[#3A3936] rounded-md px-4 py-3 text-[12px] leading-relaxed font-mono text-[#E9E9E7] overflow-x-auto whitespace-pre-wrap">
      {highlight(sql)}
    </pre>
  );
}

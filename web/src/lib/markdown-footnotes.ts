export interface MarkdownFootnote {
  num: number;
  url: string;
  label: string;
}

export function parseFootnotes(raw: string): {
  body: string;
  footnotes: MarkdownFootnote[];
} {
  const refRegex = /\[(\d+)\]\((https?:\/\/[^\s)]+)(?:\s+"[^"]*")?\)/g;
  const footnotes: MarkdownFootnote[] = [];

  for (const match of raw.matchAll(refRegex)) {
    const num = Number.parseInt(match[1], 10);
    const url = match[2];
    footnotes.push({
      num,
      url,
      label: url.length > 50 ? `${url.slice(0, 47)}...` : url,
    });
  }

  return { body: raw, footnotes };
}

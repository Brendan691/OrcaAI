"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatSource } from "@/lib/api";
import { parseFootnotes } from "@/lib/markdown-footnotes";

type Components = Record<string, React.ComponentType<any>>;

export function Markdown({
  content,
  citations = [],
}: {
  content: string;
  citations?: ChatSource[];
}) {
  const { body, footnotes } = parseFootnotes(content);

  const components: Components = {
    a: ({ href, children, ...props }: any) => {
      const citation = citations.find((item) => item.id === href);
      if (citation) {
        return (
          <sup>
            <button
              type="button"
              title={`查看来源 ${citation.index}: ${citation.title}`}
              aria-label={`查看来源 ${citation.index}: ${citation.title}`}
              className="font-semibold text-primary hover:underline"
              onClick={() => {
                document
                  .getElementById(`citation-${citation.id}`)
                  ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
              }}
            >
              [{citation.index}]
            </button>
          </sup>
        );
      }
      const label = String(children);
      if (/^\d+$/.test(label) && href?.startsWith("http")) {
        return (
          <sup>
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-primary hover:underline"
              title={`打开来源 ${label}`}
            >
              [{label}]
            </a>
          </sup>
        );
      }
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary underline underline-offset-2 hover:opacity-80"
          {...props}
        >
          {children}
        </a>
      );
    },
    table: ({ children }: any) => (
      <div className="my-3 overflow-x-auto rounded-lg border">
        <table className="min-w-full text-sm">{children}</table>
      </div>
    ),
    thead: ({ children }: any) => (
      <thead className="bg-muted">{children}</thead>
    ),
    th: ({ children }: any) => (
      <th className="whitespace-nowrap border-r px-3 py-2 text-left text-xs font-semibold last:border-r-0">
        {children}
      </th>
    ),
    td: ({ children }: any) => (
      <td className="border-r border-t px-3 py-2 text-xs last:border-r-0">
        {children}
      </td>
    ),
    h1: ({ children }: any) => (
      <h1 className="mb-2 mt-4 text-xl font-bold">{children}</h1>
    ),
    h2: ({ children }: any) => (
      <h2 className="mb-2 mt-3 text-lg font-semibold">{children}</h2>
    ),
    h3: ({ children }: any) => (
      <h3 className="mb-1 mt-3 text-base font-semibold">{children}</h3>
    ),
    p: ({ children }: any) => (
      <p className="mb-2 leading-relaxed">{children}</p>
    ),
    ul: ({ children }: any) => (
      <ul className="mb-2 ml-5 list-disc">{children}</ul>
    ),
    ol: ({ children }: any) => (
      <ol className="mb-2 ml-5 list-decimal">{children}</ol>
    ),
    li: ({ children }: any) => (
      <li className="mb-1">{children}</li>
    ),
    strong: ({ children }: any) => (
      <strong className="font-semibold">{children}</strong>
    ),
    blockquote: ({ children }: any) => (
      <blockquote className="my-2 border-l-4 border-primary/30 pl-3 italic text-muted-foreground">
        {children}
      </blockquote>
    ),
    hr: () => <hr className="my-4" />,
  };

  return (
    <div className="text-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {body}
      </ReactMarkdown>
      {footnotes.length > 0 && (
        <div className="mt-4 border-t pt-3 text-xs text-muted-foreground">
          <div className="mb-2 font-semibold text-foreground">参考来源</div>
          <div className="space-y-1">
            {[...new Map(footnotes.map((fn) => [fn.url, fn])).values()]
              .sort((a, b) => a.num - b.num)
              .map((fn) => (
                <div key={fn.url} className="flex items-baseline gap-1">
                  <sup className="shrink-0 font-bold text-primary">[{fn.num}]</sup>
                  <a
                    href={fn.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="truncate text-primary underline underline-offset-2 hover:opacity-80"
                  >
                    {fn.label}
                  </a>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

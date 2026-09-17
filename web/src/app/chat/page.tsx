"use client";

import { useState, useRef, useEffect } from "react";
import {
  Send,
  Loader2,
  Bot,
  User,
  Globe,
  ExternalLink,
  FileText,
  CircleAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { api, API_BASE, ChatSource } from "@/lib/api";
import { Markdown } from "@/components/markdown";

interface Msg {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  confidence?: number;
  searchStatus?: "disabled" | "ok" | "degraded" | "failed";
  searchMessage?: string;
}

function sourceHref(source: ChatSource): string | undefined {
  if (!source.url) return undefined;
  if (source.url.startsWith("http://") || source.url.startsWith("https://")) {
    return source.url;
  }
  return `${API_BASE}${source.url.startsWith("/") ? "" : "/"}${source.url}`;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [searchInternet, setSearchInternet] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async () => {
    const msg = input.trim();
    if (!msg || loading) return;
    setMessages((m) => [...m, { role: "user", content: msg }]);
    setInput("");
    setLoading(true);
    try {
      const res = await api.chat(msg, searchInternet);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: res.answer,
          sources: res.sources,
          confidence: res.confidence,
          searchStatus: res.search_status,
          searchMessage: res.search_message,
        },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "请求失败,请检查后端服务是否运行。" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-[calc(100dvh-8.5rem)] min-h-[28rem] flex-col md:h-[calc(100vh-4rem)]">
      <div className="mb-4">
        <h1 className="text-2xl font-semibold">知识问答</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          基于你收藏的内容回答,有出处、不编造(RAG)
        </p>
      </div>

      {/* 消息区 */}
      <div className="flex-1 space-y-4 overflow-y-auto pr-2">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-center text-sm text-muted-foreground">
            <div>
              <Bot className="mx-auto mb-3 h-10 w-10 opacity-40" />
              向知识库提问,例如「最近集装箱运价趋势如何」
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}
          >
            <div
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                m.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted"
              }`}
            >
              {m.role === "user" ? (
                <User className="h-4 w-4" />
              ) : (
                <Bot className="h-4 w-4" />
              )}
            </div>
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                m.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted"
              }`}
            >
              {m.role === "assistant" ? (
                <Markdown content={m.content} citations={m.sources} />
              ) : (
                <div className="whitespace-pre-wrap text-sm">{m.content}</div>
              )}
              {m.sources && m.sources.length > 0 && (
                <div className="mt-3 border-t border-border/60 pt-2.5 text-xs">
                  <div className="mb-1.5 font-medium">参考来源</div>
                  <div className="divide-y divide-border/50">
                    {m.sources.map((source) => {
                      const href = sourceHref(source);
                      const content = (
                        <>
                          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center font-semibold text-primary">
                            {source.index}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="flex items-center gap-1 font-medium text-foreground">
                              {source.source_type === "web" ? (
                                <Globe className="h-3.5 w-3.5 shrink-0" />
                              ) : (
                                <FileText className="h-3.5 w-3.5 shrink-0" />
                              )}
                              <span className="truncate">{source.title}</span>
                            </span>
                            <span className="mt-0.5 block line-clamp-2 text-muted-foreground">
                              {source.snippet}
                            </span>
                            <span className="mt-0.5 block text-muted-foreground">
                              {source.locator_label || source.provider || "知识库切片"}
                              {source.score != null &&
                                ` · 相关度 ${Math.round(source.score * 100)}%`}
                            </span>
                          </span>
                          {href && <ExternalLink className="mt-1 h-3.5 w-3.5 shrink-0" />}
                        </>
                      );
                      return href ? (
                        <a
                          id={`citation-${source.id}`}
                          key={source.id}
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex gap-2 py-2 hover:text-primary"
                        >
                          {content}
                        </a>
                      ) : (
                        <div
                          id={`citation-${source.id}`}
                          key={source.id}
                          className="flex gap-2 py-2"
                        >
                          {content}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              {m.searchStatus === "degraded" && (
                <div className="mt-2 flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
                  <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>{m.searchMessage || "托管搜索不可用，已使用降级搜索。"}</span>
                </div>
              )}
              {m.searchStatus === "failed" && (
                <div className="mt-2 flex items-start gap-1.5 text-xs text-destructive">
                  <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>{m.searchMessage || "联网搜索失败。"}</span>
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted">
              <Bot className="h-4 w-4" />
            </div>
            <div className="flex items-center rounded-2xl bg-muted px-4 py-2.5 text-sm text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 小鲸正在思考…
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* 输入区 */}
      <div className="mt-4 space-y-3 border-t pt-4">
        <div className="flex items-center gap-2">
          <Switch
            id="search-internet"
            checked={searchInternet}
            onCheckedChange={setSearchInternet}
          />
          <Label htmlFor="search-internet" className="flex items-center gap-1.5 text-sm cursor-pointer">
            <Globe className="h-4 w-4" />
            联网搜索(知识库不足时补充互联网内容)
          </Label>
        </div>
        <div className="flex gap-2">
          <Input
            placeholder="向知识库提问…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            disabled={loading}
          />
          <Button onClick={send} disabled={loading || !input.trim()}>
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

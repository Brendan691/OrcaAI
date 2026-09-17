"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Search, Loader2, ExternalLink } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TagList } from "@/components/tag-list";
import { api, SearchHit } from "@/lib/api";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const doSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const res = await api.search(query.trim(), 10);
      setHits(res.results);
    } catch {
      toast.error("搜索失败,请检查后端");
      setHits([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">知识搜索</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          混合检索:向量语义 + 关键词 + 时间 + 标签四维加权
        </p>
      </div>

      <div className="flex gap-2">
        <Input
          placeholder="例如:集装箱运价走势、港口拥堵…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && doSearch()}
        />
        <Button onClick={doSearch} disabled={loading || !query.trim()}>
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
          搜索
        </Button>
      </div>

      {searched && !loading && hits.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            未找到相关内容,换个关键词试试。
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {hits.map((hit, i) => (
          <Card key={`${hit.doc_id}-${i}`}>
            <CardContent className="py-4">
              <div className="flex items-start justify-between gap-3">
                <div className="font-medium">
                  {i + 1}. {hit.title}
                </div>
                {hit.url && (
                  <a
                    href={hit.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 text-primary hover:underline"
                  >
                    <ExternalLink className="h-4 w-4" />
                  </a>
                )}
              </div>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {hit.content}
              </p>
              <div className="mt-3">
                <TagList tags={hit.tags} max={6} />
              </div>
              {/* 四维得分 */}
              <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground/80">
                <span className="font-medium text-foreground">
                  综合 {hit.score.toFixed(3)}
                </span>
                <span>向量 {hit.vector_score.toFixed(2)}</span>
                <span>关键词 {hit.keyword_score.toFixed(2)}</span>
                <span>时间 {hit.time_score.toFixed(2)}</span>
                <span>标签 {hit.tag_score.toFixed(2)}</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

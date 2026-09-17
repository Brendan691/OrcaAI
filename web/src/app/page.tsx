"use client";

import { useEffect, useState } from "react";
import { FileText, Layers, Tag, Boxes } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TagList } from "@/components/tag-list";
import { api, DocItem, formatTime, sourceLabel } from "@/lib/api";

export default function OverviewPage() {
  const [loading, setLoading] = useState(true);
  const [chunkCount, setChunkCount] = useState(0);
  const [docs, setDocs] = useState<DocItem[]>([]);
  const [tagTotal, setTagTotal] = useState(0);
  const [dimCount, setDimCount] = useState(0);

  useEffect(() => {
    (async () => {
      try {
        const [status, docList, tags] = await Promise.all([
          api.status(),
          api.listDocuments(),
          api.tags(),
        ]);
        setChunkCount(status.document_count);
        setDocs(docList.documents);
        const dims = Object.values(tags.dimensions);
        setDimCount(dims.length);
        setTagTotal(dims.reduce((s, d) => s + d.values.length, 0));
      } catch {
        // 后端未连接时保持零值
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const stats = [
    { label: "收藏文档", value: docs.length, icon: FileText },
    { label: "文档切片", value: chunkCount, icon: Layers },
    { label: "标签维度", value: dimCount, icon: Boxes },
    { label: "标签总数", value: tagTotal, icon: Tag },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">系统概览</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          快速了解知识库的整体状况
        </p>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map(({ label, value, icon: Icon }) => (
          <Card key={label}>
            <CardContent className="flex items-center gap-4 py-5">
              <div className="rounded-lg bg-primary/10 p-2.5 text-primary">
                <Icon className="h-5 w-5" />
              </div>
              <div>
                <div className="text-2xl font-semibold tabular-nums">
                  {loading ? <Skeleton className="h-7 w-10" /> : value}
                </div>
                <div className="text-xs text-muted-foreground">{label}</div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* 最近文档 */}
      <div>
        <h2 className="mb-3 text-lg font-medium">最近收藏</h2>
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        ) : docs.length === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              还没有收藏任何文档。用 Chrome 插件一键收藏,或在「文档管理」手动添加。
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {docs.slice(0, 5).map((doc) => (
              <Card key={doc.doc_id}>
                <CardContent className="py-4">
                  <div className="font-medium">{doc.title}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    🕐 {formatTime(doc.created_at)} · 🔗 {sourceLabel(doc)}
                  </div>
                  <div className="mt-2.5">
                    <TagList tags={doc.tags} max={8} />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

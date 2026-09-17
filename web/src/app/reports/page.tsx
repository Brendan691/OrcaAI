"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { FileText, Loader2, Globe } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import { Markdown } from "@/components/markdown";

export default function ReportsPage() {
  const [types, setTypes] = useState<{ id: string; name: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState<string | null>(null);
  const [searchInternet, setSearchInternet] = useState(false);
  const [reports, setReports] = useState<
    { type: string; title: string; content: string; time: string }[]
  >([]);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.reportTypes();
        setTypes(res.types);
      } catch {
        toast.error("无法加载报告类型");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const generate = async (typeId: string) => {
    setGenerating(typeId);
    try {
      const res = await api.generateReport(typeId, searchInternet);
      if (res.success) {
        toast.success("报告已生成");
        setReports((prev) => [
          { type: typeId, title: res.title, content: res.content, time: res.generated_at },
          ...prev,
        ]);
      } else {
        toast.error("生成失败");
      }
    } catch {
      toast.error("生成失败,请检查后端");
    } finally {
      setGenerating(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">AI 报告生成</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          基于知识库内容,自动生成航运周报、风险预警等报告
        </p>
      </div>

      {/* 联网搜索开关 */}
      <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-4 py-3">
        <Switch
          id="report-internet"
          checked={searchInternet}
          onCheckedChange={setSearchInternet}
        />
        <Label htmlFor="report-internet" className="cursor-pointer text-sm">
          <span className="inline-flex items-center gap-1">
            <Globe className="h-4 w-4" />
            联网搜索
          </span>
          <span className="ml-2 text-xs text-muted-foreground">
            知识库素材不足时自动搜索互联网补充(不存入知识库)
          </span>
        </Label>
      </div>

      {/* 报告类型 */}
      <div>
        <h2 className="mb-3 text-sm font-medium">选择报告类型</h2>
        {loading ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {types.map((t) => (
              <Card key={t.id}>
                <CardContent className="py-4">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <FileText className="h-4 w-4 text-primary" />
                    {t.name}
                  </div>
                  <Button
                    size="sm"
                    className="mt-3 w-full"
                    onClick={() => generate(t.id)}
                    disabled={generating === t.id}
                  >
                    {generating === t.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      "生成"
                    )}
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* 生成历史 */}
      {reports.length > 0 && (
        <div>
          <h2 className="mb-3 text-sm font-medium">生成历史</h2>
          <div className="space-y-3">
            {reports.map((r, i) => (
              <Card key={i}>
                <CardContent className="py-4">
                  <div className="font-medium">{r.title}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {new Date(r.time).toLocaleString("zh-CN")}
                  </div>
                  <div className="mt-3 rounded-md bg-muted/50 p-4">
                    <Markdown content={r.content} />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

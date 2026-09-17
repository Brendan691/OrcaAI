"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Trash2, ExternalLink, Plus, Loader2, ChevronDown } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { TagList } from "@/components/tag-list";
import { api, DocItem, formatTime, sourceLabel } from "@/lib/api";

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingDelete, setPendingDelete] = useState<DocItem | null>(null);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [openId, setOpenId] = useState<string | null>(null);

  // 表单
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.listDocuments();
      setDocs(res.documents);
    } catch {
      toast.error("无法连接后端,请确认服务已启动");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const togglePreview = async (doc: DocItem) => {
    if (openId === doc.doc_id) {
      setOpenId(null);
      return;
    }
    setOpenId(doc.doc_id);
    if (!previews[doc.doc_id]) {
      try {
        const res = await api.search(doc.title, 2, [doc.doc_id]);
        const content = res.results.find((r) => r.content)?.content ?? "";
        setPreviews((p) => ({ ...p, [doc.doc_id]: content || "（暂无预览内容）" }));
      } catch {
        setPreviews((p) => ({ ...p, [doc.doc_id]: "（预览加载失败）" }));
      }
    }
  };

  const doDelete = async () => {
    if (!pendingDelete) return;
    try {
      await api.deleteDocument(pendingDelete.doc_id);
      toast.success(`已删除《${pendingDelete.title}》`);
      setPendingDelete(null);
      load();
    } catch {
      toast.error("删除失败");
    }
  };

  const submitUrl = async () => {
    if (!url.trim()) return;
    setSubmitting(true);
    try {
      const res = await api.uploadUrl(url.trim());
      if (res.success) {
        toast.success(res.message);
        setUrl("");
        load();
      } else {
        toast.error(res.message);
      }
    } catch {
      toast.error("解析失败,请检查链接或后端");
    } finally {
      setSubmitting(false);
    }
  };

  const submitText = async () => {
    if (!text.trim()) return;
    setSubmitting(true);
    try {
      const res = await api.uploadText(title.trim() || "未命名文档", text.trim());
      if (res.success) {
        toast.success(res.message);
        setTitle("");
        setText("");
        load();
      } else {
        toast.error(res.message);
      }
    } catch {
      toast.error("保存失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">文档管理</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          查看、预览、删除知识库文档,或手动添加
        </p>
      </div>

      <Tabs defaultValue="list">
        <TabsList>
          <TabsTrigger value="list">📋 文档列表</TabsTrigger>
          <TabsTrigger value="add">
            <Plus className="mr-1 h-4 w-4" /> 手动添加
          </TabsTrigger>
        </TabsList>

        {/* 列表 */}
        <TabsContent value="list" className="mt-4 space-y-3">
          {loading ? (
            [1, 2, 3].map((i) => <Skeleton key={i} className="h-28 w-full" />)
          ) : docs.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                知识库还是空的,去添加第一篇文档吧!
              </CardContent>
            </Card>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">共 {docs.length} 篇文档</p>
              {docs.map((doc) => (
                <Card key={doc.doc_id}>
                  <CardContent className="py-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="font-medium">{doc.title}</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          🕐 {formatTime(doc.created_at)}
                          {doc.url && (
                            <>
                              {" · "}
                              <a
                                href={doc.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-0.5 text-primary hover:underline"
                              >
                                原文 <ExternalLink className="h-3 w-3" />
                              </a>
                            </>
                          )}
                          {!doc.url && ` · ${sourceLabel(doc)}`}
                        </div>
                        <div className="mt-2.5">
                          <TagList tags={doc.tags} />
                        </div>
                        <button
                          onClick={() => togglePreview(doc)}
                          className="mt-3 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                        >
                          <ChevronDown
                            className={`h-3.5 w-3.5 transition-transform ${openId === doc.doc_id ? "rotate-180" : ""}`}
                          />
                          预览内容
                        </button>
                        {openId === doc.doc_id && (
                          <div className="mt-2 rounded-md bg-muted/50 p-3 text-sm leading-relaxed text-muted-foreground">
                            {previews[doc.doc_id] ?? (
                              <span className="inline-flex items-center gap-1">
                                <Loader2 className="h-3 w-3 animate-spin" /> 加载中…
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="shrink-0 text-muted-foreground hover:text-destructive"
                        onClick={() => setPendingDelete(doc)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </>
          )}
        </TabsContent>

        {/* 手动添加 */}
        <TabsContent value="add" className="mt-4">
          <Card>
            <CardContent className="space-y-6 py-6">
              <div className="space-y-2">
                <label className="text-sm font-medium">粘贴网页链接</label>
                <div className="flex gap-2">
                  <Input
                    placeholder="https://... (支持公众号文章)"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                  />
                  <Button onClick={submitUrl} disabled={submitting || !url.trim()}>
                    {submitting && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                    解析保存
                  </Button>
                </div>
              </div>
              <div className="space-y-2 border-t pt-6">
                <label className="text-sm font-medium">直接输入文本</label>
                <Input
                  placeholder="标题(可选)"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
                <Textarea
                  placeholder="粘贴要收藏的文本内容…"
                  rows={6}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
                <Button onClick={submitText} disabled={submitting || !text.trim()}>
                  {submitting && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                  保存到知识库
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 删除二次确认 */}
      <Dialog open={!!pendingDelete} onOpenChange={(o) => !o && setPendingDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              确定要删除《{pendingDelete?.title}》吗?此操作不可撤销。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingDelete(null)}>
              取消
            </Button>
            <Button variant="destructive" onClick={doDelete}>
              确认删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/**
 * 小鲸 OrcaAI — 后端 API 客户端
 * 封装所有对 FastAPI 后端的请求。后端地址通过环境变量配置,默认 localhost:8000。
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---- 类型定义(对应后端返回结构)----

export interface DocTags {
  business_type: string[];
  geographic_region: string[];
  topic_category: string[];
  event_nature: string[];
  confidence?: number;
}

export interface DocItem {
  doc_id: string;
  title: string;
  url: string;
  source_type: string;
  created_at: string;
  tags: DocTags;
}

export interface SearchHit {
  doc_id: string;
  title: string;
  content: string;
  url: string;
  score: number;
  vector_score: number;
  keyword_score: number;
  time_score: number;
  tag_score: number;
  tags: DocTags;
}

export interface ChatSource {
  id: string;
  index: number;
  cite_marker: string;
  source_type: "knowledge" | "web";
  doc_id: string;
  chunk_id: string;
  chunk_index?: number;
  title: string;
  snippet: string;
  score?: number;
  url: string;
  start_idx?: number;
  end_idx?: number;
  line_start?: number;
  line_end?: number;
  locator_label: string;
  provider: string;
}

export interface ChatResult {
  answer: string;
  sources: ChatSource[];
  confidence: number;
  search_status: "disabled" | "ok" | "degraded" | "failed";
  search_message: string;
}

// ---- 通用请求封装 ----

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ---- 各接口 ----

export const api = {
  health: () => request<{ status: string }>("/health"),

  status: () =>
    request<{ document_count: number; version: string; name: string }>(
      "/api/status"
    ),

  listDocuments: () =>
    request<{ documents: DocItem[]; total: number }>("/api/documents"),

  uploadUrl: (url: string) =>
    request<{ success: boolean; doc_id?: string; message: string; tags?: DocTags }>(
      "/api/documents/upload",
      { method: "POST", body: JSON.stringify({ url }) }
    ),

  uploadText: (title: string, content: string) =>
    request<{ success: boolean; doc_id?: string; message: string; tags?: DocTags }>(
      "/api/documents/upload",
      { method: "POST", body: JSON.stringify({ title, content }) }
    ),

  deleteDocument: (docId: string) =>
    request<{ success: boolean; message: string }>(
      `/api/documents/${docId}`,
      { method: "DELETE" }
    ),

  search: (query: string, topK = 5, docFilter?: string[]) =>
    request<{ results: SearchHit[]; total: number }>("/api/search", {
      method: "POST",
      body: JSON.stringify({ query, top_k: topK, doc_filter: docFilter }),
    }),

  chat: (message: string, searchInternet: boolean = false) =>
    request<ChatResult>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, search_internet: searchInternet }),
    }),

  tags: () =>
    request<{ dimensions: Record<string, { display_name: string; values: string[] }> }>(
      "/api/tags"
    ),

  reportTypes: () =>
    request<{ types: { id: string; name: string }[] }>(
      "/api/generate/report-types"
    ),

  generateReport: (reportType: string, searchInternet: boolean = false) =>
    request<{ success: boolean; title: string; content: string; generated_at: string }>(
      "/api/generate/report",
      { method: "POST", body: JSON.stringify({ report_type: reportType, search_internet: searchInternet }) }
    ),
};

// ---- 工具函数 ----

/** 把 ISO 时间转成可读格式: 2026-07-30T11:07:28.204 → 2026-07-30 11:07 */
export function formatTime(iso: string): string {
  if (!iso) return "未知";
  try {
    return iso.replace("T", " ").split(".")[0].slice(0, 16);
  } catch {
    return iso;
  }
}

/** 汇总一个文档的所有标签为扁平数组 */
export function flattenTags(tags?: DocTags): string[] {
  if (!tags) return [];
  return [
    ...(tags.business_type || []),
    ...(tags.geographic_region || []),
    ...(tags.topic_category || []),
    ...(tags.event_nature || []),
  ];
}

/** 根据来源类型返回可读来源 */
export function sourceLabel(doc: DocItem): string {
  if (doc.url) return doc.url;
  if (doc.source_type === "text") return "手动输入";
  if (doc.source_type === "file") return "文件上传";
  return doc.source_type || "未知来源";
}

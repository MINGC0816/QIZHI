const API_BASE = "/api-proxy";

export type ChatResponse = {
  answer: string;
  thread_id: string;
};

export type ThreadItem = {
  thread_id: string;
  title: string;
  preview: string;
  user_id: string;
  created_at: string;
  updated_at: string;
};

export type HistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

export type IngestResult = {
  ingested: string[];
  chunk_count: number;
  errors: string[];
};

export type DocumentItem = {
  filename: string;
  indexed: boolean;
  has_raw: boolean;
};

export type DocumentPreviewPage = {
  page: number | null;
  content: string;
};

export type DocumentPreviewResult = {
  filename: string;
  page_count: number;
  content_preview: string;
  pages: DocumentPreviewPage[];
};

export type DocumentChunk = {
  chunk_id: number;
  page: number | null;
  content: string;
};

export type DocumentChunksResult = {
  filename: string;
  from_vectorstore: boolean;
  chunk_count: number;
  chunks: DocumentChunk[];
};

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    return JSON.stringify(data);
  } catch {
    return res.statusText || `HTTP ${res.status}`;
  }
}

export async function listThreads(userId = "local"): Promise<ThreadItem[]> {
  const res = await fetch(
    `${API_BASE}/api/v1/threads?user_id=${encodeURIComponent(userId)}`,
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error(await parseError(res));
  const data = (await res.json()) as { threads: ThreadItem[] };
  return data.threads ?? [];
}

export async function createThread(
  title = "新对话",
): Promise<ThreadItem> {
  const res = await fetch(`${API_BASE}/api/v1/threads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, user_id: "local" }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<ThreadItem>;
}

export async function getThreadMessages(
  threadId: string,
): Promise<HistoryMessage[]> {
  const res = await fetch(
    `${API_BASE}/api/v1/threads/${encodeURIComponent(threadId)}/messages`,
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error(await parseError(res));
  const data = (await res.json()) as { messages: HistoryMessage[] };
  return data.messages ?? [];
}

export async function deleteThread(threadId: string): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/v1/threads/${encodeURIComponent(threadId)}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(await parseError(res));
}

export async function chat(
  message: string,
  threadId: string,
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<ChatResponse>;
}

export async function listDocuments(): Promise<DocumentItem[]> {
  const res = await fetch(`${API_BASE}/api/v1/admin/documents`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseError(res));
  const data = (await res.json()) as { documents: unknown };
  const rows = data.documents ?? [];
  // 兼容旧版 string[] 返回
  return rows.map((item) => {
    if (typeof item === "string") {
      return { filename: item, indexed: true, has_raw: true };
    }
    const row = item as DocumentItem;
    return {
      filename: row.filename,
      indexed: Boolean(row.indexed),
      has_raw: Boolean(row.has_raw),
    };
  });
}

export async function ingestAll(): Promise<IngestResult> {
  const res = await fetch(`${API_BASE}/api/v1/admin/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ replace: true }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<IngestResult>;
}

export async function uploadFile(file: File): Promise<{ saved: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/v1/admin/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<{ saved: string }>;
}

export async function getDocumentPreview(
  filename: string,
): Promise<DocumentPreviewResult> {
  const res = await fetch(
    `${API_BASE}/api/v1/admin/documents/${encodeURIComponent(filename)}/preview`,
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<DocumentPreviewResult>;
}

export async function getDocumentChunks(
  filename: string,
): Promise<DocumentChunksResult> {
  const res = await fetch(
    `${API_BASE}/api/v1/admin/documents/${encodeURIComponent(filename)}/chunks`,
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<DocumentChunksResult>;
}

export async function deleteDocument(
  filename: string,
): Promise<{ ok: boolean; filename: string }> {
  const res = await fetch(
    `${API_BASE}/api/v1/admin/documents/${encodeURIComponent(filename)}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<{ ok: boolean; filename: string }>;
}

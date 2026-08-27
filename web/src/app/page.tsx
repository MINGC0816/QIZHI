"use client";

import { useCallback, useEffect, useState } from "react";
import { App } from "antd";
import ChatPanel from "@/components/ChatPanel";
import SessionSidebar from "@/components/SessionSidebar";
import {
  createThread,
  listThreads,
  type ThreadItem,
} from "@/lib/api";

const STORAGE_KEY = "qizhi_active_thread_id";

export default function HomePage() {
  const { message } = App.useApp();
  const [mounted, setMounted] = useState(false);
  const [threads, setThreads] = useState<ThreadItem[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refreshThreads = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await listThreads();
      setThreads(rows);
      return rows;
    } catch (e) {
      message.error(e instanceof Error ? e.message : "加载会话失败");
      return [] as ThreadItem[];
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const rows = await refreshThreads();
      if (cancelled) return;
      const saved =
        typeof window !== "undefined"
          ? localStorage.getItem(STORAGE_KEY)
          : null;
      if (saved && rows.some((t) => t.thread_id === saved)) {
        setActiveId(saved);
      } else if (rows.length > 0) {
        setActiveId(rows[0].thread_id);
        localStorage.setItem(STORAGE_KEY, rows[0].thread_id);
      } else {
        try {
          const t = await createThread();
          if (cancelled) return;
          setThreads([t]);
          setActiveId(t.thread_id);
          localStorage.setItem(STORAGE_KEY, t.thread_id);
        } catch (e) {
          message.error(e instanceof Error ? e.message : "创建会话失败");
        }
      }
      setMounted(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshThreads, message]);

  const onSelect = (id: string) => {
    setActiveId(id);
    localStorage.setItem(STORAGE_KEY, id);
  };

  const onCreate = async () => {
    try {
      const t = await createThread();
      await refreshThreads();
      setActiveId(t.thread_id);
      localStorage.setItem(STORAGE_KEY, t.thread_id);
    } catch (e) {
      message.error(e instanceof Error ? e.message : "创建会话失败");
    }
  };

  const onDeleted = async () => {
    const rows = await refreshThreads();
    if (activeId && !rows.some((t) => t.thread_id === activeId)) {
      if (rows[0]) {
        setActiveId(rows[0].thread_id);
        localStorage.setItem(STORAGE_KEY, rows[0].thread_id);
      } else {
        const t = await createThread();
        setThreads([t]);
        setActiveId(t.thread_id);
        localStorage.setItem(STORAGE_KEY, t.thread_id);
      }
    }
  };

  if (!mounted) {
    return <main className="app-shell app-shell-loading" aria-busy="true" />;
  }

  return (
    <main className="app-shell">
      <SessionSidebar
        threads={threads}
        activeId={activeId}
        loading={loading}
        onSelect={onSelect}
        onCreate={() => void onCreate()}
        onDeleted={() => void onDeleted()}
      />
      <ChatPanel
        threadId={activeId}
        onChatted={() => void refreshThreads()}
      />
    </main>
  );
}

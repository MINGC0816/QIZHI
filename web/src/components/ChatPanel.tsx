"use client";

import { useEffect, useRef, useState } from "react";
import { App, Button, Input, Spin, Typography } from "antd";
import { SendOutlined } from "@ant-design/icons";
import { chat, getThreadMessages } from "@/lib/api";

const { Text, Paragraph, Title } = Typography;

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type Props = {
  threadId: string | null;
  onChatted?: () => void;
};

function newId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export default function ChatPanel({ threadId, onChatted }: Props) {
  const { message } = App.useApp();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  useEffect(() => {
    if (!threadId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    setLoadingHistory(true);
    void getThreadMessages(threadId)
      .then((rows) => {
        if (cancelled) return;
        setMessages(
          rows.map((m) => ({
            id: newId(),
            role: m.role,
            content: m.content,
          })),
        );
      })
      .catch((e) => {
        if (!cancelled) {
          message.error(e instanceof Error ? e.message : "加载历史失败");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });
    return () => {
      cancelled = true;
    };
  }, [threadId, message]);

  const send = async (text: string) => {
    const content = text.trim();
    if (!content || sending || !threadId) return;

    setInput("");
    setMessages((prev) => [...prev, { id: newId(), role: "user", content }]);
    setSending(true);
    try {
      const res = await chat(content, threadId);
      setMessages((prev) => [
        ...prev,
        { id: newId(), role: "assistant", content: res.answer || "（空响应）" },
      ]);
      onChatted?.();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "问答失败");
      setMessages((prev) => [
        ...prev,
        {
          id: newId(),
          role: "assistant",
          content: "抱歉，请求失败。请确认后端已启动，且已连接 VPN / 模型服务。",
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <section className="kb-chat">
      <header className="kb-chat-header">
        <Title level={4} className="kb-chat-title">
          知识问答
        </Title>
      </header>

      <div className="kb-chat-body">
        {loadingHistory ? (
          <div className="kb-typing">
            <Spin size="small" />
            <Text type="secondary">加载会话…</Text>
          </div>
        ) : null}

        {!loadingHistory && messages.length === 0 && !sending ? (
          <div className="kb-chat-empty">
            <Title level={2} className="kb-chat-hero">
              有制度问题，先问企知
            </Title>
            <Paragraph type="secondary">
              可询问休假、报销、入职等规定。回答会标注文档来源。
            </Paragraph>
            <div className="kb-examples chat-quick">
              {["公司年休假有几天？", "报销流程是什么？", "试用期多久？"].map(
                (q) => (
                  <button
                    key={q}
                    type="button"
                    className="kb-example"
                    disabled={!threadId || sending}
                    onClick={() => void send(q)}
                  >
                    {q}
                  </button>
                ),
              )}
            </div>
          </div>
        ) : null}

        {!loadingHistory && (messages.length > 0 || sending) ? (
          <div className="kb-messages">
            {messages.map((m) => (
              <article
                key={m.id}
                className={`kb-bubble kb-bubble-${m.role}`}
              >
                <Text className="kb-bubble-role">
                  {m.role === "user" ? "我" : "企知"}
                </Text>
                <div className="kb-bubble-content">{m.content}</div>
              </article>
            ))}
            {sending ? (
              <div className="kb-typing">
                <Spin size="small" />
                <Text type="secondary">正在检索并生成回答…</Text>
              </div>
            ) : null}
            <div ref={bottomRef} />
          </div>
        ) : null}
      </div>

      <footer className="kb-chat-input">
        <Input.TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            threadId ? "输入制度相关问题…" : "请先新建或选择左侧会话"
          }
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={sending || !threadId}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              void send(input);
            }
          }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          loading={sending}
          disabled={!threadId}
          onClick={() => void send(input)}
        >
          发送
        </Button>
      </footer>
    </section>
  );
}

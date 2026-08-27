"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import {
  App,
  Button,
  Empty,
  Popconfirm,
  Spin,
  Tag,
  Typography,
  Upload,
} from "antd";
import {
  CloudUploadOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  FileTextOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import {
  deleteDocument,
  getDocumentChunks,
  getDocumentPreview,
  ingestAll,
  listDocuments,
  uploadFile,
  type DocumentChunk,
  type DocumentItem,
} from "@/lib/api";

const { Text, Title, Paragraph } = Typography;

export default function AdminPage() {
  const { message } = App.useApp();
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [activeDoc, setActiveDoc] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewText, setPreviewText] = useState("");
  const [pageCount, setPageCount] = useState(0);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [chunkCount, setChunkCount] = useState(0);
  const [fromVectorstore, setFromVectorstore] = useState(false);
  const [activeTab, setActiveTab] = useState("preview");
  const [previewError, setPreviewError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await listDocuments();
      setDocs(rows);
      if (rows.length === 0) {
        setActiveDoc(null);
        return rows;
      }
      setActiveDoc((prev) => {
        if (prev && rows.some((d) => d.filename === prev)) return prev;
        return rows[0].filename;
      });
      return rows;
    } catch (e) {
      message.error(e instanceof Error ? e.message : "加载文档失败");
      return [] as DocumentItem[];
    } finally {
      setLoading(false);
    }
  }, [message]);

  const loadPreview = useCallback(
    async (filename: string) => {
      setPreviewLoading(true);
      setPreviewText("");
      setChunks([]);
      setPageCount(0);
      setChunkCount(0);
      setFromVectorstore(false);
      setPreviewError(null);
      try {
        const [previewSettled, chunkSettled] = await Promise.allSettled([
          getDocumentPreview(filename),
          getDocumentChunks(filename),
        ]);

        const errors: string[] = [];

        if (previewSettled.status === "fulfilled") {
          setPreviewText(previewSettled.value.content_preview || "");
          setPageCount(previewSettled.value.page_count || 0);
        } else {
          setPreviewText("");
          setPageCount(0);
          const reason = previewSettled.reason;
          errors.push(
            reason instanceof Error ? reason.message : "原文预览失败",
          );
        }

        if (chunkSettled.status === "fulfilled") {
          setChunks(chunkSettled.value.chunks || []);
          setChunkCount(chunkSettled.value.chunk_count || 0);
          setFromVectorstore(Boolean(chunkSettled.value.from_vectorstore));
        } else {
          setChunks([]);
          setChunkCount(0);
          setFromVectorstore(false);
          const reason = chunkSettled.reason;
          errors.push(
            reason instanceof Error ? reason.message : "切片预览失败",
          );
        }

        if (errors.length) {
          // 去重：扫描件时常两边同一条错误
          const uniq = [...new Set(errors)];
          setPreviewError(uniq.join("；"));
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : "加载预览失败";
        setPreviewError(msg);
        message.error(msg);
      } finally {
        setPreviewLoading(false);
      }
    },
    [message],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!activeDoc) {
      setPreviewText("");
      setChunks([]);
      return;
    }
    void loadPreview(activeDoc);
  }, [activeDoc, loadPreview]);

  const onIngest = async () => {
    setIngesting(true);
    try {
      const result = await ingestAll();
      if (result.errors?.length) {
        message.warning(`入库完成，但有错误：${result.errors.join("；")}`);
      } else {
        message.success(
          `已入库 ${result.ingested.length} 个文件，共 ${result.chunk_count} 个片段`,
        );
      }
      await refresh();
      if (activeDoc) await loadPreview(activeDoc);
    } catch (e) {
      message.error(e instanceof Error ? e.message : "入库失败");
    } finally {
      setIngesting(false);
    }
  };

  const onDeleteDoc = async (filename: string) => {
    try {
      await deleteDocument(filename);
      message.success(`已删除 ${filename}`);
      const rows = await refresh();
      if (activeDoc === filename) {
        setActiveDoc(rows[0]?.filename ?? null);
        setPreviewText("");
        setChunks([]);
        setPageCount(0);
        setChunkCount(0);
        setPreviewError(null);
      }
    } catch (e) {
      message.error(e instanceof Error ? e.message : "删除失败");
    }
  };

  const activeMeta = docs.find((d) => d.filename === activeDoc) ?? null;

  return (
    <main className="admin-shell">
      <header className="admin-header">
        <div className="chat-brand">
          <Image
            src="/logo.png"
            alt="企知 Logo"
            width={42}
            height={42}
            className="kb-brand-mark"
          />
          <div>
            <Title level={3} className="kb-brand-title">
              企知 · 知识库管理
            </Title>
            <Text className="kb-brand-sub">
              全屏管理：上传、重建索引、预览原文与切片
            </Text>
          </div>
        </div>
        <div className="admin-header-actions">
          <Upload
            accept=".pdf,.docx,.md,.markdown,.txt"
            showUploadList={false}
            customRequest={async (options) => {
              const file = options.file as File;
              try {
                const r = await uploadFile(file);
                message.success(`已上传 ${r.saved}，请点击「重建索引」`);
                options.onSuccess?.(r);
                const rows = await refresh();
                setActiveDoc(r.saved);
                if (!rows.some((d) => d.filename === r.saved)) {
                  setActiveDoc(r.saved);
                }
              } catch (e) {
                const err = e instanceof Error ? e : new Error("上传失败");
                message.error(err.message);
                options.onError?.(err);
              }
            }}
          >
            <Button icon={<CloudUploadOutlined />}>上传文档</Button>
          </Upload>
          <Button
            type="primary"
            icon={<DatabaseOutlined />}
            loading={ingesting}
            onClick={() => void onIngest()}
          >
            重建索引
          </Button>
          <Button
            icon={<ReloadOutlined />}
            loading={loading}
            onClick={() => void refresh()}
          >
            刷新
          </Button>
        </div>
      </header>

      <section className="admin-workspace">
        <aside className="admin-doc-pane">
          <div className="admin-pane-title">
            <Text strong>文档列表</Text>
            <Text type="secondary">{docs.length} 个</Text>
          </div>
          <div className="admin-doc-list">
            {loading && docs.length === 0 ? (
              <div className="admin-center">
                <Spin />
              </div>
            ) : docs.length === 0 ? (
              <Empty description="暂无文档，请先上传" />
            ) : (
              <ul className="kb-doc-ul">
                {docs.map((item) => (
                  <li key={item.filename}>
                    <div
                      className={`admin-doc-btn${
                        activeDoc === item.filename ? " is-active" : ""
                      }`}
                    >
                      <button
                        type="button"
                        className="admin-doc-select"
                        onClick={() => setActiveDoc(item.filename)}
                      >
                        <span className="kb-doc-row">
                          <FileTextOutlined />
                          <span className="admin-doc-name" title={item.filename}>
                            {item.filename}
                          </span>
                        </span>
                        <span className="admin-doc-tags">
                          {item.indexed ? (
                            <Tag color="success">已入库</Tag>
                          ) : (
                            <Tag>未入库</Tag>
                          )}
                          {!item.has_raw ? (
                            <Tag color="warning">无原文</Tag>
                          ) : null}
                        </span>
                      </button>
                      <Popconfirm
                        title="删除文档"
                        description="将同时删除原文与向量库切片，确认？"
                        okText="删除"
                        cancelText="取消"
                        okButtonProps={{ danger: true }}
                        onConfirm={() => void onDeleteDoc(item.filename)}
                      >
                        <Button
                          type="text"
                          danger
                          size="small"
                          className="admin-doc-del"
                          icon={<DeleteOutlined />}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </Popconfirm>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>

        <section className="admin-preview-pane">
          {!activeDoc ? (
            <div className="admin-center">
              <Empty description="选择左侧文档以预览" />
            </div>
          ) : (
            <>
              <div className="admin-preview-head">
                <div>
                  <Title level={4} className="admin-preview-title">
                    {activeDoc}
                  </Title>
                  <Paragraph type="secondary" className="admin-preview-meta">
                    {pageCount > 0 ? `${pageCount} 页/段 · ` : ""}
                    {chunkCount} 个切片
                    {fromVectorstore ? " · 来自向量库" : " · 即时分片预览"}
                    {activeMeta && !activeMeta.indexed
                      ? " · 尚未写入向量库"
                      : ""}
                  </Paragraph>
                </div>
              </div>

              <div className="admin-tab-bar" role="tablist">
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "preview"}
                  className={`admin-tab-btn${
                    activeTab === "preview" ? " is-active" : ""
                  }`}
                  onClick={() => setActiveTab("preview")}
                >
                  原文预览
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "chunks"}
                  className={`admin-tab-btn${
                    activeTab === "chunks" ? " is-active" : ""
                  }`}
                  onClick={() => setActiveTab("chunks")}
                >
                  切片结果（{chunkCount}）
                </button>
              </div>

              <div className="admin-scroll-area">
                {previewError ? (
                  <div className="admin-error-box">
                    <Text type="danger">{previewError}</Text>
                    <Paragraph type="secondary" style={{ marginTop: 8 }}>
                      当前版本仅支持可复制文字的 PDF（非扫描件）。扫描版 PDF
                      需要 OCR，暂未接入。
                    </Paragraph>
                  </div>
                ) : null}
                {previewLoading ? (
                  <div className="admin-center">
                    <Spin
                      description={
                        activeTab === "preview" ? "加载原文…" : "加载切片…"
                      }
                    />
                  </div>
                ) : activeTab === "preview" ? (
                  previewText ? (
                    <pre className="admin-preview-text">{previewText}</pre>
                  ) : previewError ? null : (
                    <Empty description="无法读取原文（文件可能不在 raw 目录）" />
                  )
                ) : chunks.length === 0 ? (
                  previewError ? null : (
                    <Empty description="暂无切片，请先重建索引或确认文件可解析" />
                  )
                ) : (
                  <div className="admin-chunk-list">
                    {chunks.map((c) => (
                      <article
                        key={`${c.chunk_id}-${c.page}`}
                        className="admin-chunk-card"
                      >
                        <header className="admin-chunk-head">
                          <Text strong>切片 #{c.chunk_id}</Text>
                          {c.page != null ? <Tag>page {c.page}</Tag> : null}
                          <Text type="secondary">{c.content.length} 字</Text>
                        </header>
                        <pre className="admin-chunk-body">{c.content}</pre>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </section>
      </section>
    </main>
  );
}

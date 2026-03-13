"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  HardDrive,
  RefreshCw,
  Download,
  FileText,
  FileSpreadsheet,
  File,
  Loader2,
  CheckCircle2,
  Database,
  ExternalLink,
  FolderOpen,
} from "lucide-react";
import { apiFetch } from "@/lib/api-client";
import {
  isGoogleAuthCompleteMessage,
  openGoogleAuthPopup,
} from "@/lib/google-auth-popup";
import { useToast } from "@/components/toast";

interface DriveStatus {
  connected: boolean;
  email?: string;
  vectorStore: { totalDocuments: number; sources: Record<string, number> };
}

interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  modifiedTime: string;
}

function getFileIcon(mimeType: string) {
  if (mimeType.includes("spreadsheet")) return FileSpreadsheet;
  if (mimeType.includes("document") || mimeType.includes("text") || mimeType.includes("pdf"))
    return FileText;
  return File;
}

interface DrivePanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function DrivePanel({ isOpen, onClose }: DrivePanelProps) {
  const { toast } = useToast();
  const [status, setStatus] = useState<DriveStatus | null>(null);
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [ingestProgress, setIngestProgress] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await apiFetch("/api/drive/status");
      const data = await res.json();
      setStatus(data);
    } catch {
      setStatus(null);
    }
  }, []);

  const fetchFiles = useCallback(async () => {
    try {
      const res = await apiFetch("/api/drive/files");
      if (res.ok) {
        const data = await res.json();
        setFiles(data.files ?? []);
      }
    } catch {
      setFiles([]);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  useEffect(() => {
    if (status?.connected) fetchFiles();
  }, [status?.connected, fetchFiles]);

  const handleConnect = async () => {
    setLoading(true);
    const popup = openGoogleAuthPopup("archon-drive-connect");
    if (!popup) {
      setLoading(false);
      toast("error", "Google sign-in popup was blocked. Allow pop-ups and try again.");
      return;
    }

    let pollId: number | null = null;
    let timeoutId: number | null = null;

    const cleanup = () => {
      if (pollId !== null) {
        window.clearInterval(pollId);
      }
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
      window.removeEventListener("message", handleMessage);
    };

    const refreshConnection = async () => {
      try {
        const statusRes = await apiFetch("/api/drive/status");
        const statusData = await statusRes.json();
        if (statusData.connected) {
          cleanup();
          setStatus(statusData);
          setLoading(false);
          popup.close();
          return true;
        }
      } catch {
        /* polling fallback */
      }

      return false;
    };

    const handleMessage = (event: MessageEvent) => {
      if (!isGoogleAuthCompleteMessage(event)) {
        return;
      }
      void refreshConnection();
    };

    window.addEventListener("message", handleMessage);

    try {
      const res = await apiFetch("/api/drive/auth");
      const data = await res.json();
      if (res.ok && data.url) {
        popup.location.href = data.url;
        popup.focus();
        pollId = window.setInterval(async () => {
          if (popup.closed) {
            cleanup();
            setLoading(false);
            return;
          }

          await refreshConnection();
        }, 500);

        timeoutId = window.setTimeout(() => {
          cleanup();
          popup.close();
          setLoading(false);
        }, 60_000);
        return;
      }

      cleanup();
      popup.close();
      setLoading(false);
      if (data.error) {
        toast("error", data.error);
      }
    } catch {
      cleanup();
      popup.close();
      setLoading(false);
      toast("error", "Could not reach the auth server. Check that the backend is running.");
    }
  };

  const handleIngest = async (incremental: boolean) => {
    setIngesting(true);
    setIngestProgress("Starting ingestion...");

    try {
      const res = await apiFetch("/api/drive/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ incremental }),
      });

      const reader = res.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === "progress") {
              setIngestProgress(
                `Processing ${event.processed}/${event.total}: ${event.current ?? "..."}`
              );
            } else if (event.type === "complete") {
              setIngestProgress(
                `Done! ${event.processed} files. ${event.errors?.length ?? 0} errors.`
              );
            }
          } catch {
            /* skip */
          }
        }
      }
    } catch (err) {
      setIngestProgress(`Error: ${err instanceof Error ? err.message : "Unknown"}`);
    } finally {
      setIngesting(false);
      fetchStatus();
    }
  };

  return (
    <>
      {/* Mobile backdrop */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 z-30 lg:hidden"
            onClick={onClose}
          />
        )}
      </AnimatePresence>

      {/* Fixed right panel */}
      <aside
        className={`
          h-full bg-[var(--color-sidebar)] overflow-hidden shrink-0
          transition-all duration-300 ease-in-out
          max-lg:fixed max-lg:top-0 max-lg:right-0 max-lg:z-40
          ${isOpen ? "w-[280px]" : "w-0 max-lg:translate-x-full"}
        `}
      >
        <div className="w-[280px] min-w-[280px] h-full flex flex-col">
          {/* Header */}
          <div className="h-11 flex items-center justify-between px-3 shrink-0">
            <div className="flex items-center gap-2">
              <HardDrive className="w-4 h-4 text-[var(--color-text-muted)]" />
              <span className="text-sm font-medium text-[var(--color-text-secondary)]">Drive</span>
              {status?.connected && (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              )}
            </div>
            
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-3 pb-4">
            {!status?.connected ? (
              <div className="text-center py-10 space-y-4">
                <div className="w-14 h-14 mx-auto rounded-2xl bg-[var(--color-card)] flex items-center justify-center">
                  <HardDrive className="w-7 h-7 text-[var(--color-text-muted)]" />
                </div>
                <div>
                  <h3 className="font-medium text-sm">Connect Google Drive</h3>
                  <p className="text-xs text-[var(--color-text-muted)] mt-1 max-w-[200px] mx-auto">
                    Search and index your Drive files for research.
                  </p>
                </div>
                <button
                  onClick={handleConnect}
                  disabled={loading}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white text-black font-medium text-xs hover:bg-gray-200 disabled:opacity-50 transition-all cursor-pointer"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    <>
                      <ExternalLink className="w-3.5 h-3.5" />
                      Connect
                    </>
                  )}
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Status */}
                <div className="flex items-center gap-2.5 p-2.5 rounded-xl bg-emerald-500/10">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-emerald-300">Connected</p>
                    {status.email && (
                      <p className="text-[10px] text-[var(--color-text-muted)] truncate">{status.email}</p>
                    )}
                  </div>
                </div>

                {/* Vector store stats */}
                <div className="p-3 rounded-xl bg-[var(--color-card)]">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Database className="w-3.5 h-3.5 text-[var(--color-text-muted)]" />
                    <span className="text-[11px] text-[var(--color-text-muted)]">Vector Store</span>
                  </div>
                  <p className="text-xl font-bold">
                    {status.vectorStore.totalDocuments}
                    <span className="text-xs font-normal text-[var(--color-text-muted)] ml-1">chunks</span>
                  </p>
                </div>

                {/* Sync buttons */}
                <div className="space-y-1.5">
                  <p className="text-[11px] text-[var(--color-text-muted)] px-1">Sync</p>
                  <div className="flex gap-1.5">
                    <button
                      onClick={() => handleIngest(true)}
                      disabled={ingesting}
                      className="flex-1 flex items-center justify-center gap-1.5 px-2 py-2 rounded-xl bg-[var(--color-card)] text-xs text-[var(--color-text-secondary)] hover:bg-[var(--color-card-hover)] disabled:opacity-50 transition-colors cursor-pointer"
                    >
                      {ingesting ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                      Incremental
                    </button>
                    <button
                      onClick={() => handleIngest(false)}
                      disabled={ingesting}
                      className="flex-1 flex items-center justify-center gap-1.5 px-2 py-2 rounded-xl bg-[var(--color-card)] text-xs text-[var(--color-text-secondary)] hover:bg-[var(--color-card-hover)] disabled:opacity-50 transition-colors cursor-pointer"
                    >
                      <Download className="w-3 h-3" />
                      Full
                    </button>
                  </div>
                  {ingestProgress && (
                    <p className="text-[10px] text-[var(--color-text-muted)] p-2 bg-[var(--color-card)] rounded-lg">
                      {ingestProgress}
                    </p>
                  )}
                </div>

                {/* Files list */}
                <div className="space-y-1.5">
                  <div className="flex items-center gap-1.5 px-1">
                    <FolderOpen className="w-3 h-3 text-[var(--color-text-muted)]" />
                    <p className="text-[11px] text-[var(--color-text-muted)]">
                      Files{files.length > 0 && ` (${files.length})`}
                    </p>
                  </div>
                  {files.length === 0 ? (
                    <p className="text-xs text-[var(--color-text-muted)] px-1 py-4 text-center">
                      No files synced yet
                    </p>
                  ) : (
                    <div className="space-y-0.5 max-h-[calc(100vh-380px)] overflow-y-auto">
                      {files.map((file) => {
                        const Icon = getFileIcon(file.mimeType);
                        return (
                          <div
                            key={file.id}
                            className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-[var(--color-card)] transition-colors"
                          >
                            <Icon className="w-3.5 h-3.5 text-[var(--color-text-muted)] shrink-0" />
                            <div className="min-w-0 flex-1">
                              <p className="text-xs text-[var(--color-text-secondary)] truncate">{file.name}</p>
                              <p className="text-[10px] text-[var(--color-text-muted)]">
                                {new Date(file.modifiedTime).toLocaleDateString()}
                              </p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}

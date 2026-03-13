"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plus,
  MessageSquare,
  Loader2,
  Trash2,
  LogOut,
} from "lucide-react";
import { apiFetch } from "@/lib/api-client";

interface HistoryItem {
  id: string;
  task: string;
  status: string;
  createdAt: string;
}

function groupByDate(items: HistoryItem[]) {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayStart = new Date(todayStart);
  yesterdayStart.setDate(yesterdayStart.getDate() - 1);
  const weekStart = new Date(todayStart);
  weekStart.setDate(weekStart.getDate() - 7);

  const groups: { label: string; items: HistoryItem[] }[] = [
    { label: "Today", items: [] },
    { label: "Yesterday", items: [] },
    { label: "Previous 7 days", items: [] },
    { label: "Older", items: [] },
  ];

  for (const item of items) {
    const d = new Date(item.createdAt);
    if (d >= todayStart) groups[0].items.push(item);
    else if (d >= yesterdayStart) groups[1].items.push(item);
    else if (d >= weekStart) groups[2].items.push(item);
    else groups[3].items.push(item);
  }

  return groups.filter((g) => g.items.length > 0);
}

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onLogout?: () => void;
}

export function Sidebar({ isOpen, onClose, onNewChat, onLogout }: SidebarProps) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/api/history?limit=30")
      .then((r) => r.json())
      .then((data) => setItems(data.items ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await apiFetch(`/api/history/${id}`, { method: "DELETE" }).catch(() => {});
    setItems((prev) => prev.filter((i) => i.id !== id));
  };

  const groups = groupByDate(items);

  return (
    <>
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

      <aside
        className={`
          h-full bg-[var(--color-sidebar)] overflow-hidden shrink-0
          transition-all duration-300 ease-in-out
          max-lg:fixed max-lg:top-0 max-lg:left-0 max-lg:z-40
          ${isOpen ? "w-[260px]" : "w-0 max-lg:-translate-x-full"}
        `}
      >
        <div className="w-[260px] min-w-[260px] h-full flex flex-col">
          {/* New chat */}
          <div className="p-3">
            <button
              onClick={() => {
                onNewChat();
                onClose();
              }}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl hover:bg-[var(--color-card)] text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              New chat
            </button>
          </div>

          {/* History */}
          <div className="flex-1 overflow-y-auto px-2 pb-2">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-4 h-4 text-[var(--color-text-muted)] animate-spin" />
              </div>
            ) : items.length === 0 ? (
              <div className="text-center py-8 px-4">
                <MessageSquare className="w-6 h-6 text-[var(--color-text-muted)] mx-auto mb-2 opacity-30" />
                <p className="text-xs text-[var(--color-text-muted)]">No history yet</p>
              </div>
            ) : (
              <div className="space-y-5">
                {groups.map((group) => (
                  <div key={group.label}>
                    <p className="text-[11px] font-medium text-[var(--color-text-muted)] px-2 py-1">
                      {group.label}
                    </p>
                    <div className="space-y-px">
                      {group.items.map((item) => (
                        <div
                          key={item.id}
                          className="group flex items-center gap-2 px-2.5 py-2 rounded-lg hover:bg-[var(--color-card)] transition-colors cursor-pointer"
                        >
                          <span className="text-sm text-[var(--color-text-secondary)] truncate flex-1">
                            {item.task}
                          </span>
                          <button
                            onClick={(e) => handleDelete(item.id, e)}
                            className="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-[var(--color-card-hover)] text-[var(--color-text-muted)] hover:text-red-400 transition-all cursor-pointer shrink-0"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Bottom actions */}
          <div className="p-2">
            <button
              onClick={onLogout}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] hover:bg-[var(--color-card)] transition-colors cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
              Log out
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

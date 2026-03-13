"use client";

import { useState, useRef, useEffect } from "react";
import { ArrowUp, Loader2 } from "lucide-react";

interface AgentInputProps {
  onSubmit: (task: string, maxSteps: number) => void;
  isRunning: boolean;
  onCancel?: () => void;
  placeholder?: string;
}

export function AgentInput({
  onSubmit,
  isRunning,
  placeholder,
}: AgentInputProps) {
  const [task, setTask] = useState("");
  const [maxSteps, setMaxSteps] = useState(10);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 180) + "px";
    }
  }, [task]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        textareaRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const handleSubmit = () => {
    if (!task.trim() || isRunning) return;
    onSubmit(task.trim(), maxSteps);
    setTask("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="w-full">
        <div className="relative bg-[#2f2f2f] rounded-3xl overflow-hidden">
        <textarea
          ref={textareaRef}
          value={task}
          onChange={(e) => setTask(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder ?? "Ask anything..."}
          rows={1}
          disabled={isRunning}
          className="w-full bg-transparent text-[var(--color-text] placeholder:text-[var(--color-text-muted] pl-4 pr-24 pt-3.5 pb-3.5 resize-none focus:outline-none text-[15px] leading-relaxed"
        />

        <div className="absolute right-2 bottom-2 flex items-center gap-1.5">
          <select
            value={maxSteps}
            onChange={(e) => setMaxSteps(Number(e.target.value))}
            disabled={isRunning}
            className="bg-transparent text-xs text-[var(--color-text-muted] focus:outline-none cursor-pointer py-1 px-1 rounded-lg hover:text-[var(--color-text-secondary] transition-colors"
            title="Research depth"
          >
            {[5, 8, 10, 12, 15].map((n) => (
              <option key={n} value={n} className="bg-[#2f2f2f]">
                {n} steps
              </option>
            ))}
          </select>

          <button
            onClick={handleSubmit}
            disabled={!task.trim() || isRunning}
            className="w-8 h-8 rounded-full bg-white text-black flex items-center justify-center disabled:opacity-20 disabled:bg-[#676767] transition-all cursor-pointer"
          >
            {isRunning ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <ArrowUp className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useRef } from "react";
import type { SSEEvent } from "@/types";

/** Events that should NOT be shown in the log */
const HIDDEN_EVENTS = new Set(["connected", "heartbeat"]);

const AGENT_LABELS: Record<string, string> = {
  dispatcher: "Диспетчер",
  memory: "Кеш",
  source_map: "Карта источников",
  collectors: "Сборщики",
  validator: "Валидатор",
  error_handler: "Обработчик ошибок",
  analyst: "Аналитик",
  prioritizer: "Приоритизатор",
  passport_generator: "Паспорт",
  outreach_preparer: "Outreach",
  logger_agent: "Логгер",
  system: "Система",
};

const EVENT_ICONS: Record<string, string> = {
  agent_started: "▶",
  agent_completed: "✓",
  agent_failed: "✗",
  thinking: "…",
  pipeline_started: "🚀",
  pipeline_completed: "✅",
  pipeline_failed: "❌",
  pipeline_error: "❌",
  cache_hit: "💾",
  error: "⚠",
};

const EVENT_COLORS: Record<string, string> = {
  agent_started: "text-blue-400",
  agent_completed: "text-green-400",
  agent_failed: "text-red-400",
  thinking: "text-yellow-400",
  pipeline_started: "text-blue-300",
  pipeline_completed: "text-green-300",
  pipeline_failed: "text-red-400",
  pipeline_error: "text-red-400",
  cache_hit: "text-purple-400",
  error: "text-red-400",
};

function formatTime(ts: string | undefined): string {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

interface Props {
  events: SSEEvent[];
  isRunning: boolean;
}

export default function LiveLogsWindow({ events, isRunning }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const displayEvents = events.filter((ev) => !HIDDEN_EVENTS.has(ev.type));

  return (
    <div className="flex flex-col gap-0 rounded-xl border border-gray-800 bg-gray-900 font-mono text-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
        <span className="text-xs font-semibold uppercase tracking-widest text-gray-400">
          Лог агентов
        </span>
        {isRunning && (
          <span className="flex items-center gap-2 text-xs text-blue-400">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
            </span>
            в процессе
          </span>
        )}
      </div>

      {/* Log lines */}
      <div className="h-96 overflow-y-auto px-4 py-3 scrollbar-thin">
        {displayEvents.length === 0 ? (
          <p className="text-gray-500">Ожидание событий...</p>
        ) : (
          displayEvents.map((ev, i) => {
            const time = formatTime(ev.timestamp);
            const agent = ev.agent
              ? AGENT_LABELS[ev.agent] ?? ev.agent
              : "";
            return (
              <div key={i} className="mb-1 flex items-start gap-2">
                {time && (
                  <span className="mt-px shrink-0 text-gray-600">{time}</span>
                )}
                <span
                  className={`shrink-0 ${EVENT_COLORS[ev.type] ?? "text-gray-400"}`}
                >
                  {EVENT_ICONS[ev.type] ?? "·"}
                </span>
                {agent && (
                  <span className="shrink-0 text-gray-400">[{agent}]</span>
                )}
                <span className="text-gray-200">{ev.message}</span>
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

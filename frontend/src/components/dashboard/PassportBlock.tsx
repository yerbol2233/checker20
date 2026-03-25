"use client";

import { useState } from "react";
import type { PassportBlock as TPassportBlock } from "@/types";

interface Props {
  blockNum: number;
  title: string;
  block: TPassportBlock;
}

export default function PassportBlock({ blockNum, title, block }: Props) {
  const [open, setOpen] = useState(blockNum <= 3); // First 3 open by default

  const hasData = block.data != null;
  const confidencePct = Math.round((block.confidence ?? 0) * 100);
  const confidenceColor =
    confidencePct >= 70
      ? "text-green-400"
      : confidencePct >= 40
      ? "text-yellow-400"
      : "text-gray-500";

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900">
      {/* Accordion header */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
      >
        <div className="flex items-center gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-gray-800 text-xs font-bold text-gray-400">
            {blockNum}
          </span>
          <span className="font-medium text-gray-200">{title}</span>
          {!hasData && (
            <span className="rounded bg-gray-800 px-1.5 py-0.5 text-xs text-gray-500">
              нет данных
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {hasData && (
            <span className={`text-xs font-medium ${confidenceColor}`}>
              {confidencePct}%
            </span>
          )}
          <span className="text-gray-500 transition-transform duration-200" style={{ transform: open ? "rotate(180deg)" : undefined }}>
            ▾
          </span>
        </div>
      </button>

      {/* Accordion body */}
      {open && (
        <div className="border-t border-gray-800 px-5 py-4">
          {!hasData ? (
            <p className="text-sm text-gray-500">Данные не найдены</p>
          ) : (
            <DataRenderer data={block.data!} />
          )}

          {/* Sources */}
          {block.sources?.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {block.sources.map((src, i) => (
                <a
                  key={i}
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded border border-gray-700 px-2 py-0.5 text-xs text-gray-400 hover:border-gray-500 hover:text-gray-300"
                >
                  {src.source_name}
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Рекурсивный рендер данных
function DataRenderer({ data }: { data: unknown }) {
  if (data === null || data === undefined) {
    return <span className="text-gray-500">—</span>;
  }

  if (typeof data === "string") {
    if (data.startsWith("⚠️ Гипотеза:")) {
      return (
        <span className="inline-block rounded bg-yellow-900/30 px-2 py-0.5 text-xs text-yellow-300">
          {data}
        </span>
      );
    }
    if (data === "Данные не найдены") {
      return <span className="text-gray-500 text-sm">{data}</span>;
    }
    return <span className="text-sm text-gray-300">{data}</span>;
  }

  if (typeof data === "number" || typeof data === "boolean") {
    return <span className="text-sm text-blue-300">{String(data)}</span>;
  }

  if (Array.isArray(data)) {
    return (
      <ul className="space-y-1">
        {data.map((item, i) => (
          <li key={i} className="flex gap-2 text-sm">
            <span className="mt-1 shrink-0 text-gray-600">•</span>
            <DataRenderer data={item} />
          </li>
        ))}
      </ul>
    );
  }

  if (typeof data === "object") {
    const entries = Object.entries(data as Record<string, unknown>);
    return (
      <dl className="space-y-1.5">
        {entries.map(([key, value]) => (
          <div key={key} className="flex flex-wrap gap-1.5 text-sm">
            <dt className="shrink-0 font-medium text-gray-400">{key}:</dt>
            <dd className="text-gray-300">
              <DataRenderer data={value} />
            </dd>
          </div>
        ))}
      </dl>
    );
  }

  return <span className="text-sm text-gray-300">{String(data)}</span>;
}

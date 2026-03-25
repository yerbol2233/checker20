"use client";

import { useState } from "react";
import type { Outreach } from "@/types";

interface Props {
  outreach: Outreach;
}

const LPR_TYPE_LABELS: Record<string, string> = {
  creator: "Создатель контента",
  active_networker: "Активный нетворкер",
  quiet_pro: "Тихий профессионал",
  connector: "Коннектор",
};

const PATH_LABELS: Record<string, string> = {
  value: "Путь ценности",
  own: "Путь своего",
  curiosity: "Путь любопытства",
};

type Tab = "linkedin" | "warmup" | "followup" | "email";

export default function OutreachPanel({ outreach }: Props) {
  const [tab, setTab] = useState<Tab>("linkedin");
  const [copied, setCopied] = useState<string | null>(null);

  function copy(text: string, key: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(key);
      setTimeout(() => setCopied(null), 2000);
    });
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "linkedin", label: "LinkedIn DM" },
    { key: "warmup", label: "Warmup" },
    { key: "followup", label: "Follow-up" },
    { key: "email", label: "Email" },
  ];

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900">
      {/* Header */}
      <div className="border-b border-gray-800 px-5 py-4">
        <div className="mb-2 flex items-start justify-between">
          <h2 className="text-lg font-semibold text-gray-200">Outreach тексты</h2>
          <span className="rounded bg-blue-900/50 px-2 py-0.5 text-xs text-blue-300">
            English only
          </span>
        </div>
        <div className="flex flex-wrap gap-3 text-sm text-gray-400">
          <span>
            Тип ЛПР:{" "}
            <span className="text-gray-200">
              {LPR_TYPE_LABELS[outreach.lpr_type ?? ""] ?? outreach.lpr_type ?? "—"}
            </span>
          </span>
          <span>·</span>
          <span>
            Стратегия:{" "}
            <span className="text-gray-200">
              {PATH_LABELS[outreach.selected_path ?? ""] ?? outreach.selected_path ?? "—"}
            </span>
          </span>
        </div>
        {outreach.path_selection_rationale && (
          <p className="mt-2 text-xs text-gray-500">
            {outreach.path_selection_rationale}
          </p>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-800">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium transition ${
              tab === t.key
                ? "border-b-2 border-blue-500 text-blue-400"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="p-5">
        {tab === "linkedin" && (
          <div className="space-y-4">
            {(outreach.linkedin_messages ?? []).length === 0 ? (
              <p className="text-sm text-gray-500">Нет сообщений</p>
            ) : (
              outreach.linkedin_messages.map((msg, i) => (
                <div key={i} className="rounded-lg border border-gray-700 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-medium text-gray-400">
                      Вариант {msg.variant} · {msg.tone}
                    </span>
                    <button
                      onClick={() => copy(msg.message, `li-${i}`)}
                      className="text-xs text-gray-500 hover:text-gray-300"
                    >
                      {copied === `li-${i}` ? "Скопировано ✓" : "Копировать"}
                    </button>
                  </div>
                  <p className="whitespace-pre-wrap text-sm text-gray-200">
                    {msg.message}
                  </p>
                  {msg.hook_used && (
                    <p className="mt-2 text-xs text-gray-500">
                      Зацепка: {msg.hook_used}
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {tab === "warmup" && (
          <div className="space-y-3">
            {(outreach.warmup_comments ?? []).length === 0 ? (
              <p className="text-sm text-gray-500">Нет комментариев</p>
            ) : (
              outreach.warmup_comments.map((c, i) => (
                <div key={i} className="rounded-lg border border-gray-700 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs text-gray-500">{c.intent}</span>
                    <button
                      onClick={() => copy(c.comment_text, `wm-${i}`)}
                      className="text-xs text-gray-500 hover:text-gray-300"
                    >
                      {copied === `wm-${i}` ? "Скопировано ✓" : "Копировать"}
                    </button>
                  </div>
                  <p className="text-sm text-gray-200">{c.comment_text}</p>
                </div>
              ))
            )}
          </div>
        )}

        {tab === "followup" && (
          <div className="space-y-3">
            {outreach.followup_message ? (
              <div className="rounded-lg border border-gray-700 p-4">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs text-gray-500">
                    Угол: {outreach.followup_new_angle ?? "—"}
                  </span>
                  <button
                    onClick={() => copy(outreach.followup_message!, "fu")}
                    className="text-xs text-gray-500 hover:text-gray-300"
                  >
                    {copied === "fu" ? "Скопировано ✓" : "Копировать"}
                  </button>
                </div>
                <p className="whitespace-pre-wrap text-sm text-gray-200">
                  {outreach.followup_message}
                </p>
              </div>
            ) : (
              <p className="text-sm text-gray-500">Нет follow-up сообщения</p>
            )}
          </div>
        )}

        {tab === "email" && (
          <div className="space-y-3">
            {outreach.email_subject ? (
              <>
                <div className="rounded-lg border border-gray-700 p-4">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-xs text-gray-500">Тема письма</span>
                    <button
                      onClick={() => copy(outreach.email_subject!, "subj")}
                      className="text-xs text-gray-500 hover:text-gray-300"
                    >
                      {copied === "subj" ? "Скопировано ✓" : "Копировать"}
                    </button>
                  </div>
                  <p className="font-medium text-gray-200">{outreach.email_subject}</p>
                </div>
                <div className="rounded-lg border border-gray-700 p-4">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-xs text-gray-500">Тело письма</span>
                    <button
                      onClick={() => copy(outreach.email_body ?? "", "body")}
                      className="text-xs text-gray-500 hover:text-gray-300"
                    >
                      {copied === "body" ? "Скопировано ✓" : "Копировать"}
                    </button>
                  </div>
                  <p className="whitespace-pre-wrap text-sm text-gray-200">
                    {outreach.email_body}
                  </p>
                </div>
              </>
            ) : (
              <p className="text-sm text-gray-500">Нет email</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

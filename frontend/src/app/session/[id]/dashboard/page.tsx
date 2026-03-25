"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import PassportBlock from "@/components/dashboard/PassportBlock";
import OutreachPanel from "@/components/dashboard/OutreachPanel";
import AgentTimeline from "@/components/dashboard/AgentTimeline";
import CompletenessScale from "@/components/dashboard/CompletenessScale";
import SourcesUsed from "@/components/dashboard/SourcesUsed";
import TokenCostBadge from "@/components/dashboard/TokenCostBadge";
import FeedbackForm from "@/components/dashboard/FeedbackForm";
import type { DashboardData } from "@/types";

const BLOCK_TITLES: Record<string, string> = {
  "1_general": "Общий профиль",
  "2_sales_model": "Модель продаж",
  "3_pains": "Потенциальные боли",
  "4_people": "Ключевые люди",
  "5_context": "Контекст и зацепки",
  "6_competitors": "Конкурентная среда",
  "7_readiness": "Готовность к покупке",
  "8_reputation": "Репутация и отзывы",
  "9_triggers": "Триггеры входа",
  "10_lpr": "Профиль ЛПР",
  "11_industry": "Контекст отрасли",
};

export default function DashboardPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getDashboard(id)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="text-gray-400">Загрузка дашборда...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-3xl space-y-4 py-12 text-center">
        <h1 className="text-2xl font-bold text-red-400">Ошибка загрузки</h1>
        <p className="text-gray-400">{error ?? "Данные не найдены"}</p>
        <a
          href="/"
          className="inline-block rounded-lg bg-gray-800 px-6 py-2.5 text-sm font-semibold text-white hover:bg-gray-700"
        >
          На главную
        </a>
      </div>
    );
  }

  const { session, passport, outreach, agent_timeline, token_summary } = data;
  const company =
    session.resolved_company_name ??
    session.company_name ??
    session.website_url;

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <div className="mb-1 flex items-center gap-2 text-sm text-gray-400">
          <a href="/" className="hover:text-gray-200">Главная</a>
          <span>/</span>
          <a href={`/session/${session.id}`} className="hover:text-gray-200">
            Анализ
          </a>
          <span>/</span>
          <span>Дашборд</span>
        </div>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-white">{company}</h1>
            <p className="mt-1 text-gray-400">{session.website_url}</p>
          </div>
          <div className="flex flex-col items-end gap-1 text-right text-sm text-gray-400">
            <span>
              Статус:{" "}
              <span
                className={`font-medium ${
                  session.status === "completed"
                    ? "text-green-400"
                    : session.status === "failed"
                    ? "text-red-400"
                    : "text-yellow-400"
                }`}
              >
                {session.status}
              </span>
            </span>
            {session.duration_seconds && (
              <span>Время: {session.duration_seconds.toFixed(1)}с</span>
            )}
            {session.is_cached && (
              <span className="rounded bg-gray-800 px-1.5 py-0.5 text-xs text-gray-400">
                из кеша
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Completeness + Token cost */}
      <div className="grid gap-4 lg:grid-cols-2">
        <CompletenessScale session={session} />
        <TokenCostBadge summary={token_summary} />
      </div>

      {/* Top 3 hooks */}
      {passport?.top3_hooks && passport.top3_hooks.length > 0 && (
        <div className="rounded-xl border border-yellow-900/50 bg-yellow-950/20 p-5">
          <h2 className="mb-3 font-semibold text-yellow-300">
            Топ-3 зацепки для outreach
          </h2>
          <div className="space-y-3">
            {passport.top3_hooks.map((hook, i) => (
              <div key={i} className="flex gap-3 text-sm">
                <span className="mt-0.5 shrink-0 font-bold text-yellow-500">
                  #{hook.rank ?? i + 1}
                </span>
                <div>
                  <p className="text-gray-200">{hook.hook}</p>
                  {hook.rationale && (
                    <p className="mt-0.5 text-xs text-gray-500">{hook.rationale}</p>
                  )}
                  <div className="mt-1 flex gap-3 text-xs text-gray-500">
                    <span>Блок {hook.source_block}</span>
                    <span>Свежесть: {hook.freshness_days} дн.</span>
                    {hook.score && (
                      <span>Оценка: {(hook.score * 100).toFixed(0)}%</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Passport 11 blocks */}
      {passport ? (
        <section>
          <h2 className="mb-4 text-xl font-bold text-gray-200">
            Паспорт компании
          </h2>
          <div className="space-y-3">
            {Object.entries(passport.blocks).map(([key, block]) => {
              const num = parseInt(key.split("_")[0]);
              return (
                <PassportBlock
                  key={key}
                  blockNum={num}
                  title={BLOCK_TITLES[key] ?? key}
                  block={block}
                />
              );
            })}
          </div>
        </section>
      ) : (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-6 text-center text-gray-500">
          Паспорт не сгенерирован
        </div>
      )}

      {/* Outreach panel */}
      {outreach ? (
        <section>
          <h2 className="mb-4 text-xl font-bold text-gray-200">Outreach</h2>
          <OutreachPanel outreach={outreach} />
        </section>
      ) : (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-6 text-center text-gray-500">
          Outreach не сгенерирован
        </div>
      )}

      {/* Sources used */}
      {passport && (
        <section>
          <h2 className="mb-4 text-xl font-bold text-gray-200">
            Использованные источники
          </h2>
          <SourcesUsed passport={passport} />
        </section>
      )}

      {/* Agent timeline */}
      {agent_timeline.length > 0 && (
        <section>
          <h2 className="mb-4 text-xl font-bold text-gray-200">
            Хронология пайплайна
          </h2>
          <AgentTimeline logs={agent_timeline} />
        </section>
      )}

      {/* Feedback */}
      <section>
        <FeedbackForm sessionId={session.id} />
      </section>
    </div>
  );
}


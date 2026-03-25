"use client";

import { useState } from "react";
import { api } from "@/lib/api";

interface Props {
  sessionId: string;
}

type Result = "useful" | "not_useful" | "partial";

export default function FeedbackForm({ sessionId }: Props) {
  const [result, setResult] = useState<Result | null>(null);
  const [notes, setNotes] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!result) return;
    setLoading(true);
    try {
      await api.submitFeedback(sessionId, {
        result,
        passport_useful: result !== "not_useful",
        best_hook: null,
        message_strategy: null,
        notes: notes || null,
      });
      setSubmitted(true);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  if (submitted) {
    return (
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5 text-center">
        <p className="text-green-400">Спасибо за обратную связь!</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <h3 className="mb-4 font-semibold text-gray-200">Обратная связь</h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <p className="mb-2 text-sm text-gray-400">Насколько полезен результат?</p>
          <div className="flex gap-2">
            {(
              [
                { value: "useful", label: "Полезен" },
                { value: "partial", label: "Частично" },
                { value: "not_useful", label: "Не полезен" },
              ] as { value: Result; label: string }[]
            ).map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setResult(opt.value)}
                className={`rounded-lg border px-3 py-1.5 text-sm transition ${
                  result === opt.value
                    ? "border-blue-500 bg-blue-900/40 text-blue-300"
                    : "border-gray-700 text-gray-400 hover:border-gray-500"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-sm text-gray-400">
            Комментарий (необязательно)
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            placeholder="Что можно улучшить?"
            className="w-full resize-none rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 placeholder-gray-500 outline-none focus:border-blue-500"
          />
        </div>

        <button
          type="submit"
          disabled={!result || loading}
          className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-300 transition hover:border-gray-500 disabled:opacity-40"
        >
          {loading ? "Отправка..." : "Отправить отзыв"}
        </button>
      </form>
    </div>
  );
}

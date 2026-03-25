"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function InputForm() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const fd = new FormData(e.currentTarget);
    const website_url = (fd.get("website_url") as string).trim();
    const linkedin_lpr_url = (fd.get("linkedin_lpr_url") as string).trim() || undefined;
    const company_name = (fd.get("company_name") as string).trim() || undefined;

    try {
      const session = await api.createSession({ website_url, linkedin_lpr_url, company_name });
      router.push(`/session/${session.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Произошла ошибка");
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Website URL */}
      <div>
        <label className="mb-1.5 block text-sm font-medium text-gray-300">
          Сайт компании <span className="text-red-400">*</span>
        </label>
        <input
          name="website_url"
          type="text"
          required
          placeholder="https://example.com"
          className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2.5 text-sm text-gray-100 placeholder-gray-500 outline-none ring-0 transition focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* LinkedIn LPR */}
      <div>
        <label className="mb-1.5 block text-sm font-medium text-gray-300">
          LinkedIn ЛПР{" "}
          <span className="text-xs text-gray-500">(необязательно)</span>
        </label>
        <input
          name="linkedin_lpr_url"
          type="text"
          placeholder="https://linkedin.com/in/..."
          className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2.5 text-sm text-gray-100 placeholder-gray-500 outline-none ring-0 transition focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* Company name */}
      <div>
        <label className="mb-1.5 block text-sm font-medium text-gray-300">
          Название компании{" "}
          <span className="text-xs text-gray-500">(если известно)</span>
        </label>
        <input
          name="company_name"
          type="text"
          placeholder="Acme Corp"
          className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2.5 text-sm text-gray-100 placeholder-gray-500 outline-none ring-0 transition focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {error && (
        <p className="rounded-lg border border-red-800 bg-red-950/50 px-4 py-2.5 text-sm text-red-400">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Запуск анализа..." : "Анализировать компанию"}
      </button>

      <p className="text-center text-xs text-gray-500">
        Анализ занимает 2–5 минут. Вы будете перенаправлены на страницу с логами.
      </p>
    </form>
  );
}

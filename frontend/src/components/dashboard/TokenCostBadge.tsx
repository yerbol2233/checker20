import type { TokenSummary } from "@/types";

interface Props {
  summary: TokenSummary;
}

const PROVIDER_LABELS: Record<string, string> = {
  claude: "Claude",
  gemini: "Gemini",
  openai: "GPT",
};

export default function TokenCostBadge({ summary }: Props) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <h3 className="mb-3 font-semibold text-gray-200">Расход токенов</h3>

      <div className="mb-4 flex items-baseline gap-2">
        <span className="text-2xl font-bold text-white">
          ${summary.total_cost_usd.toFixed(4)}
        </span>
        <span className="text-sm text-gray-400">
          {summary.total_tokens.toLocaleString("ru-RU")} токенов
        </span>
      </div>

      <div className="space-y-2">
        {Object.entries(summary.by_provider).map(([provider, stats]) => (
          <div key={provider} className="flex items-center justify-between text-sm">
            <span className="text-gray-400">
              {PROVIDER_LABELS[provider] ?? provider}
            </span>
            <div className="flex gap-4 text-right">
              <span className="text-gray-400">{stats.calls} вызовов</span>
              <span className="w-20 text-gray-300">
                {stats.tokens.toLocaleString("ru-RU")} токенов
              </span>
              <span className="w-16 font-medium text-white">
                ${stats.cost_usd.toFixed(4)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

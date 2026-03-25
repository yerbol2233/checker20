import type { Session } from "@/types";

interface Props {
  session: Session;
}

export default function CompletenessScale({ session }: Props) {
  const score = session.completeness_score ?? 0;
  const isReady = session.completeness_status === "ready";

  const color =
    score >= 70 ? "bg-green-500" : score >= 40 ? "bg-yellow-500" : "bg-red-500";
  const label =
    score >= 70 ? "Высокая полнота" : score >= 40 ? "Средняя полнота" : "Низкая полнота";

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-semibold text-gray-200">Полнота паспорта</h3>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
            isReady
              ? "bg-green-900/60 text-green-400"
              : "bg-yellow-900/60 text-yellow-400"
          }`}
        >
          {isReady ? "Готов к работе" : "Неполный"}
        </span>
      </div>

      {/* Progress bar */}
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-gray-400">{label}</span>
        <span className="font-semibold text-white">{score}/100</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-800">
        <div
          className={`h-2 rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${score}%` }}
        />
      </div>

      {/* Reasons */}
      {session.incompleteness_reasons?.length > 0 && (
        <ul className="mt-3 space-y-1">
          {session.incompleteness_reasons.map((r, i) => (
            <li key={i} className="flex items-center gap-2 text-xs text-gray-400">
              <span className="text-yellow-500">⚠</span>
              {r.reason}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

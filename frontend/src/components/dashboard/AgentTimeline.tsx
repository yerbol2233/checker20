import type { AgentLogEntry } from "@/types";

interface Props {
  logs: AgentLogEntry[];
}

const AGENT_LABELS: Record<string, string> = {
  dispatcher: "Диспетчер",
  memory: "Кеш",
  source_map: "Карта источников",
  collectors: "Сборщики данных",
  validator: "Валидатор",
  error_handler: "Обработчик ошибок",
  analyst_pains: "Анализ болей",
  analyst_triggers: "Триггеры",
  analyst_competitors: "Конкуренты",
  analyst_industry: "Отрасль",
  analyst_lpr: "ЛПР",
  analyst_sales_model: "Модель продаж",
  prioritizer: "Приоритизатор",
  passport_generator: "Паспорт",
  outreach_warmup: "Warmup комментарии",
  outreach_linkedin: "LinkedIn сообщения",
  outreach_followup: "Follow-up",
  outreach_email: "Email",
  outreach_preparer: "Outreach",
};

export default function AgentTimeline({ logs }: Props) {
  if (logs.length === 0) return null;

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <h3 className="mb-4 font-semibold text-gray-200">Хронология агентов</h3>
      <div className="relative space-y-3 pl-6 before:absolute before:left-2 before:top-1 before:h-full before:w-px before:bg-gray-800">
        {logs.map((log) => (
          <div key={log.id} className="relative">
            <div
              className={`absolute -left-4 mt-1.5 h-2.5 w-2.5 rounded-full border-2 ${
                log.is_error
                  ? "border-red-500 bg-red-900"
                  : "border-blue-500 bg-blue-900"
              }`}
            />
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="text-sm font-medium text-gray-300">
                {AGENT_LABELS[log.agent_name] ?? log.agent_name}
              </span>
              <span className="text-xs text-gray-500">{log.event_type}</span>
              {log.duration_ms != null && (
                <span className="text-xs text-gray-600">
                  {log.duration_ms}мс
                </span>
              )}
            </div>
            <p className="text-xs text-gray-400">{log.message}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

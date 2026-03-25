import InputForm from "@/components/InputForm";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-lg">
      <div className="mb-8 text-center">
        <h1 className="mb-2 text-3xl font-bold tracking-tight text-white">
          Анализ компании
        </h1>
        <p className="text-gray-400">
          Введите сайт компании — получите паспорт из 11 блоков и готовые
          outreach-тексты
        </p>
      </div>

      <div className="rounded-2xl border border-gray-800 bg-gray-900 p-6">
        <InputForm />
      </div>

      <div className="mt-6 grid grid-cols-3 gap-4 text-center text-xs text-gray-500">
        <div className="rounded-lg border border-gray-800 p-3">
          <div className="text-base font-semibold text-gray-300">11 блоков</div>
          <div>паспорт компании</div>
        </div>
        <div className="rounded-lg border border-gray-800 p-3">
          <div className="text-base font-semibold text-gray-300">19 источников</div>
          <div>данных и сигналов</div>
        </div>
        <div className="rounded-lg border border-gray-800 p-3">
          <div className="text-base font-semibold text-gray-300">2–5 мин</div>
          <div>полный анализ</div>
        </div>
      </div>
    </div>
  );
}

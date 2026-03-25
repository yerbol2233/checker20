import type { Passport } from "@/types";

interface Props {
  passport: Passport;
}

export default function SourcesUsed({ passport }: Props) {
  // Collect unique sources across all blocks
  const sourceMap = new Map<
    string,
    { url: string; confidence: number; blocks: number[] }
  >();

  Object.entries(passport.blocks).forEach(([blockKey, block]) => {
    const blockNum = parseInt(blockKey.split("_")[0]);
    block.sources?.forEach((src) => {
      const existing = sourceMap.get(src.source_name);
      if (existing) {
        existing.blocks.push(blockNum);
      } else {
        sourceMap.set(src.source_name, {
          url: src.url,
          confidence: src.confidence,
          blocks: [blockNum],
        });
      }
    });
  });

  const sources = Array.from(sourceMap.entries()).sort(
    (a, b) => b[1].confidence - a[1].confidence
  );

  if (sources.length === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <h3 className="mb-3 font-semibold text-gray-200">
        Источники ({sources.length})
      </h3>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {sources.map(([name, info]) => (
          <div
            key={name}
            className="flex items-center gap-2 rounded-lg border border-gray-800 px-3 py-2 text-xs"
          >
            <span
              className={`h-2 w-2 shrink-0 rounded-full ${
                info.confidence >= 0.7
                  ? "bg-green-500"
                  : info.confidence >= 0.4
                  ? "bg-yellow-500"
                  : "bg-gray-500"
              }`}
            />
            <div className="min-w-0">
              <div className="truncate font-medium text-gray-300">{name}</div>
              <div className="text-gray-500">
                Блоки: {info.blocks.slice(0, 4).join(", ")}
                {info.blocks.length > 4 ? "…" : ""}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

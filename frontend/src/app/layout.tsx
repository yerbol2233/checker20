import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CIA — Company Intelligence Agent",
  description: "B2B разведка компаний: паспорт + outreach за минуты",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body className="min-h-screen bg-gray-950 text-gray-100">
        <header className="border-b border-gray-800 px-6 py-4">
          <div className="mx-auto max-w-6xl flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded bg-blue-600 text-sm font-bold text-white">
              CIA
            </div>
            <span className="text-lg font-semibold tracking-tight">
              Company Intelligence Agent
            </span>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}

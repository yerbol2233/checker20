"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import LiveLogsWindow from "@/components/LiveLogsWindow";
import { api } from "@/lib/api";
import type { SSEEvent, Session } from "@/types";

export default function ProcessingPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [isRunning, setIsRunning] = useState(true);
  const [failed, setFailed] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Redirect to dashboard
  const goToDashboard = useCallback(() => {
    setTimeout(() => router.push(`/session/${id}/dashboard`), 1500);
  }, [id, router]);

  // Load session info
  useEffect(() => {
    api.getSession(id).then((s) => {
      setSession(s);
      // If already completed — redirect immediately
      if (s.status === "completed" || s.status === "cached") {
        setIsRunning(false);
        goToDashboard();
      } else if (s.status === "failed") {
        setIsRunning(false);
        setFailed(true);
      }
    }).catch(console.error);
  }, [id, goToDashboard]);

  // Connect SSE stream
  useEffect(() => {
    const url = api.streamUrl(id);
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const event: SSEEvent = JSON.parse(e.data);
        if (event.type === "heartbeat") return; // skip heartbeats

        setEvents((prev) => [...prev, event]);

        if (event.type === "pipeline_completed") {
          setIsRunning(false);
          es.close();
          goToDashboard();
        }

        if (event.type === "pipeline_failed") {
          setIsRunning(false);
          setFailed(true);
          es.close();
        }
      } catch {
        // non-JSON, ignore
      }
    };

    es.onerror = () => {
      // SSE disconnected — start polling as fallback
      es.close();
      if (!pollRef.current) {
        pollRef.current = setInterval(async () => {
          try {
            const s = await api.getSession(id);
            setSession(s);
            if (s.status === "completed" || s.status === "cached") {
              setIsRunning(false);
              clearInterval(pollRef.current!);
              pollRef.current = null;
              goToDashboard();
            } else if (s.status === "failed") {
              setIsRunning(false);
              setFailed(true);
              clearInterval(pollRef.current!);
              pollRef.current = null;
            }
          } catch {
            // ignore polling errors
          }
        }, 3000);
      }
    };

    return () => {
      es.close();
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [id, goToDashboard]);

  const company = session?.resolved_company_name ?? session?.company_name ?? session?.website_url ?? "Компания";

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div>
        <div className="mb-1 flex items-center gap-2 text-sm text-gray-400">
          <a href="/" className="hover:text-gray-200">Главная</a>
          <span>/</span>
          <span>Анализ</span>
        </div>
        <h1 className="text-2xl font-bold text-white">{company}</h1>
        {session?.website_url && (
          <p className="text-sm text-gray-400">{session.website_url}</p>
        )}
      </div>

      {/* Status banner */}
      {failed ? (
        <div className="rounded-xl border border-red-800 bg-red-950/40 p-4 text-red-400">
          Анализ завершился с ошибкой. Попробуйте снова или проверьте URL.
        </div>
      ) : !isRunning && events.some((e) => e.type === "pipeline_completed") ? (
        <div className="rounded-xl border border-green-800 bg-green-950/40 p-4 text-green-400">
          Анализ завершён. Переход на дашборд...
        </div>
      ) : (
        <div className="rounded-xl border border-blue-900 bg-blue-950/30 p-4">
          <p className="text-sm text-blue-300">
            Идёт сбор и анализ данных. Не закрывайте страницу.
          </p>
        </div>
      )}

      {/* Live logs */}
      <LiveLogsWindow events={events} isRunning={isRunning} />

      {/* Manual navigation */}
      {!isRunning && !failed && (
        <div className="text-center">
          <button
            onClick={() => router.push(`/session/${id}/dashboard`)}
            className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-500"
          >
            Перейти на дашборд
          </button>
        </div>
      )}
    </div>
  );
}


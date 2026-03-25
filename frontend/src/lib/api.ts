import type {
  Session,
  DashboardData,
  SessionCreateRequest,
  FeedbackRequest,
} from "@/types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  /** POST /api/sessions — создать новую сессию анализа */
  createSession(data: SessionCreateRequest): Promise<Session> {
    return apiFetch<Session>("/sessions", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /** GET /api/sessions/{id} — статус сессии */
  getSession(id: string): Promise<Session> {
    return apiFetch<Session>(`/sessions/${id}`);
  },

  /** GET /api/sessions/{id}/dashboard — полный дашборд */
  getDashboard(id: string): Promise<DashboardData> {
    return apiFetch<DashboardData>(`/sessions/${id}/dashboard`);
  },

  /** POST /api/sessions/{id}/feedback — отправить обратную связь */
  submitFeedback(id: string, data: FeedbackRequest): Promise<unknown> {
    return apiFetch(`/sessions/${id}/feedback`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /** URL для SSE-стрима (используется с EventSource) */
  streamUrl(id: string): string {
    return `${API_BASE}/api/sessions/${id}/stream`;
  },
};

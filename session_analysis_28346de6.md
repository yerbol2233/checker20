# Анализ сессии 28346de6 (JB Warranties)

## 1. Список отсутствующих данных

Ниже перечислены поля, которые остались незаполненными («Данные не найдены» или null) для компании **JB Warranties** (сайт: jbwarranties.com):

### Блок 1: Общий профиль
- [ ] **Штаб-квартира (headquarters)**: Пусто.
- [ ] **Раунды финансирования (funding_rounds)**: Пусто.
- [ ] **Количество сотрудников (employees_count)**: Пусто.
- [ ] **Оценка выручки (revenue_estimate)**: Пусто.
- [ ] **Соцсети (Twitter/LinkedIn followers)**: Пусто.

### Блок 4: Ключевые люди
- [ ] **Основатели (founders)**: Пусто.
- [ ] **Ключевые руководители (key_executives)**: Пусто.
- [ ] **Лица, принимающие решения (decision_makers)**: Пусто.
- [ ] **Сигналы о найме (hiring_signals)**: Пусто.

### Блок 5: Контекст и инфоповоды
- [ ] **Последние новости (recent_news)**: Пусто.
- [ ] **Посты компании (company_posts)**: Пусто.
- [ ] **Значимые события (notable_events)**: Пусто.

### Блок 6: Конкурентная среда
- [ ] **Прямые конкуренты (direct_competitors)**: Пусто.
- [ ] **Непрямые конкуренты (indirect_competitors)**: Пусто.
- [ ] **Позиция на рынке (market_position)**: Пусто.

### Блок 10: Профиль ЛПР
- [ ] **LPR Profile**: Весь блок пуст (null). Это критическая точка, так как не был найден или обработан профиль целевого лица.

### Блок 11: Отраслевой контекст
- [ ] **Размер рынка (market_size)**: Пусто.

---

## 2. Пути к логам пайплайна

Для детальной диагностики этой сессии нужно смотреть логи внутри контейнеров (или в volume `backend_logs`):

1.  **Лог приложения**: `/app/logs/app.log` (общая координация).
2.  **Лог LLM**: `/app/logs/llm.log` (запросы к Gemini/Claude и их ответы).
3.  **Лог скрапинга**: `/app/logs/scraping.log` (результаты поиска в DuckDuckGo, Reddit и т.д.).
4.  **Лог воркеров**: `docker compose logs -f celery_worker` (процесс выполнения задач).

---

## 3. Источники данных и процесс обработки

### Список источников (Sources)
Система использует многослойный сбор:
- **Поисковики**: DuckDuckGo (основной fallback).
- **Спец. сервисы**: Crunchbase, SimilarWeb (трафик), Apollo (если настроен).
- **Соцсети**: LinkedIn (компания/персоны), Twitter, Reddit (боли).
- **Отзывы**: Google Reviews, Trustpilot, G2, Capterra.
- **Прямой скрапинг**: Анализ текста главной страницы и страницы "About Us" сайта компании.

### Процесс обработки (Processing Flow)
1.  **Discovery (SourceMapAgent)**: На основе URL сайта определяет нишу и формирует план сбора (какие сайты искать).
2.  **Collection (Celery Workers)**: Запускает параллельные задачи. Каждый коллектор (например, `DuckDuckGoCollector`) делает 5-10 запросов.
3.  **Synthesis (AnalystAgent)**: Собирает «сырые» данные из всех источников и просит LLM структурировать их по 11 блокам.
4.  **Formatting (PassportGenerator)**: Финализирует JSON, добавляет ссылки на источники и считает индекс доверия (confidence score).
5.  **Streaming**: Результаты по кусочкам отправляются во фронтенд через SSE (Server-Sent Events).


## Анализ логов

CIA Stabilization Walkthrough
We have successfully stabilized the Company Intelligence Agent (CIA) pipeline, resolving critical issues in both the backend orchestration and the frontend real-time display.

Key Fixes & Improvements
1. Backend: SSE Streaming & Stability
SSE Delivery: Removed named event types (e.g., event: agent_started) in favor of unnamed data: messages. This ensures compatibility with the frontend's EventSource.onmessage handler.
Asyncio Loop Safety: Implemented NullPool for the SQLAlchemy engine in the Celery worker. This prevents "Future attached to a different loop" errors by ensuring fresh database connections for every task, regardless of loop transitions.
Model Upgrade: Replaced deprecated gemini-2.0-flash with gemini-2.5-flash to resolve 404 errors from the Google Generative AI API.
2. Frontend: Dashboard & Real-time UI
Dashboard 404: Converted the Dashboard from a Server Component to a Client Component. This resolves DNS issues where the server-side fetch tried to reach localhost:8000 inside the Docker container (where the backend is not on localhost).
Live Logs Reliability: Updated the log window to filter out system events (connected, heartbeat) and safely handle missing timestamps, resolving the "Invalid Date" and empty log line issues.
SSE Fallback: Added a polling fallback (every 3 seconds) to the session page to ensure the user is redirected to the dashboard even if the SSE connection drops.
3. Pipeline Performance
Cache Hits: Optimized the cache-hit path to generate fresh outreach even when using a cached passport, ensuring the AI responses are always relevant.
Dispatcher Alignment: Refactored the 
DispatcherAgent
 to match the actual collector and agent method signatures, preventing runtime TypeError and missing argument crashes.
4. Deployment & Version Control
GitHub: The stabilized code has been pushed to yerbol2233/checker20.git.
Docker: Environment is optimized for production-like execution with all necessary healthchecks and environment variables.
Verification Results
End-to-End Pipeline Test
Triggered Session (Stripe): Recognized as cached. Successful fresh outreach generation in ~8 seconds.
Triggered Session (Linear): Full 12-step pipeline execution. Completed successfully in ~140 seconds with completeness: ready.
Both sessions were executed sequentially in the same Celery worker process, verifying that the NullPool fix correctly handles event loop transitions.

Current System State
 Backend API: Online (Port 8000)
 Celery Worker: Stable (NullPool active)
 Frontend: Functional (Port 3000)
 SSE Stream: Live
 Dashboard: Accessible
Troubleshooting & Logs
If data is missing (e.g., "Данные не найдены"), check the following log locations:

Collective Logs (Backend): /app/logs/app.log (internal container path)
Scraping Details: /app/logs/scraping.log (shows DuckDuckGo, Reddit, etc. results)
LLM Full Context: /app/logs/llm.log (raw prompts and model responses)
Worker Execution: docker compose logs -f celery_worker
Data Sources & Processing
The CIA system uses a multi-layered approach to ensure data coverage:

1. Data Sources
Primary: Website analysis, LinkedIn (Company/Person), Crunchbase.
Secondary: Reddit (for pains/hooks), SimilarWeb (for traffic/niche).
Fallback: DuckDuckGo (targeted queries for founders, competitors, and LPRs).
Reviews: Google Reviews, Trustpilot.
2. Processing Pipeline
Source Mapping: Analyzes the domain to determine the industry and specific search queries.
Parallel Collection: Parallelized tasks via Celery gather snippets from all sources.
Synthesis: 
AnalystAgent
 merges data into 11 thematic blocks.
JSON Repair: If an LLM response is truncated, json_repair recovers partial data to prevent dashboard crashes.
Output: Results are streamed via SSE and persisted to PostgreSQL.
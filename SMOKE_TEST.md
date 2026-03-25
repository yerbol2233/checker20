# CIA — Smoke Test

Пошаговая инструкция для проверки системы end-to-end.

## Предварительные требования

1. Docker и Docker Compose установлены
2. `.env` файл создан на основе `.env.example` с реальными API ключами:
   - `ANTHROPIC_API_KEY` — обязательно
   - `GOOGLE_API_KEY` — обязательно
   - `SCRAPEOPS_API_KEY` — обязательно
   - `OPENAI_API_KEY` — опционально (fallback)

## 1. Запуск инфраструктуры

```bash
cd cia-system

# Скопировать .env.example → .env и заполнить ключи
cp .env.example .env
# ... отредактировать .env ...

# Запустить все сервисы
docker compose up -d --build

# Проверить что все контейнеры запустились
docker compose ps
```

Ожидаемый результат — 6 контейнеров (postgres, redis, backend, celery_worker, celery_beat, frontend), все в статусе `Up (healthy)`.

## 2. Применить миграции БД

```bash
docker compose exec backend alembic upgrade head
```

Ожидаемый результат: таблицы `sessions`, `passports`, `outreach_texts`, `feedback`, `agent_logs`, `token_logs`, `company_cache` созданы.

## 3. Проверить health-эндпоинт

```bash
curl http://localhost:8000/health
```

Ожидаемый ответ:
```json
{"status": "ok", "service": "cia-backend", "database": "ok", "redis": "ok"}
```

## 4. Проверить frontend

Открыть в браузере: http://localhost:3000

Ожидаемый результат: Input Page с формой (URL сайта + LinkedIn ЛПР + Название компании).

## 5. Smoke test пайплайна

### Через UI:
1. На http://localhost:3000 ввести:
   - **URL сайта**: `https://stripe.com` (или любой реальный B2B-сайт)
   - **LinkedIn ЛПР**: оставить пустым (опционально)
   - **Название компании**: `Stripe` (опционально)
2. Нажать «Запустить анализ»
3. На Processing Page наблюдать SSE-логи в реальном времени
4. Через 2-5 минут → автоматический редирект на Dashboard
5. На Dashboard проверить:
   - 11 блоков паспорта (русский язык)
   - Outreach тексты (английский язык)
   - Шкала полноты
   - Топ-3 зацепки

### Через API (curl):
```bash
# Создать сессию
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"website_url": "https://stripe.com", "company_name": "Stripe"}'

# Ответ: {"session_id": "UUID", "status": "running", ...}
# Запомнить SESSION_ID

# Проверить статус
curl http://localhost:8000/api/sessions/{SESSION_ID}

# Получить результат (после завершения)
curl http://localhost:8000/api/sessions/{SESSION_ID}/dashboard
```

## 6. Проверить логи

```bash
# Общий лог
docker compose exec backend cat /app/logs/app.log | tail -20

# Лог скрапинга
docker compose exec backend cat /app/logs/scraping.log | tail -20

# Лог LLM
docker compose exec backend cat /app/logs/llm.log | tail -20

# CSV расходов
docker compose exec backend cat /app/logs/token_costs.csv
```

## 7. Проверить кеш (повторный запуск)

Запустить тот же сайт повторно → должен сработать кеш (`"status": "cached"`), но outreach сгенерироваться заново.

## Критерий успеха

✅ **Полный smoke test пройден**, если:
- Ввод URL → паспорт за < 5 минут
- 11 блоков паспорта на русском
- Outreach тексты на английском
- SSE-логи отображаются в реальном времени
- Логи пишутся в файлы (app.log, scraping.log, llm.log, token_costs.csv)
- Повторный запуск → кеш-хит + свежий outreach

## Устранение неполадок

| Ошибка | Решение |
|--------|---------|
| `database: error` в /health | Проверить `DATABASE_URL` в `.env`, `docker compose logs postgres` |
| `redis: error` в /health | `docker compose logs redis` |
| Pipeline timeout | Увеличить `time_limit` в `pipeline_task.py` или проверить API ключи |
| Frontend не загружается | `docker compose logs frontend`, проверить `NEXT_PUBLIC_API_URL` |
| Celery не стартует | `docker compose logs celery_worker` |

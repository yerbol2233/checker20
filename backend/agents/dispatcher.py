"""
DispatcherAgent — оркестратор полного пайплайна CIA.

12 шагов: кеш → карта источников → сбор → валидация → ошибки →
анализ → приоритизация → паспорт → outreach → БД → кеш → SSE.
"""
import asyncio
import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ── Маппинг имя коллектора → класс ──────────────────────────────────────
def _get_collector_map() -> dict:
    from collectors import (
        WebsiteCollector, DuckDuckGoCollector, LinkedInCompanyCollector,
        LinkedInPersonCollector, GlassdoorCollector, CrunchbaseCollector,
        TwitterCollector, G2Collector, CapterraCollector, TrustpilotCollector,
        YelpCollector, GoogleReviewsCollector, IndeedCollector,
        SimilarWebCollector, BuiltWithCollector, SECEdgarCollector,
        YouTubeCollector, ApolloCollector, RedditCollector,
    )
    return {
        "website": WebsiteCollector,
        "duckduckgo": DuckDuckGoCollector,
        "linkedin_company": LinkedInCompanyCollector,
        "linkedin_person": LinkedInPersonCollector,
        "glassdoor": GlassdoorCollector,
        "crunchbase": CrunchbaseCollector,
        "twitter": TwitterCollector,
        "g2": G2Collector,
        "capterra": CapterraCollector,
        "trustpilot": TrustpilotCollector,
        "yelp": YelpCollector,
        "google_reviews": GoogleReviewsCollector,
        "indeed": IndeedCollector,
        "similarweb": SimilarWebCollector,
        "builtwith": BuiltWithCollector,
        "sec_edgar": SECEdgarCollector,
        "youtube": YouTubeCollector,
        "apollo": ApolloCollector,
        "reddit": RedditCollector,
    }


class DispatcherAgent:
    """Главный оркестратор пайплайна CIA."""

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._logger_agent = None

    def _get_logger_agent(self, session_id: str):
        if self._logger_agent is None:
            from agents.logger_agent import LoggerAgent
            self._logger_agent = LoggerAgent(session_id)
        return self._logger_agent

    async def _publish_sse(self, session_id: str, event: dict):
        if self._redis is None:
            return
        channel = f"sse:session:{session_id}"
        try:
            await self._redis.publish(channel, json.dumps(event, default=str))
        except Exception as exc:
            logger.warning(f"SSE publish failed: {exc}")

    async def _emit(
        self, session_id: str, event_type: str, agent: str,
        message: str, data: Optional[dict] = None,
    ):
        event = {
            "type": event_type,
            "agent": agent,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if data:
            event["data"] = data
        await self._publish_sse(session_id, event)

    # ── Основная точка входа ─────────────────────────────────────────────

    async def run(self, session_id: str, context: dict) -> dict:
        website_url = (context.get("website_url") or "").strip()
        if not website_url:
            return {"status": "failed", "error": "website_url is required"}

        if not website_url.startswith(("http://", "https://")):
            website_url = f"https://{website_url}"
            context["website_url"] = website_url

        start_time = datetime.now(timezone.utc)
        log = self._get_logger_agent(session_id)

        await self._update_session_status(session_id, "running", start_time)
        await self._emit(session_id, "pipeline_started", "dispatcher",
                         "Pipeline started")

        try:
            result = await self._execute_pipeline(session_id, context, log)
        except asyncio.CancelledError:
            logger.warning(f"Pipeline cancelled for session {session_id}")
            await self._update_session_status(session_id, "failed")
            await self._emit(session_id, "pipeline_error", "dispatcher",
                             "Pipeline cancelled (timeout)")
            return {"status": "failed", "error": "Pipeline cancelled (timeout)"}
        except Exception as exc:
            logger.error(f"Pipeline failed: {exc}", exc_info=True)
            await self._update_session_status(session_id, "failed")
            await self._emit(session_id, "pipeline_error", "dispatcher",
                             f"Pipeline failed: {exc}")
            await log.log_event("dispatcher", "pipeline_error", str(exc),
                                details={"traceback": traceback.format_exc()},
                                is_error=True)
            return {"status": "failed", "error": str(exc)}

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        await self._emit(session_id, "pipeline_completed", "dispatcher",
                         f"Pipeline completed in {duration:.1f}s",
                         {"duration_seconds": duration})
        await log.finalize_session()
        return result

    # ── 12-шаговый пайплайн ──────────────────────────────────────────────

    async def _execute_pipeline(self, session_id: str, context: dict, log) -> dict:

        # ── Шаг 1: Кеш ──────────────────────────────────────────────────
        await self._emit(session_id, "agent_started", "memory", "Checking cache")
        from agents.memory import MemoryAgent
        memory = MemoryAgent()
        domain = self._extract_domain(context.get("website_url", ""))
        try:
            cached = await memory.check_cache(domain)
        except Exception as exc:
            logger.warning(f"Cache check failed (non-critical): {exc}")
            cached = None

        if cached:
            await self._emit(session_id, "cache_hit", "memory",
                             "Cache hit — using cached passport, generating fresh outreach")
            return await self._handle_cache_hit(session_id, context, cached, memory, log)

        await self._emit(session_id, "agent_completed", "memory", "No cache found")

        # ── Шаг 2: Карта источников ──────────────────────────────────────
        await self._emit(session_id, "agent_started", "source_map",
                         "Building collection plan")
        try:
            from agents.source_map import SourceMapAgent
            source_map = SourceMapAgent()
            plan = await source_map.build_collection_plan(
                website_url=context.get("website_url", ""),
                company_name=context.get("company_name"),
                linkedin_lpr_url=context.get("linkedin_lpr_url"),
                session_id=session_id,
            )
            # Обновляем context из плана
            context.update(plan.context)
            await self._emit(session_id, "agent_completed", "source_map",
                             f"Plan: {len(plan.collectors)} collectors, niche: {plan.niche}",
                             {"collectors": plan.collectors, "niche": plan.niche})
        except Exception as exc:
            logger.error(f"SourceMap failed: {exc}", exc_info=True)
            await self._emit(session_id, "agent_failed", "source_map",
                             f"Source map failed: {exc}")
            raise

        # ── Шаг 3: Сбор данных (двухфазный) ──────────────────────────────
        # Фаза 1: website + duckduckgo — быстрые, обогащают контекст
        await self._emit(session_id, "agent_started", "collectors",
                         "Phase 1: website + search (context enrichment)")
        phase1_results = await self._run_collectors(
            ["website", "duckduckgo"], plan.context, session_id
        )
        # Обогащаем контекст: LinkedIn URL компании + LinkedIn URL ЛПР
        plan.context = self._enrich_context_from_phase1(plan.context, phase1_results)
        # Если нашли LinkedIn ЛПР — добавляем linkedin_person в план
        if plan.context.get("linkedin_lpr_url") and "linkedin_person" not in plan.collectors:
            plan.collectors.append("linkedin_person")
            await self._emit(session_id, "agent_started", "source_map",
                             f"LPR found: {plan.context['linkedin_lpr_url']}")

        # Фаза 2: все остальные коллекторы с обогащённым контекстом
        phase2_names = [c for c in plan.collectors if c not in ("website", "duckduckgo")]
        await self._emit(session_id, "agent_started", "collectors",
                         f"Phase 2: {len(phase2_names)} collectors")
        phase2_results = await self._run_collectors(
            phase2_names, plan.context, session_id
        )

        raw_results = phase1_results + phase2_results
        usable = sum(1 for r in raw_results if r.is_usable())
        await self._emit(session_id, "agent_completed", "collectors",
                         f"Collected: {usable}/{len(raw_results)} usable",
                         {"usable": usable, "total": len(raw_results)})

        if usable == 0:
            logger.error(f"No usable data for session {session_id}")
            await self._update_session_status(session_id, "failed")
            return {"status": "failed", "error": "No usable data from any source"}

        # ── Шаг 4: Валидация ─────────────────────────────────────────────
        await self._emit(session_id, "agent_started", "validator", "Validating data")
        try:
            from agents.validators import ValidatorAgent
            validator = ValidatorAgent()
            validation_result = await validator.validate(raw_results, session_id)
            await self._emit(session_id, "agent_completed", "validator",
                             f"Gaps: {len(validation_result.gaps)}, "
                             f"contradictions: {len(validation_result.contradictions)}")
        except Exception as exc:
            logger.error(f"Validation failed: {exc}", exc_info=True)
            await self._emit(session_id, "agent_failed", "validator", str(exc))
            raise

        # ── Шаг 5: Обработка ошибок ──────────────────────────────────────
        await self._emit(session_id, "agent_started", "error_handler",
                         "Processing gaps")
        try:
            from agents.error_handler import ErrorHandlerAgent
            error_handler = ErrorHandlerAgent()
            cleaned_data = await error_handler.process(
                validation_result, plan.context, session_id
            )
            await self._emit(session_id, "agent_completed", "error_handler",
                             f"Ready: {cleaned_data.is_passport_ready}, "
                             f"retries: {len(cleaned_data.retry_results)}")
        except Exception as exc:
            logger.error(f"ErrorHandler failed: {exc}", exc_info=True)
            await self._emit(session_id, "agent_failed", "error_handler", str(exc))
            raise

        # ── Шаг 6: Анализ ────────────────────────────────────────────────
        await self._emit(session_id, "agent_started", "analyst", "Analyzing data")
        try:
            from agents.analyst import AnalystAgent
            analyst = AnalystAgent()
            analysis = await analyst.analyze(cleaned_data, context, session_id)
            await self._emit(session_id, "agent_completed", "analyst",
                             f"Pains: {len(analysis.pains)}, "
                             f"readiness: {analysis.readiness.get('score', 0)}/100")
        except Exception as exc:
            logger.error(f"Analyst failed: {exc}", exc_info=True)
            await self._emit(session_id, "agent_failed", "analyst", str(exc))
            raise

        # ── Шаг 7: Приоритизация ─────────────────────────────────────────
        await self._emit(session_id, "agent_started", "prioritizer", "Prioritizing")
        try:
            from agents.prioritizer import PrioritizerAgent
            prioritizer = PrioritizerAgent()
            prioritized = await prioritizer.prioritize(
                cleaned_data, analysis, context, session_id
            )
            await self._emit(session_id, "agent_completed", "prioritizer",
                             f"Completeness: {prioritized.completeness.score}/100, "
                             f"top hooks: {len(prioritized.top3_hooks)}")
        except Exception as exc:
            logger.error(f"Prioritizer failed: {exc}", exc_info=True)
            await self._emit(session_id, "agent_failed", "prioritizer", str(exc))
            raise

        # ── Шаг 8: Генерация паспорта ────────────────────────────────────
        await self._emit(session_id, "agent_started", "passport_generator",
                         "Generating 11-block passport")
        try:
            from agents.passport_generator import PassportGeneratorAgent
            passport_gen = PassportGeneratorAgent()
            passport = await passport_gen.generate(prioritized, context, session_id)
            await self._emit(session_id, "agent_completed", "passport_generator",
                             f"Passport generated: {passport.id}")
        except Exception as exc:
            logger.error(f"PassportGenerator failed: {exc}", exc_info=True)
            await self._emit(session_id, "agent_failed", "passport_generator", str(exc))
            raise

        # ── Шаг 9: Outreach ──────────────────────────────────────────────
        await self._emit(session_id, "agent_started", "outreach_preparer",
                         "Generating outreach texts (English)")
        try:
            from agents.outreach_preparer import OutreachPreparerAgent
            outreach_agent = OutreachPreparerAgent()
            passport_dict = self._passport_to_dict(passport)
            outreach = await outreach_agent.prepare(
                prioritized, passport_dict, context, session_id
            )
            await self._emit(session_id, "agent_completed", "outreach_preparer",
                             f"Outreach: type={outreach.lpr_type}, path={outreach.selected_path}")
        except Exception as exc:
            logger.error(f"Outreach failed: {exc}", exc_info=True)
            await self._emit(session_id, "agent_failed", "outreach_preparer", str(exc))
            raise

        # ── Шаг 10: Обновить БД ──────────────────────────────────────────
        await self._update_session_final(session_id, context, prioritized)

        # ── Шаг 11: Кеш ─────────────────────────────────────────────────
        try:
            await memory.save_passport(session_id, domain, passport)
        except Exception as exc:
            logger.warning(f"Cache save failed (non-critical): {exc}")

        return {
            "status": "completed",
            "passport_id": str(passport.id),
            "outreach_id": str(outreach.id),
            "completeness_score": prioritized.completeness.score,
        }

    # ── Обработка кеш-хита ───────────────────────────────────────────────

    async def _handle_cache_hit(
        self, session_id: str, context: dict, cached: dict, memory, log
    ) -> dict:
        """Кеш-хит: outreach генерируется заново (outreach НЕ кешируется)."""
        passport = cached.get("passport")
        if passport is None:
            return None

        await self._update_session_status(session_id, "cached")

        try:
            from agents.outreach_preparer import OutreachPreparerAgent
            from agents.prioritizer import PrioritizedData, CompletenessResult
            from agents.analyst import AnalysisResult
            from agents.error_handler import CleanedData

            # Минимальные объекты для outreach
            minimal_analysis = AnalysisResult(
                pains=[], readiness={"score": 0}, lpr_overheating={},
                triggers={"positive": [], "negative": []},
                industry_context={}, sales_model_signals={}, competitors=[],
            )
            minimal_cleaned = CleanedData(
                results_by_source={}, gaps=[], is_passport_ready=True,
            )
            minimal_prioritized = PrioritizedData(
                blocks_filled={}, top3_hooks=passport.top3_hooks or [],
                completeness=CompletenessResult(score=0, is_ready=True),
                analysis=minimal_analysis, cleaned_data=minimal_cleaned,
            )

            outreach_agent = OutreachPreparerAgent()
            passport_dict = self._passport_to_dict(passport)
            outreach = await outreach_agent.prepare(
                minimal_prioritized, passport_dict, context, session_id
            )
            return {
                "status": "cached",
                "passport_id": str(passport.id),
                "outreach_id": str(outreach.id),
            }
        except Exception as exc:
            logger.warning(f"Outreach on cache hit failed: {exc}")
            return {
                "status": "cached",
                "passport_id": str(passport.id),
                "outreach_error": str(exc),
            }

    # ── Обогащение контекста из фазы 1 ───────────────────────────────────

    def _enrich_context_from_phase1(self, context: dict, results: list) -> dict:
        """
        Извлекает из website + duckduckgo результатов:
        - linkedin_company_url (из footer/header сайта)
        - linkedin_lpr_url (из DDG поиска по "CEO site:linkedin.com/in")
        и добавляет их в контекст для использования в фазе 2.
        """
        import re
        for r in results:
            if not r.is_usable():
                continue

            if r.source_name == "website":
                # LinkedIn страница компании найдена на сайте
                li_url = r.data.get("linkedin_company_url")
                if li_url and not context.get("linkedin_company_url"):
                    context["linkedin_company_url"] = li_url
                    logger.info(f"Found LinkedIn company URL on website: {li_url}")

            if r.source_name == "duckduckgo":
                # Ищем LinkedIn профиль ЛПР в результатах lpr_linkedin
                if not context.get("linkedin_lpr_url"):
                    lpr_hits = r.data.get("lpr_linkedin", [])
                    for hit in lpr_hits:
                        url = hit.get("url", "")
                        # Только прямые профили /in/ (не /company/, не /pub/)
                        if re.search(r"linkedin\.com/in/[a-z0-9\-]+", url, re.I):
                            clean_url = url.split("?")[0].rstrip("/")
                            context["linkedin_lpr_url"] = clean_url
                            logger.info(f"Found LPR LinkedIn URL via DDG: {clean_url}")
                            break

                # Дополнительно: ищем LPR в key_people результатах
                if not context.get("linkedin_lpr_url"):
                    key_people_hits = r.data.get("key_people", [])
                    for hit in key_people_hits:
                        url = hit.get("url", "")
                        if re.search(r"linkedin\.com/in/[a-z0-9\-]+", url, re.I):
                            clean_url = url.split("?")[0].rstrip("/")
                            context["linkedin_lpr_url"] = clean_url
                            logger.info(f"Found LPR LinkedIn URL in key_people: {clean_url}")
                            break

        return context

    # ── Запуск коллекторов ───────────────────────────────────────────────

    async def _run_collectors(
        self, collector_names: list[str], context: dict, session_id: str
    ) -> list:
        """Запустить коллекторы параллельно по именам."""
        from collectors.base import make_failed_result
        cmap = _get_collector_map()

        async def _safe_run(name: str):
            cls = cmap.get(name)
            if cls is None:
                logger.warning(f"Unknown collector: {name}")
                return make_failed_result(name, "", f"Unknown collector: {name}")
            collector = cls()
            timeout = getattr(collector, "timeout_seconds", 60)
            try:
                return await asyncio.wait_for(
                    collector.safe_collect(context), timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(f"Collector {name} timed out after {timeout}s")
                return make_failed_result(name, "", f"Timeout after {timeout}s")
            except Exception as exc:
                logger.warning(f"Collector {name} error: {exc}")
                return make_failed_result(name, "", str(exc))

        tasks = [_safe_run(n) for n in collector_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final = []
        for name, result in zip(collector_names, results):
            if isinstance(result, Exception):
                final.append(make_failed_result(name, "", str(result)))
            else:
                final.append(result)
        return final

    # ── Вспомогательные ──────────────────────────────────────────────────

    def _extract_domain(self, url: str) -> str:
        if not url:
            return ""
        try:
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split("/")[0]
            if domain.startswith("www."):
                domain = domain[4:]
            return domain.lower().strip("/")
        except Exception:
            return url.lower().strip("/")

    def _passport_to_dict(self, passport) -> dict:
        return {
            "block1": passport.block1_general,
            "block2": passport.block2_sales_model,
            "block3": passport.block3_pains,
            "block4": passport.block4_people,
            "block5": passport.block5_context,
            "block7": passport.block7_readiness,
            "block10": passport.block10_lpr,
            "top3_hooks": passport.top3_hooks,
        }

    async def _update_session_status(
        self, session_id: str, status: str, started_at: Optional[datetime] = None,
    ):
        from database import AsyncSessionLocal
        from models.session import Session
        from sqlalchemy import update

        updates = {"status": status}
        if started_at:
            updates["pipeline_started_at"] = started_at
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(Session).where(Session.id == session_id).values(**updates)
                )
                await db.commit()
        except Exception as exc:
            logger.warning(f"Session status update failed: {exc}")

    async def _update_session_final(self, session_id: str, context: dict, prioritized):
        from database import AsyncSessionLocal
        from models.session import Session
        from sqlalchemy import update

        now = datetime.now(timezone.utc)
        updates = {
            "status": "completed",
            "pipeline_finished_at": now,
            "resolved_company_name": context.get("company_name"),
            "resolved_domain": self._extract_domain(context.get("website_url", "")),
            "completeness_score": prioritized.completeness.score,
            "completeness_status": "ready" if prioritized.completeness.is_ready else "incomplete",
        }
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(Session).where(Session.id == session_id).values(**updates)
                )
                await db.commit()
        except Exception as exc:
            logger.warning(f"Session final update failed: {exc}")

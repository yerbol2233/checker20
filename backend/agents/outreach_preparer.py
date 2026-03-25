"""
OutreachPreparerAgent — генерация outreach-текстов на английском.

Раздел 5, Агент 12 ТЗ.
Правила: СТРОГО НА АНГЛИЙСКОМ. Никогда не кешировать.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from agents.prioritizer import PrioritizedData
from llm.base import TaskType

logger = logging.getLogger(__name__)

# 13 абсолютных правил копирайтинга (из ТЗ раздел 7)
COPYWRITING_RULES = [
    "Never use generic openers (Hi, I wanted to reach out, I hope this finds you well)",
    "No feature lists — connect to ONE specific pain or trigger",
    "Use the company's exact language from their website/posts",
    "Reference a specific, verifiable fact (not flattery)",
    "One clear CTA per message (not multiple asks)",
    "Messages max 3 sentences for LinkedIn (no scrolling)",
    "Lead with THEIR world, not our product",
    "Never pitch on first message — open a conversation",
    "Warmup comments must be genuinely useful (not 'Great post!')",
    "Followup must bring NEW value, not just bump the thread",
    "Subject line = specific insight, not a question",
    "Email body max 5 sentences",
    "Always end with a soft CTA (curious if, worth a quick chat)",
]

# Матрица путей по типу ЛПР
LPR_PATH_MATRIX = {
    "creator": "own",        # Создатель контента → путь 'своё'
    "active_networker": "value",  # Активный нетворкер → путь 'ценность'
    "quiet_pro": "value",    # Тихий профессионал → путь 'ценность'
    "connector": "curiosity",  # Коннектор → путь 'любопытство'
}

SYSTEM_PROMPT = """You are a world-class B2B copywriter specializing in cold outreach for sales tools.
Language: STRICTLY ENGLISH.
Rules:
- Never use generic openers
- Reference SPECIFIC facts from the company data
- Lead with their world, not your product
- LinkedIn messages: max 3 sentences
- Email body: max 5 sentences
- Warmup comments: genuinely insightful, not generic praise
Respond ONLY with valid JSON."""


class OutreachPreparerAgent:
    """Генератор outreach-текстов (СТРОГО на английском)."""

    def __init__(self):
        self._router = None

    def _get_router(self):
        if self._router is None:
            from llm.router import get_llm_router
            self._router = get_llm_router()
        return self._router

    async def prepare(
        self,
        prioritized: PrioritizedData,
        passport_data: dict,
        context: dict,
        session_id: Optional[str] = None,
    ):
        """Подготовить outreach-тексты и сохранить в БД."""
        from models.outreach import OutreachText

        company_name = context.get("company_name", "the company")
        results = prioritized.cleaned_data.results_by_source
        analysis = prioritized.analysis

        # Определяем тип ЛПР
        lpr_type, lpr_rationale = self._detect_lpr_type(results, analysis)

        # Выбираем путь
        selected_path = LPR_PATH_MATRIX.get(lpr_type, "value")

        # Контекст для генерации
        outreach_context = self._build_outreach_context(
            company_name, prioritized, passport_data, context
        )

        # Генерируем параллельно
        import asyncio
        warmup_task = asyncio.create_task(
            self._generate_warmup_comments(outreach_context, lpr_type, session_id)
        )
        linkedin_task = asyncio.create_task(
            self._generate_linkedin_messages(
                outreach_context, lpr_type, selected_path, session_id
            )
        )
        followup_task = asyncio.create_task(
            self._generate_followup(outreach_context, session_id)
        )
        email_task = asyncio.create_task(
            self._generate_email(outreach_context, session_id)
        )
        path_rationale_task = asyncio.create_task(
            self._generate_path_rationale(
                outreach_context, lpr_type, selected_path, session_id
            )
        )

        warmup_comments = await warmup_task
        linkedin_messages = await linkedin_task
        followup_result = await followup_task
        email_result = await email_task
        path_rationale = await path_rationale_task

        outreach = OutreachText(
            id=uuid.uuid4(),
            session_id=uuid.UUID(session_id) if session_id else uuid.uuid4(),
            created_at=datetime.now(timezone.utc),
            lpr_type=lpr_type,
            selected_path=selected_path,
            warmup_comments=warmup_comments,
            linkedin_messages=linkedin_messages,
            followup_message=followup_result.get("message"),
            followup_new_angle=followup_result.get("new_angle"),
            email_subject=email_result.get("subject"),
            email_body=email_result.get("body"),
            lpr_type_rationale=lpr_rationale,
            path_selection_rationale=path_rationale,
            copywriting_rules_applied=COPYWRITING_RULES[:8],  # ключевые 8
        )

        # Сохраняем в БД
        from database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            db.add(outreach)
            await db.commit()
            await db.refresh(outreach)

        return outreach

    def _detect_lpr_type(self, results: dict, analysis) -> tuple[str, str]:
        """Определить тип ЛПР детерминированно."""
        lpr_data = results.get("linkedin_person")
        if not lpr_data or not lpr_data.is_usable():
            return "quiet_pro", "No LPR data — defaulting to quiet_pro"

        data = lpr_data.data
        posts_per_month = data.get("posts_per_month_estimate", 0)
        connections = data.get("connections", 0)
        profile_type = data.get("profile_type", "")
        followers = data.get("followers", 0)

        if profile_type == "creator" or posts_per_month >= 8:
            return "creator", f"Posts/month: {posts_per_month}, profile_type: {profile_type}"

        if connections > 5000 or followers > 3000:
            return "active_networker", f"Connections: {connections}, followers: {followers}"

        if posts_per_month >= 2:
            return "connector", f"Moderate activity: {posts_per_month} posts/month"

        return "quiet_pro", f"Low activity: {posts_per_month} posts/month, {connections} connections"

    def _build_outreach_context(
        self,
        company_name: str,
        prioritized: PrioritizedData,
        passport_data: dict,
        context: dict,
    ) -> dict:
        """Собрать контекст для генерации outreach."""
        from agents.product_config import ProductConfiguratorAgent
        product_ctx = ProductConfiguratorAgent().format_for_llm()

        top_hook = ""
        if prioritized.top3_hooks:
            top_hook = prioritized.top3_hooks[0].get("hook", "")

        top_pain = ""
        if prioritized.analysis.pains:
            top_pain = prioritized.analysis.pains[0].get("pain", "")

        lpr_result = prioritized.cleaned_data.results_by_source.get("linkedin_person")
        lpr_name = ""
        lpr_title = ""
        if lpr_result and lpr_result.is_usable():
            lpr_name = lpr_result.data.get("full_name", "")
            lpr_title = lpr_result.data.get("headline", "")

        return {
            "company_name": company_name,
            "lpr_name": lpr_name,
            "lpr_title": lpr_title,
            "top_hook": top_hook,
            "top_pain": top_pain,
            "readiness_score": prioritized.analysis.readiness.get("score", 0),
            "product_context": product_ctx,
            "triggers": prioritized.analysis.triggers.get("positive", [])[:2],
            "top3_hooks": prioritized.top3_hooks,
        }

    async def _generate_warmup_comments(
        self, ctx: dict, lpr_type: str, session_id: Optional[str]
    ) -> list:
        """Генерировать 2-3 warmup-комментария к постам ЛПР."""
        router = self._get_router()
        try:
            result = await router.complete_json(
                task_type=TaskType.OUTREACH_GENERATION,
                system_prompt=SYSTEM_PROMPT,
                prompt=(
                    f"Company: {ctx['company_name']}\\n"
                    f"LPR: {ctx['lpr_name']} ({ctx['lpr_title']})\\n"
                    f"LPR type: {lpr_type}\\n"
                    f"Recent context/hooks: {ctx['top_hook']}\\n"
                    f"Product: {ctx['product_context']}\\n\\n"
                    f"Generate 2-3 warmup LinkedIn COMMENTS (not messages) to engage "
                    f"before cold outreach. Each comment must be genuinely insightful "
                    f"(max 2 sentences, no generic praise, reference their specific content).\\n"
                    f'JSON array: [{{"comment_text": "...", "intent": "establish_credibility/show_expertise/add_value"}}]'
                ),
                max_tokens=600,
                session_id=session_id,
                agent_name="outreach_warmup",
            )
            if isinstance(result, list):
                return result
        except Exception as exc:
            logger.warning(f"Warmup generation failed: {exc}")
        return []

    async def _generate_linkedin_messages(
        self,
        ctx: dict,
        lpr_type: str,
        path: str,
        session_id: Optional[str],
    ) -> list:
        """Генерировать 3 варианта LinkedIn DM."""
        path_descriptions = {
            "value": "lead with a specific insight or benchmark relevant to their business",
            "own": "acknowledge their own content/work, connect it to a shared challenge",
            "curiosity": "open with an intriguing question based on a specific observation",
        }
        path_desc = path_descriptions.get(path, "lead with value")

        router = self._get_router()
        try:
            result = await router.complete_json(
                task_type=TaskType.OUTREACH_GENERATION,
                system_prompt=SYSTEM_PROMPT,
                prompt=(
                    f"Company: {ctx['company_name']}\\n"
                    f"LPR: {ctx['lpr_name']} ({ctx['lpr_title']})\\n"
                    f"LPR type: {lpr_type}, selected path: {path} — {path_desc}\\n"
                    f"Top hook: {ctx['top_hook']}\\n"
                    f"Top pain: {ctx['top_pain']}\\n"
                    f"Entry triggers: {ctx['triggers']}\\n"
                    f"Our product: {ctx['product_context']}\\n\\n"
                    f"Generate 3 LinkedIn cold DM variants using the '{path}' path. "
                    f"Rules: max 3 sentences each, no feature lists, "
                    f"reference specific verifiable facts, soft CTA only, "
                    f"no pitching on first message.\\n"
                    f'JSON: [{{"variant": 1, "message": "...", "hook_used": "...", "tone": "..."}}]'
                ),
                max_tokens=800,
                session_id=session_id,
                agent_name="outreach_linkedin",
            )
            if isinstance(result, list):
                return result
        except Exception as exc:
            logger.warning(f"LinkedIn messages generation failed: {exc}")
        return []

    async def _generate_followup(
        self, ctx: dict, session_id: Optional[str]
    ) -> dict:
        """Генерировать follow-up сообщение с новым углом."""
        router = self._get_router()
        try:
            result = await router.complete_json(
                task_type=TaskType.OUTREACH_GENERATION,
                system_prompt=SYSTEM_PROMPT,
                prompt=(
                    f"Company: {ctx['company_name']}\\n"
                    f"LPR: {ctx['lpr_name']} ({ctx['lpr_title']})\\n"
                    f"Top hooks: {ctx['top3_hooks']}\\n"
                    f"Our product: {ctx['product_context']}\\n\\n"
                    f"Generate a follow-up LinkedIn message (3-5 days after no response). "
                    f"Rules: bring NEW value (not 'just bumping this'), "
                    f"use a completely different angle from the first message, "
                    f"max 3 sentences, soft CTA.\\n"
                    f'JSON: {{"message": "...", "new_angle": "brief description of the angle used"}}'
                ),
                max_tokens=400,
                session_id=session_id,
                agent_name="outreach_followup",
            )
            if isinstance(result, dict):
                return result
        except Exception as exc:
            logger.warning(f"Followup generation failed: {exc}")
        return {"message": "", "new_angle": ""}

    async def _generate_email(
        self, ctx: dict, session_id: Optional[str]
    ) -> dict:
        """Генерировать cold email (subject + body)."""
        router = self._get_router()
        try:
            result = await router.complete_json(
                task_type=TaskType.OUTREACH_GENERATION,
                system_prompt=SYSTEM_PROMPT,
                prompt=(
                    f"Company: {ctx['company_name']}\\n"
                    f"LPR: {ctx['lpr_name']} ({ctx['lpr_title']})\\n"
                    f"Top pain: {ctx['top_pain']}\\n"
                    f"Top hook: {ctx['top_hook']}\\n"
                    f"Our product: {ctx['product_context']}\\n\\n"
                    f"Generate a cold email. Rules:\\n"
                    f"- Subject: specific insight (not a question, not generic)\\n"
                    f"- Body: max 5 sentences, lead with their world,\\n"
                    f"  reference one specific fact, one soft CTA\\n"
                    f'JSON: {{"subject": "...", "body": "..."}}'
                ),
                max_tokens=500,
                session_id=session_id,
                agent_name="outreach_email",
            )
            if isinstance(result, dict):
                return result
        except Exception as exc:
            logger.warning(f"Email generation failed: {exc}")
        return {"subject": "", "body": ""}

    async def _generate_path_rationale(
        self,
        ctx: dict,
        lpr_type: str,
        path: str,
        session_id: Optional[str],
    ) -> str:
        """Обоснование выбора пути."""
        return (
            f"LPR type '{lpr_type}' → path '{path}'. "
            f"Readiness score: {ctx['readiness_score']}/100. "
            f"Top hook: {ctx['top_hook'][:100] if ctx['top_hook'] else 'none'}."
        )

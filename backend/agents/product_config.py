"""
ProductConfiguratorAgent — жёстко захардкоженный контекст продукта.

ВАЖНО: данные НЕ из LLM, НЕ из БД. Меняются только вручную здесь.
Передаётся Аналитику для понимания ICP и relevance болей.
НЕ передаётся Подготовщику outreach (outreach строится из паспорта).
"""

# Контекст продукта — раздел 1.2 ТЗ
PRODUCT_CONTEXT = {
    "product_name": "Digital Sales Rooms Platform",
    "description": (
        "Превращает телефонный звонок менеджера в автоматическую воронку дожима "
        "через персональные цифровые комнаты продаж"
    ),
    "target": "B2C компании США с SDR/sales командами, работающими по телефону",
    "icp_signals": [
        "наличие sales team 5+ человек",
        "работают по телефону с клиентами",
        "ищут способы повысить конверсию звонков",
        "есть CRM (Salesforce/HubSpot)",
        "стадия: Seed+",
        "B2C модель",
    ],
    "pain_relevance_map": {
        "low_call_conversion": "critical",
        "no_follow_up_process": "critical",
        "manual_deal_tracking": "high",
        "slow_sales_cycle": "high",
        "poor_demo_attendance": "high",
        "sdrs_not_hitting_quota": "critical",
        "high_sdrs_turnover": "high",
        "no_call_recordings": "medium",
    },
    "value_props": [
        "Повышает конверсию звонка в демо на 30-50%",
        "Автоматизирует follow-up после звонка",
        "Персональная комната продаж для каждого лида",
        "Интеграция с CRM (Salesforce, HubSpot)",
    ],
}


class ProductConfiguratorAgent:
    """Предоставляет контекст продукта аналитику."""

    def get_context(self) -> dict:
        return PRODUCT_CONTEXT

    def get_pain_relevance(self, pain_keyword: str) -> str:
        """Возвращает релевантность боли: critical | high | medium | low."""
        pain_lower = pain_keyword.lower()
        for key, level in PRODUCT_CONTEXT["pain_relevance_map"].items():
            if key.replace("_", " ") in pain_lower or pain_lower in key:
                return level
        return "low"

    def format_for_llm(self) -> str:
        """Форматирует контекст для вставки в LLM промпт."""
        ctx = PRODUCT_CONTEXT
        icp = "\n".join(f"  - {s}" for s in ctx["icp_signals"])
        values = "\n".join(f"  - {v}" for v in ctx["value_props"])
        return (
            f"Product: {ctx['product_name']}\n"
            f"Description: {ctx['description']}\n"
            f"Target: {ctx['target']}\n"
            f"ICP Signals:\n{icp}\n"
            f"Value Props:\n{values}"
        )

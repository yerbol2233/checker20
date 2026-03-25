"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── sessions ─────────────────────────────────────────────────────────────
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("website_url", sa.Text, nullable=False),
        sa.Column("linkedin_lpr_url", sa.Text, nullable=True),
        sa.Column("company_name", sa.Text, nullable=True),
        sa.Column("resolved_company_name", sa.Text, nullable=True),
        sa.Column("resolved_domain", sa.Text, nullable=True),
        sa.Column("pipeline_started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("pipeline_finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("is_cached", sa.Boolean, server_default=sa.text("false")),
        sa.Column("cache_source_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("completeness_score", sa.Integer, nullable=True),
        sa.Column("completeness_status", sa.String(20), nullable=True),
        sa.Column("incompleteness_reasons", postgresql.JSONB, nullable=True),
        sa.Column("errors", postgresql.JSONB, server_default=sa.text("'[]'::jsonb")),
    )

    # ── passports ────────────────────────────────────────────────────────────
    op.create_table(
        "passports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        # Block 1
        sa.Column("block1_general", postgresql.JSONB, nullable=True),
        sa.Column("block1_sources", postgresql.JSONB, nullable=True),
        sa.Column("block1_confidence", sa.Float, nullable=True),
        # Block 2
        sa.Column("block2_sales_model", postgresql.JSONB, nullable=True),
        sa.Column("block2_sources", postgresql.JSONB, nullable=True),
        sa.Column("block2_confidence", sa.Float, nullable=True),
        # Block 3
        sa.Column("block3_pains", postgresql.JSONB, nullable=True),
        sa.Column("block3_sources", postgresql.JSONB, nullable=True),
        sa.Column("block3_confidence", sa.Float, nullable=True),
        # Block 4
        sa.Column("block4_people", postgresql.JSONB, nullable=True),
        sa.Column("block4_sources", postgresql.JSONB, nullable=True),
        sa.Column("block4_confidence", sa.Float, nullable=True),
        # Block 5
        sa.Column("block5_context", postgresql.JSONB, nullable=True),
        sa.Column("block5_sources", postgresql.JSONB, nullable=True),
        sa.Column("block5_confidence", sa.Float, nullable=True),
        # Block 6
        sa.Column("block6_competitors", postgresql.JSONB, nullable=True),
        sa.Column("block6_sources", postgresql.JSONB, nullable=True),
        sa.Column("block6_confidence", sa.Float, nullable=True),
        # Block 7
        sa.Column("block7_readiness", postgresql.JSONB, nullable=True),
        sa.Column("block7_sources", postgresql.JSONB, nullable=True),
        sa.Column("block7_confidence", sa.Float, nullable=True),
        # Block 8
        sa.Column("block8_reputation", postgresql.JSONB, nullable=True),
        sa.Column("block8_sources", postgresql.JSONB, nullable=True),
        sa.Column("block8_confidence", sa.Float, nullable=True),
        # Block 9
        sa.Column("block9_triggers", postgresql.JSONB, nullable=True),
        sa.Column("block9_sources", postgresql.JSONB, nullable=True),
        sa.Column("block9_confidence", sa.Float, nullable=True),
        # Block 10
        sa.Column("block10_lpr", postgresql.JSONB, nullable=True),
        sa.Column("block10_sources", postgresql.JSONB, nullable=True),
        sa.Column("block10_confidence", sa.Float, nullable=True),
        # Block 11
        sa.Column("block11_industry", postgresql.JSONB, nullable=True),
        sa.Column("block11_sources", postgresql.JSONB, nullable=True),
        sa.Column("block11_confidence", sa.Float, nullable=True),
        # Meta
        sa.Column("top3_hooks", postgresql.JSONB, nullable=True),
        sa.Column("raw_collected_data", postgresql.JSONB, nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )

    # ── outreach_texts ────────────────────────────────────────────────────────
    op.create_table(
        "outreach_texts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("lpr_type", sa.String(30), nullable=True),
        sa.Column("selected_path", sa.String(20), nullable=True),
        sa.Column("warmup_comments", postgresql.JSONB, nullable=True),
        sa.Column("linkedin_messages", postgresql.JSONB, nullable=True),
        sa.Column("followup_message", sa.Text, nullable=True),
        sa.Column("followup_new_angle", sa.Text, nullable=True),
        sa.Column("email_subject", sa.Text, nullable=True),
        sa.Column("email_body", sa.Text, nullable=True),
        sa.Column("lpr_type_rationale", sa.Text, nullable=True),
        sa.Column("path_selection_rationale", sa.Text, nullable=True),
        sa.Column("copywriting_rules_applied", postgresql.JSONB, nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )

    # ── feedback ──────────────────────────────────────────────────────────────
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("result", sa.String(30), nullable=True),
        sa.Column("passport_useful", sa.Boolean, nullable=True),
        sa.Column("best_hook", sa.Integer, nullable=True),
        sa.Column("best_hook_custom", sa.Text, nullable=True),
        sa.Column("message_strategy", sa.String(30), nullable=True),
        sa.Column("message_strategy_custom", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )

    # ── agent_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "agent_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("agent_name", sa.String(50), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("details", postgresql.JSONB, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("is_error", sa.Boolean, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )

    # ── token_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "token_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("agent_name", sa.String(50), nullable=False),
        sa.Column("llm_provider", sa.String(20), nullable=False),
        sa.Column("model_name", sa.String(50), nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=False),
        sa.Column("completion_tokens", sa.Integer, nullable=False),
        sa.Column("total_tokens", sa.Integer, nullable=False),
        sa.Column("cost_usd", sa.Float, nullable=False),
        sa.Column("task_description", sa.Text, nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )

    # ── company_cache ─────────────────────────────────────────────────────────
    op.create_table(
        "company_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("domain", sa.Text, nullable=False),
        sa.Column("last_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("passport_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cached_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW() + INTERVAL '30 days'"), nullable=False),
        sa.UniqueConstraint("domain", name="uq_company_cache_domain"),
        sa.ForeignKeyConstraint(["last_session_id"], ["sessions.id"]),
        sa.ForeignKeyConstraint(["passport_id"], ["passports.id"]),
    )

    # ── Indexes ───────────────────────────────────────────────────────────────
    op.create_index("idx_sessions_domain", "sessions", ["resolved_domain"])
    op.create_index("idx_agent_logs_session", "agent_logs", ["session_id", "created_at"])
    op.create_index("idx_token_logs_session", "token_logs", ["session_id"])
    op.create_index("idx_company_cache_domain", "company_cache", ["domain"])
    op.create_index("idx_company_cache_expires", "company_cache", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_company_cache_expires")
    op.drop_index("idx_company_cache_domain")
    op.drop_index("idx_token_logs_session")
    op.drop_index("idx_agent_logs_session")
    op.drop_index("idx_sessions_domain")

    op.drop_table("company_cache")
    op.drop_table("token_logs")
    op.drop_table("agent_logs")
    op.drop_table("feedback")
    op.drop_table("outreach_texts")
    op.drop_table("passports")
    op.drop_table("sessions")

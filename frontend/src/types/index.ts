// ── Session ────────────────────────────────────────────────────────────────

export interface Session {
  id: string;
  status: "pending" | "running" | "completed" | "failed" | "cached";
  website_url: string;
  linkedin_lpr_url: string | null;
  company_name: string | null;
  resolved_company_name: string | null;
  resolved_domain: string | null;
  created_at: string;
  updated_at: string;
  pipeline_started_at: string | null;
  pipeline_finished_at: string | null;
  duration_seconds: number | null;
  is_cached: boolean;
  completeness_score: number | null;
  completeness_status: string | null;
  incompleteness_reasons: Array<{ block_id: number; reason: string }>;
  errors: Array<{ error: string; at: string }>;
}

// ── SSE Events ─────────────────────────────────────────────────────────────

export interface SSEEvent {
  type:
    | "connected"
    | "heartbeat"
    | "cache_hit"
    | "agent_started"
    | "agent_completed"
    | "agent_failed"
    | "thinking"
    | "pipeline_started"
    | "pipeline_completed"
    | "pipeline_failed"
    | "pipeline_error"
    | "error";
  agent: string;
  message: string;
  timestamp: string;
  data?: Record<string, unknown>;
}

// ── Passport ───────────────────────────────────────────────────────────────

export interface PassportBlock {
  data: Record<string, unknown> | null;
  sources: SourceRef[];
  confidence: number;
}

export interface SourceRef {
  source_name: string;
  url: string;
  confidence: number;
  retrieved_at: string;
}

export interface Passport {
  id: string;
  created_at: string;
  blocks: {
    "1_general": PassportBlock;
    "2_sales_model": PassportBlock;
    "3_pains": PassportBlock;
    "4_people": PassportBlock;
    "5_context": PassportBlock;
    "6_competitors": PassportBlock;
    "7_readiness": PassportBlock;
    "8_reputation": PassportBlock;
    "9_triggers": PassportBlock;
    "10_lpr": PassportBlock;
    "11_industry": PassportBlock;
  };
  top3_hooks: HookItem[];
}

export interface HookItem {
  rank: number;
  hook: string;
  source_block: number;
  freshness_days: number;
  score: number;
  rationale?: string;
}

// ── Outreach ───────────────────────────────────────────────────────────────

export interface LinkedInMessage {
  variant: number;
  message: string;
  hook_used: string;
  tone: string;
}

export interface WarmupComment {
  comment_text: string;
  intent: string;
}

export interface Outreach {
  id: string;
  lpr_type: string | null;
  lpr_type_rationale: string | null;
  selected_path: string | null;
  path_selection_rationale: string | null;
  warmup_comments: WarmupComment[];
  linkedin_messages: LinkedInMessage[];
  followup_message: string | null;
  followup_new_angle: string | null;
  email_subject: string | null;
  email_body: string | null;
  copywriting_rules_applied: string[];
}

// ── Agent Timeline ─────────────────────────────────────────────────────────

export interface AgentLogEntry {
  id: string;
  agent_name: string;
  event_type: string;
  message: string;
  details: Record<string, unknown> | null;
  duration_ms: number | null;
  is_error: boolean;
  created_at: string;
}

// ── Token Summary ──────────────────────────────────────────────────────────

export interface TokenSummary {
  total_cost_usd: number;
  total_tokens: number;
  by_provider: Record<
    string,
    { tokens: number; cost_usd: number; calls: number }
  >;
}

// ── Dashboard ──────────────────────────────────────────────────────────────

export interface DashboardData {
  session: Session;
  passport: Passport | null;
  outreach: Outreach | null;
  agent_timeline: AgentLogEntry[];
  token_summary: TokenSummary;
}

// ── Forms ──────────────────────────────────────────────────────────────────

export interface SessionCreateRequest {
  website_url: string;
  linkedin_lpr_url?: string;
  company_name?: string;
}

export interface FeedbackRequest {
  result: "useful" | "not_useful" | "partial";
  passport_useful: boolean;
  best_hook: string | null;
  message_strategy: string | null;
  notes: string | null;
}

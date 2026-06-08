CREATE TABLE IF NOT EXISTS launchbot_help_article_runs (
  run_id TEXT PRIMARY KEY,
  issue_key TEXT NOT NULL,
  jira_updated_at TIMESTAMPTZ,
  launch_priority TEXT,
  product_lead_jira_account_id TEXT,
  product_lead_slack_user_id TEXT,
  status TEXT NOT NULL CHECK (
    status IN (
      'received',
      'blocked',
      'planning',
      'drafting',
      'drafted',
      'review_requested',
      'feedback_pending',
      'publish_confirmation_requested',
      'published',
      'failed'
    )
  ),
  slack_channel_id TEXT,
  slack_thread_ts TEXT,
  locales JSONB NOT NULL DEFAULT '{"en": {}, "id": {}}'::jsonb,
  evidence_paths JSONB NOT NULL DEFAULT '[]'::jsonb,
  error_summary TEXT,
  event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS launchbot_help_article_runs_issue_key_idx
  ON launchbot_help_article_runs (issue_key);

CREATE INDEX IF NOT EXISTS launchbot_help_article_runs_status_idx
  ON launchbot_help_article_runs (status);

CREATE INDEX IF NOT EXISTS launchbot_help_article_runs_slack_thread_idx
  ON launchbot_help_article_runs (slack_channel_id, slack_thread_ts);

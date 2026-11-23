-- F3: job sources (APIs), saved searches and local per-source call limits. Additive only.

CREATE TABLE searches (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    query TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    remote TEXT NOT NULL DEFAULT 'any' CHECK (remote IN ('any', 'only', 'exclude')),
    sources TEXT NOT NULL DEFAULT '[]',
    required TEXT NOT NULL DEFAULT '[]',
    excluded TEXT NOT NULL DEFAULT '[]',
    last_run_at TEXT,
    last_summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE source_calls (
    source TEXT PRIMARY KEY,
    endpoint TEXT NOT NULL DEFAULT '',
    day TEXT NOT NULL DEFAULT '',
    calls_today INTEGER NOT NULL DEFAULT 0,
    last_call_at TEXT
);

ALTER TABLE jobs ADD COLUMN source TEXT NOT NULL DEFAULT 'manual';
ALTER TABLE jobs ADD COLUMN external_id TEXT;
ALTER TABLE jobs ADD COLUMN match_key TEXT;
ALTER TABLE jobs ADD COLUMN search_id INTEGER REFERENCES searches (id) ON DELETE SET NULL;

CREATE INDEX ix_jobs_match_key ON jobs (match_key);
CREATE INDEX ix_jobs_source ON jobs (source);
CREATE INDEX ix_jobs_search_id ON jobs (search_id);

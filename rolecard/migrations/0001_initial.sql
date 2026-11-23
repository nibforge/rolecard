-- Initial schema. Later migrations are additive only.

CREATE TABLE profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL,
    source_text TEXT NOT NULL DEFAULT '',
    needs_review INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE jobs (
    id INTEGER PRIMARY KEY,
    url TEXT,
    url_key TEXT UNIQUE,
    text TEXT NOT NULL,
    text_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'prepared', 'sent', 'replied', 'interview', 'offer', 'discarded')),
    score INTEGER CHECK (score BETWEEN 0 AND 100),
    score_summary TEXT NOT NULL DEFAULT '',
    score_met TEXT NOT NULL DEFAULT '[]',
    score_missing TEXT NOT NULL DEFAULT '[]',
    scored_at TEXT,
    follow_up_on TEXT,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX ix_jobs_status ON jobs (status);

CREATE TABLE job_events (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    at TEXT NOT NULL
);

CREATE INDEX ix_job_events_job_id ON job_events (job_id);

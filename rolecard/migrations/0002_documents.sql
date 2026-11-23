-- F2: tailored documents (CV and cover letter) per job. Additive only.

CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('cv', 'letter')),
    language TEXT NOT NULL,
    content TEXT NOT NULL,
    source_snapshot TEXT NOT NULL DEFAULT '{}',
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (job_id, kind)
);

ALTER TABLE jobs ADD COLUMN doc_language TEXT NOT NULL DEFAULT '';

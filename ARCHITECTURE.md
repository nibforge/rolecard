# Architecture

rolecard is a local Flask app: one process, one SQLite file, one user. It listens on
127.0.0.1 only and keeps every piece of data in the user's folder (`~/.rolecard` or
`ROLECARD_HOME`).

## Layers
| Layer | Where | What it does |
|---|---|---|
| Entry point | `rolecard/cli.py`, `rolecard/__main__.py` | Parses the options, serves the app with waitress on 127.0.0.1 and opens the browser. |
| App factory | `rolecard/__init__.py` | Builds the Flask app: settings, database, migrations, security, i18n, blueprints. |
| Security | `rolecard/security.py` | Host check, CSRF token and `Origin` on every POST, CSP and the other headers. |
| Views | `rolecard/views/` | One blueprint per page; they only read the form, call a service and render. |
| Services | `rolecard/services/` | The rules of the product (scoring, tailoring, provenance, tracking, search). |
| AI | `rolecard/ai/` | The providers, the prompts and the strict JSON schemas of every answer. |
| Sources | `rolecard/sources/` | The job APIs (Remotive, Arbeitnow, Adzuna), their limits and normalisation. |
| Data | `rolecard/models.py`, `rolecard/db.py`, `rolecard/migrations/` | SQLAlchemy models and numbered SQL migrations. |
| Interface | `rolecard/templates/`, `rolecard/static/`, `rolecard/locales/` | Jinja + HTMX, own CSS, every text through an i18n key (en/es). |

## The flow, file by file
1. **Profile.** The user uploads a CV (`rolecard/views/profile.py`). The text is read in
   memory (`rolecard/services/profile.py`). The AI turns it into a profile
   (`rolecard/ai/prompts.py`, `profile_prompt`), and its answer is validated
   (`rolecard/services/profile_schema.py`).
2. **Offers.** The user pastes an offer or runs a saved search (`rolecard/views/jobs.py`,
   `rolecard/services/search.py`). The search asks the APIs (`rolecard/sources/`).
   Duplicates are removed (`rolecard/services/dedup.py`), and a cheap filter runs before
   any AI call (`rolecard/services/prefilter.py`).
3. **Score.** The AI rates the fit of each offer with the profile
   (`rolecard/services/scoring.py`).
4. **Tailor.** The AI writes a CV and a cover letter for one offer
   (`rolecard/services/tailoring.py`, `rolecard/services/documents.py`). Every sentence
   cites its sources in the profile.
5. **Check.** The server checks every sentence against those sources: paths, figures and
   names (`rolecard/services/provenance.py`). Nothing is exported until the user has
   resolved every flagged sentence and marked the document reviewed. Then it is exported
   to PDF or DOCX (`rolecard/services/export_pdf.py`).
6. **Track.** The board and the home page follow each offer up to the answer
   (`rolecard/services/tracking.py`, `rolecard/services/board.py`,
   `rolecard/services/home.py`).

## AI providers
`rolecard/ai/__init__.py` (`resolve`) chooses the provider. With «Automatic», an
OpenAI-compatible service the user has set up comes first, then Claude Code if it is
installed.
- `rolecard/ai/claude_code.py`: `claude -p`, with no tools and in safe mode. The prompt
  goes through stdin, and the process gets a closed list of environment variables.
- `rolecard/ai/openai_compat.py`: any `/chat/completions` endpoint (Ollama, OpenAI…),
  with plain `urllib`.

Every answer goes through `AIProvider.complete_json` (`rolecard/ai/base.py`): one JSON
object that must match its schema (`rolecard/ai/schema.py`), or it is rejected.

## Data
- Schema changes only through `rolecard/migrations/NNNN_name.sql`, applied in order by
  `rolecard/db.py`. Before applying a pending migration, the database is copied as
  `rolecard.sqlite3.bak-v<N>`, and the two newest copies are kept.
- Settings and keys live in `config.toml`, in the data folder (`rolecard/config.py`).
- The local log is `rolecard.log` (`rolecard/logs.py`). It never holds the text of an AI
  answer.

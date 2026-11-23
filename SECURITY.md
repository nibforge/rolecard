# Security

## Reporting a vulnerability
Please report it privately through GitHub's «Report a vulnerability» (Security tab of
this repository), not in a public issue. Include the version and the steps to reproduce.

## Threat model
rolecard runs on your computer for you alone. What it protects is your CV, your offers
and your API keys, against other websites open in your browser, other machines on your
network and the text of the offers themselves.

- **Local only.** The server listens on 127.0.0.1, with no option to change it. Requests
  with another `Host` are refused (DNS rebinding).
- **Every POST** needs the session's CSRF token and an `Origin` of the app itself. A
  test walks every route to check it (`tests/test_csrf_all_posts.py`).
- **Headers.** A strict CSP (`default-src 'self'`, no inline scripts and no `eval`),
  `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy` and `no-store`. Session cookie
  `HttpOnly` and `SameSite=Strict`.
- **Untrusted text.** Offers and CVs are data, never instructions. They are escaped
  everywhere they are shown. In the prompts they go between `<untrusted_document>`
  tags, and so does the profile.
- **The CV upload** stays in memory, with limits on size, pages and unzipped size.

## The AI
- **What leaves your computer.** Your profile and the offers you score or tailor go to
  the provider you choose. Settings tells you which one is in use, and warns you when it
  is a cloud service. With «Automatic», an OpenAI-compatible service you have set up
  (such as Ollama on your computer) comes before Claude Code.
- **Claude Code** runs with no tools, no MCP servers, no slash commands and no saved
  session. It runs in safe mode (`--safe-mode`: none of your CLAUDE.md, hooks or
  plugins), in an empty temporary folder, with a time limit. It gets only the
  environment variables it needs (`ENV_ALLOWED` in `rolecard/ai/claude_code.py`), so
  rolecard's own keys never reach it. `ANTHROPIC_*` and `CLAUDE_*` do pass: they are
  your own Claude Code settings, such as `ANTHROPIC_API_KEY` to pay per use with an
  Anthropic API key. rolecard never stores or reads them. A Claude Code release without `--safe-mode` fails
  with an error: update it.
- **API keys** are kept in `config.toml` (permissions 0600) or in environment
  variables. They are never shown in the page and never sent over plain `http://`,
  except to your own computer. Redirects are not followed.
- **The AI never invents facts.** Every sentence of a CV or a letter cites where it
  comes from in your profile. The server checks that every cited source exists, and
  that every figure in the sentence is in its sources; if not, the sentence is
  *unsourced*. A sentence that names something (a company, an acronym, a technology)
  that is not in its sources waits for your confirmation, and so does a sentence that
  cites only the offer. Nothing is exported until you have dealt with every flagged
  sentence and reviewed the document. The check is literal: it catches a missing name or
  number, not a false claim made in ordinary words. That is why you review every
  document.

## Your data
- Everything lives in your data folder: the database, `config.toml`, `secret_key` and
  the log. On Linux and macOS the folder is 0700. On Windows, `chmod` has no effect: the
  protection is the access control of your user profile (`%USERPROFILE%`).
- Deleted rows are overwritten (`PRAGMA secure_delete`). Before a schema migration the
  database is copied next to it (the two newest copies are kept).
- The log (`rolecard.log`) records errors. For a rejected AI answer it keeps only the
  type of error, its length and a hash, never its text. A crash trace may contain a
  fragment of a value: the log never leaves your folder.
- No telemetry and no update checks. The job sources are fixed https APIs, with limits
  on size and time.

## Audit
Before the first public release the code was audited with gitleaks (whole history),
pip-audit, bandit, vulture and ruff, plus a manual review of the points above. Results:
no secrets or personal data in the history, no known vulnerable dependencies, and no
critical findings. The medium and minor findings were fixed or recorded on purpose.

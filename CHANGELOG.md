# Changelog

## [0.1.2] - 2026-11-24

Fixes.

- Adzuna only shares a summary of each offer: the offer page now says so, and
  **Edit details** has an **Offer text** field to paste the full description from the
  offer's page (then score again).
- Generating a cover letter no longer fails when one sentence cites many items of your
  profile (`sources: has too many items`).
- The tailored CV summary and the cover letter are written in the first person.

## [0.1.1] - 2026-11-23

Download and open rolecard without git or a terminal.

- Double-click launchers: `Iniciar rolecard.bat` (Windows), `Iniciar rolecard.command`
  (macOS) and `start.sh` (Linux). They check for Python 3.12+, prepare rolecard the
  first time and open it in your browser; on Windows they offer a desktop shortcut.
- A **Quit** button in the sidebar closes rolecard.
- Opening rolecard while it is already running just opens the browser.
- The console says, in your system language, where rolecard is open and how to quit.
- `rolecard.zip` on every release, and a step-by-step guide for non-technical users
  (`docs/install.en.md`, `docs/install.es.md`).

## [0.1.0] - 2026-11-23

First public release.

- Upload your CV (PDF or DOCX) and review it as a structured profile.
- Add offers by pasting them, or find them through public job APIs (Remotive,
  Arbeitnow, Adzuna) with saved searches.
- The AI scores each offer against your profile, with what you meet and what is missing.
- Tailored CV and cover letter for each offer: every sentence cites its source in your
  profile, flagged sentences must be fixed or confirmed, and nothing is exported until
  you review it. Export to PDF, a print view or plain text.
- Board and home page to track every application, with follow-up dates.
- Use your own AI: Gemini, Ollama or any OpenAI-compatible service, or Claude Code.
- English and Spanish interface.

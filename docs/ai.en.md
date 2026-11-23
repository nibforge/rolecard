# Use your own AI

[Español](ai.es.md) · [Home](index.md)

rolecard has no AI service of its own and no account to sign up for. It uses the one you
choose: a free tier, a model on your own computer, or a plan you already pay for.

## Why your own AI

rolecard is built for a few applications done well, not for many sent blindly. Each CV
and letter is tailored to one offer, every sentence shows the fact from your profile it
comes from, you review it, and you apply yourself from the original offer. That takes
little AI: scoring 100 offers and preparing 10 CVs and 10 letters used about 92,000
input tokens and 20,000 output tokens in our measurement (below). That fits in a free
tier, and on a paid one it costs cents.

Using your own AI also means you decide where your CV goes, and you can change provider
at any time in **Settings**.

## The options

| Option | Cost | Where your data goes | How rolecard uses it |
|---|---|---|---|
| Gemini (Google AI Studio) | Free tier; pay per use if you enable billing | Google's servers | OpenAI-compatible |
| Ollama | Free | Stays on your computer (local models) | OpenAI-compatible |
| Claude Code | Your Claude plan (Pro, Max…) | Anthropic's servers | Claude Code |
| OpenAI API | Pay per use | OpenAI's servers | OpenAI-compatible |
| Anthropic API | Pay per use | Anthropic's servers | Claude Code with your key (`ANTHROPIC_API_KEY`) |
| ChatGPT plans (Codex) | — | — | Not supported |

ChatGPT plans include Codex, but there is no documented way for another app to use Codex
with your account's session, so rolecard does not.

## What is an API key?

An API key is a password that identifies your account to the AI service. Anyone who has
it can spend your allowance or your credit. So:

- **Never share it**, not in screenshots and not in messages.
- **Never upload it anywhere**: not to a repository, a forum or a shared document.
- **If it leaks, revoke it** on the provider's website and create a new one.

rolecard keeps the key in `config.toml`, inside your data folder (`~/.rolecard`, or the
one you set with `ROLECARD_HOME`), never in the code or the repository. If you would
rather not keep it in that file, leave the field empty and put the key in the
`ROLECARD_OPENAI_API_KEY` environment variable.

Claude Code with your plan and Ollama use no key: Claude Code uses the session signed in on your
computer, and Ollama runs on your own machine.

## Set up Gemini (free)

You need a Google account (a Gmail one works). If you have none, create it first at
[Google](https://accounts.google.com/signup).

1. Go to [Google AI Studio](https://aistudio.google.com/) and sign in with your Google
   account.
2. The first time, AI Studio asks you to accept its terms of service. Accept them: for
   new accounts it then creates a default project and key.
3. Open the **API Keys** page ([aistudio.google.com/api-keys](https://aistudio.google.com/api-keys)).
   If you already see a key in the list, skip the next step.
4. If there is none, press **Create API key**. If you already used Google Cloud and have
   no project in AI Studio, import it first: in **Projects**, **Import projects**, pick
   the project and press **Import**. When done, the key shows in the table next to its
   project.
5. Open the key and copy all of it. Keep it only where you will use it.
6. Check that billing is not on: on the projects page
   ([aistudio.google.com/projects](https://aistudio.google.com/projects)), the **Billing
   Tier** column should show the free tier (**Free**) or **Set up billing**. With no
   billing account linked, Google cannot charge you anything.
7. In rolecard, open **Settings** and choose **OpenAI-compatible**. Fill in:
   - **Service address**: `https://generativelanguage.googleapis.com/v1beta/openai`
   - **Model**: `gemini-3.5-flash-lite`
   - **API key**: paste your key (or leave it empty and set the
     `ROLECARD_OPENAI_API_KEY` environment variable).
8. Press **Save settings**, then **Test connection**. If all is well, you see
   "Connection OK with…" and the provider's name.

**Revoking the key.** Google says to disable or delete it on the credentials page of the
[Google Cloud console](https://console.cloud.google.com/apis/credentials), and to create
a new one if the old one leaked. The AI Studio docs do not describe a delete button on
its own site. Source: [Gemini API keys](https://aistudio.google.com/docs/api-key).

We recommend `gemini-3.5-flash-lite`: it answered all four operations correctly on the
first try. `gemini-3.8-flash` also works, but its free tier allowed only 20 requests a
day in our test, not enough to score 100 offers. `gemini-2.5-flash` is no longer
available to new accounts.

**Free-tier limits.** Google sets daily and per-minute limits per project, shown in AI
Studio and on its [rate limits page](https://ai.google.dev/gemini-api/docs/rate-limits).
When you reach one, rolecard tells you and, when Google says how long to wait, when to
try again. It sends one request and does not retry in a loop, and scoring in bulk stops
at the first error, so a used-up limit does not burn more requests. Gemini sometimes
answers "high demand" (HTTP 503) when its servers are busy: rolecard does not retry that
either; try again a few minutes later.

**Privacy on the free tier.** On the free tier, Google uses what you send and the answers
to improve its products and AI, and human reviewers may read them (disconnected from
your account); Google asks you not to send personal or confidential information.
**Exception:** in the European Economic Area, Switzerland and the United Kingdom, the
paid-service terms apply to all use, the free tier included, and under them your data is
not used to improve products. Elsewhere, enabling billing gives you those terms. There
is no other switch. Source: [Gemini API terms](https://ai.google.dev/gemini-api/terms),
"How Google Uses Your Data".

## Set up Ollama (local, free)

1. Download Ollama from its [download page](https://ollama.com/download) and install
   it:
   - **Windows**: run `OllamaSetup.exe`. It needs no administrator rights and keeps
     running in the background.
   - **macOS**: open `ollama.dmg` and drag Ollama to **Applications**.
   - **Linux**: in a terminal, `curl -fsSL https://ollama.com/install.sh | sh`.

   Requirements for each system: [Windows](https://docs.ollama.com/windows),
   [macOS](https://docs.ollama.com/macos), [Linux](https://docs.ollama.com/linux).
2. Pick a model in the [Ollama library](https://ollama.com/library) and download it
   with `ollama pull <model>`. Models take several GB and need memory: read what its
   page says before you choose. We have not measured any with rolecard.
3. Check that it works with `ollama run <model>`: a chat opens; type something, see that
   it answers, and leave with `/bye`. On Linux, if it is not running, start it with
   `ollama serve`. Ollama listens on `http://localhost:11434`.
4. In **Settings**, choose **OpenAI-compatible**:
   - **Service address**: `http://localhost:11434/v1`
   - **Model**: the same name you used in `ollama pull`
   - **API key**: leave it empty; with local models Ollama does not ask for one.
5. **Save settings**, then **Test connection**.

Sources: [Ollama quickstart](https://docs.ollama.com/quickstart),
[OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility).

With local models, Ollama does not collect, store or send your prompts or answers. Its
"cloud" models are different: they run on Ollama's servers. Sources:
[Ollama privacy](https://ollama.com/privacy), [Ollama FAQ](https://docs.ollama.com/faq).
How fast and how good the answers are depends on your computer and the model; we have
not measured it.

## Set up Claude Code (with your plan)

There is **no key to copy** here: Claude Code is a program you install on your computer
and sign in to with your Claude account. rolecard runs it and uses that session.

1. **Requirements.** A [Claude plan](https://claude.com/pricing) that includes Claude
   Code (Pro, Max, Team, Enterprise…). The free claude.ai plan does not include it.
2. **Install it** with the official installer. Open a terminal and run:
   - macOS and Linux:
     ```
     curl -fsSL https://claude.ai/install.sh | bash
     ```
   - Windows, in **PowerShell**:
     ```
     irm https://claude.ai/install.ps1 | iex
     ```
   - Windows, in **Command Prompt** (CMD):
     ```
     curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
     ```
   On Windows you do not need to be an administrator. If PowerShell says `&&` is not
   valid, you are in PowerShell with the CMD command (or the other way round if it says
   `irm` is not recognized): use the other one.
3. **Sign in.** Close and reopen the terminal, type `claude` and follow the prompts: the
   browser opens so you can sign in with your Claude account. When done, you are back
   in the terminal with the session signed in; you can close it now.
4. **Check it** with `claude --version`, which shows the installed version, or with
   `claude doctor`, which checks the install without opening a session.
5. In rolecard, open **Settings** and choose **Claude Code** (or **Automatic**, which
   uses it when no OpenAI-compatible service is set up). Next to it you should see
   "Found on this computer." Press **Save settings**, then **Test connection**.

**With an Anthropic API key (pay per use).** Claude Code also works with a Claude
Console account, which charges each request instead of using a plan. Put your key in the
`ANTHROPIC_API_KEY` environment variable before starting rolecard and choose **Claude
Code** in **Settings**. rolecard neither stores nor reads that key: it only lets it reach
Claude Code, like the other `ANTHROPIC_*` variables
([SECURITY.md](https://github.com/nibforge/rolecard/blob/main/SECURITY.md)). If it is
set, Claude Code may use it instead of your plan; remove it if you prefer the
subscription. We have not measured its usage. Source: [installing Claude Code](https://code.claude.com/docs/en/setup),
"Authenticate".

Sources: [installing Claude Code](https://code.claude.com/docs/en/setup),
[quickstart](https://code.claude.com/docs/en/quickstart).

rolecard runs it with no tools, in safe mode, in an empty temporary folder
([SECURITY.md](https://github.com/nibforge/rolecard/blob/main/SECURITY.md)). It uses your
plan's allowance, not a per-token price. Whether Anthropic may train on your sessions
depends on the "Help improve Claude" setting in your
[privacy settings](https://claude.ai/settings/data-privacy-controls). Sources:
[Claude Code data usage](https://code.claude.com/docs/en/data-usage),
[how long Anthropic keeps your data](https://privacy.claude.com/en/articles/10023548-how-long-do-you-store-my-data).

## Set up the OpenAI API (pay per use)

The OpenAI API **is not ChatGPT**: it has its own account and its own billing, and
paying for ChatGPT (Plus or another plan) does not include API usage
([source](https://help.openai.com/en/articles/8156019)).

1. Go to the [OpenAI developer platform](https://platform.openai.com/) and create an
   account or sign in.
2. **Add credit.** On the billing page
   ([Billing](https://platform.openai.com/settings/organization/billing)), press **Add
   payment details**, enter your payment method and choose the first amount (the
   minimum is $5). Automatic top-up (**Use auto-reload**) comes switched on: turn it off
   if you do not want it to top up on its own. Later, **Buy credits** or **Add to credit
   balance** adds more. Source: [prepaid billing](https://help.openai.com/en/articles/8264644-how-can-i-set-up-prepaid-billing).
3. **Set a spending limit.** In [Limits](https://platform.openai.com/settings/organization/limits),
   under **Spend**, press **Edit spend limit**, type your cap in **Monthly spend limit**,
   turn on **Enforce a hard limit** and press **Save**. OpenAI warns that the cut-off is
   not instant and spending may go slightly over. Source: [spend limits](https://developers.openai.com/api/docs/guides/spend-limits).
4. **Create the key** on the [API keys](https://platform.openai.com/api-keys) page. Copy
   the key as soon as it appears: do not count on seeing it again later; if you lose
   it, create another.
5. In rolecard, open **Settings** and choose **OpenAI-compatible**: **Service address**
   `https://api.openai.com/v1`, the **Model** you want from the ones OpenAI lists and,
   in **API key**, your key.
6. **Save settings**, then **Test connection**.

**Revoking the key.** OpenAI says to rotate it from the same **API keys** page: create a
new one and revoke the old one once the new one works. Source: [API key safety](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety).

OpenAI does not train on API data unless you opt
in, and keeps it for up to 30 days to monitor abuse. Source:
[OpenAI: your data](https://developers.openai.com/api/docs/guides/your-data). We have not
measured its usage.

## What we measured

Measured on 2026-11-22 with `scripts/measure_usage.py` and the fictional demo data. The
tokens are the ones each provider reported in its answers; nothing is estimated.

| Operation | Gemini 3.5 Flash-Lite (input / output) | Claude Code 2.1.330 (input / output) |
|---|---|---|
| Read the CV | 534 / 351 | 3,079 / 514 |
| Score an offer | 750 / 111 | 3,335 / 232 |
| Tailored CV | 888 / 539 | 3,575 / 549 |
| Cover letter | 785 / 304 | 3,418 / 662 |

Gemini's output includes its "thinking" tokens. Most of Claude Code's input is the CLI's
own context, not rolecard's prompt.

Cost of 100 offers with Gemini 3.5 Flash-Lite, at the official paid price of $0.30 per
million input tokens and $2.50 per million output tokens
([pricing](https://ai.google.dev/gemini-api/docs/pricing), checked on 2026-11-22):

| Case | Requests | Tokens (input / output) | Paid tier | Free tier |
|---|---|---|---|---|
| 100 scores + 10 CVs + 10 letters | 120 | 91,730 / 19,530 | $0.08 | $0 |
| 100 scores + 100 CVs + 100 letters | 300 | 242,300 / 95,400 | $0.31 | $0 |

Claude Code has no price in dollars: it uses your plan's allowance, which Anthropic does
not express in tokens. Run the script yourself to measure your own provider.

## Common problems

- **"The key cannot contain spaces or line breaks, nor be longer than 500 characters."**
  A space or a line break slipped into the key when you copied it. rolecard removes the
  ones at the start and the end, but not those in the middle: copy the whole key again,
  in one go, and paste it again.
- **Test connection fails.** The test uses the saved settings: press **Save settings**
  first. If you see "The AI service rejected the request. Check the address, model and
  key.", check those three fields letter by letter. If you see "Cannot reach the AI
  service. Check that it is running and the address is right.", check your connection
  or, with Ollama, that it is running.
- **"The AI service's usage limit is used up…"** You reached the free tier's limit
  (usually a daily one). rolecard does not retry; when Google says how long to wait, the
  message tells you. Try again later.
- **"The AI service is busy right now…"** Gemini answered "high demand" (HTTP 503): its
  servers are busy. It is not a problem with your key. rolecard does not retry: try
  again in a few minutes.
- **Claude Code not signed in.** If you see "The AI could not answer. Check that it
  works and that you are signed in.", open a terminal, run `claude` and sign in. If you
  see "Claude Code is not installed or not on the PATH…", reopen the terminal after
  installing it or read the [install troubleshooting
  guide](https://code.claude.com/docs/en/troubleshoot-install).

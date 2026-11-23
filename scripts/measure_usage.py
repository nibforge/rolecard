"""Measure the real token usage of each AI operation with the demo data.

    python scripts/measure_usage.py openai --base-url URL --model MODEL
    python scripts/measure_usage.py claude
    ... [--price-in USD --price-out USD] [--docs N]

It runs the four operations (read a CV, score every demo offer, write a CV, write a
cover letter) against a real provider and reads the token counts the provider itself
reports (``usage`` in an OpenAI-compatible answer, the JSON envelope of ``claude -p``).
Nothing is estimated: an operation whose usage the provider does not report is shown as
unmeasured. With prices per million tokens it also gives the cost of 100 offers
(100 scores + N CVs and N letters).

The API key is read from ``ROLECARD_OPENAI_API_KEY`` and never printed. Only fictional
demo data is sent: no real profile, no real offer.
"""

from __future__ import annotations

import argparse
import http.client
import io
import json
import os
import sys
import time
import urllib.error
from collections.abc import Callable
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make ``rolecard`` and ``scripts`` importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rolecard.ai import AIError, AIProvider
from rolecard.ai.claude_code import ClaudeCodeProvider, run_tree
from rolecard.ai.doc_schema import CV_SCHEMA, LETTER_SCHEMA
from rolecard.ai.openai_compat import _NO_REDIRECT_OPENER, OpenAICompatibleProvider
from rolecard.ai.prompts import cv_prompt, letter_prompt, profile_prompt, score_prompt
from rolecard.config import ENV_API_KEY
from rolecard.services.profile_schema import PROFILE_SCHEMA
from rolecard.services.scoring import SCORE_SCHEMA
from scripts.demo_data import OFFERS, PROFILE, offer_text

OFFERS_FOR_COST = 100
RETRY_WAITS = (15, 30, 60, 120)  # seconds, for a 503 or a dropped connection


def demo_cv_text(profile: dict = PROFILE) -> str:
    """The demo profile written out as the plain text a PDF CV would give."""
    basics = profile["basics"]
    lines = [basics["name"], basics["headline"], basics["email"], basics["location"],
             *basics["links"], "", "Summary", basics["summary"], "", "Experience"]
    for job in profile["experience"]:
        end = job["end"] or "present"
        lines.append(f"{job['role']}, {job['company']} ({job['start']}-{end}), "
                     f"{job['location']}")
        lines += [f"- {item}" for item in job["highlights"]]
    lines += ["", "Projects"]
    for project in profile["projects"]:
        lines.append(f"{project['name']}: {project['description']}")
        lines += [f"- {item}" for item in project["highlights"]]
    lines += ["", "Education"]
    lines += [f"{e['degree']}, {e['institution']} ({e['start']}-{e['end']})"
              for e in profile["education"]]
    lines += ["", "Languages"]
    lines += [f"{lang['language']}: {lang['level']}" for lang in profile["languages"]]
    lines += ["", "Skills", ", ".join(profile["skills"])]
    return "\n".join(lines)


def _openai_usage(raw: bytes) -> dict | None:
    try:
        usage = json.loads(raw.decode("utf-8")).get("usage") or {}
        prompt = int(usage["prompt_tokens"])
        # total - prompt also counts the "thinking" tokens some models bill as output
        output = int(usage.get("total_tokens", 0)) - prompt
        output = max(output, int(usage.get("completion_tokens", 0)))
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    return {"input": prompt, "output": output}


def _busy(exc: Exception) -> bool:
    """A temporary failure worth retrying: the server is overloaded or hung up."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 503
    return isinstance(exc, http.client.RemoteDisconnected)


def recording_opener(sink: list, inner: Callable, waits: tuple = RETRY_WAITS,
                     sleep: Callable = time.sleep) -> Callable:
    """An ``opener`` for ``OpenAICompatibleProvider`` that notes the reported usage and
    retries a busy server after each of ``waits`` seconds."""
    def open_(req, timeout):
        for wait in (*waits, None):
            try:
                with inner(req, timeout=timeout) as resp:
                    raw = resp.read()
                break
            except (urllib.error.HTTPError, http.client.RemoteDisconnected) as exc:
                if wait is None or not _busy(exc):
                    raise
                sleep(wait)
        sink.append(_openai_usage(raw))
        return io.BytesIO(raw)
    return open_


def _claude_usage(stdout: str) -> dict | None:
    try:
        envelope = json.loads(stdout)
        usage = envelope["usage"]
        prompt = sum(int(usage.get(key, 0)) for key in (
            "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        result = {"input": prompt, "output": int(usage["output_tokens"])}
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    if isinstance(envelope.get("total_cost_usd"), int | float):
        result["reported_cost_usd"] = float(envelope["total_cost_usd"])
    return result


def recording_runner(sink: list, inner: Callable = run_tree) -> Callable:
    """A ``runner`` for ``ClaudeCodeProvider`` that notes the usage in the envelope."""
    def run(cmd, **kwargs):
        proc = inner(cmd, **kwargs)
        sink.append(_claude_usage(proc.stdout or "") if proc.returncode == 0 else None)
        return proc
    return run


def operations() -> list[tuple[str, str, dict]]:
    """(operation, prompt, schema) for every call the measurement makes."""
    first = offer_text(*OFFERS[0][:3], OFFERS[0][7])
    calls = [("read_cv", profile_prompt(demo_cv_text()), PROFILE_SCHEMA)]
    calls += [("score", score_prompt(PROFILE, offer_text(*row[:3], row[7]), "en"),
               SCORE_SCHEMA) for row in OFFERS]
    calls.append(("cv", cv_prompt(PROFILE, first, "en"), CV_SCHEMA))
    calls.append(("letter", letter_prompt(PROFILE, first, "en"), LETTER_SCHEMA))
    return calls


def measure(provider: AIProvider, sink: list) -> list[dict]:
    """Run every operation once; each row: operation, status and the reported usage."""
    rows = []
    for name, prompt, schema in operations():
        before = len(sink)
        row = {"operation": name, "status": "ok"}
        try:
            provider.complete_json(prompt, schema)
        except AIError as exc:  # code and detail only: never the answer (it may quote a CV)
            row.update(status=exc.code, detail=exc.detail[:200])
        usages = [u for u in sink[before:] if u is not None]
        row["calls"] = len(sink) - before
        if usages and len(usages) == len(sink) - before:
            row["input"] = sum(u["input"] for u in usages)
            row["output"] = sum(u["output"] for u in usages)
        rows.append(row)
    return rows


def summarize(rows: list[dict]) -> dict:
    """Mean input and output tokens per operation (only the measured rows)."""
    summary = {}
    for name in dict.fromkeys(row["operation"] for row in rows):
        measured = [r for r in rows if r["operation"] == name and "input" in r]
        if measured:
            summary[name] = {
                "runs": len(measured),
                "input": round(sum(r["input"] for r in measured) / len(measured)),
                "output": round(sum(r["output"] for r in measured) / len(measured)),
            }
    return summary


def cost_of_100(summary: dict, price_in: float, price_out: float, docs: int) -> dict | None:
    """USD for 100 scores plus ``docs`` CVs and letters, prices per million tokens."""
    if not all(op in summary for op in ("score", "cv", "letter")):
        return None
    counts = {"score": OFFERS_FOR_COST, "cv": docs, "letter": docs}
    tokens_in = sum(summary[op]["input"] * n for op, n in counts.items())
    tokens_out = sum(summary[op]["output"] * n for op, n in counts.items())
    usd = (tokens_in * price_in + tokens_out * price_out) / 1_000_000
    return {"offers": OFFERS_FOR_COST, "documents": docs, "input_tokens": tokens_in,
            "output_tokens": tokens_out, "usd": round(usd, 4)}


def build_provider(args, sink: list, opener: Callable | None = None,
                   runner: Callable | None = None) -> AIProvider:
    if args.provider == "claude":
        return ClaudeCodeProvider(timeout=args.timeout,
                                  runner=recording_runner(sink, runner or run_tree))
    return OpenAICompatibleProvider(
        args.base_url, args.model, os.environ.get(ENV_API_KEY, ""), args.timeout,
        opener=recording_opener(sink, opener or _NO_REDIRECT_OPENER.open))


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("provider", choices=("openai", "claude"))
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--price-in", type=float, help="USD per million input tokens")
    parser.add_argument("--price-out", type=float, help="USD per million output tokens")
    parser.add_argument("--docs", type=int, default=10,
                        help="CVs and letters counted in the cost of 100 offers")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, opener: Callable | None = None,
         runner: Callable | None = None) -> int:
    args = parse_args(argv)
    sink: list = []
    try:
        provider = build_provider(args, sink, opener, runner)
    except AIError as exc:
        print(f"error: {exc.code}", file=sys.stderr)
        return 2
    rows = measure(provider, sink)
    summary = summarize(rows)
    report = {"provider": args.provider, "model": args.model or None, "rows": rows,
              "per_operation": summary}
    if args.price_in is not None and args.price_out is not None:
        report["cost_of_100_offers"] = cost_of_100(summary, args.price_in, args.price_out,
                                                   args.docs)
    print(json.dumps(report, indent=2))
    return 0 if all(row["status"] == "ok" for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())

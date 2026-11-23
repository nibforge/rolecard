"""Structured output, the one-fence parser tolerance and UTF-8 end to end."""

import io
import json
import sys
import urllib.error

import pytest

from rolecard import get_db
from rolecard.ai import AIError
from rolecard.ai.base import PING_SCHEMA, parse_json_object
from rolecard.ai.claude_code import ClaudeCodeProvider, run_tree
from rolecard.ai.openai_compat import OpenAICompatibleProvider
from rolecard.ai.schema import to_json_schema
from rolecard.encoding import fix_mojibake
from rolecard.services.profile import get_profile
from tests.helpers import PROFILE, make_pdf

F = "`" * 3
OBJ = '{"ok": true}'


@pytest.mark.parametrize("raw", [
    OBJ, f"\n  {OBJ}  \n", f"{F}json\n{OBJ}\n{F}", f"{F}\n{OBJ}\n{F}", f"{F}JSON\r\n{OBJ}\r\n{F}",
    f"{F}json\n{OBJ}{F}", f"  {F}json {OBJ} {F}\n",
])
def test_parser_accepts_clean_json_or_one_fence(raw):
    assert parse_json_object(raw) == {"ok": True}


@pytest.mark.parametrize("raw", [
    f"Here is the profile:\n{F}json\n{OBJ}\n{F}",
    f"{F}json\n{OBJ}\n{F}\nHope it helps!",
    f"Sure: {OBJ}",
    f"{F}json\n{OBJ}\n{F}\n{F}json\n{OBJ}\n{F}",
    f"{F}python\n{OBJ}\n{F}",
])
def test_parser_rejects_prose_or_more_than_one_block(raw):
    with pytest.raises(AIError) as info:
        parse_json_object(raw)
    assert info.value.code == "not_json"


def test_schema_converts_to_standard_json_schema():
    schema = {"type": "object", "properties": {"a": {"type": "string", "nullable": True},
              "b": {"type": "array", "items": {"type": ["string", "integer"]}}}}
    out = to_json_schema(schema)
    assert out["additionalProperties"] is False
    assert out["properties"]["a"] == {"type": ["string", "null"]}
    assert out["properties"]["b"]["items"]["type"] == ["string", "integer"]


class Opener:
    def __init__(self, *outcomes):
        self.outcomes, self.bodies = list(outcomes), []

    def __call__(self, req, timeout):
        self.bodies.append(json.loads(req.data))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": outcome}}]}).encode())


def _http(code):
    return urllib.error.HTTPError("u", code, "no", {}, None)


def test_openai_asks_for_the_json_schema():
    opener = Opener(OBJ)
    OpenAICompatibleProvider("http://x/v1", "m", opener=opener).check()
    fmt = opener.bodies[0]["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["schema"] == to_json_schema(PING_SCHEMA)


def test_openai_falls_back_to_json_object_when_schema_unsupported():
    opener = Opener(_http(400), OBJ)
    OpenAICompatibleProvider("http://x/v1", "m", opener=opener).check()
    assert [b["response_format"]["type"] for b in opener.bodies] == ["json_schema", "json_object"]


def test_openai_does_not_retry_other_http_errors():
    opener = Opener(_http(401), OBJ)
    with pytest.raises(AIError):
        OpenAICompatibleProvider("http://x/v1", "m", opener=opener).check()
    assert len(opener.bodies) == 1


def test_claude_gets_a_json_only_system_prompt():
    seen = []
    provider = ClaudeCodeProvider(executable="claude", runner=lambda cmd, **kw: seen.append(cmd))
    with pytest.raises(AttributeError):
        provider.complete("p")
    cmd = seen[0]
    assert "JSON" in cmd[cmd.index("--append-system-prompt") + 1]
    assert cmd[cmd.index("--output-format") + 1] == "json"


def test_fix_mojibake_repairs_only_double_encoded_runs():
    assert fix_mojibake("TÃ©cnico, AÃ±o, Â¿quÃ©? Â¡sÃ\xad!") == "Técnico, Año, ¿qué? ¡sí!"
    assert fix_mojibake("Técnico y TÃ©cnico") == "Técnico y Técnico"
    assert fix_mojibake("Ã ver: niño, ¿qué? ¡ya!") == "Ã ver: niño, ¿qué? ¡ya!"


def test_utf8_from_the_claude_subprocess_reaches_the_saved_profile(client, csrf, app):
    data = json.loads(json.dumps(PROFILE))
    data["basics"].update(headline="Técnico de soporte", summary="¿Año? ¡España!")
    stdout = json.dumps({"type": "result", "is_error": False,
                         "result": f"{F}json\n{json.dumps(data, ensure_ascii=False)}\n{F}"},
                        ensure_ascii=False).encode("utf-8")
    script = f"import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write({stdout!r})"

    def runner(cmd, **kwargs):  # a real child process writing raw UTF-8 bytes
        return run_tree([sys.executable, "-c", script], **kwargs)

    provider = ClaudeCodeProvider(executable="claude", runner=runner)
    app.config["AI_PROVIDER_FACTORY"] = lambda: provider
    client.post("/profile/upload", data={"csrf_token": csrf, "cv": (io.BytesIO(make_pdf()),
                "cv.pdf")}, content_type="multipart/form-data")
    with app.app_context():
        basics = get_profile(get_db()).data["basics"]
    assert basics["headline"] == "Técnico de soporte"
    assert basics["summary"] == "¿Año? ¡España!"


def test_cv_text_with_mojibake_is_repaired_before_the_ai_sees_it():
    from rolecard.services.profile import extract_text
    from tests.helpers import make_docx

    lines = ["Ana Test Example", "TÃ©cnico de soporte en EspaÃ±a"]
    text = extract_text("cv.docx", make_docx(lines))
    assert "Técnico de soporte en España" in text


def test_openai_last_try_sends_no_response_format():
    opener = Opener(_http(400), _http(422), OBJ)
    OpenAICompatibleProvider("http://x/v1", "m", opener=opener).check()
    assert [b.get("response_format", {}).get("type") for b in opener.bodies] == [
        "json_schema", "json_object", None]

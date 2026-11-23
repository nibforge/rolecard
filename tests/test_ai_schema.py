import pytest

from rolecard.ai.schema import SchemaError, validate

SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "summary": {"type": "string", "maxLength": 20},
        "lang": {"type": "string", "enum": ["en", "es"]},
        "met": {"type": "array", "items": {"type": "string", "minLength": 1}, "maxItems": 2},
        "title": {"type": "string", "nullable": True},
        "remote": {"type": "boolean"},
    },
    "required": ["score", "summary"],
}


def test_accepts_a_matching_object():
    validate({"score": 70, "summary": "ok", "lang": "es", "met": ["a"], "title": None,
              "remote": False}, SCHEMA)


@pytest.mark.parametrize(
    ("value", "where"),
    [
        ([], "$"),
        ({"score": 70}, "$.summary"),
        ({"score": 70, "summary": "ok", "hack": 1}, "$.hack"),
        ({"score": 150, "summary": "ok"}, "$.score"),
        ({"score": -1, "summary": "ok"}, "$.score"),
        ({"score": "70", "summary": "ok"}, "$.score"),
        ({"score": 70.0, "summary": "ok"}, "$.score"),
        ({"score": True, "summary": "ok"}, "$.score"),
        ({"score": 70, "summary": "x" * 21}, "$.summary"),
        ({"score": 70, "summary": "ok", "lang": "fr"}, "$.lang"),
        ({"score": 70, "summary": "ok", "met": ["a", "b", "c"]}, "$.met"),
        ({"score": 70, "summary": "ok", "met": [""]}, "$.met[0]"),
        ({"score": 70, "summary": "ok", "met": "a"}, "$.met"),
        ({"score": 70, "summary": None}, "$.summary"),
        ({"score": 70, "summary": "ok", "remote": 1}, "$.remote"),
    ],
)
def test_rejects_anything_else(value, where):
    with pytest.raises(SchemaError) as info:
        validate(value, SCHEMA)
    assert info.value.path == where


def test_nested_objects_are_closed_too():
    schema = {"type": "object", "properties": {"a": {"type": "object", "properties": {}}}}
    with pytest.raises(SchemaError):
        validate({"a": {"x": 1}}, schema)


def test_unknown_keywords_are_a_programming_error():
    with pytest.raises(ValueError, match="unsupported"):
        validate("x", {"type": "string", "pattern": "x"})


def _cv(**changes):
    answer = {"summary": [{"text": "Backend dev.", "sources": ["basics.headline"]}],
              "experience": [{"index": 0, "highlights": [{"text": "Built APIs",
                                                           "sources": []}]}],
              "projects": [], "skills": [0, 1]}
    answer.update(changes)
    return answer


def test_cv_and_letter_schemas_accept_good_answers():
    from rolecard.ai.doc_schema import CV_SCHEMA, LETTER_SCHEMA
    validate(_cv(), CV_SCHEMA)
    validate({"paragraphs": [[{"text": "Hi", "sources": ["offer"]}]]}, LETTER_SCHEMA)


@pytest.mark.parametrize("changes", [
    {"summary": [{"text": "x"}]},
    {"summary": [{"text": "", "sources": []}]},
    {"summary": [{"text": "x" * 401, "sources": []}]},
    {"summary": [{"text": "x", "sources": ["a" * 81]}]},
    {"summary": [{"text": "x", "sources": [], "state": "sourced"}]},
    {"experience": [{"index": -1, "highlights": []}]},
    {"experience": [{"index": "0", "highlights": []}]},
    {"skills": [True]},
    {"name": "Invented Name"},
])
def test_cv_schema_rejects_bad_answers(changes):
    from rolecard.ai.doc_schema import CV_SCHEMA
    with pytest.raises(SchemaError):
        validate(_cv(**changes), CV_SCHEMA)


@pytest.mark.parametrize("answer", [
    {"paragraphs": []},
    {"paragraphs": [[{"text": "x", "sources": []}]] * 6},
    {"paragraphs": [[{"text": "x", "sources": []}]], "greeting": "Dear"},
])
def test_letter_schema_rejects_bad_answers(answer):
    from rolecard.ai.doc_schema import LETTER_SCHEMA
    with pytest.raises(SchemaError):
        validate(answer, LETTER_SCHEMA)


def test_find_errors_lists_every_problem_with_path_and_code():
    from rolecard.ai.schema import find_errors

    problems = find_errors({"score": "x", "summary": None, "met": ["", "b", "c"], "extra": 1},
                           SCHEMA)
    found = {(p.path, p.code) for p in problems}
    assert found == {("$.extra", "unexpected"), ("$.score", "type"), ("$.summary", "null"),
                     ("$.met", "too_many"), ("$.met[0]", "too_short")}


def test_a_list_of_types_accepts_any_of_them():
    schema = {"type": ["string", "integer"]}
    validate("2019", schema)
    validate(2019, schema)
    with pytest.raises(SchemaError):
        validate(True, schema)

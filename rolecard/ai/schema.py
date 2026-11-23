"""Strict validator for the small JSON-schema subset the AI answers use.

Supported keywords: ``type`` (object, array, string, integer, boolean, or a list of
them), ``properties``,
``required``, ``items``, ``minItems``, ``maxItems``, ``minLength``, ``maxLength``,
``enum``, ``minimum``, ``maximum`` and ``nullable``. Objects are ALWAYS closed: a key
that is not in ``properties`` is an error. Anything that does not match is rejected
whole; nothing is coerced. ``find_errors`` lists every problem; ``validate`` raises the
first one.
"""

from __future__ import annotations

_KNOWN = frozenset(
    {"type", "properties", "required", "items", "minItems", "maxItems", "minLength",
     "maxLength", "enum", "minimum", "maximum", "nullable"}
)

# Problem codes (``SchemaError.code``) and their English wording for logs.
PROBLEMS = {
    "null": "must not be null",
    "type": "has the wrong type",
    "unexpected": "is not an expected field",
    "required": "is required",
    "too_few": "has too few items",
    "too_many": "has too many items",
    "too_short": "is too short",
    "too_long": "is too long",
    "too_small": "is below the minimum",
    "too_large": "is above the maximum",
    "enum": "is not one of the allowed values",
}


class SchemaError(ValueError):
    """The value does not match the schema; ``path`` says where, ``code`` what."""

    def __init__(self, path: str, code: str) -> None:
        self.path = path or "$"
        self.code = code
        super().__init__(f"{self.path}: {PROBLEMS[code]}")


def validate(value: object, schema: dict, path: str = "$") -> None:
    """Raise ``SchemaError`` unless ``value`` matches ``schema`` exactly."""
    problems = find_errors(value, schema, path)
    if problems:
        raise problems[0]


def find_errors(value: object, schema: dict, path: str = "$") -> list[SchemaError]:
    """Every mismatch between ``value`` and ``schema`` (empty when it matches)."""
    out: list[SchemaError] = []
    _check(value, schema, path, out)
    return out


def _check(value, schema, path, out) -> None:
    unknown = set(schema) - _KNOWN
    if unknown:
        raise ValueError(f"unsupported schema keywords: {sorted(unknown)}")
    if value is None:
        if not schema.get("nullable"):
            out.append(SchemaError(path, "null"))
        return
    kinds = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
    for kind in kinds:
        if kind not in _CHECKS:
            raise ValueError(f"unsupported schema type: {kind}")
    if not any(_CHECKS[kind](value, schema, path, out) for kind in kinds):
        out.append(SchemaError(path, "type"))
        return
    if "enum" in schema and value not in schema["enum"]:
        out.append(SchemaError(path, "enum"))


def _object(value, schema, path, out) -> bool:
    if not isinstance(value, dict):
        return False
    props = schema.get("properties", {})
    for key in sorted(map(str, set(value) - set(props))):
        out.append(SchemaError(f"{path}.{key}", "unexpected"))
    for key in schema.get("required", ()):
        if key not in value:
            out.append(SchemaError(f"{path}.{key}", "required"))
    for key, item in value.items():
        if key in props:
            _check(item, props[key], f"{path}.{key}", out)
    return True


def _array(value, schema, path, out) -> bool:
    if not isinstance(value, list):
        return False
    if len(value) < schema.get("minItems", 0):
        out.append(SchemaError(path, "too_few"))
    if "maxItems" in schema and len(value) > schema["maxItems"]:
        out.append(SchemaError(path, "too_many"))
    for index, item in enumerate(value):
        _check(item, schema["items"], f"{path}[{index}]", out)
    return True


def _string(value, schema, path, out) -> bool:
    if not isinstance(value, str):
        return False
    if len(value) < schema.get("minLength", 0):
        out.append(SchemaError(path, "too_short"))
    if "maxLength" in schema and len(value) > schema["maxLength"]:
        out.append(SchemaError(path, "too_long"))
    return True


def _integer(value, schema, path, out) -> bool:
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    if "minimum" in schema and value < schema["minimum"]:
        out.append(SchemaError(path, "too_small"))
    if "maximum" in schema and value > schema["maximum"]:
        out.append(SchemaError(path, "too_large"))
    return True


def _boolean(value, schema, path, out) -> bool:
    return isinstance(value, bool)


_CHECKS = {
    "object": _object,
    "array": _array,
    "string": _string,
    "integer": _integer,
    "boolean": _boolean,
}


def to_json_schema(schema: dict) -> dict:
    """The same schema in standard JSON Schema (for providers' structured output):
    ``nullable`` becomes a ``null`` type and objects get ``additionalProperties: false``."""
    out = {k: v for k, v in schema.items() if k != "nullable"}
    kinds = list(out["type"]) if isinstance(out["type"], list) else [out["type"]]
    if schema.get("nullable"):
        kinds.append("null")
    out["type"] = kinds[0] if len(kinds) == 1 else kinds
    if "properties" in out:
        out["properties"] = {k: to_json_schema(v) for k, v in out["properties"].items()}
        out["additionalProperties"] = False
    if "items" in out:
        out["items"] = to_json_schema(out["items"])
    return out

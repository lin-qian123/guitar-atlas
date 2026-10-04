"""Lossless, dependency-free transport for the browser catalog.

The canonical JSON remains the audit/export format. This projection replaces
repeated strings and object key lists with small indices, then uses standard
gzip. The same self-contained envelope works over HTTPS and from a file origin.
No score information or translation evidence is removed.
"""

from __future__ import annotations

import base64
import binascii
import gzip
import json
import math
import zlib
from collections import Counter


CODEC = "guitar-atlas-catalog-v1"
MAX_EXPANDED_BYTES = 128 * 1024 * 1024


def pack_payload(payload: object) -> dict:
    counts: Counter[str] = Counter()

    def count(value: object) -> None:
        if isinstance(value, str):
            counts[value] += 1
        elif isinstance(value, list):
            for child in value:
                count(child)
        elif isinstance(value, dict):
            for child in value.values():
                count(child)

    count(payload)
    # Very short strings cost as much as their references and dictionary entry.
    strings = [value for value, total in counts.items() if total > 1 and len(value) > 3]
    references = {value: index for index, value in enumerate(strings)}
    shapes: list[tuple[str, ...]] = []
    shape_ids: dict[tuple[str, ...], int] = {}

    def encode(value: object) -> object:
        if isinstance(value, str):
            return references.get(value, value)
        if value is None or isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            if not math.isfinite(value):
                raise ValueError("catalog transport requires finite numbers")
            return [2, value]
        if isinstance(value, list):
            return [0, *(encode(child) for child in value)]
        if isinstance(value, dict):
            keys = tuple(value)
            if any(not isinstance(key, str) for key in keys):
                raise ValueError("catalog transport object keys must be strings")
            if keys not in shape_ids:
                shape_ids[keys] = len(shapes)
                shapes.append(keys)
            return [1, shape_ids[keys], *(encode(child) for child in value.values())]
        raise ValueError("catalog transport accepts JSON values only")

    value = encode(payload)
    body = json.dumps({"strings": strings, "shapes": shapes, "value": value},
                      ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(body) > MAX_EXPANDED_BYTES:
        raise ValueError("catalog transport exceeds its expanded size limit")
    return {"codec": CODEC, "encoding": "gzip-base64", "uncompressed_bytes": len(body),
            "payload": base64.b64encode(gzip.compress(body, compresslevel=6, mtime=0)).decode("ascii")}


def unpack_payload(payload: object) -> object:
    """Decode the transport, accepting pre-transport offline snapshots unchanged."""
    if not isinstance(payload, dict) or "codec" not in payload:
        return payload
    if (set(payload) != {"codec", "encoding", "uncompressed_bytes", "payload"}
            or payload.get("codec") != CODEC or payload.get("encoding") != "gzip-base64"):
        raise ValueError("unsupported catalog transport")
    size = payload.get("uncompressed_bytes")
    if type(size) is not int or not 0 < size <= MAX_EXPANDED_BYTES:
        raise ValueError("invalid catalog transport size")
    try:
        compressed = base64.b64decode(payload["payload"], validate=True)
        decoder = zlib.decompressobj(wbits=31)
        body = decoder.decompress(compressed, size + 1)
        if (len(body) != size or decoder.unconsumed_tail or decoder.unused_data
                or not decoder.eof):
            raise ValueError("catalog transport expanded size mismatch")
        packed = json.loads(body)
    except (binascii.Error, TypeError, zlib.error, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid catalog transport payload") from exc
    if not isinstance(packed, dict) or set(packed) != {"strings", "shapes", "value"}:
        raise ValueError("invalid catalog transport tables")
    strings, shapes = packed["strings"], packed["shapes"]
    if not isinstance(strings, list) or any(not isinstance(value, str) for value in strings):
        raise ValueError("invalid catalog transport string table")
    if (not isinstance(shapes, list) or any(not isinstance(keys, list)
            or any(not isinstance(key, str) for key in keys) or len(set(keys)) != len(keys)
            for keys in shapes)):
        raise ValueError("invalid catalog transport shape table")
    used_strings: set[int] = set()
    used_shapes: set[int] = set()

    def decode(value: object) -> object:
        if type(value) is int:
            if not 0 <= value < len(strings):
                raise ValueError("catalog transport string reference out of range")
            used_strings.add(value)
            return strings[value]
        if value is None or isinstance(value, (str, bool)):
            return value
        if not isinstance(value, list) or not value or type(value[0]) is not int:
            raise ValueError("invalid catalog transport value")
        tag = value[0]
        if tag == 0:
            return [decode(child) for child in value[1:]]
        if tag == 2 and len(value) == 2 and type(value[1]) in {int, float} and math.isfinite(value[1]):
            return value[1]
        if tag == 1 and len(value) >= 2 and type(value[1]) is int and 0 <= value[1] < len(shapes):
            used_shapes.add(value[1])
            keys = shapes[value[1]]
            if len(value) != len(keys) + 2:
                raise ValueError("catalog transport object arity mismatch")
            return {key: decode(child) for key, child in zip(keys, value[2:], strict=True)}
        raise ValueError("invalid catalog transport tag")

    result = decode(packed["value"])
    if len(used_strings) != len(strings) or len(used_shapes) != len(shapes):
        raise ValueError("catalog transport contains unused table entries")
    return result

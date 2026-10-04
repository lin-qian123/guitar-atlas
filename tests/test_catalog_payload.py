"""Browser transport preserves source evidence and verified offline guards."""

from __future__ import annotations

import base64
import gzip
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from catalog_payload import CODEC, MAX_EXPANDED_BYTES, pack_payload, unpack_payload
from tests.basic_helpers import ROOT


@pytest.mark.parametrize("value", [None, False, True, 0, -3, 0.5, "", "中文 🎸", [], {},
    [1, "Repeated string", "Repeated string", False, None],
    {"empty": {}, "array": [[], {}], "number": 12, "float": 1.25},
    {"source_id": "mutopia", "source_record_id": "1200", "title_en": "Rialto Ripples",
     "translation": {"title": {"status": "reference", "basis": "exact_source_guard", "reason": "参考对应"}},
     "local_editions": [{"category_id": 8, "unavailable_count": 1, "files": [
         {"label": "Guitar 1.pdf", "href": "sources/mutopia/objects/score.pdf"},
         {"label": "Guitar 2.pdf", "href": "sources/mutopia/objects/part.pdf"}]}],
     "offline_inputs": {"schema_version": 1, "inputs": {"sources/mutopia/catalog.json": "a" * 64}}},
    {"__proto__": {"polluted": True}, "constructor": "source string", "prototype": []},
])
def test_exact_roundtrip(value):
    packed = pack_payload(value)
    assert unpack_payload(packed) == value
    assert pack_payload(value) == packed, "mtime and dictionary ordering must be reproducible"
    assert "<" not in json.dumps(packed), "embedded payload cannot terminate a script element"


def test_legacy_offline_snapshot_passes_through():
    legacy = {"data": {"works": [], "offline_inputs": {"inputs": {}}}, "aliases": {}}
    assert unpack_payload(legacy) is legacy


@pytest.mark.parametrize("change", ["codec", "encoding", "missing", "extra", "zero_size", "size",
                                  "oversize", "corrupt", "trailing_gzip", "boolean_size"])
def test_transport_rejects_invalid_envelope(change):
    packed = pack_payload({"data": {"works": []}})
    if change == "codec": packed["codec"] = "unknown-v2"
    elif change == "encoding": packed["encoding"] = "unsupported"
    elif change == "missing": packed.pop("payload")
    elif change == "extra": packed["hidden"] = "field"
    elif change == "zero_size": packed["uncompressed_bytes"] = 0
    elif change == "size": packed["uncompressed_bytes"] += 1
    elif change == "oversize": packed["uncompressed_bytes"] = MAX_EXPANDED_BYTES + 1
    elif change == "corrupt": packed["payload"] = "not base64!"
    elif change == "boolean_size": packed["uncompressed_bytes"] = True
    else:
        packed["payload"] = base64.b64encode(base64.b64decode(packed["payload"]) + gzip.compress(b"extra")).decode()
    with pytest.raises(ValueError):
        unpack_payload(packed)


def envelope(body):
    data = json.dumps(body).encode()
    return {"codec": CODEC, "encoding": "gzip-base64", "uncompressed_bytes": len(data),
            "payload": base64.b64encode(gzip.compress(data)).decode()}


@pytest.mark.parametrize("body", [
    {"strings": [], "shapes": [], "value": 0},
    {"strings": [], "shapes": [], "value": [1, 0]},
    {"strings": [], "shapes": [["field"]], "value": [1, 0]},
    {"strings": [], "shapes": [["field", "field"]], "value": [1, 0, None, None]},
    {"strings": [1], "shapes": [], "value": None},
    {"strings": [], "shapes": [], "value": [3, 0]},
    {"strings": [], "shapes": [], "value": [2, True]},
    {"strings": [], "shapes": [], "value": 0.5},
])
def test_invalid_shapes_references_and_tags_are_rejected(body):
    with pytest.raises(ValueError):
        unpack_payload(envelope(body))


def test_packing_rejects_non_json_values():
    with pytest.raises(ValueError): pack_payload({"bad": float("nan")})
    with pytest.raises(ValueError): pack_payload({"bad": Path("private")})
    with pytest.raises(ValueError): pack_payload({1: "numeric key"})


@pytest.mark.parametrize("table", ["strings", "shapes"])
def test_unused_table_entries_cannot_hide_private_metadata(table):
    packed = {"strings": [], "shapes": [["id"]], "value": [1, 0, "public:42"]}
    # The decoded result would still match the safe canonical object exactly.
    packed[table].append("/Volumes/private/cache/secret.pdf" if table == "strings" else ["local_path"])
    with pytest.raises(ValueError, match="unused table entries"):
        unpack_payload(envelope(packed))


def test_browser_rejects_hidden_unused_strings_and_shapes():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed for cross-runtime decoder verification")
    script = """
const codec = require(process.argv[1]);
for (const table of ['strings', 'shapes']) {
  const packed = {strings: [], shapes: [['id']], value: [1, 0, 'public:42']};
  packed[table].push(table === 'strings' ? '/Volumes/private/cache/secret.pdf' : ['local_path']);
  let rejected = false;
  try { codec.unpack(packed); } catch (error) { rejected = error.message.includes('unused table entries'); }
  if (!rejected) throw Error(`hidden ${table} entry accepted`);
}
process.stdout.write('Hidden unused table entries rejected.');
"""
    result = subprocess.run([node, "-e", script, str(ROOT / "public_site/assets/catalog-codec.js")],
                            capture_output=True, text=True, check=True)
    assert "rejected" in result.stdout


def test_browser_decoder_matches_python_and_preserves_special_keys(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed for cross-runtime decoder verification")
    value = {"data": {"works": [{"id": "source:1200", "title_zh": "🎸 二重奏", "category_ids": [0, 1],
              "translation": {"title": {"status": "machine", "reason": "尚待复核"}},
              "local_editions": [{"files": [{"href": "sources/source/objects/part.pdf", "label": "Part 1"}]}]}]},
             "aliases": {}, "ranking": {}, "__proto__": {"polluted": True}}
    path = tmp_path / "transport.json"
    path.write_text(json.dumps(pack_payload(value)), encoding="utf-8")
    script = """
const fs = require('node:fs');
const codec = require(process.argv[1]);
const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
(async () => {
  const decoded = await codec.decode(input);
  if (({}).polluted || !Object.hasOwn(decoded, '__proto__')) throw Error('unsafe object reconstruction');
  if (await codec.decode(decoded) !== decoded) throw Error('legacy passthrough failed');
  process.stdout.write(JSON.stringify(decoded));
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run([node, "-e", script, str(ROOT / "public_site/assets/catalog-codec.js"), str(path)],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == value


def test_public_export_writes_safe_compact_sibling(tmp_path):
    from export_public_site import export_public_catalog
    from tests.test_public_site import make_library
    make_library(tmp_path)
    output = tmp_path / "public/data/catalog.json"
    canonical = export_public_catalog(tmp_path, output)
    compact = json.loads(output.with_name("catalog.compact.json").read_text())
    assert unpack_payload(compact) == canonical
    assert json.loads(output.read_text()) == canonical

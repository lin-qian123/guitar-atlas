from __future__ import annotations

from copy import deepcopy

from catalog_sources import (
    MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION,
    public_source_instrumentation,
)


def test_exact_musescore_placeholder_projects_native_source_names_without_counts() -> None:
    native = {
        "id": "musescore:6099968",
        "metadata": {
            "instrumentation": MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION,
            "source_instruments": [
                {"name": "Guitar", "count": 1},
                {"name": "Piano", "count": 1},
            ],
        },
    }
    original = deepcopy(native)

    assert public_source_instrumentation(native) == "Guitar；Piano"
    assert native == original


def test_exact_musescore_placeholder_without_named_declarations_returns_none() -> None:
    native = {
        "id": "musescore:6099968",
        "metadata": {
            "instrumentation": MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION,
            "source_instruments": [{"name": ""}, {"count": 3}, None],
        },
    }

    assert public_source_instrumentation(native) is None


def test_other_source_and_nonplaceholder_declarations_are_preserved_verbatim() -> None:
    declaration = "Guitar-related source declaration; file scope pending"
    other_source = {"id": "classclef:6099968", "metadata": {"instrumentation": declaration,
                                                                "source_instruments": [{"name": "Guitar"}]}}
    real_declaration = {"id": "musescore:6099968", "metadata": {"instrumentation": "Guitar (2)",
                                                                    "source_instruments": [{"name": "Piano"}]}}

    assert public_source_instrumentation(other_source) == declaration
    assert public_source_instrumentation(real_declaration) == "Guitar (2)"


def test_projection_repairs_only_source_instrumentation_detail(tmp_path) -> None:
    import hashlib
    from export_public_site import build_public_catalog
    from tests.test_catalog_instrumentation import reviewed_library
    from tests.test_public_site import write_json

    catalog, overlay = reviewed_library(tmp_path)
    native = catalog["works"][0]
    native["metadata"].update(
        instrumentation=MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION,
        license="CC0 1.0",
        source_instruments=[{"name": "Guitar", "count": 1}, {"name": "Piano", "count": 1}],
    )
    write_json(tmp_path / "sources/musescore/catalog.json", catalog)
    overlay["catalog_sha256"] = hashlib.sha256(
        (tmp_path / "sources/musescore/catalog.json").read_bytes()).hexdigest()
    write_json(tmp_path / "sources/musescore/instrumentation-review.json", overlay)
    before_native = deepcopy(catalog)

    projected = next(row for row in build_public_catalog(tmp_path)["works"] if row["source_id"] == "musescore")

    assert projected["details"]["source_instrumentation"] == "Guitar；Piano"
    assert projected["details"]["instrumentation"] == "2 guitars, violin and cello"
    assert projected["details"]["instrumentation_review"].startswith("MXL、MIDI与PDF交叉核验")
    assert projected["details"]["license"] == "CC0 1.0"
    assert catalog == before_native

    native["metadata"]["source_instruments"] = [{"count": 1}, {"name": " "}]
    write_json(tmp_path / "sources/musescore/catalog.json", catalog)
    overlay["catalog_sha256"] = hashlib.sha256(
        (tmp_path / "sources/musescore/catalog.json").read_bytes()).hexdigest()
    write_json(tmp_path / "sources/musescore/instrumentation-review.json", overlay)
    projected = next(row for row in build_public_catalog(tmp_path)["works"] if row["source_id"] == "musescore")
    assert "source_instrumentation" not in projected["details"]

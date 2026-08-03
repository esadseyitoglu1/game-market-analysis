"""contracts.py testleri — findings.json şeması ve LLM'e giden veri miktarı."""

import json

from src.discovery.base import Finding
from src.contracts import select_top_findings, build_universe_metadata, MAX_FINDINGS_FOR_LLM
from src.narrative.render import render_findings


def _make_finding(label: str, effect: float, fragile: bool = False) -> Finding:
    return Finding(
        family="tags_list_single", label=label, metric="visibility_pct",
        n=200, n_baseline=5000,
        effect=effect, effect_ci=(effect - 0.05, effect + 0.05),
        p_value=1e-10, q_value=0.001,
        direction="positive" if effect > 0 else "negative",
        group_median=0.7, baseline_median=0.6,
        confidence="high", fragile=fragile,
    )


def test_select_top_findings_respects_max():
    findings = [_make_finding(f"Tag{i}", effect=0.2 + i * 0.01) for i in range(20)]
    top = select_top_findings(findings)
    assert len(top) == MAX_FINDINGS_FOR_LLM


def test_select_top_findings_sorted_by_effect_magnitude():
    findings = [_make_finding("Weak", effect=0.21), _make_finding("Strong", effect=0.60),
                _make_finding("Medium", effect=0.35)]
    top = select_top_findings(findings, max_n=3)
    assert [f.label for f in top] == ["Strong", "Medium", "Weak"]


def test_select_top_findings_excludes_fragile():
    findings = [_make_finding("Solid", effect=0.30),
                _make_finding("Fragile", effect=0.90, fragile=True)]
    top = select_top_findings(findings, max_n=5)
    labels = [f.label for f in top]
    assert "Fragile" not in labels
    assert "Solid" in labels


def test_findings_json_schema_has_required_fields():
    findings = [_make_finding("TestTag", effect=0.35)]
    rendered = render_findings(findings)
    assert len(rendered) == 1

    required_keys = {"baslik", "claim", "evidence", "hook", "chart_path", "confidence", "fragile"}
    assert required_keys.issubset(rendered[0].keys())

    evidence = rendered[0]["evidence"]
    assert "n" in evidence and "effect" in evidence and "q_value" in evidence


def test_universe_metadata_shape():
    meta = build_universe_metadata(31991)
    assert meta["n"] == 31991
    assert "filter" in meta
    assert "metric" in meta

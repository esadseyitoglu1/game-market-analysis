"""contracts.py testleri — findings.json şeması ve LLM'e giden veri miktarı."""

import json

from src.discovery.base import Finding
from src.contracts import (
    select_top_findings, build_universe_metadata, MAX_FINDINGS_FOR_LLM,
    MAX_PER_FAMILY, NON_ACTIONABLE_FAMILIES,
)
from src.narrative.render import render_findings


def _make_finding(label: str, effect: float, fragile: bool = False, family: str = "tags_list_single") -> Finding:
    return Finding(
        family=family, label=label, metric="visibility_pct",
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


def test_select_top_findings_respects_max_per_family():
    """Aynı aileden en fazla MAX_PER_FAMILY bulgu seçilmeli — sadece |effect|
    sıralaması kullanılsaydı tek bir güçlü aile (bkz. temporal_trend, plan
    Adım A/B) tüm slotları doldurabilirdi. Havuz yeterince çeşitliyse (birden
    fazla aile, her biri yeterli sayıda), aile sınırı GERÇEKTEN uygulanmalı.
    """
    # 3 farklı aile, her birinden 3'er bulgu (havuz aile sınırını test etmeye yetecek kadar büyük)
    findings = []
    for fam in ["price_band", "categories_list_single", "peak_ccu_split"]:
        for i in range(3):
            findings.append(_make_finding(f"{fam}_{i}", effect=0.90 - i * 0.05, family=fam))

    top = select_top_findings(findings, max_n=6, max_per_family=2)
    family_counts = {}
    for f in top:
        family_counts[f.family] = family_counts.get(f.family, 0) + 1

    for fam, count in family_counts.items():
        assert count <= 2, f"{fam} ailesinden {count} bulgu seçildi, max_per_family=2 aşıldı"
    assert len(top) == 6  # 3 aile x 2 = 6, tam doldu


def test_select_top_findings_excludes_non_actionable_families_when_pool_sufficient():
    """NON_ACTIONABLE_FAMILIES'deki aileler (tags_list_single, tags_list_pair)
    LLM'e gönderilen havuzda YER ALMAMALI — bunlar 'etiket koy, görünür ol'
    tarzı tuzak bulgular (bkz. plan Adım B, kullanıcı geri bildirimi).
    Havuz yeterince büyükse (aksiyona dönüşen bulgular max_n'den fazlaysa).
    """
    actionable = [_make_finding(f"Action{i}", effect=0.50 + i * 0.01, family="price_band") for i in range(10)]
    non_actionable = [_make_finding(f"Tag{i}", effect=0.99, family="tags_list_single") for i in range(5)]

    top = select_top_findings(actionable + non_actionable, max_n=5)
    for f in top:
        assert f.family not in NON_ACTIONABLE_FAMILIES, (
            f"'{f.family}' aksiyona dönüşmeyen bir aile ama seçildi (label={f.label})"
        )


def test_select_top_findings_falls_back_to_non_actionable_when_pool_too_small():
    """Havuz FALLBACK: aksiyona dönüşen bulgu sayısı max_n'den azsa, etiket
    bulguları geri devreye girmeli — sistem asla boş/eksik rapor üretmemeli
    (bkz. plan Adım B, güvenlik dalı).
    """
    only_two_actionable = [_make_finding("Action1", effect=0.60, family="price_band"),
                            _make_finding("Action2", effect=0.55, family="peak_ccu_split")]
    tag_findings = [_make_finding(f"Tag{i}", effect=0.40 + i * 0.01, family="tags_list_single") for i in range(10)]

    top = select_top_findings(only_two_actionable + tag_findings, max_n=5)
    assert len(top) == 5  # havuz yeterli değildi, fallback devreye girip 5'e tamamladı
    tag_count = sum(1 for f in top if f.family == "tags_list_single")
    assert tag_count > 0  # fallback gerçekten tag bulgularını geri getirdi

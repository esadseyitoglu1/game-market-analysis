"""narrative/ ve contracts.py testleri.

Bu testler, üretilen metinlerin GERÇEKTEN Finding nesnesinden türediğini ve
hiçbir serbest/hardcoded iddia içermediğini doğrular — bkz. plan Context
bölümü: eski insight_engine.py'nin en büyük sorunu buydu (insight_80pct_cliff
df'i hiç okumadan iddia üretiyordu).
"""

import numpy as np
import pytest

from src.discovery.base import Finding
from src.narrative.templates import render_claim, contains_forbidden_words, FORBIDDEN_WORDS


def _make_finding(direction="positive", effect=0.35, family="tags_list_single") -> Finding:
    return Finding(
        family=family, label="Test Etiketi", metric="visibility_pct",
        n=200, n_baseline=5000,
        effect=effect, effect_ci=(0.28, 0.42),
        p_value=1e-20, q_value=0.001,
        direction=direction,
        group_median=0.75, baseline_median=0.60,
        confidence="high",
    )


def test_render_claim_direction_matches_finding():
    """Şablon seçimi finding.direction'a göre olmalı — group_median >
    baseline_median olduğunda 'daha görünür', tersinde 'daha az görünür'
    ifadesi üretilmeli (bkz. plan Adım C — gündelik dile çevrildi).
    """
    positive_finding = _make_finding(direction="positive")  # group=0.75 > baseline=0.60
    claim_pos = render_claim(positive_finding)
    assert "daha görünür" in claim_pos
    assert "daha az görünür" not in claim_pos

    negative_finding = _make_finding(direction="negative")
    negative_finding.group_median, negative_finding.baseline_median = 0.60, 0.75
    claim_neg = render_claim(negative_finding)
    assert "daha az görünür" in claim_neg


def test_render_claim_contains_all_evidence_numbers():
    """Üretilen cümlede Finding'in n değeri ve medyan farkından türeyen puan
    farkı GEÇMELİ — yani cümle gerçekten o Finding'den türemiş olmalı,
    hardcoded değil. İstatistiksel jargon (effect/ci) artık claim'de HİÇ
    geçmiyor (bkz. plan Adım C) — bunlar evidence alanında ayrıca duruyor.
    """
    finding = _make_finding()
    claim = render_claim(finding)

    assert f"{finding.n:,}" in claim
    expected_gap = round((finding.group_median - finding.baseline_median) * 100)
    assert str(abs(expected_gap)) in claim


def test_render_claim_no_statistical_jargon():
    """claim cümlesinde istatistik jargonu (etki büyüklüğü, güven aralığı,
    percentile, Spearman, p/q-değeri) HİÇ geçmemeli — editöre gidecek metin
    bu (bkz. plan Adım C, kullanıcı geri bildirimi: LLM jargonu script'e
    sadakatle aktarıyordu çünkü kaynağı claim cümlesiydi).
    """
    jargon = ["etki büyüklüğü", "güven aralığı", "percentile", "Spearman",
              "p-değeri", "q-değeri", " GA ", "effect"]
    for direction in ["positive", "negative"]:
        for family in ["tags_list_single", "tags_list_pair", "boolean_flag",
                        "categories_list_single", "price_band",
                        "achievements_split", "entity_repeat", "temporal_trend",
                        "unknown_family"]:
            finding = _make_finding(direction=direction, family=family)
            claim = render_claim(finding)
            for term in jargon:
                assert term.lower() not in claim.lower(), (
                    f"family={family} direction={direction}: jargon '{term}' claim'de bulundu: {claim}"
                )


def test_render_claim_no_forbidden_words():
    """Şablonların ürettiği hiçbir cümle yasak/abartı kelime içermemeli."""
    for direction in ["positive", "negative"]:
        for family in ["tags_list_single", "tags_list_pair", "boolean_flag",
                        "achievements_split", "entity_repeat", "unknown_family"]:
            finding = _make_finding(direction=direction, family=family)
            claim = render_claim(finding)
            forbidden = contains_forbidden_words(claim)
            assert forbidden == [], f"family={family} direction={direction}: yasak kelimeler bulundu: {forbidden}"


def test_forbidden_words_detector_works():
    """contains_forbidden_words fonksiyonunun kendisi doğru çalışıyor mu — pozitif kontrol."""
    assert "kesinlikle" in contains_forbidden_words("Bu kesinlikle doğru.")
    assert contains_forbidden_words("Bu tamamen normal bir cümle.") == []


def test_different_findings_produce_different_claims():
    """Farklı n/effect değerlerine sahip iki Finding, FARKLI cümleler üretmeli
    — yani şablon gerçekten parametrik, sabit metin değil.
    """
    f1 = _make_finding()
    f2 = _make_finding()
    f2.n = 999
    f2.effect = 0.55
    f2.effect_ci = (0.50, 0.60)

    claim1 = render_claim(f1)
    claim2 = render_claim(f2)
    assert claim1 != claim2
    assert "999" in claim2
    assert "999" not in claim1

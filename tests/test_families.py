"""discovery/families/*.py testleri — Adım 5'te eklenen yeni aileler."""

import numpy as np
import pandas as pd
import pytest

from src.discovery.families.temporal import compute_cagr, test_temporal_trend as run_temporal_trend
from src.discovery.families.studio_repeat import test_studio_repeat as run_studio_repeat
from src.discovery.families.quality_cliff import (
    test_cliff_at_80 as run_cliff_at_80,
    test_quality_trap as run_quality_trap,
)


def test_compute_cagr_handles_zero_growth_correctly():
    """Regresyon testi: eski analyzer.py'de `if cagr else None` bug'ı vardı —
    cagr==0.0 (gerçek sıfır büyüme) yanlışlıkla None'a çevriliyordu. Burada
    v_start > 0 ve v_end == v_start olduğunda cagr tam olarak 0.0 dönmeli,
    None DEĞİL.
    """
    df = pd.DataFrame({
        "tags_list": [["TestTag"]] * 20,
        "release_year": [2020] * 10 + [2024] * 10,
    })
    cagr = compute_cagr(df, "TestTag", 2020, 2024)
    assert cagr is not None
    assert cagr == 0.0


def test_compute_cagr_none_when_no_start_year_data():
    """v_start == 0 ise CAGR hesaplanamaz (sıfıra bölme), None dönmeli."""
    df = pd.DataFrame({
        "tags_list": [["TestTag"]] * 5,
        "release_year": [2024] * 5,
    })
    cagr = compute_cagr(df, "TestTag", 2020, 2024)
    assert cagr is None


def test_temporal_trend_detects_market_relative_signal():
    """Sentetik veri: pazarın TAMAMI yıllar içinde yükseliyor (genel enflasyon),
    ama bir tag pazardan FARKLI bir hızda hareket ediyor. Detrend edilmiş test
    bu göreli farkı yakalamalı — ham (detrend edilmemiş) test yakalayamazdı
    (bkz. modül docstring'i, gerçek veriyle keşfedilen confound).
    """
    rng = np.random.default_rng(0)
    rows = []
    for year in range(2016, 2025):
        # Pazar geneli yıllar içinde yükseliyor (75 -> 90 arası, genel enflasyon)
        market_level = 75 + (year - 2016) * 2
        for _ in range(200):
            rows.append({"release_year": year, "review_score": market_level + rng.normal(0, 3), "tags_list": []})
        # 'DecliningTag' pazarla YÜKSELMİYOR, sabit kalıyor -> pazara göre GÖRELİ DÜŞÜŞ
        for _ in range(30):
            rows.append({"release_year": year, "review_score": 75 + rng.normal(0, 3), "tags_list": ["DecliningTag"]})

    df = pd.DataFrame(rows)
    finding = run_temporal_trend(df, "DecliningTag", start_year=2016, end_year=2024, min_n_per_year=10)

    assert finding is not None, "Pazara göre göreli düşüş tespit edilemedi"
    assert finding.direction == "negative"


def test_studio_repeat_requires_multiple_releases():
    """Hiç tekrar-stüdyo yoksa (herkes 1 oyun yapmışsa) None dönmeli."""
    df = pd.DataFrame({
        "developers_list": [[f"Studio{i}"] for i in range(50)],
        "release_date": pd.date_range("2020-01-01", periods=50, freq="30D"),
        "visibility_pct": np.random.default_rng(0).uniform(0, 1, 50),
    })
    finding = run_studio_repeat(df, min_games=2, min_n=10)
    assert finding is None


def test_quality_cliff_functions_return_none_on_tiny_data():
    """Çok küçük evrenlerde (min_n altında) None dönmeli, hata fırlatmamalı."""
    df = pd.DataFrame({
        "is_indie": [True] * 5,
        "total_reviews": [20] * 5,
        "review_score": [85, 90, 78, 92, 88],
        "visibility_pct": [0.5, 0.6, 0.4, 0.7, 0.55],
    })
    assert run_cliff_at_80(df, min_n=100) is None
    assert run_quality_trap(df, min_n=100) is None

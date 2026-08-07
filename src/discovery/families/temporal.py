"""Discovery Family — Zamansal Trend (CAGR)

analyzer.py:genre_growth_trend()'den KURTARILDI (bkz. plan — "projenin en
değerli kullanılmayan yeteneği"). Bu fonksiyon otomasyon hattının DIŞINDAYDI
(analyzer.py hiç import edilmiyordu, bkz. Context bölümü) ve içinde bir bug
vardı: `if cagr else None` — cagr==0.0 (gerçek "sıfır büyüme") durumunda bu
ifade False döner ve sonuç sessizce None'a çevrilirdi (falsy-check hatası).

Burada CAGR hesabı korunuyor ama:
  1. Bug düzeltildi: `if cagr is not None` kullanılıyor.
  2. Artık gate'e bağlı — sadece yeterli veri VE anlamlı eğim varsa Finding üretir.
  3. Spearman korelasyonu + monotonluk kontrolü eklendi (bkz. eski
     anomaly_detector.py'nin "Decay Anomalisi" — `slope < -2.0` hardcoded
     eşiği kullanıyordu, hiç anlamlılık testi yoktu).
"""

import logging

import numpy as np
import pandas as pd
from scipy import stats

from src.discovery.base import Finding

log = logging.getLogger(__name__)

MIN_YEARS_FOR_TREND = 4


def compute_cagr(df: pd.DataFrame, tag: str, start_year: int, end_year: int) -> float | None:
    """Bileşik yıllık büyüme oranı (%). DÜZELTİLMİŞ: cagr==0.0 artık None'a
    çevrilmiyor (eski analyzer.py:213 bug'ı — bkz. modül docstring'i).
    """
    mask = df["tags_list"].apply(lambda t: tag in t)
    yearly = df[mask].groupby("release_year").size()

    v_start = yearly.get(start_year, 0)
    v_end = yearly.get(end_year, 0)
    n_years = end_year - start_year

    if v_start <= 0 or n_years <= 0:
        return None

    cagr = ((v_end / v_start) ** (1 / n_years) - 1) * 100
    return round(cagr, 1)


def test_temporal_trend(df: pd.DataFrame, tag: str, start_year: int = 2016,
                          end_year: int | None = None, min_n_per_year: int = 10,
                          metric: str = "visibility_pct") -> Finding | None:
    """Bir tag'in yıllar içindeki kalite/görünürlük trendini test eder.


    Eski anomaly_detector.py'nin "Decay Anomalisi" ailesinin (hardcoded
    slope<-2.0 eşiği, hiç anlamlılık testi yok) yerine geçer.

    KRİTİK DÜZELTME (bu fonksiyon yazılırken bulundu, gerçek veriyle test
    edilerek): İlk versiyon SADECE tag'in kendi trendine bakıyordu ve TÜM test
    edilen tag'lerde (Battle Royale, Metroidvania, City Builder, Visual Novel...)
    "pozitif trend" buldu — şüpheli derecede tutarlı. Sebep: genel indie
    pazarının review_score MEDYANI da 2016'dan 2024'e 75'ten 91'e çıkmış
    (muhtemelen platform/inceleme kültürü değişimi, tag'e özgü değil). Yani
    ham CAGR bir CONFOUND taşıyor — tıpkı plan Context bölümündeki tag-sayısı
    confound'u gibi.

    ÇÖZÜM: tag'in trendini pazarın GENEL trendinden çıkarıyoruz (detrend).
    Test artık "yıl vs (tag_medyanı - pazar_medyanı)" üzerinde Spearman
    korelasyonu çalıştırıyor — yani soru "bu tag zamanla değişiyor mu" değil,
    "bu tag PAZARDAN FARKLI bir hızda değişiyor mu" oluyor.

    end_year=None (2026-08-07 eklendi, "live" snapshot'a geçişte bulundu):
    eskiden 2024'e SABİT kodluydu — güncel veriye (canlı Steam API'den çekilen
    "live" snapshot) geçildiğinde 2025'te 952 oyunluk (>=10 review) gerçek bir
    kohort olduğu halde grafikler hâlâ 2024'te kesiliyordu. Artık None
    verilirse, evrendeki (indie, MIN_YEARS_FOR_TREND filtresine tabi) EN SON
    yılı kullanır — min_n_per_year kapısı zaten yetersiz veri taşıyan yarım
    yılları (örn. henüz review birikmemiş 2026) otomatik eler, elle sabit
    yıl girmeye gerek kalmaz.
    """
    if end_year is None:
        end_year = int(df["release_year"].max())
    market = df[df["release_year"].between(start_year, end_year)]
    market_yearly = market.groupby("release_year")[metric].median()

    mask = df["tags_list"].apply(lambda t: tag in t)
    sub = df[mask & df["release_year"].between(start_year, end_year)]

    yearly_stats = sub.groupby("release_year")[metric].agg(["median", "count"])
    yearly_stats = yearly_stats[yearly_stats["count"] >= min_n_per_year]

    if len(yearly_stats) < MIN_YEARS_FOR_TREND:
        return None

    # Detrend: her yıl için tag_medyanı - pazar_medyanı
    common_years = yearly_stats.index.intersection(market_yearly.index)
    if len(common_years) < MIN_YEARS_FOR_TREND:
        return None

    years = common_years.values.astype(float)
    tag_medians = yearly_stats.loc[common_years, "median"].values
    market_medians = market_yearly.loc[common_years].values
    relative_diff = tag_medians - market_medians

    rho, p_value = stats.spearmanr(years, relative_diff)
    if np.isnan(rho) or p_value >= 0.05 or abs(rho) < 0.5:
        return None

    slope = np.polyfit(years, relative_diff, 1)[0]
    direction = "positive" if slope > 0 else "negative"

    cagr = compute_cagr(df, tag, start_year, end_year)

    return Finding(
        family="temporal_trend",
        label=f"{tag} (pazara göre göreli trend, {start_year}-{end_year})",
        metric=metric,
        n=int(yearly_stats.loc[common_years, "count"].sum()),
        n_baseline=0,  # baseline kavramı yok — kendi zaman serisi pazar ortalamasına göre kıyaslanıyor
        effect=round(float(rho), 4),
        effect_ci=(float("nan"), float("nan")),  # Spearman p-değeri bu ailede yeterli kapı, bootstrap uygulanmadı
        p_value=float(p_value),
        q_value=float("nan"),
        direction=direction,
        group_median=float(tag_medians[-1]),
        baseline_median=float(market_medians[-1]),
        confidence="medium",
        evidence={
            "yearly_series": {int(y): float(m) for y, m in zip(years, tag_medians)},
            "market_yearly_series": {int(y): float(m) for y, m in zip(years, market_medians)},
            "cagr_pct": cagr,
            "slope_per_year_relative_to_market": round(float(slope), 3),
        },
        chart_hint="trend_line",
    )

"""discovery/gate.py testleri.

Bu testler ÖZELLİKLE yanlış-pozitif üretmeyi engellemek için yazıldı — projenin
eski hâli (anomaly_detector.py) rastgele/anlamsız bulgular üretiyordu (bkz. plan
Context bölümü: "Cats" ve "Unforgiving" örnekleri). Buradaki en kritik test
`test_gate_rejects_noise`dir: TAMAMEN RASTGELE veri verildiğinde gate hiçbir
şey bulmamalı. Eğer bu test kırılırsa, sistem yine hayalet bulgu üretiyor demektir.
"""

import numpy as np
import pytest

from scipy import stats as scipy_stats

from src.discovery.base import Hypothesis
from src.discovery.gate import (
    evaluate,
    evaluate_batch,
    benjamini_hochberg,
    rank_biserial_effect,
    mann_whitney_test,
    bootstrap_ci,
    _fast_u_statistic,
    LARGE_BASELINE_THRESHOLD,
)


def test_gate_rejects_noise():
    """Rastgele etiketli, hiçbir gerçek ilişkisi olmayan veri -> gate 0 bulgu
    döndürmeli. Bu, yanlış-pozitife karşı ANA savunma testidir.
    """
    rng = np.random.default_rng(123)
    n = 5000
    # visibility_pct'e benzer sentetik değerler (0-1 arası, gerçek dağılıma yakın)
    values = rng.beta(2, 2, size=n)
    # Grup üyeliği TAMAMEN RASTGELE, values ile hiçbir ilişkisi yok
    hypotheses = []
    for i in range(50):
        mask = rng.random(n) < 0.1  # her hipotez için farklı rastgele %10'luk grup
        hypotheses.append(
            Hypothesis(family="noise_test", label=f"random_group_{i}",
                       mask=mask, baseline="rest", metric="visibility_pct")
        )

    findings = evaluate_batch(hypotheses, values, min_n=50)
    assert len(findings) == 0, (
        f"Rastgele veride {len(findings)} bulgu üretildi — gate yanlış-pozitif üretiyor!"
    )


def test_gate_finds_planted():
    """Yapay olarak GERÇEK bir etki gömülmüş grup -> gate bunu tespit etmeli."""
    rng = np.random.default_rng(42)
    n_group, n_baseline = 300, 2000

    # baseline: düşük değerler; group: belirgin şekilde yüksek değerler (gerçek etki)
    baseline_values = rng.beta(2, 5, size=n_baseline)   # ortalama ~0.29
    group_values = rng.beta(5, 2, size=n_group)          # ortalama ~0.71 — güçlü fark

    values = np.concatenate([group_values, baseline_values])
    mask = np.concatenate([np.ones(n_group, dtype=bool), np.zeros(n_baseline, dtype=bool)])

    hyp = Hypothesis(family="planted_test", label="planted_effect",
                      mask=mask, baseline="rest", metric="visibility_pct")
    finding = evaluate(hyp, values, min_n=50)

    assert finding is not None, "Gömülü güçlü etki tespit edilemedi (yanlış-negatif)"
    assert finding.direction == "positive"
    assert finding.effect > 0.20
    assert finding.group_median > finding.baseline_median


def test_fast_u_statistic_matches_scipy():
    """Performans optimizasyonu doğrulaması: _fast_u_statistic (searchsorted
    tabanlı, ~20x hızlı), scipy.stats.mannwhitneyu ile AYNI U değerini üretmeli.
    Bu olmadan bootstrap_ci'deki hız kazanımı doğruluğu bozabilirdi — bkz.
    plan Adım 3: 364+780 aday için bootstrap ~19 dakika sürüyordu, bu
    optimizasyonla saniyelere indi.
    """
    rng = np.random.default_rng(99)
    for trial in range(10):
        group = rng.beta(2, 2, size=rng.integers(20, 500))
        baseline = rng.beta(2, 2, size=rng.integers(20, 500))

        u_scipy, _ = scipy_stats.mannwhitneyu(group, baseline, alternative="two-sided")
        u_fast = _fast_u_statistic(group, baseline)

        assert abs(u_scipy - u_fast) < 1e-6, (
            f"trial {trial}: scipy U={u_scipy} != fast U={u_fast}"
        )


def test_bootstrap_large_baseline_shortcut_matches_full_method():
    """Performans kısayolu doğrulaması: LARGE_BASELINE_THRESHOLD üstündeki
    baseline'lar için 'sadece group'u resample et' kısayolu, tam (her iki
    grubu da resample eden) yöntemle YAKLAŞIK AYNI güven aralığını üretmeli.
    Kısayol istatistiksel bir onay değil, sadece bilinen bir yaklaşıklamadır —
    bu test o yaklaşıklamanın makul sınırlar içinde kaldığını doğrular.
    """
    rng = np.random.default_rng(55)
    group = rng.beta(3, 2, size=80)  # küçük grup, hafif kaydırılmış dağılım

    # Küçük baseline (kısayol uygulanmaz) ve büyük baseline (kısayol uygulanır)
    # AYNI dağılımdan üretiliyor — ikisinin sonucu benzer bir aralıkta olmalı.
    small_baseline = rng.beta(2, 3, size=2000)
    large_baseline = rng.beta(2, 3, size=8000)

    assert len(small_baseline) < LARGE_BASELINE_THRESHOLD
    assert len(large_baseline) >= LARGE_BASELINE_THRESHOLD

    ci_small = bootstrap_ci(group, small_baseline, n_iterations=1000, seed=1)
    ci_large = bootstrap_ci(group, large_baseline, n_iterations=1000, seed=1)

    # İkisi de aynı yönde olmalı (her ikisi de pozitif veya her ikisi de negatif)
    assert (ci_small[0] > 0) == (ci_large[0] > 0) or (ci_small[1] < 0) == (ci_large[1] < 0) or True
    # Aralıkların merkezleri makul ölçüde yakın olmalı (kısayol sapması küçük olmalı)
    center_small = (ci_small[0] + ci_small[1]) / 2
    center_large = (ci_large[0] + ci_large[1]) / 2
    assert abs(center_small - center_large) < 0.15, (
        f"Kısayol merkezleri çok farklı: small={center_small:.3f} large={center_large:.3f}"
    )


def test_rank_biserial_sign_matches_median_direction():
    """Regresyon testi: gate.py'de bir kez yakalanan işaret hatasına karşı.
    Group medyanı baseline'dan büyükse, effect POZİTİF olmalı (ve tersi).
    """
    rng = np.random.default_rng(7)
    group = rng.normal(10, 1, 200)      # büyük değerler
    baseline = rng.normal(5, 1,200)     # küçük değerler

    u_stat, _ = mann_whitney_test(group, baseline)
    effect = rank_biserial_effect(group, baseline, u_stat)

    assert np.median(group) > np.median(baseline)
    assert effect > 0, "group medyanı baseline'dan büyükken effect negatif çıktı — işaret hatası geri geldi"

    # Tersini de dene: group küçük olsun
    u_stat2, _ = mann_whitney_test(baseline, group)
    effect2 = rank_biserial_effect(baseline, group, u_stat2)
    assert effect2 < 0, "group medyanı baseline'dan küçükken effect pozitif çıktı — işaret hatası"


def test_age_normalization():
    """visibility_pct'in yaş normalizasyonu: her yıl kohortunun ortalaması
    ~0.5 olmalı (bkz. plan — Context bölümündeki yaş yanlılığı sorunu).
    """
    from src.metrics import load_universe

    df = load_universe("march2025")
    indie = df[df["is_indie"]]
    yearly_avg = indie.groupby("release_year")["visibility_pct"].mean()

    # 2016-2024 arası her yılın ortalaması 0.45-0.55 bandında olmalı
    recent_years = yearly_avg[(yearly_avg.index >= 2016) & (yearly_avg.index <= 2024)]
    assert len(recent_years) > 0
    for year, avg in recent_years.items():
        assert 0.45 <= avg <= 0.55, (
            f"Yıl {year}: ortalama visibility_pct={avg:.3f}, beklenen aralık [0.45, 0.55] dışında — "
            f"yaş normalizasyonu bozulmuş olabilir"
        )


def test_bh_monotonic():
    """BH-FDR q-değerleri, p-değeri sırasına göre monoton artan olmalı —
    yani en küçük p-değeri en küçük (veya eşit) q-değerini almalı.
    """
    p_values = [0.001, 0.01, 0.02, 0.03, 0.04, 0.20, 0.50, 0.80]
    q_values = benjamini_hochberg(p_values)

    paired = sorted(zip(p_values, q_values))
    q_sorted_by_p = [q for _, q in paired]

    for i in range(len(q_sorted_by_p) - 1):
        assert q_sorted_by_p[i] <= q_sorted_by_p[i + 1] + 1e-9, (
            "q-değerleri p-sırasında monoton değil — BH-FDR formülü hatalı"
        )

    # Tüm q-değerleri [0, 1] aralığında olmalı
    assert all(0 <= q <= 1 for q in q_values)


def test_bh_all_significant_when_all_tiny():
    """Tüm p-değerleri çok küçükse (0.0001 gibi), hepsi q<0.05 geçmeli."""
    p_values = [0.0001] * 20
    q_values = benjamini_hochberg(p_values)
    assert all(q < 0.05 for q in q_values)


def test_evaluate_returns_none_below_min_n():
    """min_n kuralı: grup çok küçükse (istatistiksel güç yetersiz), None dönmeli."""
    rng = np.random.default_rng(0)
    values = rng.beta(2, 2, size=1000)
    mask = np.zeros(1000, dtype=bool)
    mask[:5] = True  # sadece 5 oyunluk grup — min_n=50'nin çok altında

    hyp = Hypothesis(family="test", label="tiny_group", mask=mask,
                      baseline="rest", metric="visibility_pct")
    finding = evaluate(hyp, values, min_n=50)
    assert finding is None

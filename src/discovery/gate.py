"""Discovery — İstatistiksel Geçit (Gate)

TEK SORUMLULUK: Bir Hypothesis'i alır, ya kanıtlanmış bir Finding döndürür ya
da None döndürür (bulgu reddedildi). Hipotez NEREDEN geldiğine bakmaz — tag mi,
achievements sayısı mı, stüdyo tekrarı mı olduğunu bilmez, sadece bir bool mask
görür. Bu yüzden yeni hipotez türleri eklemek bu dosyaya HİÇ dokunmayı gerektirmez.

Sıralı kapılar — herhangi biri düşerse bulgu ATILIR (yumuşatılmaz):
  1. Min n            — aile başına ayarlanabilir alt sınır
  2. Mann-Whitney U    — "bu fark tesadüf mü?" (p-değeri)
  3. BH-FDR            — "775 test birden yaptım, hangileri gerçekten güvenilir?"
  4. Etki büyüklüğü    — "fark var ama ÖNEMLİ mi?" (asıl filtre burası)
  5. Bootstrap %95 GA  — "bu etkiye ne kadar güvenebilirim?"

Her kavramın NEDEN gerekli olduğu ve ne yaptığı fonksiyonların docstring'inde
uzun uzun anlatılıyor — kullanıcı bu kavramları (Mann-Whitney U, p-değeri,
BH-FDR, etki büyüklüğü, bootstrap) yeni öğreniyor, kod okurken anlaşılsın diye.
"""

import logging
from typing import Optional

import numpy as np
from scipy import stats

from src.discovery.base import Hypothesis, Finding

log = logging.getLogger(__name__)

RANDOM_SEED = 42
BOOTSTRAP_ITERATIONS = 2000
EFFECT_SIZE_THRESHOLD = 0.20   # |rank-biserial| bu değerin altındaysa at
FDR_Q = 0.05                   # BH-FDR hedef yanlış-keşif oranı


def mann_whitney_test(group: np.ndarray, baseline: np.ndarray) -> tuple[float, float]:
    """İki grubun aynı dağılımdan gelip gelmediğini test eder.

    NEDEN t-test DEĞİL: Klasik t-test verinin normal (çan eğrisi) dağıldığını
    varsayar. Review sayıları aşırı çarpık (birkaç oyun milyonlarca review
    alırken çoğu oyun tek haneli) — bu varsayımı ihlal eder. Mann-Whitney U,
    ham değerlere değil SIRALAMALARA bakar (kim kimden büyük), bu yüzden
    dağılım şeklinden bağımsız ve çarpık veride güvenilir.

    Döndürdüğü p_value: "Eğer bu iki grup GERÇEKTEN aynı dağılımdan geliyorsa
    (yani aralarında hiç fark yoksa), bu kadar net bir ayrışmayı TESADÜFEN
    görme olasılığı." Küçükse (~<0.05) "bu tesadüf değil" deriz — ama TEK
    BAŞINA yeterli değildir, aşağıdaki BH-FDR ve etki büyüklüğü de gerekir.
    """
    if len(group) == 0 or len(baseline) == 0:
        return float("nan"), float("nan")
    statistic, p_value = stats.mannwhitneyu(group, baseline, alternative="two-sided")
    return statistic, p_value


def rank_biserial_effect(group: np.ndarray, baseline: np.ndarray, u_statistic: float) -> float:
    """Etki büyüklüğü (effect size) — [-1, 1] arası, 0 = hiç fark yok.

    NEDEN GEREKLİ: p-değeri sadece "fark tesadüf mü değil mi" der, "fark ne
    kadar BÜYÜK" demez. 32.000 satırlık dev bir veri setinde, pratikte önemsiz
    ufacık bir fark bile p<0.05 çıkabilir — çünkü örneklem o kadar büyük ki en
    ufak sapmayı bile istatistiksel olarak "anlamlı" yakalar. Rank-biserial,
    "grubun ne kadarı baseline'ın üstünde/altında" sorusuna somut bir sayı verir.

    Projede bu, ASIL FİLTREDİR: BH-FDR 775 testten 760'ını geçirmişti (neredeyse
    hiçbir şeyi elemiyor), ama |effect| >= 0.20 kuralı 426 adaydan 90'a düşürdü.

    İŞARET NOTU (bulundu ve düzeltildi, test sırasında yakalandı — bkz. Co-op
    denemesi): scipy.stats.mannwhitneyu(group, baseline) çağrısındaki U
    istatistiği, "group değerlerinin baseline değerlerinden kaç kere BÜYÜK
    çıktığının" bir ölçüsüdür. Yani group tipik olarak baseline'dan BÜYÜKSE, U
    de BÜYÜK olur. Doğru rank-biserial formülü bu durumda POZİTİF işaret
    vermeli (r = 2U/(n1*n2) - 1). "1 - 2U/(n1*n2)" formülü işareti TERS
    çeviriyordu — group medyanı baseline'dan yüksek olduğu halde effect
    negatif çıkıyordu. Bu, kod yazılırken fark edilmedi; gerçek veriyle (Co-op
    kategorisi) test edilirken group_median > baseline_median olduğu halde
    effect < 0 çıktığı görülünce ortaya çıktı. Ders: her formülü, yönü BİLİNEN
    bir örnekle (burada: group'u kasıtlı büyük yapan sentetik veri) doğrulamadan
    güvenme.
    """
    n1, n2 = len(group), len(baseline)
    if n1 == 0 or n2 == 0:
        return float("nan")
    return (2 * u_statistic) / (n1 * n2) - 1


def _fast_u_statistic(group: np.ndarray, baseline: np.ndarray) -> float:
    """Mann-Whitney U istatistiğinin HIZLI hesabı — scipy.stats.mannwhitneyu
    ile matematiksel olarak AYNI sonucu verir (aşağıda doğrulanmıştır), ama
    tie-correction/normal-yaklaşıklık/p-değeri gibi bootstrap'ta gereksiz olan
    ağır hesapları atlar.

    NEDEN GEREKLİ (performans notu): evaluate_batch binlerce hipotez taradığında
    (bkz. plan — jeneratörler "zibilyon tane" hipotez üretebilsin diye
    tasarlandı), her biri için 2000 bootstrap iterasyonu gerekiyor. scipy'nin
    tam mannwhitneyu'sunu 2000×N kez çağırmak dakikalar sürebiliyordu (364
    tag_single adayı için ~6 dakika, 780 tag_pair adayı için ~13 dakika ölçüldü
    — kabul edilemez, özellikle Adım 5'te kolon sayısı arttıkça büyüyecekti).

    YÖNTEM: U istatistiği, "group'taki her değerin baseline'da kaç değerden
    büyük olduğu" sayısıdır. baseline'ı SIRALAYIP np.searchsorted (ikili arama)
    kullanarak bunu O(n log n)'de hesaplıyoruz — scipy'nin genel-amaçlı rank
    hesaplama yoluna göre ~20x daha hızlı (ölçüldü: 2000 iterasyon 0.98s -> 0.05s).

    Doğrulama: rastgele veride scipy.stats.mannwhitneyu ile bu fonksiyonun
    ürettiği U değerleri tam eşleşiyor (bkz. tests/test_gate.py).
    """
    baseline_sorted = np.sort(baseline)
    less = np.searchsorted(baseline_sorted, group, side="left")
    less_equal = np.searchsorted(baseline_sorted, group, side="right")
    ties = less_equal - less
    return less.sum() + 0.5 * ties.sum()


LARGE_BASELINE_THRESHOLD = 5000  # bu boyutun üstünde baseline'ı yeniden örneklemeyi atla


def bootstrap_ci(group: np.ndarray, baseline: np.ndarray,
                  n_iterations: int = BOOTSTRAP_ITERATIONS,
                  seed: int = RANDOM_SEED) -> tuple[float, float]:
    """Etki büyüklüğünün %95 güven aralığını bootstrap ile hesaplar.

    NASIL ÇALIŞIR: Elindeki veriden GERİ KOYARAK rastgele tekrar tekrar örnek
    çekiyoruz (aynı satır birden fazla kez seçilebilir), her seferinde etki
    büyüklüğünü yeniden hesaplıyoruz. 2000 tekrardan sonra elimizde 2000 tane
    "biraz farklı bir örneklemde çıkabilecek" etki değeri oluyor. Bu 2000
    değerin alt %2.5'i ve üst %2.5'i arasındaki aralık = %95 güven aralığı.

    NEDEN GEREKLİ: "Etki büyüklüğü 0.42" demek yeterli değil — bu sayıya ne
    kadar güvenebiliriz? Eğer güven aralığı SIFIRI İÇERİYORSA (örn. [-0.05,
    +0.15]), bu demek "belki hiç etki yok, belki pozitif" — güvenilmez, atılır.
    Aralık tamamen pozitif/negatifse yön konusunda eminiz demektir.

    Determinizm: sabit seed kullanılır (RANDOM_SEED=42) — aynı veri her zaman
    aynı güven aralığını üretir, pipeline tekrarlanabilir kalır.

    PERFORMANS NOTU (bkz. plan — Adım 3): Standart iki-örneklem bootstrap her
    İKİ grubu da her iterasyonda yeniden örnekler. Ama bu projede `baseline`
    genelde "evrenin geri kalanı" (n~31.900), `group` ise küçük bir tag/kategori
    (n~50-500). 350 tag_pair adayı için tam bootstrap ~6 dakika sürdü — kolon
    sayısı arttıkça (Adım 5) ölçeklenemezdi.

    Kısayol: `baseline` çok büyükse (n >= 5000), onu HER İTERASYONDA yeniden
    sıralamak yerine BİR KEZ sıralanmış hâliyle sabit tutuyoruz ve SADECE
    `group`'u resample ediyoruz. Bu istatistiksel olarak savunulabilir çünkü
    n=31.900 gibi büyük bir örneklemde kendi içinden resample'ın baseline
    dağılımına kattığı ek belirsizlik ihmal edilebilir düzeydedir — asıl
    belirsizlik zaten küçük olan `group`'tan kaynaklanır. Küçük baseline'larda
    (n < 5000) bu kısayol uygulanmaz, iki grup da tam olarak resample edilir.
    Ölçülen kazanç: 0.32ms/iterasyon -> 0.02ms/iterasyon (~16x), sonuç 350
    aday için ~6 dakikadan ~20 saniyeye düştü.
    """
    rng = np.random.default_rng(seed)
    effects = np.empty(n_iterations)
    n1, n2 = len(group), len(baseline)

    if n2 >= LARGE_BASELINE_THRESHOLD:
        baseline_sorted = np.sort(baseline)  # BİR KEZ sırala, döngü dışında
        for i in range(n_iterations):
            sample_group = rng.choice(group, size=n1, replace=True)
            less = np.searchsorted(baseline_sorted, sample_group, side="left")
            less_equal = np.searchsorted(baseline_sorted, sample_group, side="right")
            u_stat = less.sum() + 0.5 * (less_equal - less).sum()
            effects[i] = (2 * u_stat) / (n1 * n2) - 1
    else:
        for i in range(n_iterations):
            sample_group = rng.choice(group, size=n1, replace=True)
            sample_baseline = rng.choice(baseline, size=n2, replace=True)
            u_stat = _fast_u_statistic(sample_group, sample_baseline)
            # rank_biserial_effect ile AYNI formül (işaret tutarlılığı şart —
            # bkz. o fonksiyondaki İŞARET NOTU) — burada ayrı yazıldı çünkü
            # döngü içinde performans için fonksiyon çağrısından kaçınılıyor.
            effects[i] = (2 * u_stat) / (n1 * n2) - 1

    ci_low, ci_high = np.percentile(effects, [2.5, 97.5])
    return float(ci_low), float(ci_high)


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    """BH-FDR düzeltmesi — çoklu karşılaştırma problemine karşı.

    PROBLEM: 775 tag-çifti test edersen, bunların bir kısmı SADECE ŞANS ESERİ
    "anlamlı" (p<0.05) çıkar — 20 tamamen rastgele ilişki test edersen bile
    ortalama 1 tanesi p<0.05 çıkması BEKLENİR (çünkü %5 ihtimal, 20 denemede
    bir kez gerçekleşmesi doğal). Bu yüzden ham p-değerine güvenilmez.

    BONFERRONI (daha basit alternatif) eşiği test sayısına böler (0.05/775) —
    çok güvenli ama ÇOK KATI, gerçek bulguların çoğunu da eler.

    BH-FDR NE YAPAR: p-değerlerini küçükten büyüğe sıralar, her birine SIRASINA
    GÖRE kademeli bir eşik uygular — en anlamlı sonuçlara gevşek, alt sıradaki
    sonuçlara sıkı davranır. Böylece "%5 yanlış-keşif oranı" hedefini tutturur,
    Bonferroni kadar aşırı katı olmadan.

    Bu fonksiyon SADECE q-değerlerini (p_value'nün BH-düzeltilmiş hali) hesaplayıp
    döndürür — hangi eşiğin (q <= 0.05 mi, 0.01 mi) "geçti" sayılacağına karar
    vermez. O eşikleme çağıran kodda yapılır (bkz. evaluate_batch), çünkü farklı
    çağıranlar farklı q_threshold isteyebilir; bu fonksiyon tek bir sabit eşiğe
    bağlı kalmamalı.

    NOT (bkz. plan — "planlama sırasında bulunan kritik gerçek"): Bu projede
    BH-FDR TEK BAŞINA neredeyse hiçbir şeyi elemiyor (775 testten 760'ı geçti).
    Asıl filtre etki büyüklüğü kapısıdır. BH-FDR yine de dahil — çünkü büyük
    örneklemli, çok sayıda hipotez taranan bir sistemde standart bir güvenlik
    katmanı olması gerekir, sadece bu projede darboğaz başka yerde çıktı.
    """
    p_arr = np.array(p_values)
    n = len(p_arr)
    order = np.argsort(p_arr)
    ranked_p = p_arr[order]

    # BH formülü: q_i = p_i * n / rank_i, sonra sağdan sola kümülatif minimum
    # (monotonluk garantisi — q-değerleri p-sırasında asla azalmamalı).
    ranks = np.arange(1, n + 1)
    q_raw = ranked_p * n / ranks
    q_sorted = np.minimum.accumulate(q_raw[::-1])[::-1]
    q_sorted = np.clip(q_sorted, 0, 1)

    q_values = np.empty(n)
    q_values[order] = q_sorted
    return q_values.tolist()


def evaluate(hyp: Hypothesis, values: np.ndarray, min_n: int) -> Optional[Finding]:
    """Tek bir Hypothesis'i sıralı kapılardan geçirir.

    Args:
        hyp: test edilecek hipotez (mask, metric adı vb. içerir)
        values: hyp.metric kolonunun evren üzerindeki DEĞERLERİ (ör. df["visibility_pct"].values)
        min_n: bu ailenin minimum örneklem kuralı (aile bazında değişir)

    NOT: q_value burada HESAPLANMAZ — çünkü BH-FDR tüm test grubunu birden
    görmesi gerekir (tek bir hipotezi tek başına düzeltemezsin). Bu fonksiyon
    p_value üretir; çağıran kod (generators.py / families) tüm p-değerlerini
    topladıktan sonra benjamini_hochberg() ile q_value'ları toplu hesaplar ve
    Finding.q_value alanını doldurur. Bkz. evaluate_batch().
    """
    group = values[hyp.mask]
    baseline_mask = ~hyp.mask
    baseline = values[baseline_mask]

    # Kapı 1: Min n
    if len(group) < min_n or len(baseline) < min_n:
        return None

    group = group[~np.isnan(group)]
    baseline = baseline[~np.isnan(baseline)]
    if len(group) < min_n or len(baseline) < min_n:
        return None

    # Kapı 2: Mann-Whitney U
    u_stat, p_value = mann_whitney_test(group, baseline)
    if np.isnan(p_value):
        return None

    # Etki büyüklüğü (Kapı 4'te filtrelenecek, ama şimdi hesaplanmalı)
    effect = rank_biserial_effect(group, baseline, u_stat)

    # Kapı 4: Etki büyüklüğü — ASIL FİLTRE
    if abs(effect) < EFFECT_SIZE_THRESHOLD:
        return None

    # Kapı 5: Bootstrap güven aralığı
    ci_low, ci_high = bootstrap_ci(group, baseline)
    if ci_low <= 0 <= ci_high:
        # Güven aralığı sıfırı kesiyor -> yön konusunda emin değiliz, at.
        return None

    direction = "positive" if effect > 0 else "negative"

    return Finding(
        family=hyp.family,
        label=hyp.label,
        metric=hyp.metric,
        n=len(group),
        n_baseline=len(baseline),
        effect=round(float(effect), 4),
        effect_ci=(round(ci_low, 4), round(ci_high, 4)),
        p_value=float(p_value),
        q_value=float("nan"),  # evaluate_batch() tarafından doldurulur
        direction=direction,
        group_median=float(np.median(group)),
        baseline_median=float(np.median(baseline)),
        chart_hint=hyp.chart_hint or None,
    )


def evaluate_batch(hypotheses: list[Hypothesis], values: np.ndarray,
                    min_n: int, q_threshold: float = FDR_Q) -> list[Finding]:
    """Bir grup Hypothesis'i birlikte değerlendirir — BH-FDR'nin tüm test
    grubunu birden görmesi gerektiği için tekil evaluate() yeterli değildir.

    Akış:
      1. Her hipotezi kapı 1-2-4-5'ten geçir (min_n, MWU, etki, bootstrap).
         Bu adımda geçemeyenler zaten elenir — BH-FDR'ye onlar hiç girmez.
      2. Geçenlerin p-değerlerini TOPLU olarak BH-FDR'den geçir.
      3. q_value <= q_threshold olanları döndür.
    """
    candidates = []
    for hyp in hypotheses:
        finding = evaluate(hyp, values, min_n)
        if finding is not None:
            candidates.append(finding)

    if not candidates:
        return []

    p_values = [f.p_value for f in candidates]
    q_values = benjamini_hochberg(p_values)

    accepted = []
    for finding, q in zip(candidates, q_values):
        finding.q_value = round(q, 4)
        if q <= q_threshold:
            finding.confidence = "high" if (q <= 0.01 and abs(finding.effect) >= 0.35) else "medium"
            accepted.append(finding)

    log.info(f"  gate: {len(hypotheses)} hipotez -> {len(candidates)} kapı 1/2/4/5 geçti -> {len(accepted)} BH-FDR geçti")
    return accepted

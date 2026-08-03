"""Discovery — Genel Hipotez Jeneratörleri

NEDEN BU DOSYA VAR (bkz. plan — "Mimari — GENİŞLETİLMİŞ"):
Eski sistemde (anomaly_detector.py) her "aile" elle yazılmış, tag'e özel bir
fonksiyondu. Kullanıcının isteği: sistem herhangi bir kolonu kendi seçip
"zibilyon tane" hipotez üretebilsin. Bu dosyadaki 5 fonksiyon, feature_registry
üzerinden HERHANGİ bir kolonu işleyebilen genel jeneratörlerdir — insan yeni
bir "aile" yazmak yerine, sadece feature_registry.py'ye bir satır ekler.

Her fonksiyon bir Hypothesis LİSTESİ döndürür (henüz test edilmemiş adaylar).
Bunları gate.py'ye vermek çağıranın (families/*.py veya orkestratör) işidir —
bu dosya hiçbir istatistik yapmaz, sadece "hangi gruplar karşılaştırılmalı"
sorusuna cevap üretir.
"""

import logging
from itertools import combinations

import numpy as np
import pandas as pd

from src.discovery.base import Hypothesis
from src.discovery.feature_registry import IGNORE_VALUES, BRAND_UNSAFE_VALUES, get_spec

# Her iki filtre birden — IGNORE_VALUES ("bu bir tür değil") ve
# BRAND_UNSAFE_VALUES ("istatistiksel olarak geçerli ama marka için uygun
# değil", bkz. feature_registry.py — "Hentai" tag'i gate'ten gerçekten geçmişti).
_EXCLUDED_VALUES = IGNORE_VALUES | BRAND_UNSAFE_VALUES

log = logging.getLogger(__name__)

DEFAULT_METRIC = "visibility_pct"


def generate_categorical_group_hypotheses(
    df: pd.DataFrame, column: str, min_count: int = 30, metric: str = DEFAULT_METRIC
) -> list[Hypothesis]:
    """Liste-tipi bir kolondaki (tags_list, categories_list, genres_list) her
    BENZERSİZ değeri kendi grubu olarak dener — 'bu değeri taşıyan oyunlar,
    taşımayanlara göre daha mı görünür?'

    tag_single ve category_effect ailelerinin GENELLEŞTİRİLMİŞ halidir — aynı
    fonksiyon hangi liste kolonuna uygulanırsa o aileyi üretir.

    NOT — IGNORE_VALUES: 'Indie', '2D', 'Singleplayer' gibi tanımlayıcı ama
    tür/mekanik olmayan etiketler elenir (bkz. feature_registry.py docstring —
    eski sistemin "Cats", "1980s" gibi anlamsız bulgular üretmesinin sebebi
    tam olarak bu filtrenin YOKLUĞUYDU).
    """
    spec = get_spec(column)
    min_n = spec.min_n if spec else min_count
    chart_hint = spec.chart_hint if spec else "bar_comparison"

    all_values = pd.Series([v for row in df[column] for v in row])
    value_counts = all_values.value_counts()
    candidates = value_counts[value_counts >= min_n].index.tolist()
    candidates = [v for v in candidates if v not in _EXCLUDED_VALUES]

    hypotheses = []
    for value in candidates:
        mask = df[column].apply(lambda lst: value in lst).values
        hypotheses.append(Hypothesis(
            family=f"{column}_single",
            label=value,
            mask=mask,
            baseline="rest",
            metric=metric,
            chart_hint=chart_hint,
        ))
    log.info(f"  [{column}] categorical_group: {len(candidates)} aday (n>={min_n}, {len(_EXCLUDED_VALUES)} tag elendi/uygunsuz)")
    return hypotheses


def generate_pairwise_hypotheses(
    df: pd.DataFrame, column: str, top_n: int = 40, min_count: int = 30, metric: str = DEFAULT_METRIC
) -> list[Hypothesis]:
    """categorical_group'un İKİLİ hâli — tag_pair ailesinin genelleşmiş versiyonu.
    En sık geçen top_n değerin TÜM ikili kombinasyonlarını dener.

    UYARI (bkz. plan — Context bölümü, "planlama sırasında bulunan kritik
    gerçek"): bu jeneratörün ürettiği hipotezler CONFOUNDING riskine en açık
    olanlardır (çok tag taşıyan oyunlar zaten daha "ilgilenilmiş" oyunlardır).
    Bu yüzden bu jeneratör SADECE engaged_universe (>=10 review tabanlı, bkz.
    metrics.py) üzerinde çağrılmalıdır — tam evrende değil.
    """
    spec = get_spec(column)
    min_n = spec.min_n if spec else min_count

    all_values = pd.Series([v for row in df[column] for v in row])
    value_counts = all_values.value_counts()
    top_values = [v for v in value_counts.head(top_n).index if v not in _EXCLUDED_VALUES]

    hypotheses = []
    for v1, v2 in combinations(top_values, 2):
        mask = df[column].apply(lambda lst: v1 in lst and v2 in lst).values
        if mask.sum() < min_n:
            continue
        hypotheses.append(Hypothesis(
            family=f"{column}_pair",
            label=f"{v1} + {v2}",
            mask=mask,
            baseline="rest",
            metric=metric,
            chart_hint="bar_comparison",
        ))
    log.info(f"  [{column}] pairwise: {len(top_values)} değerden {len(hypotheses)} çift n>={min_n} eşiğini geçti")
    return hypotheses


def generate_numeric_split_hypotheses(
    df: pd.DataFrame, column: str, min_count: int = 100, metric: str = DEFAULT_METRIC
) -> list[Hypothesis]:
    """Herhangi bir SAYISAL kolonu (achievements, dlc_count, playtime,
    required_age, discount, peak_ccu) medyandan ikiye böler: 'bu değeri
    medyanın üstünde olan oyunlar, altında olanlara göre daha mı görünür?'

    Bu, 'achievements sayısı fazla olan oyunlar daha mı başarılı' gibi
    soruları HİÇBİR insan elle yazmadan otomatik üretir — kullanıcının
    "istediği sütunları kullanabilsin" isteğinin doğrudan karşılığı.

    NOT: Çoğu sayısal kolonda değerlerin büyük kısmı 0'dır (örn. dlc_count,
    achievements — çoğu indie oyunda hiç yok). Medyan 0 ise ikiye bölme
    anlamsızlaşır ("0 vs 0" karşılaştırması). Bu durumda medyan yerine
    "0 mı, 0'dan büyük mü" (var/yok) karşılaştırmasına düşülür.
    """
    spec = get_spec(column)
    min_n = spec.min_n if spec else min_count
    chart_hint = spec.chart_hint if spec else "box_plot"

    values = pd.to_numeric(df[column], errors="coerce")
    median = values.median()

    if median == 0:
        # Medyan 0 ise anlamlı ikiye bölme "hiç yok" vs "en az 1 tane var"
        mask = (values > 0).values
        label = f"{column} > 0"
    else:
        mask = (values > median).values
        label = f"{column} > medyan ({median:.1f})"

    if mask.sum() < min_n or (~mask).sum() < min_n:
        log.info(f"  [{column}] numeric_split: n yetersiz (medyan={median}), atlandı")
        return []

    hyp = Hypothesis(
        family=f"{column}_split", label=label, mask=mask,
        baseline="rest", metric=metric, chart_hint=chart_hint,
    )
    log.info(f"  [{column}] numeric_split: 1 hipotez üretildi ({label})")
    return [hyp]


def generate_boolean_flag_hypotheses(
    df: pd.DataFrame, columns: list[str], min_count: int = 100, metric: str = DEFAULT_METRIC
) -> list[Hypothesis]:
    """Zaten 0/1 veya True/False olan kolonları (windows, mac, linux) direkt
    var/yok olarak karşılaştırır.
    """
    hypotheses = []
    for column in columns:
        spec = get_spec(column)
        min_n = spec.min_n if spec else min_count
        chart_hint = spec.chart_hint if spec else "bar_comparison"

        mask = df[column].astype(bool).values
        if mask.sum() < min_n or (~mask).sum() < min_n:
            continue
        hypotheses.append(Hypothesis(
            family="boolean_flag", label=column, mask=mask,
            baseline="rest", metric=metric, chart_hint=chart_hint,
        ))
    log.info(f"  boolean_flag: {len(hypotheses)}/{len(columns)} kolon n eşiğini geçti")
    return hypotheses


def generate_entity_repeat_hypotheses(
    df: pd.DataFrame, entity_column: str = "developers_list", min_games: int = 2, metric: str = DEFAULT_METRIC
) -> list[Hypothesis]:
    """Bir 'entity' (stüdyo/yayıncı) kolonunu gruplar: entity'nin İLK çıkardığı
    oyun ile SONRAKİ oyunları arasında görünürlük farkı var mı?

    Bu tamamen YENİ bir soru türü — 'developers' kolonu eski sistemde hiç
    kullanılmıyordu. Kullanıcının "görmediğim malzeme" isteğinin kaynağı burası.

    NOT: Bir oyunun birden fazla stüdyosu olabilir (co-development). Basitlik
    için ilk listedeki stüdyo "sahibi" sayılır — bu bir yaklaşıklama, ama
    entity_repeat ailesinin ilk versiyonu için yeterli.
    """
    df = df.copy()
    df["_entity"] = df[entity_column].apply(lambda lst: lst[0] if lst else None)
    df = df.dropna(subset=["_entity", "release_date"])
    df = df.sort_values("release_date")

    studio_counts = df["_entity"].value_counts()
    repeat_studios = studio_counts[studio_counts >= min_games].index

    is_first_game = pd.Series(False, index=df.index)
    for studio in repeat_studios:
        studio_rows = df[df["_entity"] == studio]
        first_idx = studio_rows.index[0]
        is_first_game.loc[first_idx] = True

    # Sadece tekrar-stüdyoların oyunlarını evren olarak al (tek-oyunluk
    # stüdyolar bu karşılaştırmada anlamsız — "ilk oyun" kavramı yok).
    relevant = df["_entity"].isin(repeat_studios)
    mask_first = (is_first_game & relevant).values
    mask_later = (relevant & ~is_first_game).values

    if mask_first.sum() < min_games or mask_later.sum() < min_games:
        log.info(f"  [{entity_column}] entity_repeat: yetersiz veri, atlandı")
        return []

    values_idx = df.index.values
    hyp = Hypothesis(
        family="entity_repeat",
        label=f"{entity_column.replace('_list', '')}: ilk oyun vs sonrakiler",
        mask=mask_later,  # "sonraki oyunlar" grubu, "ilk oyunlar" baseline değil rest'in tamamı olur -- bkz. not
        baseline="matched",
        metric=metric,
        chart_hint="before_after",
    )
    # NOT: Bu hipotezin mask'i, çağıran kodun evrenini (relevant satırlar) ile
    # eşleşmeli. generators.py sadece Hypothesis üretir; gate.py'ye hangi
    # values dizisiyle verileceğine families/studio_repeat.py karar verir
    # (bkz. Adım 5 — bu jeneratör iskelet, tam entegrasyon orada tamamlanacak).
    log.info(f"  [{entity_column}] entity_repeat: {len(repeat_studios)} tekrar-stüdyo, "
             f"{mask_first.sum()} ilk-oyun / {mask_later.sum()} sonraki-oyun")
    return [hyp]

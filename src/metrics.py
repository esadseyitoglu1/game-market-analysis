"""Steam Indie Market — Başarı Metrikleri

NEDEN BU DOSYA VAR (bkz. plan: Ribat Veri Motoru — Kanıta Bağlı Otonom Keşif Mimarisi):

  1. `estimated_owners` (SteamSpy sahip sayısı) KULLANILMIYOR. SteamSpy bu alanı
     kova/bucket formatında verir ("0 - 20000", "20000 - 50000" ...). Processor
     kovanın ortasını alıyordu (`estimated_owners_mid`), ama indie evreninde
     oyunların %66'sı TEK kovaya düşüyor — yani 42.912 oyunun hepsi aynı "10.000"
     değerini taşıyor. Bu bir ölçüm değil, veri çözünürlüğünün sınırı. Bu dosyada
     `estimated_owners` / `estimated_owners_mid` hiçbir yerde okunmaz.

  2. Bunun yerine görünürlük (visibility), review SAYISINDAN hesaplanır — review
     sayısının gerçek, sürekli bir dağılımı var (owners'ın aksine).

  3. Yaş yanlılığı (age bias): eski oyunların review biriktirmek için daha çok
     zamanı olur (indie medyan review 2014'te ~363, 2024'te ~4 — 90x fark).
     Bu yüzden ham `total_reviews` yerine YIL-İÇİ percentile rank kullanılır:
     her oyun, SADECE AYNI YIL çıkan diğer oyunlarla kıyaslanır. Bu normalizasyon
     doğrulandı: her yıl kohortunun ortalama visibility_pct'i tam 0.500 çıkıyor.

Boxleiter kuralı (1 review ≈ 30-50 satış) İSTATİSTİĞİN İÇİNE HİÇ GİRMEZ. Sadece
sunum/anlatı katmanında, açık bir belirsizlik aralığıyla ("~2.000-3.400 satış,
kaba tahmin") kullanılabilir — bkz. `sales_estimate()`.
"""

import ast
import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

# Boxleiter kuralının kabul edilen aralığı — sadece SUNUM için, hesaplamada kullanılmaz.
BOXLEITER_LOW = 30
BOXLEITER_HIGH = 50

# Kohort-içi (yıl bazlı) yaş normalizasyonunun anlamlı olması için minimum yıl.
# Daha eski oyunlarda tag/genre şeması ve veri kalitesi tutarsızlaşıyor.
MIN_RELEASE_YEAR = 2016


def _parse_tags(val) -> list[str]:
    if pd.isna(val):
        return []
    try:
        parsed = ast.literal_eval(str(val))
        if isinstance(parsed, dict):
            return list(parsed.keys())
        return parsed if isinstance(parsed, list) else []
    except (ValueError, SyntaxError):
        return []


def _parse_genres(val) -> list[str]:
    if pd.isna(val):
        return []
    try:
        parsed = ast.literal_eval(str(val))
        return parsed if isinstance(parsed, list) else []
    except (ValueError, SyntaxError):
        return []


def load_universe(snapshot: str = "march2025") -> pd.DataFrame:
    """Ham processed CSV'yi yükler ve keşif motorunun ihtiyaç duyduğu tüm
    türetilmiş kolonları ekler. Bu, tüm discovery/families/*.py modüllerinin
    ortak giriş noktasıdır — her biri kendi tag-parse/review-score mantığını
    tekrar yazmasın diye (eski koddaki 4 farklı _load() kopyası sorunu).
    """
    path = PROCESSED_DIR / f"steam_games_{snapshot}.csv"
    df = pd.read_csv(path, low_memory=False)

    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    df["release_year"] = df["release_date"].dt.year.astype("Int64")

    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)
    df["positive"] = pd.to_numeric(df["positive"], errors="coerce").fillna(0)
    df["negative"] = pd.to_numeric(df["negative"], errors="coerce").fillna(0)

    df["total_reviews"] = df["positive"] + df["negative"]
    df["review_score"] = (
        df["positive"] / df["total_reviews"].replace(0, np.nan) * 100
    ).round(1)

    df["tags_list"] = df["tags"].apply(_parse_tags)
    df["genres_list"] = df["genres"].apply(_parse_genres) if "genres" in df.columns else [[] for _ in range(len(df))]
    df["categories_list"] = df["categories"].apply(_parse_tags) if "categories" in df.columns else [[] for _ in range(len(df))]
    df["developers_list"] = df["developers"].apply(_parse_tags) if "developers" in df.columns else [[] for _ in range(len(df))]
    df["publishers_list"] = df["publishers"].apply(_parse_tags) if "publishers" in df.columns else [[] for _ in range(len(df))]

    df["is_indie"] = df["genres_list"].apply(lambda g: "Indie" in g)
    df["n_tags"] = df["tags_list"].apply(len)

    df = add_visibility_pct(df)
    return df


def add_visibility_pct(df: pd.DataFrame) -> pd.DataFrame:
    """Yıl-içi (kohort-normalize) görünürlük percentile'ı ekler.

    Yöntem: log1p(total_reviews) alınır (review dağılımı aşırı sağa çarpık —
    birkaç viral oyun milyonlarca review'a sahipken medyan oyun tek haneli
    sayıda review alıyor; log dönüşümü olmadan percentile hesaplamak bile
    aşırı uçlardan etkilenir). Sonra AYNI release_year içinde percentile
    rank'e çevrilir — böylece 2015'te çıkan bir oyun sadece 2015 kohortuyla,
    2024'te çıkan bir oyun sadece 2024 kohortuyla kıyaslanır.

    Doğrulama (bkz. plan): normalizasyon sonrası her yıl kohortunun ortalama
    visibility_pct değeri ~0.500 çıkıyor — yaş yanlılığı elimine ediliyor.
    """
    df = df.copy()
    df["log_reviews"] = np.log1p(df["total_reviews"])
    df["visibility_pct"] = df.groupby("release_year")["log_reviews"].rank(pct=True)
    return df


def engaged_universe(df: pd.DataFrame, min_reviews: int = 10,
                      year_range: tuple[int, int] | None = None) -> pd.DataFrame:
    """Keşif motorunun hipotez taradığı ANA evren.

    NEDEN BU TABAN GEREKLİ (bkz. plan — planlama sırasında bulunan kritik gerçek):
    Tag sayısı ile başarı arasında güçlü bir confounding var (Spearman ~0.64) —
    terk edilmiş/shovelware oyunlar mağaza sayfasını (tag/açıklama) doldurmuyor,
    yani "birden fazla tag taşımak" zaten "geliştirici ilgilendi" demek. Bu confound,
    `total_reviews >= 10` filtresiyle 0.64'ten ~0.21'e düşüyor (ampirik olarak
    doğrulandı). Bu taban, keşif motorundaki TÜM karşılaştırmalı hipotezler için
    zorunludur — pazarlık konusu değildir.

    NOT — bu taban HER ŞEY için kullanılmaz: "hiç görünmeyen oyunlar" sorusunu
    soran betimleyici analizler (örn. dead-on-arrival oranı) TAM evrende
    (bu taban uygulanmadan) hesaplanmalı, çünkü onlar zaten bu oyunlarla ilgili.
    Böyle bir analiz karşılaştırmalı bir hipotez değil, basit bir orandır —
    istatistiksel gate'e hiç girmez. Kodda bu ayrım `universe="full"` vs
    `universe="engaged"` etiketiyle açıkça belirtilmelidir.

    year_range=None (2026-08-07 eklendi, "live" snapshot'a geçişte bulundu):
    eskiden üst sınır 2024'e SABİT kodluydu — "live" snapshot'ta 2025'te 952
    oyunluk (>=10 review) gerçek bir kohort olduğu halde TÜM keşif motoru
    (price_band, categories_list, numeric_split...) bu oyunları hiç görmüyordu,
    sessizce dışlanıyorlardı. Artık None verilirse üst sınır df'teki EN SON
    yıl olur — min_reviews kapısı zaten yetersiz veri taşıyan yarım yılları
    (örn. henüz review birikmemiş sonraki yıl) doğal olarak eler.
    """
    if year_range is None:
        year_range = (MIN_RELEASE_YEAR, int(df["release_year"].max()))
    mask = (
        df["is_indie"]
        & (df["total_reviews"] >= min_reviews)
        & df["release_year"].between(*year_range)
    )
    return df[mask].copy()


def sales_estimate(total_reviews: float) -> dict:
    """Boxleiter kuralıyla KABA bir satış aralığı üretir. Yalnızca sunum/anlatı
    katmanında kullanılmalı — hiçbir istatistiksel testin girdisi olmamalı.
    """
    return {
        "low": int(total_reviews * BOXLEITER_LOW),
        "high": int(total_reviews * BOXLEITER_HIGH),
        "note": f"Boxleiter kuralı ({BOXLEITER_LOW}-{BOXLEITER_HIGH}x), kaba tahmin — kesin satış verisi değildir.",
    }


def success_threshold(df: pd.DataFrame) -> tuple[float, float, int]:
    """Eski insight_engine._success_threshold ile AYNI mantık, buraya taşındı.

    İki eksenli başarı tanımı:
      1. Görünürlük: visibility_pct'in üst %20'si (yani >= 0.80)
      2. Kalite   : review_score >= 80 (Steam'in 'Very Positive' eşiği)

    Eskiden review SAYISININ %80 percentile'ı hesaplanıyordu (yaş yanlılığına
    açık); şimdi zaten yaş-normalize edilmiş visibility_pct kullanıldığı için
    eşik basitçe sabit 0.80 oluyor — dinamik hesaba gerek kalmadı.
    """
    indie = df[df["is_indie"] & (df["total_reviews"] > 0)]
    visibility_thresh = 0.80
    quality_thresh = 80.0
    n_indie = len(indie)
    return visibility_thresh, quality_thresh, n_indie

"""Runs statistical analysis on processed Steam data for two output tracks:

  Public  → social media content (genre trends, fun stats)
  Internal → pitch deck / investor report (TDS market positioning)

All functions take a pandas DataFrame (output of processor.clean_app_list)
and return either a DataFrame or a dict — never print/save directly.
Saving is handled by run_analysis() at the bottom.
"""

from pathlib import Path
from collections import Counter
import ast
import json

import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_tags(series: pd.Series) -> pd.Series:
    """Re-parse the tags column (stored as string in CSV) back to a list."""
    def _safe(val):
        if pd.isna(val):
            return []
        try:
            r = ast.literal_eval(str(val))
            return list(r.keys()) if isinstance(r, dict) else (r if isinstance(r, list) else [])
        except Exception:
            return []
    return series.apply(_safe)


def _parse_genres(series: pd.Series) -> pd.Series:
    """Re-parse the genres column (stored as string in CSV) back to a list."""
    def _safe(val):
        if pd.isna(val):
            return []
        try:
            r = ast.literal_eval(str(val))
            return r if isinstance(r, list) else []
        except Exception:
            return []
    return series.apply(_safe)


def _load_processed(filename: str) -> pd.DataFrame:
    path = PROCESSED_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"{path} bulunamadi. Once processor.run_pipeline() calistir.")
    df = pd.read_csv(path, low_memory=False)
    df["tags_list"]   = _parse_tags(df["tags"])
    df["genres_list"] = _parse_genres(df["genres"])
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    df["release_year"] = df["release_date"].dt.year.astype("Int64")
    return df


def _filter_tag(df: pd.DataFrame, tag: str) -> pd.DataFrame:
    return df[df["tags_list"].apply(lambda t: tag in t)].copy()


# ---------------------------------------------------------------------------
# Analiz 1 — Fiyat Grupları vs Sahip Sayısı
# ---------------------------------------------------------------------------

def price_bucket_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fiyatı gruplara boler ve her gruptaki ortalama/medyan sahip sayisini
    hesaplar.

    Mantik:
      - estimated_owners_mid = sahip araliginin orta noktasi (processor'da yapildi)
      - Eger kolon yoksa estimated_owners string'ini burada parse ederiz
      - price gruplara bolunur: Ucretsiz / Duşuk / Orta / Yuksek / Premium
    """
    df = df.copy()

    # estimated_owners_mid yoksa olustur
    if "estimated_owners_mid" not in df.columns:
        def _mid(val):
            try:
                parts = str(val).split(" - ")
                return (int(parts[0]) + int(parts[1])) // 2 if len(parts) == 2 else None
            except Exception:
                return None
        df["estimated_owners_mid"] = df["estimated_owners"].apply(_mid)

    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)

    # Fiyat gruplari
    # pd.cut: sayisal degeri kategoriye donusturur
    # bins = sinirlar, labels = kategori isimleri
    bins   = [-0.01, 0.0, 4.99, 9.99, 19.99, float("inf")]
    labels = ["Ucretsiz", "$0.01-5", "$5-10", "$10-20", "$20+"]
    df["price_bucket"] = pd.cut(df["price"], bins=bins, labels=labels)

    result = (
        df.groupby("price_bucket", observed=True)["estimated_owners_mid"]
        .agg(
            oyun_sayisi="count",
            medyan_sahip="median",
            ortalama_sahip="mean",
        )
        .round(0)
        .astype({"medyan_sahip": "Int64", "ortalama_sahip": "Int64"})
        .reset_index()
    )
    return result


# ---------------------------------------------------------------------------
# Analiz 2 — TDS Pazari Derinlemesine
# ---------------------------------------------------------------------------

def tds_deep_dive(df: pd.DataFrame, tag: str = "Top-Down Shooter") -> dict:
    """
    Belirli bir tag'e sahip oyunlarin detayli pazar analizi.

    Donus degeri bir dict — pitch deck icin kullanilacak sayilar:
      - toplam_oyun
      - medyan_fiyat
      - ortalama_review_skoru
      - en_cok_eslesen_taglar (hangi taglerle beraber geliyor?)
      - fiyat_dagilimi
      - top10_oyun (en fazla sahibi olan)
    """
    tds = _filter_tag(df, tag)

    if tds.empty:
        return {"hata": f"'{tag}' tag'i bulunan oyun yok"}

    # Birlikte en sik gelen diger taglar
    all_tags = []
    for tags in tds["tags_list"]:
        for t in tags:
            if t != tag:
                all_tags.append(t)
    top_co_tags = Counter(all_tags).most_common(15)

    # Review skoru
    tds = tds.copy()
    tds["price"] = pd.to_numeric(tds["price"], errors="coerce").fillna(0)
    if "positive" in tds.columns and "negative" in tds.columns:
        total = tds["positive"] + tds["negative"]
        tds["review_score"] = (tds["positive"] / total.replace(0, float("nan")) * 100).round(1)

    # estimated_owners_mid
    if "estimated_owners_mid" not in tds.columns:
        def _mid(val):
            try:
                parts = str(val).split(" - ")
                return (int(parts[0]) + int(parts[1])) // 2 if len(parts) == 2 else None
            except Exception:
                return None
        tds["estimated_owners_mid"] = tds["estimated_owners"].apply(_mid)

    # Top 10 oyun (sahip sayisina gore)
    top10 = (
        tds.sort_values("estimated_owners_mid", ascending=False)
        [["name", "price", "review_score", "estimated_owners_mid", "release_year"]]
        .head(10)
    )

    return {
        "tag": tag,
        "toplam_oyun": len(tds),
        "medyan_fiyat": round(float(tds["price"].median()), 2),
        "ortalama_fiyat": round(float(tds["price"].mean()), 2),
        "ucretsiz_oran_pct": round(float((tds["price"] == 0).mean() * 100), 1),
        "medyan_review_skoru": round(float(tds["review_score"].median()), 1) if "review_score" in tds.columns else None,
        "ortalama_review_skoru": round(float(tds["review_score"].mean()), 1) if "review_score" in tds.columns else None,
        "en_cok_eslesen_taglar": top_co_tags,
        "top10_oyun": top10.to_dict(orient="records"),
    }


# ---------------------------------------------------------------------------
# Analiz 3 — Yillik Tur Buyume Trendi
# ---------------------------------------------------------------------------

def genre_growth_trend(df: pd.DataFrame, tags: list[str], years: tuple = (2015, 2024)) -> pd.DataFrame:
    """
    Verilen tag listesi icin yillik oyun sayisini hesaplar.

    Soktugu bilgi:
      - Her tag icin yillik release sayisi
      - CAGR (Compound Annual Growth Rate) = yillik ortalama buyume orani
        Formul: (son_yil / ilk_yil) ^ (1 / yil_sayisi) - 1

    CAGR neden kullanilir?
      - "2019'den 2024'e %30 artti" yerine
      - "Yillik ortalama %5.7 buyudu" demek daha anlaml
        cunku yil bazli dalgalanmalari dengeler.
    """
    start_year, end_year = years
    df_filtered = df[df["release_year"].between(start_year, end_year)].copy()
    year_range = list(range(start_year, end_year + 1))

    rows = []
    for tag in tags:
        mask = df_filtered["tags_list"].apply(lambda t: tag in t)
        yearly = df_filtered[mask].groupby("release_year").size()

        v_start = yearly.get(start_year, 0)
        v_end   = yearly.get(end_year, 0)
        n_years = end_year - start_year

        cagr = ((v_end / v_start) ** (1 / n_years) - 1) * 100 if v_start > 0 else None

        row = {"tag": tag, "cagr_pct": round(cagr, 1) if cagr else None}
        for y in year_range:
            row[str(y)] = int(yearly.get(y, 0))
        row["toplam"] = int(sum(yearly.get(y, 0) for y in year_range))
        rows.append(row)

    result = pd.DataFrame(rows).sort_values("cagr_pct", ascending=False)
    return result


# ---------------------------------------------------------------------------
# Analiz 4 — Review Skoru Dagilimi
# ---------------------------------------------------------------------------

def review_score_distribution(df: pd.DataFrame, tag: str = "Top-Down Shooter") -> pd.DataFrame:
    """
    Belirli bir tag'deki oyunlarin review skorunu kategorilere boler.

    Steam kategori sistemi:
      90-100 -> Overwhelmingly Positive
      80-89  -> Very Positive
      70-79  -> Mostly Positive
      40-69  -> Mixed
      0-39   -> Negative
    """
    tds = _filter_tag(df, tag).copy()

    if "positive" not in tds.columns:
        return pd.DataFrame()

    total = tds["positive"] + tds["negative"]
    tds["review_score"] = (tds["positive"] / total.replace(0, float("nan")) * 100)

    # En az 10 review olan oyunlar (kucuk orneklem yaniltmasin)
    tds = tds[total >= 10].copy()

    bins   = [0, 39, 69, 79, 89, 100]
    labels = ["Negatif (0-39)", "Mixed (40-69)", "Mostly Positive (70-79)",
              "Very Positive (80-89)", "Overwhelmingly Positive (90-100)"]
    tds["review_category"] = pd.cut(tds["review_score"], bins=bins, labels=labels)

    result = (
        tds.groupby("review_category", observed=True)
        .size()
        .reset_index(name="oyun_sayisi")
    )
    result["yuzde"] = (result["oyun_sayisi"] / result["oyun_sayisi"].sum() * 100).round(1)
    return result


# ---------------------------------------------------------------------------
# Snapshot Karsilastirmasi (May2024 vs Mar2025)
# ---------------------------------------------------------------------------

def snapshot_comparison(tag: str = "Top-Down Shooter") -> dict:
    """
    Iki snapshot arasindaki farki hesaplar.
    Hangi oyunlar yeni geldi? Fiyat/review degisti mi?
    """
    try:
        df_may  = _load_processed("steam_games_may2024.csv")
        df_mar  = _load_processed("steam_games_march2025.csv")
    except FileNotFoundError as e:
        return {"hata": str(e)}

    tds_may = _filter_tag(df_may, tag)
    tds_mar = _filter_tag(df_mar, tag)

    # Yeni gelen oyunlar (Mar2025'te var, May2024'te yok)
    ids_may = set(tds_may["appid"].astype(str))
    ids_mar = set(tds_mar["appid"].astype(str))
    yeni_ids = ids_mar - ids_may

    yeni_oyunlar = tds_mar[tds_mar["appid"].astype(str).isin(yeni_ids)]

    def _med_price(df_sub):
        p = pd.to_numeric(df_sub["price"], errors="coerce").fillna(0)
        return round(float(p.median()), 2)

    return {
        "tag": tag,
        "may2024_oyun_sayisi": len(tds_may),
        "mar2025_oyun_sayisi": len(tds_mar),
        "yeni_oyun_sayisi": len(yeni_oyunlar),
        "buyume_pct": round((len(tds_mar) - len(tds_may)) / len(tds_may) * 100, 1),
        "may2024_medyan_fiyat": _med_price(tds_may),
        "mar2025_medyan_fiyat": _med_price(tds_mar),
        "yeni_oyunlar_ornegi": yeni_oyunlar[["name", "price", "release_year"]].head(10).to_dict(orient="records"),
    }


# ---------------------------------------------------------------------------
# Ana Pipeline
# ---------------------------------------------------------------------------

def run_analysis(snapshot: str = "march2025") -> None:
    """
    Tum analizleri sirasi ile calistirir ve sonuclari yazdirir.
    Ileride dosyaya kaydetme de eklenecek.
    """
    print("Veri yukleniyor...")
    df = _load_processed(f"steam_games_{snapshot}.csv")
    print(f"  {len(df):,} oyun yuklendi")

    TAG = "Top-Down Shooter"
    TAGS_LIST = ["Top-Down Shooter", "Action", "RPG", "Horror", "Rogue-lite",
                 "Action Roguelike", "Platformer", "Puzzle", "Simulation", "Strategy", "2D"]

    SEP = "\n" + "=" * 65 + "\n"

    # --- Analiz 1: Fiyat Gruplari ---
    print(SEP + "ANALIZ 1 — Fiyat Grubu vs Sahip Sayisi")
    price_df = price_bucket_analysis(df)
    print(price_df.to_string(index=False))

    # --- Analiz 2: TDS Derin Dalisi ---
    print(SEP + f"ANALIZ 2 — {TAG} Pazar Analizi")
    tds_data = tds_deep_dive(df, TAG)
    print(f"  Toplam oyun     : {tds_data['toplam_oyun']:,}")
    print(f"  Medyan fiyat    : ${tds_data['medyan_fiyat']}")
    print(f"  Ucretsiz oran   : %{tds_data['ucretsiz_oran_pct']}")
    print(f"  Ort. review     : %{tds_data['ortalama_review_skoru']}")
    print(f"\n  En sik eslesen taglar (ilk 10):")
    for t, count in tds_data["en_cok_eslesen_taglar"][:10]:
        print(f"    {t:<25} {count:>5} oyun")
    print(f"\n  TOP 10 oyun (sahip sayisina gore):")
    for i, g in enumerate(tds_data["top10_oyun"], 1):
        print(f"    {i:2}. {g['name']:<35} ${g.get('price', 0):<6}  %{g.get('review_score', '?')} poz.")

    # --- Analiz 3: Buyume Trendi ---
    print(SEP + "ANALIZ 3 — Yillik Tur Buyume Trendi (CAGR 2015-2024)")
    growth_df = genre_growth_trend(df, TAGS_LIST)
    print(growth_df[["tag", "2019", "2021", "2023", "2024", "cagr_pct", "toplam"]].to_string(index=False))

    # --- Analiz 4: Review Dagilimi ---
    print(SEP + f"ANALIZ 4 — {TAG} Review Skoru Dagilimi")
    rev_df = review_score_distribution(df, TAG)
    print(rev_df.to_string(index=False))

    # --- Analiz 5: Snapshot Karsilastirmasi ---
    print(SEP + "ANALIZ 5 — Snapshot Karsilastirmasi (May2024 vs Mar2025)")
    snap = snapshot_comparison(TAG)
    if "hata" in snap:
        print(f"  Atlandi: {snap['hata']}")
    else:
        print(f"  May 2024  : {snap['may2024_oyun_sayisi']:,} oyun  (medyan ${snap['may2024_medyan_fiyat']})")
        print(f"  Mar 2025  : {snap['mar2025_oyun_sayisi']:,} oyun  (medyan ${snap['mar2025_medyan_fiyat']})")
        print(f"  Yeni giren: {snap['yeni_oyun_sayisi']:,} oyun  (%{snap['buyume_pct']} artis)")
        print(f"\n  Yeni gelen oyunlardan ornekler:")
        for g in snap["yeni_oyunlar_ornegi"][:5]:
            print(f"    - {g['name']} (${g.get('price', 0)}, {g.get('release_year', '?')})")

    print("\n=== ANALIZ TAMAMLANDI ===")

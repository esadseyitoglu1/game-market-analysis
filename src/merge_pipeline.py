"""Merge Pipeline — Kaggle base verisini canlı SteamSpy API verisiyle birleştirir.

İki iş yapar:
  1. UPSERT (güncelle veya ekle):
     - Mevcut oyunlar → positive, negative, owners, ccu kolonlarını güncelle
     - Yeni oyunlar   → Steam Store API'den zenginleştirip ekle
  2. Sonucu data/processed/steam_games_live.csv olarak kaydet

Kullanım:
  python -m src.merge_pipeline              # sadece mevcut oyunları güncelle
  python -m src.merge_pipeline --add-new    # yeni oyunları da ekle (yavaş, Steam API)
  python -m src.merge_pipeline --pages 5    # kaç SteamSpy sayfası çekilsin (1 sayfa = ~1000 oyun)
"""

import argparse
import time
from pathlib import Path

import pandas as pd

from src.fetcher import (
    fetch_app_list,
    fetch_app_details,
    fetch_full_app_list_by_appid,
    REQUEST_DELAY_SECONDS,
)
from src.processor import _parse_estimated_owners

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

# SteamSpy kolonları → Kaggle kolon isimleriyle eşleşme tablosu
# Sol: SteamSpy adı   Sağ: Kaggle/base dataset adı
STEAMSPY_TO_BASE = {
    "positive":       "positive",
    "negative":       "negative",
    "owners":         "estimated_owners",   # format farklı ama aynı veri
    "ccu":            "peak_ccu",
    "average_forever": "average_playtime_forever",
    "median_forever":  "median_playtime_forever",
    "price":          "price",              # dikkat: string gelir, int'e çevir
    "discount":       "discount",
}

# Bu kolonlar değişmez — API'den gelse bile Kaggle verisini koru
IMMUTABLE_COLS = ["genres", "tags", "categories", "release_date", "release_year",
                  "short_description", "metacritic_score", "achievements",
                  "windows", "mac", "linux"]


def _load_base(snapshot: str = "march2025") -> pd.DataFrame:
    """Kaggle base verisini yükle ve appid index'e al."""
    path = PROCESSED_DIR / f"steam_games_{snapshot}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} bulunamadı. Önce processor.run_pipeline() çalıştır.")
    df = pd.read_csv(path, low_memory=False)
    df["appid"] = df["appid"].astype(int)
    return df


def fetch_all_steamspy(pages: int = 1) -> pd.DataFrame:
    """SteamSpy'dan `pages` sayfa veri çek, tek DataFrame döndür.

    1 sayfa ≈ 1000 oyun. Tam katalog için ~50+ sayfa lazım ama
    rate limit yüzünden her sayfa arasında bekleme var.

    Java benzetmesi:
      List<Map<String,Object>> allRecords = new ArrayList<>();
      for (int page = 0; page < pages; page++) {
          allRecords.addAll(fetchPage(page));
          Thread.sleep(1000);
      }
    """
    all_records = []
    for page in range(pages):
        print(f"  SteamSpy sayfa {page} çekiliyor...")
        records = fetch_app_list(page)   # list[dict] döner
        all_records.extend(records)      # listeyi büyüt — Java'da addAll()
        time.sleep(REQUEST_DELAY_SECONDS)

    if not all_records:
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    df["appid"] = pd.to_numeric(df["appid"], errors="coerce").dropna().astype(int)
    return df


def update_existing(base_df: pd.DataFrame, api_df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Mevcut oyunların dinamik kolonlarını API verisiyle güncelle.

    UPSERT'in UPDATE kısmı:
      - appid eşleşen satırlarda positive, negative, owners, ccu güncelle
      - Diğer kolonlara (genres, tags, release_date) dokunma

    Pandas 2.x Copy-on-Write notu:
      base_indexed["col"].update(other)  ← artık çalışmıyor (kopya üzerinde işlem)
      base_indexed.update(frame)         ← doğru yol: tüm frame'i güncelle

    Returns:
      (güncellenmiş DataFrame, kaç satır güncellendi)
    """
    base_indexed = base_df.set_index("appid").copy()
    api_indexed  = api_df.set_index("appid").copy()

    common_ids = base_indexed.index.intersection(api_indexed.index)
    updated_count = len(common_ids)

    # Güncellenecek kolonları tek bir frame'de topla
    update_frame = pd.DataFrame(index=base_indexed.index)

    for spy_col, base_col in STEAMSPY_TO_BASE.items():
        if spy_col not in api_indexed.columns:
            continue
        if base_col not in base_indexed.columns:
            continue

        series = api_indexed[spy_col].reindex(base_indexed.index)

        if spy_col == "price":
            # SteamSpy cent cinsinden verir: "999" → $9.99
            series = pd.to_numeric(series, errors="coerce") / 100

        elif spy_col == "discount":
            series = pd.to_numeric(series, errors="coerce").fillna(0)

        elif spy_col == "owners":
            # Format dönüşümü: "100,000,000 .. 200,000,000" → "100000000 - 200000000"
            series = series.astype(str).str.replace(" .. ", " - ").str.replace(",", "")
            update_frame["estimated_owners"] = series
            continue

        update_frame[base_col] = series

    # Tek df.update() çağrısı — Copy-on-Write güvenli
    base_indexed.update(update_frame)

    # estimated_owners_mid yeniden hesapla
    if "estimated_owners" in base_indexed.columns:
        base_indexed["estimated_owners_mid"] = _parse_estimated_owners(
            base_indexed["estimated_owners"]
        )

    # review_score yeniden hesapla
    total = pd.to_numeric(base_indexed["positive"], errors="coerce") + \
            pd.to_numeric(base_indexed["negative"], errors="coerce")
    base_indexed["review_score"] = (
        pd.to_numeric(base_indexed["positive"], errors="coerce")
        / total.replace(0, float("nan")) * 100
    ).round(1)

    return base_indexed.reset_index(), updated_count


def enrich_new_game(appid: int) -> dict | None:
    """Yeni bir oyun için Steam Store API'den detay çek.

    SteamSpy sadece temel istatistikleri verir (sahip, review).
    Genres, tags, release_date için Steam Store API gerekli.

    Bu fonksiyon fetch_app_details() wrapper'ı — hata yönetimi ekler.
    """
    details = fetch_app_details(appid)
    if details is None:
        return None

    # Steam Store API'nin döndürdüğü alanları base formatına çevir
    try:
        genres = [g["description"] for g in details.get("genres", [])]
        categories = [c["description"] for c in details.get("categories", [])]
        release = details.get("release_date", {}).get("date", "")

        return {
            "genres": str(genres),
            "categories": str(categories),
            "release_date": release,
            "short_description": details.get("short_description", ""),
            "metacritic_score": details.get("metacritic", {}).get("score", 0),
            "achievements": details.get("achievements", {}).get("total", 0),
            "windows": details.get("platforms", {}).get("windows", False),
            "mac": details.get("platforms", {}).get("mac", False),
            "linux": details.get("platforms", {}).get("linux", False),
        }
    except Exception as e:
        print(f"    [UYARI] appid {appid} zenginleştirme hatası: {e}")
        return None


def add_new_games(base_df: pd.DataFrame, api_df: pd.DataFrame,
                  max_new: int = 50, full_catalog: bool = True) -> tuple[pd.DataFrame, int]:
    """Base'de olmayan yeni oyunları bulup Steam Store API'den zenginleştir ve ekle.

    UPSERT'in INSERT kısmı.

    full_catalog=True (varsayılan): "yeni oyun" havuzu SteamSpy'ın popülerlik-
    sıralı listesi (api_df) yerine fetch_full_app_list_by_appid() ile çekilir.
    NEDEN: api_df sadece SteamSpy'ın 'all' endpoint'inden gelen ilk birkaç
    sayfa (popülerlik sırası) — bu yüzden "yeni oyun" olarak SADECE en popüler
    oyunlar arasından yeni çıkanlar bulunuyordu, indie kuyruğu hiç
    keşfedilmiyordu (bkz. plan — "SteamSpy top-1000 sınırlaması"). Steam'in
    resmi IStoreService/GetAppList'i appid sırasına göre TÜM katalogu tarar,
    popülerlik ayrımı yapmaz — indie oyunlar da diğerleri kadar keşfedilir.

    max_new: Bir seferde kaç yeni oyun işlensin (Steam Store API rate limit
    resmi olarak dokümante edilmemiş, temkinli tutuluyor).
    """
    base_ids = set(base_df["appid"].astype(int))

    if full_catalog:
        print("  Tam Steam katalogu çekiliyor (appid sırasına göre, indie dahil)...")
        catalog = fetch_full_app_list_by_appid()
        catalog_ids = {int(a["appid"]) for a in catalog if "appid" in a}
        catalog_names = {int(a["appid"]): a.get("name", "") for a in catalog if "appid" in a}
    else:
        catalog_ids = set(api_df["appid"].astype(int))
        catalog_names = {}

    # Fark kümesi — Java'da: catalogIds.removeAll(baseIds)
    new_ids = catalog_ids - base_ids
    print(f"  Yeni oyun sayısı (katalogda var, base'de yok): {len(new_ids):,}")

    if not new_ids:
        return base_df, 0

    # max_new kadarını işle — EN BÜYÜK appid'lerden başlanıyor (Steam appid'leri
    # zaman içinde artan sırada atanır, bu yüzden en büyük appid ≈ en yeni
    # kayıt). Küçükten büyüğe sıralasaydık (appid=10, 20, 30...) Counter-Strike
    # gibi 2000'lerin başından kalma oyunları "yeni" diye işlemiş olurduk —
    # bu, ilk denemede gerçek veriyle test edilirken yakalandı.
    to_process = sorted(new_ids, reverse=True)[:max_new]
    print(f"  Bu seferlik {len(to_process)} yeni oyun işlenecek (en yüksek appid'ler)...")

    new_rows = []
    api_indexed = api_df.set_index("appid") if not api_df.empty else pd.DataFrame()

    for i, appid in enumerate(to_process, 1):
        print(f"    [{i}/{len(to_process)}] appid {appid} zenginleştiriliyor...")

        # SteamSpy'da varsa (popüler yeni oyunlar için) temel istatistikleri al
        spy_row = {}
        if not api_indexed.empty and appid in api_indexed.index:
            spy_row = api_indexed.loc[appid].to_dict()

        # Steam Store API'den detay çek (tür, tag, yayın tarihi — bunlar SteamSpy'da yok)
        time.sleep(REQUEST_DELAY_SECONDS)  # rate limit
        enriched = enrich_new_game(appid)

        # SteamSpy'da yoksa (indie kuyruğunda sıkça olur) isim katalogdan gelir
        name = spy_row.get("name") or catalog_names.get(appid, "")

        # Satırı birleştir
        row = {
            "appid": appid,
            "name": name,
            "positive": spy_row.get("positive", 0),
            "negative": spy_row.get("negative", 0),
            "estimated_owners": str(spy_row.get("owners", "")).replace(" .. ", " - ").replace(",", ""),
            "peak_ccu": spy_row.get("ccu", 0),
            "average_playtime_forever": spy_row.get("average_forever", 0),
            "median_playtime_forever": spy_row.get("median_forever", 0),
            "price": pd.to_numeric(spy_row.get("price", 0), errors="coerce") / 100 or 0,
            "discount": spy_row.get("discount", 0),
        }

        if enriched:
            row.update(enriched)

        new_rows.append(row)

    if not new_rows:
        return base_df, 0

    new_df = pd.DataFrame(new_rows)
    merged = pd.concat([base_df, new_df], ignore_index=True)
    return merged, len(new_rows)


def run_merge(base_snapshot: str = "march2025",
              pages: int = 1,
              add_new: bool = False,
              max_new: int = 50,
              full_catalog: bool = True) -> Path:
    """Tam merge pipeline'ı çalıştır.

    Args:
        base_snapshot: Hangi Kaggle snapshot'ı base alınsın
        pages:         Kaç SteamSpy sayfası çekilsin
        add_new:       Yeni oyunlar da eklensin mi (Steam API çağrısı gerektirir)
        max_new:       Tek seferde max kaç yeni oyun eklensin
        full_catalog:  Yeni oyun havuzu için Steam'in TAM katalogu mu (appid
                       sıralı, indie dahil) yoksa sadece SteamSpy'ın popülerlik
                       sıralı listesi mi taransın (bkz. add_new_games notu)

    Returns:
        Oluşturulan CSV dosyasının Path'i
    """
    print("=== MERGE PIPELINE BAŞLIYOR ===\n")

    # 1. Base yükle
    print(f"1. Base dataset yükleniyor ({base_snapshot})...")
    base_df = _load_base(base_snapshot)
    print(f"   {len(base_df):,} oyun yüklendi")

    # 2. SteamSpy'dan veri çek
    print(f"\n2. SteamSpy'dan {pages} sayfa çekiliyor...")
    api_df = fetch_all_steamspy(pages)
    print(f"   {len(api_df):,} oyun çekildi")

    # 3. Mevcut oyunları güncelle (UPDATE)
    print("\n3. Mevcut oyunlar güncelleniyor...")
    base_df, updated = update_existing(base_df, api_df)
    print(f"   {updated:,} oyun güncellendi")

    # 4. Yeni oyunları ekle (INSERT) — opsiyonel
    added = 0
    if add_new:
        print(f"\n4. Yeni oyunlar ekleniyor (max {max_new})...")
        base_df, added = add_new_games(base_df, api_df, max_new=max_new, full_catalog=full_catalog)
        print(f"   {added} yeni oyun eklendi")
    else:
        print("\n4. Yeni oyun ekleme atlandı (--add-new bayrağı yok)")

    # 5. Kaydet
    output_path = PROCESSED_DIR / "steam_games_live.csv"
    base_df.to_csv(output_path, index=False)
    print(f"\n5. Kaydedildi: {output_path}")
    print(f"   Toplam: {len(base_df):,} oyun")
    print(f"   Güncellenen: {updated:,} | Eklenen: {added}")
    print("\n=== MERGE TAMAMLANDI ===")

    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Steam veri merge pipeline")
    parser.add_argument("--base", default="march2025",
                        choices=["march2025", "may2024"],
                        help="Base Kaggle snapshot (default: march2025)")
    parser.add_argument("--pages", type=int, default=1,
                        help="SteamSpy sayfa sayısı (1 sayfa ≈ 1000 oyun, default: 1)")
    parser.add_argument("--add-new", action="store_true",
                        help="Yeni oyunları Steam Store API'den zenginleştirip ekle")
    parser.add_argument("--max-new", type=int, default=50,
                        help="Tek seferde max kaç yeni oyun eklensin (default: 50)")
    parser.add_argument("--no-full-catalog", action="store_false", dest="full_catalog",
                        help="Yeni oyun taramasını SteamSpy'ın popülerlik-sıralı "
                             "listesiyle sınırla (varsayılan: Steam'in TAM katalogu, "
                             "indie dahil — bkz. add_new_games notu)")
    args = parser.parse_args()

    run_merge(
        base_snapshot=args.base,
        pages=args.pages,
        add_new=args.add_new,
        max_new=args.max_new,
        full_catalog=args.full_catalog,
    )

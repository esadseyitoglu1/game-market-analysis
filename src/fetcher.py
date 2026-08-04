"""Fetches raw market data from the SteamSpy and Steam Store APIs and saves it
to data/raw/ as JSON, ready for src/processor.py to clean.
"""

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

STEAMSPY_URL = "https://steamspy.com/api.php"
STEAM_APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
STEAM_APPLIST_URL = "https://api.steampowered.com/IStoreService/GetAppList/v1/"

STEAM_API_KEY = os.environ.get("STEAM_API_KEY")

REQUEST_DELAY_SECONDS = 1.0
MAX_RETRIES = 3


def _get_with_retry(url: str, params: dict) -> dict | None:
    """GET a URL with basic retry/backoff, returning parsed JSON or None on failure."""
    for attempt in range(1, MAX_RETRIES + 1):
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 429:
            wait = REQUEST_DELAY_SECONDS * attempt * 2
            print(f"Rate limited (429). Waiting {wait}s before retry {attempt}/{MAX_RETRIES}...")
            time.sleep(wait)
            continue

        print(f"Request failed ({response.status_code}) for {url} with params {params}")
        return None

    print(f"Giving up on {url} after {MAX_RETRIES} retries.")
    return None


def fetch_app_list(page: int = 0) -> list[dict]:
    """Fetch one page (~1000 apps) of SteamSpy's 'all apps' endpoint.

    SteamSpy paginates this endpoint instead of returning everything at once,
    since the full catalog is tens of thousands of games. Call this in a loop
    with increasing `page` values to build the full list, respecting
    REQUEST_DELAY_SECONDS between calls so SteamSpy doesn't rate-limit us.
    """
    data = _get_with_retry(STEAMSPY_URL, {"request": "all", "page": page})
    if data is None:
        return []

    # SteamSpy returns a dict keyed by app_id; we convert to a list of records
    # because that's the shape pandas.DataFrame() expects downstream.
    return list(data.values())


def fetch_full_app_list_by_appid(max_results_per_page: int = 50000,
                                   max_pages: int | None = None) -> list[dict]:
    """Steam'in TAM katalogunu (popülerliğe göre değil, appid sırasına göre)
    IStoreService/GetAppList üzerinden çeker.

    NEDEN BU FONKSİYON VAR: fetch_app_list() (yukarıda) SteamSpy'ın 'all'
    endpoint'ini kullanıyor — o endpoint POPÜLERLİĞE göre sayfalanmış, yani
    sadece ilk birkaç sayfa (~1000-5000 oyun) çekilirse en çok oynanan
    oyunlar gelir, indie kuyruğu (bu projenin asıl odak noktası) hiç
    görünmez. IStoreService/GetAppList ise appid sırasına göre sayfalıyor
    (last_appid parametresiyle devam edilir) — bu yüzden TÜM oyunları
    (indie dahil) tarar, hangisi popüler hangisi değil ayrımı yapmaz.

    Eski (deprecated) ISteamApps/GetAppList v2 yerine bu kullanılıyor —
    Valve v2'yi "artık ölçeklenmiyor" diyerek kullanımdan kaldırdı.

    Döner: appid + name içeren dict listesi (fiyat/tür gibi detaylar YOK —
    onlar için appdetails ile ayrı sorgu gerekir, bkz. fetch_app_details).
    """
    if not STEAM_API_KEY:
        print("[UYARI] STEAM_API_KEY ayarlı değil (.env dosyasına bakın). Boş liste dönülüyor.")
        return []

    all_apps = []
    last_appid = 0
    page = 0

    while True:
        if max_pages is not None and page >= max_pages:
            break

        params = {
            "key": STEAM_API_KEY,
            "max_results": max_results_per_page,
            "include_games": True,
            "include_dlc": False,
            "include_software": False,
            "include_videos": False,
            "include_hardware": False,
        }
        if last_appid:
            params["last_appid"] = last_appid

        data = _get_with_retry(STEAM_APPLIST_URL, params)
        if data is None:
            break

        response = data.get("response", {})
        apps = response.get("apps", [])
        all_apps.extend(apps)

        print(f"  GetAppList sayfa {page}: {len(apps)} oyun (toplam {len(all_apps):,})")

        if not response.get("have_more_results"):
            break

        last_appid = response.get("last_appid")
        page += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    return all_apps


def fetch_app_details(app_id: int) -> dict | None:
    """Fetch official Steam Store details (price, genres, release date) for one app.

    Unlike SteamSpy's bulk endpoint, this is a per-app call — so it's only used
    for apps we've already shortlisted via fetch_app_list(), not the whole catalog.
    """
    data = _get_with_retry(STEAM_APPDETAILS_URL, {"appids": app_id})
    if data is None:
        return None

    app_data = data.get(str(app_id), {})
    if not app_data.get("success"):
        return None

    return app_data.get("data")


def save_raw(records: list[dict] | dict, filename: str) -> Path:
    """Save fetched data as-is (raw JSON) under data/raw/.

    We save the untouched API response before any cleaning happens, so that if
    our cleaning logic in processor.py has a bug later, we can re-run it against
    this file instead of burning API calls again.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RAW_DIR / filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    return output_path


def fetch_and_save_app_list(pages: int = 1) -> Path:
    """Convenience wrapper: fetch `pages` pages of SteamSpy data and save to disk."""
    all_records = []
    for page in range(pages):
        print(f"Fetching SteamSpy page {page}...")
        all_records.extend(fetch_app_list(page))
        time.sleep(REQUEST_DELAY_SECONDS)

    return save_raw(all_records, "steamspy_app_list.json")

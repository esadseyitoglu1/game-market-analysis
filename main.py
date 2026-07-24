"""Entry point: orchestrates the full pipeline.

  fetch  → data/raw/         (SteamSpy + Steam Store API)
  process → data/processed/  (clean CSVs from Kaggle snapshots)
  analyze → terminal output  (market insights)

Usage:
  python main.py              # full pipeline (process + analyze)
  python main.py --fetch      # also hit live Steam API
  python main.py --snapshot may2024   # analyze a different snapshot
"""

import argparse

from src.processor import run_pipeline
from src.analyzer import run_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Steam Indie Game Market Analysis")
    parser.add_argument("--fetch", action="store_true",
                        help="Fetch fresh data from SteamSpy API before processing")
    parser.add_argument("--snapshot", default="march2025",
                        choices=["march2025", "may2024", "both"],
                        help="Which Kaggle snapshot to process/analyze (default: march2025)")
    args = parser.parse_args()

    # Step 1 — Fetch (optional, hits live API)
    if args.fetch:
        from src.fetcher import fetch_and_save_app_list
        print("=== ADIM 1: Canli API'den Veri Cekiliyor ===")
        output_path = fetch_and_save_app_list(pages=1)
        print(f"  Ham veri kaydedildi: {output_path}\n")
    else:
        print("=== ADIM 1: API Atlanıyor (--fetch bayragi yok) ===\n")

    # Step 2 — Process Kaggle snapshots
    print("=== ADIM 2: Kaggle Verisi Isleniyor ===")
    results = run_pipeline(args.snapshot)
    print(f"  Islenen dosyalar: {list(results.keys())}\n")

    # Step 3 — Analyze
    snapshot_to_analyze = "march2025" if args.snapshot == "both" else args.snapshot
    print(f"=== ADIM 3: Analiz Calistiriliyor ({snapshot_to_analyze}) ===")
    run_analysis(snapshot_to_analyze)


if __name__ == "__main__":
    main()

"""
Steam Indie Market Analysis - Pipeline Orchestrator (n8n Entry Point)
Bu script n8n tarafindan "python src/main.py" seklinde tetiklenir.
Tum asamalari (processor -> visualizer -> insight_engine) sirayla ve guvenle calistirir.
Hata durumunda exit(1) ile n8n'e hata firlatir, basarida exit(0) ile bitirir.
"""

import sys
import logging
from pathlib import Path

# Loglama Ayarlari (Hem ekrana hem dosyaya)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = OUTPUT_DIR / "pipeline.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("Orchestrator")

# Modulleri ice aktar
from src.processor import run_pipeline as run_processor
from src.visualizer import run_charts as run_visualizer
from src.discovery.run_all import run as run_discovery
from src.insight_engine import run as run_engine

# 2026-08-07: "march2025" -> "live". Kaggle anlik goruntusu yerine
# merge_pipeline.py'nin urettigi data/processed/steam_games_live.csv
# kullaniliyor (guncel review/fiyat/CCU + yeni cikan oyunlar). Dogrulandi:
# visibility_pct kohort ortalamasi (2016-2025) hala ~0.500, istatistik
# bozulmadi (bkz. docs/live_data_update.md). live snapshot'i tazelemek icin
# duzenli araliklarla (onerilen: ayda bir) `python -m src.merge_pipeline
# --pages 5 --add-new --max-new 300` calistirilmali, yoksa zamanla yine
# bayatlar.
ACTIVE_SNAPSHOT = "live"

def main():
    try:
        log.info("="*50)
        log.info("PIPELINE STARTING: n8n Automation")
        log.info("="*50)

        # 1. Veri Temizleme ve Hazirlama — SADECE Kaggle ham snapshot'lari icin
        # (march2025/may2024). "live" zaten merge_pipeline.py tarafindan ayri
        # uretiliyor (data/processed/steam_games_live.csv), run_processor'a
        # ihtiyaci yok — bu adim live modunda atlaniyor.
        if ACTIVE_SNAPSHOT in ("march2025", "may2024"):
            log.info("--- STEP 1: Data Processing ---")
            run_processor(ACTIVE_SNAPSHOT)
        else:
            log.info("--- STEP 1: Data Processing (atlandi, live snapshot merge_pipeline.py'den geliyor) ---")

        # 2. Grafiklerin Uretilmesi
        log.info("--- STEP 2: Visualizer ---")
        run_visualizer(ACTIVE_SNAPSHOT)

        # 3. Kanita Bagli Kesif Motoru (eski anomaly_detector.py'nin yerine).
        # NOT (2026-08-03): anomaly_detector.py'nin urettigi (kanitsiz, hardcoded
        # esikli) autonomous_anomalies.json artik uretilmiyor. Bunun yerine
        # discovery/run_all.py TUM hipotez ailelerini (tag_single, tag_pair,
        # numeric_split, boolean_flag, studio_repeat, temporal, quality_cliff)
        # TEK bir Mann-Whitney U + Benjamini-Hochberg FDR + etki buyuklugu +
        # bootstrap havuzunda degerlendirip findings.json'u uretiyor.
        log.info("--- STEP 3: Discovery Engine (Kanita Bagli Kesif) ---")
        run_discovery(ACTIVE_SNAPSHOT)

        # 4. Yorumlama ve Senaryo Uretimi (Kati JSON Ciktisi)
        log.info("--- STEP 4: Insight Engine ---")
        run_engine(ACTIVE_SNAPSHOT)

        log.info("="*50)
        log.info("PIPELINE COMPLETED SUCCESSFULLY")
        log.info("="*50)
        sys.exit(0)

    except Exception as e:
        log.error("PIPELINE FAILED!", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

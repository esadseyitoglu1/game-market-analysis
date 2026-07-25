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
from src.visualizer import run as run_visualizer
from src.insight_engine import run as run_engine

def main():
    try:
        log.info("="*50)
        log.info("PIPELINE STARTING: n8n Automation")
        log.info("="*50)
        
        # 1. Veri Temizleme ve Hazirlama
        log.info("--- STEP 1: Data Processing ---")
        run_processor("march2025")
        
        # 2. Grafiklerin Uretilmesi
        log.info("--- STEP 2: Visualizer ---")
        run_visualizer("march2025")
        
        # 3. Yorumlama ve Senaryo Uretimi (Kati JSON Ciktisi)
        log.info("--- STEP 3: Insight Engine ---")
        run_engine("march2025")
        
        log.info("="*50)
        log.info("PIPELINE COMPLETED SUCCESSFULLY")
        log.info("="*50)
        sys.exit(0)
        
    except Exception as e:
        log.error("PIPELINE FAILED!", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

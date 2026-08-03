"""
Steam Indie Market - Autonomous Anomaly Detector
Scans the dataset for statistical outliers and unusual correlations.
Outputs a JSON of raw findings for an LLM to consume.
"""

import logging
import json
import random
from pathlib import Path
import pandas as pd
import numpy as np

log = logging.getLogger(__name__)
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "insights"

# Sabit seed: aynı veri setinde her çalıştırma aynı 10 anomaliyi seçsin
# (tekrarlanabilirlik / reproducibility için). Eskiden seed'siz random.shuffle
# kullanılıyordu, bu da pipeline'ı denetlenemez kılıyordu.
RANDOM_SEED = 42

def _load(snapshot="march2025") -> pd.DataFrame:
    df = pd.read_csv(PROCESSED_DIR / f"steam_games_{snapshot}.csv", low_memory=False)
    # Use the parsed midpoint from data processor
    if "estimated_owners_mid" in df.columns:
        df["estimated_owners"] = df["estimated_owners_mid"]
        
    # Basic numeric conversion
    for col in ["price", "positive", "negative", "estimated_owners"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    
    if "positive" in df.columns and "negative" in df.columns:
        total = df["positive"] + df["negative"]
        df["review_score"] = (df["positive"] / total.replace(0, float("nan")) * 100)
    
    import ast
    def _tags(val):
        if pd.isna(val): return []
        try:
            r = ast.literal_eval(str(val))
            return list(r.keys()) if isinstance(r, dict) else (r if isinstance(r, list) else [])
        except: return []
        
    df["tags_list"] = df["tags"].apply(_tags)
    return df[df["genres"].fillna("").str.contains("Indie")].copy()

def find_anomalies(snapshot="march2025"):
    df = _load(snapshot)
    
    # 1. Explode tags to group games by tag
    df_tags = df.explode("tags_list")
    tag_stats = df_tags.groupby("tags_list").agg(
        game_count=("appid", "count"),
        median_price=("price", "median"),
        median_score=("review_score", "median"),
        median_owners=("estimated_owners", "median")
    ).reset_index()
    
    # Filter tags with at least 50 games for statistical significance
    tag_stats = tag_stats[tag_stats["game_count"] >= 50].copy()
    
    # Calculate Z-Scores
    for col in ["median_price", "median_score", "median_owners"]:
        mean = tag_stats[col].mean()
        std = tag_stats[col].std()
        tag_stats[f"{col}_z"] = (tag_stats[col] - mean) / std

    import os
    os.makedirs("scratch", exist_ok=True)
    tag_stats.to_csv("scratch/tag_stats_debug.csv", index=False)
    
    anomalies = []
    
    # 2. Quality Trap Outliers (High score, low owners)
    trap_tags = tag_stats[(tag_stats["median_score_z"] > 0.5) & (tag_stats["median_owners_z"] < -0.1)]
    log.info(f"Found {len(trap_tags)} Quality Traps")
    for _, row in trap_tags.iterrows():
        tag = row["tags_list"]
        tag_df = df_tags[df_tags["tags_list"] == tag]
        optimal_price = f"${tag_df['price'].quantile(0.6):.2f} - ${tag_df['price'].quantile(0.8):.2f}"
        anomalies.append({
            "type": "Kalite Tuzağı (Oyuncular seviyor ama satmıyor)",
            "tag": tag,
            "finding": f"İnceleme puanı harika ({row['median_score']:.1f}%), ancak satışlar yerlerde sürünüyor. Bu türdeki oyunlar dar ama fanatik bir kitleye hitap ettiği için puanı şişiriyor ama para kazandırmıyor.",
            "optimal_price_band": optimal_price,
            "median_owners": row["median_owners"]
        })
        
    # 3. Hype Balloon Outliers (High price/owners, low score)
    hype_tags = tag_stats[(tag_stats["median_score_z"] < -0.5) & (tag_stats["median_owners_z"] > 0.1)]
    log.info(f"Found {len(hype_tags)} Hype Balloons")
    for _, row in hype_tags.iterrows():
        tag = row["tags_list"]
        tag_df = df_tags[df_tags["tags_list"] == tag]
        optimal_price = f"${tag_df['price'].quantile(0.6):.2f} - ${tag_df['price'].quantile(0.8):.2f}"
        anomalies.append({
            "type": "Hype Balonu (Pazarlama harikası ama oyuncuyu üzen)",
            "tag": tag,
            "finding": f"Oyuncuların puanları berbat ({row['median_score']:.1f}%), ama satışlar ortalamanın çok üstünde. Oyuncular bu türe o kadar aç ki oyun kötü olsa bile satın alıyorlar.",
            "optimal_price_band": optimal_price,
            "median_owners": row["median_owners"]
        })
        
    # 4. Correlation Flippers
    global_corr = df["price"].corr(df["estimated_owners"])
    top_tags = tag_stats.sort_values("game_count", ascending=False).head(100)["tags_list"]
    
    for tag in top_tags:
        tag_df = df_tags[df_tags["tags_list"] == tag]
        if len(tag_df) < 50: continue
        
        local_corr = tag_df["price"].corr(tag_df["estimated_owners"])
        
        if pd.notna(local_corr) and abs(local_corr - global_corr) > 0.25:
            if local_corr > 0.1:
                trend = "Oyunun fiyatı ne kadar yüksekse o kadar ÇOK satıyor (Premium algısı)."
            else:
                trend = "Oyunun fiyatı yüksek oldukça satışlar DRAMATİK şekilde dibe vuruyor."
                
            optimal_price = f"${tag_df['price'].quantile(0.6):.2f} - ${tag_df['price'].quantile(0.8):.2f}"
            anomalies.append({
                "type": "Fiyat Psikolojisi Anomalisi",
                "tag": tag,
                "finding": f"Normalde oyunların fiyatı arttıkça satışlar düşer. Ancak '{tag}' türünde bu durum tamamen değişiyor: {trend}",
                "optimal_price_band": optimal_price,
                "median_owners": tag_df["estimated_owners"].median()
            })
            
    # 5. Decay Anomalisi (Çöküş Trendi)
    df_tags["release_year"] = pd.to_datetime(df_tags["release_date"], errors="coerce").dt.year
    decay_count = 0
    for tag in top_tags:
        tag_df = df_tags[df_tags["tags_list"] == tag]
        yearly = tag_df.groupby("release_year")["review_score"].median().dropna()
        if len(yearly) >= 4 and yearly.index.max() >= 2022:
            slope = np.polyfit(yearly.index, yearly.values, 1)[0]
            if slope < -2.0:  # Her yıl 2 puandan fazla düşüş
                optimal_price = f"${tag_df['price'].quantile(0.6):.2f} - ${tag_df['price'].quantile(0.8):.2f}"
                anomalies.append({
                    "type": "Çöküş Trendi (Altın çağı biten türler)",
                    "tag": tag,
                    "finding": f"Bu türün altın çağı bitti. Kalite ve oyuncu tatmini her yıl istikrarlı bir şekilde {abs(slope):.1f} puan düşüyor. Eski popülerliğine aldanıp bu türe girenler büyük bir hüsran yaşıyor.",
                    "optimal_price_band": optimal_price,
                    "median_owners": tag_df["estimated_owners"].median()
                })
                decay_count += 1
    log.info(f"Found {decay_count} Decay Anomalies")

    # Sisteme "Hafıza" ekliyoruz: Geçmişte LLM'e sunulan konuları bir daha asla sunma.
    # NOT: Dizin, dosyayı okumadan/yazmadan ÖNCE oluşturulmalı — aksi halde ilk
    # çalıştırmada (outputs/insights/ henüz yokken) FileNotFoundError alınır.
    insights_dir = os.path.join(os.path.dirname(__file__), "..", "outputs", "insights")
    os.makedirs(insights_dir, exist_ok=True)
    history_file = os.path.join(insights_dir, "used_tags.txt")

    used_tags = set()
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            used_tags = set(line.strip() for line in f)

    # Daha önce kullanılanları çöpe at
    fresh_anomalies = [a for a in anomalies if a["tag"] not in used_tags]

    # Eğer 131 konunun hepsini tüketirsek (aylar sonra), hafızayı sıfırla başa dön
    if len(fresh_anomalies) < 10:
        used_tags = set()
        fresh_anomalies = anomalies
        if os.path.exists(history_file):
            os.remove(history_file)

    # Kalan taze verileri DETERMİNİSTİK sırala ve 10 tane seç.
    # Eskiden random.shuffle (seed'siz) kullanılıyordu — bu, aynı girdiyle
    # farklı çıktı üretip pipeline'ı tekrarlanamaz (non-reproducible) kılıyordu.
    # Sabit seed'li bir RNG ile karıştırma hâlâ "çeşitlilik" hissi verir ama
    # aynı veri setinde her çalıştırmada aynı sonucu üretir.
    rng = random.Random(RANDOM_SEED)
    rng.shuffle(fresh_anomalies)
    final_anomalies = fresh_anomalies[:10]

    # Seçilen bu 10 konuyu hafızaya kaydet ki haftaya bir daha çıkmasınlar!
    with open(history_file, "a", encoding="utf-8") as f:
        for a in final_anomalies:
            f.write(a["tag"] + "\n")

    return final_anomalies

def run(snapshot="march2025"):
    log.info("Tarayici Baslatiliyor (Otonom Anomali Avcisi)...")
    anomalies = find_anomalies(snapshot)
    
    log.info(f"  Bulunan Anomali Sayisi: {len(anomalies)}")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "autonomous_anomalies.json"
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(anomalies, f, indent=2, ensure_ascii=False)
        
    log.info(f"  Kaydedildi -> {out_path}")
    return anomalies

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

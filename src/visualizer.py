"""Steam Indie Market — Görselleştirme Modülü (v2)

Vizyon:
  - Tüm indie pazarı, TDS odağı YOK
  - Medyan kullanılır, ortalama değil
  - Her grafikte n= örneklem sayısı belirtilir
  - Arz değil, başarı (talep) gösterilir
  - Sade, sosyal medyada paylaşılabilir tasarım

5 grafik:
  1. hype_vs_reality.png  — Hype Balonu vs Gerçek Başarı (tür bazlı)
  2. the_80pct_cliff.png  — %80 Review Uçurumu
  3. price_sweet_spot.png — Fiyat Tatlı Noktası (medyan sahip)
  4. tag_synergy.png      — En İyi Tag Kombinasyonları
  5. top10_paid_indie.png — Ücretli Indie Top 10
"""

import ast
import argparse
from pathlib import Path
from itertools import combinations

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Renk sistemi
# ---------------------------------------------------------------------------
C = {
    "bg":      "#0D1117",
    "panel":   "#161B22",
    "grid":    "#21262D",
    "text":    "#E6EDF3",
    "muted":   "#8B949E",
    "blue":    "#4FC3F7",
    "green":   "#56D364",
    "yellow":  "#E3B341",
    "red":     "#F85149",
    "purple":  "#BC8CFF",
    "gray":    "#30363D",
}

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUTPUT_DIR    = Path(__file__).resolve().parent.parent / "outputs" / "charts"

MIN_REVIEWS_FOR_QUALITY = 10    # Kalite analizi için minimum review sayısı
# NOT: Kaggle dataseti pre-filtered — owners_mid düz 10k çıkıyor.
# Başarı proxy olarak review sayısı kullanıyoruz (doğal dağılımlı).
# EŞİK KESİNLİKLE VERİDEN HESAPLANIR — kodda sabit sayı yok.
# calc_success_threshold() fonksiyonu %80 percentile'ı hesaplar.

def calc_success_threshold(df) -> tuple[int, int, int]:
    """
    Başarı eşiğini veriden hesapla: 
      1. Görünürlük: indie oyunların %80 percentile review sayısı (üst %20).
      2. Kalite: %80+ pozitif review oranı (Steam 'Very Positive').
    Döndürür: (review_thresh, quality_thresh, n_indie)
    """
    indie = df[df["is_indie"] & (df["total_reviews"] > 0)]
    review_thresh = int(indie["total_reviews"].quantile(0.80))
    quality_thresh = 80
    n_indie   = len(indie)
    return review_thresh, quality_thresh, n_indie


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _style():
    plt.rcParams.update({
        "figure.facecolor": C["bg"],   "axes.facecolor":   C["bg"],
        "axes.edgecolor":   C["grid"], "axes.labelcolor":  C["text"],
        "axes.titlecolor":  C["text"], "xtick.color":      C["text"],
        "ytick.color":      C["text"], "grid.color":       C["grid"],
        "grid.linewidth":   0.7,       "text.color":       C["text"],
        "font.family":      "sans-serif", "font.size":     11,
        "axes.titlesize":   14,        "axes.labelsize":   11,
        "figure.dpi":       150,
    })


def _save(fig, name):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUTPUT_DIR / name
    fig.savefig(p, bbox_inches="tight", facecolor=C["bg"])
    plt.close(fig)
    print(f"  Kaydedildi -> {p.name}")
    return p


def _note(ax, text):
    """Grafiğin sol alt köşesine küçük açıklama notu + zorunlu veri kaynağı."""
    full_text = (
        f"{text}\n"
        "Veri: Kaggle (artermiloff/steam-games-dataset, Mart 2025, ~90k oyun) + SteamSpy API  |  "
        "⚠️ Sahip sayıları SteamSpy tahminidir, Valve resmi rakam paylaşmaz."
    )
    ax.text(0.01, -0.10, full_text, transform=ax.transAxes,
            fontsize=7.5, color=C["muted"], va="top", wrap=True)


def _load(snapshot="march2025"):
    df = pd.read_csv(PROCESSED_DIR / f"steam_games_{snapshot}.csv", low_memory=False)
    df["release_date"]  = pd.to_datetime(df["release_date"], errors="coerce")
    df["release_year"]  = df["release_date"].dt.year.astype("Int64")
    df["release_month"] = df["release_date"].dt.month.astype("Int64")
    df["price"]         = pd.to_numeric(df["price"], errors="coerce").fillna(0)
    df["positive"]      = pd.to_numeric(df["positive"], errors="coerce").fillna(0)
    df["negative"]      = pd.to_numeric(df["negative"], errors="coerce").fillna(0)

    total = df["positive"] + df["negative"]
    df["review_score"] = (df["positive"] / total.replace(0, float("nan")) * 100).round(1)
    df["total_reviews"] = total

    def _mid(val):
        try:
            p = str(val).split(" - ")
            return (int(p[0]) + int(p[1])) // 2 if len(p) == 2 else 0
        except:
            return 0

    df["owners_mid"] = df.get(
        "estimated_owners_mid",
        df["estimated_owners"].apply(_mid) if "estimated_owners" in df.columns else 0
    )
    df["owners_mid"] = pd.to_numeric(df["owners_mid"], errors="coerce").fillna(0)

    def _tags(val):
        if pd.isna(val): return []
        try:
            r = ast.literal_eval(str(val))
            return list(r.keys()) if isinstance(r, dict) else (r if isinstance(r, list) else [])
        except:
            return []

    def _genres(val):
        if pd.isna(val): return []
        try:
            r = ast.literal_eval(str(val))
            return r if isinstance(r, list) else []
        except:
            return []

    df["tags_list"]   = df["tags"].apply(_tags)
    df["genres_list"] = df["genres"].apply(_genres) if "genres" in df.columns else [[] for _ in range(len(df))]
    df["is_indie"]    = df["genres_list"].apply(lambda g: "Indie" in g)
    df["is_free"]     = df["price"] == 0

    return df


# ---------------------------------------------------------------------------
# Grafik 1 — Hype vs Gerçeklik
# ---------------------------------------------------------------------------

def chart_hype_vs_reality(df):
    """
    Tür başına: oyun sayısı (arz) vs başarı oranı (gerçek talep).
    Mesaj: 'Herkesin koştuğu türler genellikle tuzaktır.'
    Eşik: veriden hesaplanır (%80 percentile) — keyfi sayı yok.
    """
    # Eşiği VERİDEN hesapla
    success_threshold, quality_threshold, n_indie_total = calc_success_threshold(df)

    indie = df[df["is_indie"] & df["release_year"].between(2019, 2024)].copy()
    n_total = len(indie)

    # Analiz edilecek türler (yeterli oyun sayısı olan tag'ler)
    target_tags = [
        "Action Roguelike", "Rogue-lite", "Survival", "Battle Royale",
        "Tower Defense", "Metroidvania", "Platformer", "Puzzle",
        "Visual Novel", "Top-Down Shooter", "City Builder", "Simulation",
        "Horror", "Bullet Hell", "Deck Building"
    ]
    # NOT: 'Farming Sim' cikarildi — cok spesifik bir nis (Stardew Valley tipi).
    # Genel simulasyon pazarini temsil etmez. Yerine 'Simulation' kullanildi.

    rows = []
    for tag in target_tags:
        mask   = indie["tags_list"].apply(lambda t: tag in t)
        sub    = indie[mask]
        if len(sub) < 30:
            continue
        total   = len(sub)
        # Eşik veriden gelir: %80 percentile = {success_threshold} review VE %80+ pozitif
        success = (
            (sub["total_reviews"] >= success_threshold) & 
            (sub["review_score"] >= quality_threshold)
        ).sum()
        rate    = success / total * 100
        rows.append({"tag": tag, "total": total, "rate": rate})

    if not rows:
        print("  Hype vs Reality: yeterli veri yok, atlandi.")
        return

    stats = pd.DataFrame(rows).sort_values("rate", ascending=True)

    # Eşikleri VERİ BELİRLİYOR — keyfi değil
    mean_rate = stats["rate"].mean()
    std_rate  = stats["rate"].std()
    low_thresh  = mean_rate - 0.5 * std_rate   # Ortalamanın altı = Balon
    high_thresh = mean_rate + 0.5 * std_rate   # Ortalamanın üstü = Fırsat

    colors = []
    for r in stats["rate"]:
        if r < low_thresh:
            colors.append(C["red"])     # Hype Balonu
        elif r > high_thresh:
            colors.append(C["green"])   # Fırsat
        else:
            colors.append(C["blue"])    # Rekabetli

    fig, ax = plt.subplots(figsize=(11, 8))
    bars = ax.barh(stats["tag"], stats["rate"], color=colors, height=0.6)

    for bar, row in zip(bars, stats.itertuples()):
        ax.text(bar.get_width() + 0.3,
                bar.get_y() + bar.get_height() / 2,
                f"%{row.rate:.1f}  (n={row.total:,})",
                va="center", fontsize=9, color=C["text"])

    # Ortalama çizgisi — eşiğin dayanağı
    ax.axvline(mean_rate, color=C["yellow"], linewidth=1.5, linestyle="--", alpha=0.8,
               label=f"Tüm türler ortalaması: %{mean_rate:.1f}")
    ax.axvline(low_thresh,  color=C["red"],   linewidth=1, linestyle=":", alpha=0.5)
    ax.axvline(high_thresh, color=C["green"], linewidth=1, linestyle=":", alpha=0.5)

    # Efsane
    from matplotlib.patches import Patch
    legend = [
        Patch(color=C["red"],    label=f"Hype Balonu (<%{low_thresh:.1f} — ortalamanın altı)"),
        Patch(color=C["blue"],   label=f"Rekabetli (%{low_thresh:.1f}–{high_thresh:.1f} — ortalama bant)"),
        Patch(color=C["green"],  label=f"Fırsat (>%{high_thresh:.1f} — ortalamanın üstü)"),
        Patch(color=C["yellow"], label=f"Ortalama: %{mean_rate:.1f}", alpha=0.5),
    ]
    ax.legend(handles=legend, framealpha=0.15, edgecolor=C["grid"], loc="lower right")

    ax.set_title("Tür Başına Başarı Oranı: Hype mi, Gerçek mi?\n"
                 f"'Başarı' = {success_threshold}+ review VE %{quality_threshold}+ Pozitif  |  2019-2024 indie oyunlar",
                 fontweight="bold", pad=14)
    ax.set_xlabel(f"Başarı Oranı % ({success_threshold}+ rev & %{quality_threshold}+ pozitif)  |  Eşikler veriden hesaplandı, keyfi değil")
    ax.set_xlim(0, stats["rate"].max() * 1.4)
    ax.grid(True, axis="x", alpha=0.3)
    _note(ax, f"n={n_total:,} indie oyun (2019-2024)  |  "
              f"'Başarı' = {success_threshold}+ review (üst %20) + %{quality_threshold} Pozitif Skor  |  "
              f"Eşik = %80 percentile, veriden hesaplandı")

    fig.tight_layout()
    return _save(fig, "hype_vs_reality.png")


# ---------------------------------------------------------------------------
# Grafik 2 — %80 Review Uçurumu
# ---------------------------------------------------------------------------

def chart_80pct_cliff(df):
    """
    Review skoru bantlarına göre medyan sahip sayısı — tüm indie pazarı.
    Mesaj: '%80 Very Positive eşiğini geçmek satışları katlar.'
    """
    indie = df[df["is_indie"] & (df["total_reviews"] >= MIN_REVIEWS_FOR_QUALITY)].copy()
    n_total = len(indie)

    bins   = [0, 50, 60, 70, 75, 80, 85, 90, 95, 100]
    labels = ["<50%", "50-60%", "60-70%", "70-75%", "75-80%",
              "80-85%", "85-90%", "90-95%", "95%+"]

    indie["score_band"] = pd.cut(indie["review_score"], bins=bins, labels=labels, right=False)
    # Medyan review sayısı: review sayısı doğal dağılımlı, owners_mid değil
    stats = indie.groupby("score_band", observed=True).agg(
        medyan_review=("total_reviews", "median"),
        n=("total_reviews", "count")
    ).reset_index()

    colors = [C["red"] if str(b) in ["<50%", "50-60%", "60-70%"]
              else (C["yellow"] if str(b) in ["70-75%", "75-80%"]
              else C["green"]) for b in stats["score_band"]]

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(stats["score_band"].astype(str), stats["medyan_review"],
                  color=colors, width=0.65)

    for bar, row in zip(bars, stats.itertuples()):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 5,
                f"{row.medyan_review:.0f}\n(n={row.n:,})",
                ha="center", va="bottom", fontsize=9, color=C["text"])

    # %80 eşiği vurgusu
    ax.axvline(x=4.5, color=C["yellow"], linewidth=2, linestyle="--", alpha=0.8)
    ax.text(4.6, ax.get_ylim()[1] * 0.85, "Very Positive\nEşiği (%80)",
            color=C["yellow"], fontsize=10, fontweight="bold")

    ax.set_title("Review Skoru Bandına Göre Medyan Review Sayısı\n"
                 "Daha memnun oyuncular = daha fazla review = daha çok görünürlük",
                 fontweight="bold", pad=14)
    ax.set_xlabel("Review Skoru Bandı")
    ax.set_ylabel("Medyan Review Sayısı")
    ax.grid(True, axis="y", alpha=0.3)
    _note(ax, f"n={n_total:,} indie oyun (min {MIN_REVIEWS_FOR_QUALITY} review)  |  "
              f"'Kalite' = Steam oyuncu memnuniyeti skoru  |  "
              f"Medyan review sayısı: popülerlik proxy'si")
    fig.tight_layout()
    return _save(fig, "the_80pct_cliff.png")


# ---------------------------------------------------------------------------
# Grafik 4 — En İyi Tag Kombinasyonları (Tag Sinerjisi)
# ---------------------------------------------------------------------------

def chart_tag_synergy(df):
    """
    En yüksek medyan review getiren 2-tag (tür) kombinasyonları.
    Mesaj: 'Bu iki tür birlikte olunca altın.'
    """
    indie = df[df["is_indie"] & (df["total_reviews"] > 0)].copy()
    n_total = len(indie)
    
    # Başarı eşiğini al (ör: 171+ review ve %80+ kalite)
    success_threshold, quality_threshold, _ = calc_success_threshold(df)

    # En sık görülen tag'leri bul (analiz için)
    from collections import Counter
    all_tags = [t for tags in indie["tags_list"] for t in tags]
    
    # Meta-tag'leri çıkar (gerçek tür sinerjisi bulmak için)
    ignore_tags = {
        "Indie", "Singleplayer", "Multiplayer", "Co-op", "2D", "3D", 
        "Early Access", "Free to Play", "Casual", "Action", "Adventure",
        "Strategy", "Simulation", "RPG", "Great Soundtrack", "Atmospheric",
        "Pixel Graphics", "Story Rich", "Sci-fi", "Fantasy", "Anime",
        "VR", "Gore", "Violent", "Nudity", "Sexual Content"
    }
    
    top_tags = [t for t, _ in Counter(all_tags).most_common(60) if t not in ignore_tags]

    combo_stats = []
    for t1, t2 in combinations(top_tags, 2):
        mask = indie["tags_list"].apply(lambda tags: t1 in tags and t2 in tags)
        sub  = indie[mask]
        if len(sub) < 30: # Min 30 oyun
            continue
        combo_stats.append({
            "combo": f"{t1} + {t2}",
            "medyan_review": sub["total_reviews"].median(),
            "medyan_score": sub["review_score"].median(),
            "n": len(sub)
        })

    if not combo_stats:
        print("  Tag Synergy: yeterli veri yok, atlandi.")
        return

    stats = (pd.DataFrame(combo_stats)
             .sort_values("medyan_review", ascending=False)
             .head(12)
             .sort_values("medyan_review", ascending=True))

    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Renk mantığı: Hem görünürlük (171) hem de kalite (%80) eşiğini geçiyorsa YEŞİL (Başarılı)
    colors = [C["green"] if (row["medyan_review"] >= success_threshold and row["medyan_score"] >= quality_threshold) else C["blue"] 
              for _, row in stats.iterrows()]
              
    bars = ax.barh(stats["combo"], stats["medyan_review"], color=colors, height=0.6)

    for bar, row in zip(bars, stats.itertuples()):
        ax.text(bar.get_width() + (ax.get_xlim()[1] * 0.02),
                bar.get_y() + bar.get_height() / 2,
                f"{row.medyan_review:.0f}  (n={row.n}, %{row.medyan_score:.0f})",
                va="center", fontsize=9, color=C["text"])

    ax.set_title("Hangi İki Tür Bir Arada Olunca Başarı İhtimali Artıyor?\n"
                 f"Yeşil barlar: Ortalama bir oyun hem {success_threshold}+ review alıyor, hem de %{quality_threshold}+ pozitif not alıyor.",
                 fontweight="bold", pad=14)
    ax.set_xlabel("Ortalama Bir Oyunun Aldığı Review Sayısı")
    ax.grid(True, axis="x", alpha=0.3)
    _note(ax, f"n={n_total:,} indie oyun  |  Min 30 oyunlu kombinasyonlar  |  "
              f"Meta-tagler hariç tutuldu  |  Çift eşik (Görünürlük + Kalite) kullanıldı")
    fig.tight_layout()
    return _save(fig, "tag_synergy.png")


# ---------------------------------------------------------------------------
# Grafik 5 — Ücretli Indie Top 10
# ---------------------------------------------------------------------------

def chart_top10_paid_indie(df):
    """
    Ücretsiz oyunları filtrele, ücretli indie top 10.
    Mesaj: 'Başarının anatomisi — bu oyunlar ne yaptı?'
    """
    paid_indie = df[
        df["is_indie"] & ~df["is_free"] & (df["price"] > 0) &
        (df["total_reviews"] >= 100)
    ].copy()

    top10 = paid_indie.nlargest(10, "owners_mid").sort_values("owners_mid", ascending=True)
    n_total = len(paid_indie)

    # Fiyat bandına göre renk
    def price_color(p):
        if p <= 5:   return C["yellow"]
        if p <= 15:  return C["blue"]
        return C["green"]

    colors = [price_color(p) for p in top10["price"]]

    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(top10["name"], top10["owners_mid"] / 1_000_000,
                   color=colors, height=0.65)

    for bar, row in zip(bars, top10.itertuples()):
        label = (f"{row.owners_mid/1_000_000:.1f}M sahip  |  "
                 f"${row.price:.2f}  |  %{row.review_score:.0f} poz.")
        ax.text(bar.get_width() + 0.03,
                bar.get_y() + bar.get_height() / 2,
                label, va="center", fontsize=8.5, color=C["text"])

    from matplotlib.patches import Patch
    legend = [
        Patch(color=C["yellow"], label="$1-5"),
        Patch(color=C["blue"],   label="$5-15"),
        Patch(color=C["green"],  label="$15+"),
    ]
    ax.legend(handles=legend, framealpha=0.15, edgecolor=C["grid"],
              title="Fiyat Bandı", loc="lower right")

    ax.set_title("Ücretli Indie Oyunlar — En Fazla Sahibe Ulaşan 10 Oyun\n"
                 "Ücretsiz ve F2P oyunlar hariç tutuldu",
                 fontweight="bold", pad=14)
    ax.set_xlabel("Tahmini Sahip (milyon)")
    ax.grid(True, axis="x", alpha=0.3)
    _note(ax, f"n={n_total:,} ücretli indie oyun (min 100 review)  |  "
              f"Ücretsiz/F2P oyunlar hariç: adil karşılaştırma için")
    fig.tight_layout()
    return _save(fig, "top10_paid_indie.png")


# ---------------------------------------------------------------------------
# Ana çalıştırıcı
# ---------------------------------------------------------------------------

def run_charts(snapshot="march2025"):
    _style()
    print(f"Veri yukleniyor ({snapshot})...")
    df = _load(snapshot)
    indie = df[df["is_indie"]]
    print(f"  {len(df):,} oyun  |  Indie: {len(indie):,}  |  "
          f"Ucretli Indie: {len(indie[~indie['is_free']]):,}\n")
    print("Grafikler olusturuluyor...")

    chart_hype_vs_reality(df)
    chart_80pct_cliff(df)
    chart_tag_synergy(df)
    chart_top10_paid_indie(df)

    print(f"\nTumu hazir -> {OUTPUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="march2025",
                        choices=["march2025", "may2024", "live"])
    args = parser.parse_args()
    run_charts(args.snapshot)

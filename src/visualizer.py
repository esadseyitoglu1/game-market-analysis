"""Steam Indie Market — Görselleştirme Modülü

6 grafik, indie developer ve yatırımcı için anlamlı:
  1. genre_trend.png         — TDS Steam ortalamasının üzerinde büyüyor (revize)
  2. market_saturation.png   — Başarı oranı düşüyor mu? (YENİ)
  3. success_rate_price.png  — Hangi fiyat bandında başarı olasılığı yüksek? (YENİ)
  4. min_viable_quality.png  — Kaç review skoru gerekli? (YENİ)
  5. price_review_matrix.png — Fiyat × Kalite → ortalama sahip ısı haritası (YENİ)
  6. review_distribution.png — TDS review dağılımı + hedef bölge (revize)
"""

import ast
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
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
    "tds":     "#4FC3F7",   # senin türün — açık mavi
    "success": "#56D364",   # başarı — yeşil
    "warning": "#E3B341",   # dikkat — sarı
    "danger":  "#F85149",   # tehlike — kırmızı
    "accent":  "#BC8CFF",   # vurgu — mor
    "avg":     "#30363D",   # ortalama — koyu gri
}

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUTPUT_DIR    = Path(__file__).resolve().parent.parent / "outputs" / "charts"


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


def _load(snapshot="march2025"):
    df = pd.read_csv(PROCESSED_DIR / f"steam_games_{snapshot}.csv", low_memory=False)
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    df["release_year"] = df["release_date"].dt.year.astype("Int64")
    df["release_month"] = df["release_date"].dt.month.astype("Int64")
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
    df["positive"] = pd.to_numeric(df["positive"], errors="coerce").fillna(0)
    df["negative"] = pd.to_numeric(df["negative"], errors="coerce").fillna(0)
    total = df["positive"] + df["negative"]
    df["review_score"] = (df["positive"] / total.replace(0, float("nan")) * 100).round(1)
    df["total_reviews"] = total

    def _mid(val):
        try:
            p = str(val).split(" - ")
            return (int(p[0]) + int(p[1])) // 2 if len(p) == 2 else 0
        except: return 0

    df["owners_mid"] = df.get("estimated_owners_mid",
                              df["estimated_owners"].apply(_mid) if "estimated_owners" in df.columns else 0)
    df["owners_mid"] = pd.to_numeric(df["owners_mid"], errors="coerce").fillna(0)

    def _tags(val):
        if pd.isna(val): return []
        try:
            r = ast.literal_eval(str(val))
            return list(r.keys()) if isinstance(r, dict) else (r if isinstance(r, list) else [])
        except: return []

    def _genres(val):
        if pd.isna(val): return []
        try:
            r = ast.literal_eval(str(val))
            return r if isinstance(r, list) else []
        except: return []

    df["tags_list"]   = df["tags"].apply(_tags)
    df["genres_list"] = df["genres"].apply(_genres) if "genres" in df.columns else [[]] * len(df)
    df["is_indie"]    = df["genres_list"].apply(lambda g: "Indie" in g)
    df["is_tds"]      = df["tags_list"].apply(lambda t: "Top-Down Shooter" in t)
    return df


# ---------------------------------------------------------------------------
# Grafik 1 — Genre Trend (revize: TDS'i ortalamayla karşılaştır)
# ---------------------------------------------------------------------------

def chart_genre_trend(df):
    """
    TDS büyümesini Steam ortalamasıyla ve yavaş büyüyen türlerle karşılaştır.
    Mesaj: 'TDS pazar ortalamasının üzerinde büyüyor'
    """
    years  = list(range(2016, 2025))
    filt   = df[df["release_year"].between(2016, 2024)].copy()

    # Steam genel
    steam_yearly = filt.groupby("release_year").size().reindex(years, fill_value=0)
    steam_base   = steam_yearly[2016]
    steam_idx    = (steam_yearly / steam_base * 100).values  # endeks (2016=100)

    tag_configs = [
        ("Top-Down Shooter", C["tds"],     "o",  2.5, True),   # senin türün
        ("Action Roguelike", C["accent"],  "s",  2.0, True),   # hızlı büyüyen komşu
        ("RPG",              C["warning"], "^",  1.5, False),  # yavaş komşu
        ("Strategy",         C["muted"],   "v",  1.5, False),  # yavaş komşu
    ]

    fig, ax = plt.subplots(figsize=(12, 6))

    # Steam ortalaması — referans çizgi
    ax.plot(years, steam_idx, color=C["avg"], linewidth=1.5,
            linestyle="--", label="Steam Ortalaması", zorder=1)
    ax.fill_between(years, steam_idx, alpha=0.06, color=C["avg"])

    for tag, color, marker, lw, highlight in tag_configs:
        mask   = filt["tags_list"].apply(lambda t: tag in t)
        yearly = filt[mask].groupby("release_year").size().reindex(years, fill_value=0)
        base   = max(yearly[2016], 1)
        idx    = (yearly / base * 100).values

        ax.plot(years, idx, color=color, marker=marker,
                linewidth=lw + (0.5 if highlight else 0),
                markersize=6 if highlight else 5,
                label=tag, zorder=3 if highlight else 2,
                alpha=1.0 if highlight else 0.65)

        # Son değer etiketi — sadece öne çıkanlar
        if highlight:
            ax.annotate(f"+{idx[-1]-100:.0f}%",
                        xy=(years[-1], idx[-1]),
                        xytext=(6, 0), textcoords="offset points",
                        color=color, fontsize=9, va="center", fontweight="bold")

    ax.axhline(100, color=C["grid"], linewidth=0.8, linestyle=":")
    ax.set_title("Steam'de Tür Büyüme Endeksi — 2016 Bazlı (2016 = 100)",
                 fontweight="bold", pad=14)
    ax.set_ylabel("Büyüme Endeksi (2016 = 100)")
    ax.set_xlabel("Yıl")
    ax.set_xticks(years)
    ax.legend(framealpha=0.15, edgecolor=C["grid"], loc="upper left")
    ax.grid(True, axis="y", alpha=0.35)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x)}"))

    # Açıklama notu
    ax.text(0.01, 0.02,
            "Not: Endeks = her türün kendi 2016 değerine göre büyüme oranı",
            transform=ax.transAxes, fontsize=8, color=C["muted"])

    fig.tight_layout()
    return _save(fig, "genre_trend.png")


# ---------------------------------------------------------------------------
# Grafik 2 — Pazar Doygunluğu: Başarı Oranı Trendi (YENİ)
# ---------------------------------------------------------------------------

def chart_market_saturation(df):
    """
    Her yıl kaç TDS oyunu çıktı, bunların kaçı 500+ review aldı?
    Mesaj: 'Pazar büyüyor ama başarı oranı X — erken girmek hâlâ mantıklı'

    500 review ≈ Steam'de 'görünür' olmak için minimum kabul edilen eşik
    (500 review → tahminen ~15-20k satış)
    """
    REVIEW_THRESHOLD = 500
    years = list(range(2018, 2025))  # 2025 tamamlanmadı

    tds = df[df["is_tds"] & df["release_year"].between(2018, 2024)].copy()

    rows = []
    for y in years:
        cohort   = tds[tds["release_year"] == y]
        total    = len(cohort)
        visible  = (cohort["total_reviews"] >= REVIEW_THRESHOLD).sum()
        rate     = visible / total * 100 if total > 0 else 0
        rows.append({"yil": y, "toplam": total, "basarili": visible, "oran": rate})

    sat = pd.DataFrame(rows)

    fig, ax1 = plt.subplots(figsize=(11, 6))
    ax2 = ax1.twinx()  # iki y ekseni

    # Sol eksen: bar — yıllık yeni oyun sayısı
    bars = ax1.bar(sat["yil"], sat["toplam"], color=C["avg"],
                   alpha=0.55, width=0.6, label="Yeni TDS oyunu")
    ax1.bar(sat["yil"], sat["basarili"], color=C["success"],
            alpha=0.85, width=0.6, label=f"{REVIEW_THRESHOLD}+ review (görünür)")

    # Sağ eksen: çizgi — başarı oranı
    ax2.plot(sat["yil"], sat["oran"], color=C["warning"],
             marker="o", linewidth=2, markersize=7, label="Başarı oranı %", zorder=5)
    for _, row in sat.iterrows():
        ax2.annotate(f"%{row['oran']:.1f}",
                     xy=(row["yil"], row["oran"]),
                     xytext=(0, 10), textcoords="offset points",
                     ha="center", color=C["warning"], fontsize=9, fontweight="bold")

    ax1.set_title(f"TDS Pazarı: Yıllık Yeni Oyun vs Başarıya Ulaşan ({REVIEW_THRESHOLD}+ Review)",
                  fontweight="bold", pad=14)
    ax1.set_xlabel("Çıkış Yılı")
    ax1.set_ylabel("Oyun Sayısı", color=C["text"])
    ax2.set_ylabel(f"Başarı Oranı % ({REVIEW_THRESHOLD}+ review)", color=C["warning"])
    ax2.tick_params(axis="y", colors=C["warning"])
    ax2.set_ylim(0, 35)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2,
               framealpha=0.15, edgecolor=C["grid"], loc="upper left")
    ax1.grid(True, axis="y", alpha=0.3)

    ax1.text(0.01, 0.02,
             f"Not: {REVIEW_THRESHOLD}+ review ≈ tahminen 15-25k satış eşiği",
             transform=ax1.transAxes, fontsize=8, color=C["muted"])

    fig.tight_layout()
    return _save(fig, "market_saturation.png")


# ---------------------------------------------------------------------------
# Grafik 3 — Fiyat Bandına Göre Başarı Oranı (REPLACE: price_vs_owners)
# ---------------------------------------------------------------------------

def chart_success_rate_by_price(df):
    """
    Sadece indie oyunlarda: Her fiyat bandındaki oyunların kaçı 10k+ sahibe ulaştı?
    Mesaj: 'Mutlak sahip değil, ORAN önemli — hangi fiyat daha güvenli?'
    """
    OWNER_THRESHOLD = 10_000
    indie = df[df["is_indie"] & (df["price"] > 0)].copy()  # ücretsiz hariç

    bins   = [0.01, 4.99, 9.99, 14.99, 19.99, float("inf")]
    labels = ["$1–5", "$5–10", "$10–15", "$15–20", "$20+"]
    indie["bucket"] = pd.cut(indie["price"], bins=bins, labels=labels)

    stats = (indie.groupby("bucket", observed=True)
             .apply(lambda g: pd.Series({
                 "n": len(g),
                 "basarili": (g["owners_mid"] >= OWNER_THRESHOLD).sum(),
                 "oran": (g["owners_mid"] >= OWNER_THRESHOLD).mean() * 100,
                 "medyan_owners": g["owners_mid"].median(),
             }), include_groups=False)
             .reset_index())

    fig, ax = plt.subplots(figsize=(10, 6))

    colors = [C["warning"] if r < 20 else C["success"] for r in stats["oran"]]
    bars = ax.bar(stats["bucket"].astype(str), stats["oran"],
                  color=colors, width=0.55, edgecolor="none")

    for bar, row in zip(bars, stats.itertuples()):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"%{row.oran:.1f}\n({row.basarili}/{row.n} oyun)",
                ha="center", va="bottom", fontsize=9.5, fontweight="bold",
                color=C["text"])

    ax.axhline(stats["oran"].mean(), color=C["accent"], linewidth=1.5,
               linestyle="--", label=f"Ortalama: %{stats['oran'].mean():.1f}")

    ax.set_title(f"Indie Oyunlarda Fiyat Bandına Göre Başarı Oranı\n"
                 f"({OWNER_THRESHOLD:,}+ tahmini sahip = başarı)",
                 fontweight="bold", pad=14)
    ax.set_xlabel("Fiyat Bandı")
    ax.set_ylabel("Başarı Oranı %")
    ax.set_ylim(0, max(stats["oran"]) * 1.35)
    ax.legend(framealpha=0.15, edgecolor=C["grid"])
    ax.grid(True, axis="y", alpha=0.3)

    ax.text(0.01, 0.02,
            "Not: Ücretsiz oyunlar hariç. 'Başarı' = 10,000+ tahmini sahip.",
            transform=ax.transAxes, fontsize=8, color=C["muted"])

    fig.tight_layout()
    return _save(fig, "success_rate_price.png")


# ---------------------------------------------------------------------------
# Grafik 4 — Minimum Viable Quality (YENİ)
# ---------------------------------------------------------------------------

def chart_min_viable_quality(df):
    """
    10k / 100k / 500k sahibe ulaşan TDS oyunlarının review skoru dağılımı.
    Mesaj: 'Şu review skorunun altında kalmak çok maliyetli'
    """
    tds = df[df["is_tds"] & (df["total_reviews"] >= 20)].copy()

    tiers = [
        ("10k+ sahip",    10_000,  C["warning"]),
        ("100k+ sahip",   100_000, C["tds"]),
        ("500k+ sahip",   500_000, C["success"]),
    ]

    fig, ax = plt.subplots(figsize=(11, 6))

    # Tüm TDS arka plan dağılımı
    all_scores = tds["review_score"].dropna()
    ax.hist(all_scores, bins=30, color=C["avg"], alpha=0.4,
            label=f"Tüm TDS (n={len(all_scores):,})", edgecolor="none")

    for label, threshold, color in tiers:
        subset = tds[tds["owners_mid"] >= threshold]["review_score"].dropna()
        if len(subset) < 5:
            continue
        ax.hist(subset, bins=20, color=color, alpha=0.65,
                label=f"{label} (n={len(subset):,}, med=%{subset.median():.0f})",
                edgecolor="none")
        # Medyan çizgisi
        ax.axvline(subset.median(), color=color, linewidth=1.5,
                   linestyle="--", alpha=0.9)

    # Tehlike bölgesi — %70 altı
    ax.axvspan(0, 70, alpha=0.07, color=C["danger"])
    ax.text(35, ax.get_ylim()[1] * 0.85, "Tehlike\nbölgesi",
            ha="center", color=C["danger"], fontsize=9, alpha=0.8)

    ax.set_title("TDS Oyunlarında Review Skoru vs Başarı Seviyesi\n"
                 "('Başarılı' oyunlar hangi review skoruyla çıkmış?)",
                 fontweight="bold", pad=14)
    ax.set_xlabel("Review Skoru (%)")
    ax.set_ylabel("Oyun Sayısı")
    ax.set_xlim(0, 100)
    ax.legend(framealpha=0.15, edgecolor=C["grid"])
    ax.grid(True, axis="y", alpha=0.3)

    ax.text(0.01, 0.02,
            "Not: Minimum 20 review olan oyunlar dahil.",
            transform=ax.transAxes, fontsize=8, color=C["muted"])

    fig.tight_layout()
    return _save(fig, "min_viable_quality.png")


# ---------------------------------------------------------------------------
# Grafik 5 — Fiyat × Kalite Matrisi (YENİ)
# ---------------------------------------------------------------------------

def chart_price_quality_matrix(df):
    """
    Fiyat aralığı × Review skoru kesişiminde ortalama sahip sayısı ısı haritası.
    Mesaj: 'Yüksek kalite + doğru fiyat = en iyi konum'
    """
    tds = df[df["is_tds"] & (df["total_reviews"] >= 10)].copy()
    tds = tds[(tds["price"] > 0) & (tds["price"] <= 30)].copy()

    price_bins  = [0, 5, 10, 15, 20, 30]
    price_lbls  = ["$1–5", "$5–10", "$10–15", "$15–20", "$20–30"]
    review_bins = [0, 60, 70, 80, 90, 100]
    review_lbls = ["<60%", "60–70%", "70–80%", "80–90%", "90%+"]

    tds["p_bucket"] = pd.cut(tds["price"],        bins=price_bins,  labels=price_lbls)
    tds["r_bucket"] = pd.cut(tds["review_score"], bins=review_bins, labels=review_lbls)

    pivot = tds.pivot_table(
        index="r_bucket", columns="p_bucket",
        values="owners_mid", aggfunc="median",
        observed=True
    )

    # Eksik hücreleri 0 yap
    pivot = pivot.reindex(index=review_lbls, columns=price_lbls).fillna(0)

    fig, ax = plt.subplots(figsize=(10, 7))

    # Manuel ısı haritası (seaborn yerine)
    data = pivot.values.astype(float)
    vmax = data.max()
    im   = ax.imshow(data, cmap="Blues", aspect="auto",
                     vmin=0, vmax=max(vmax, 1))

    ax.set_xticks(range(len(price_lbls)))
    ax.set_yticks(range(len(review_lbls)))
    ax.set_xticklabels(price_lbls)
    ax.set_yticklabels(review_lbls)

    # Hücre değerleri
    for i in range(len(review_lbls)):
        for j in range(len(price_lbls)):
            val = data[i, j]
            txt = f"{val/1000:.0f}k" if val >= 1000 else ("—" if val == 0 else f"{int(val)}")
            brightness = val / max(vmax, 1)
            txt_color  = "white" if brightness > 0.5 else C["text"]
            ax.text(j, i, txt, ha="center", va="center",
                    fontsize=10, color=txt_color, fontweight="bold")

    plt.colorbar(im, ax=ax, label="Medyan Tahmini Sahip", shrink=0.8)
    ax.set_title("TDS Oyunları: Fiyat × Review Skoru → Medyan Sahip Sayısı\n"
                 "(Hangi kombinasyon en çok sahibe ulaştırıyor?)",
                 fontweight="bold", pad=14)
    ax.set_xlabel("Fiyat Bandı")
    ax.set_ylabel("Review Skoru")

    ax.text(0.01, -0.08,
            "Not: Minimum 10 review, ücretsiz hariç TDS oyunları.",
            transform=ax.transAxes, fontsize=8, color=C["muted"])

    fig.tight_layout()
    return _save(fig, "price_quality_matrix.png")


# ---------------------------------------------------------------------------
# Grafik 6 — Review Dağılımı (revize: hedef bölge vurgusu)
# ---------------------------------------------------------------------------

def chart_review_distribution(df):
    """TDS oyunlarının review dağılımı + 'buraya ulaşman gerekiyor' oku."""
    tds = df[df["is_tds"] & (df["total_reviews"] >= 10)].copy()

    bins   = [0, 39, 69, 79, 89, 100]
    labels = ["Negatif\n(<40%)", "Mixed\n(40–69%)", "Mostly Pos.\n(70–79%)",
              "Very Pos.\n(80–89%)", "Overwhelmingly\nPos. (90%+)"]
    colors = [C["danger"], C["warning"], "#FFF176", "#A5D6A7", C["tds"]]

    tds["cat"] = pd.cut(tds["review_score"], bins=bins, labels=labels)
    counts = tds["cat"].value_counts().reindex(labels).fillna(0)

    fig, ax = plt.subplots(figsize=(11, 6))
    bars = ax.bar(labels, counts.values, color=colors, width=0.6, edgecolor="none")

    total = counts.sum()
    for bar, val in zip(bars, counts.values):
        pct = val / total * 100
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 8,
                f"{int(val)}\n(%{pct:.1f})",
                ha="center", va="bottom", fontsize=9.5, color=C["text"])

    # "Hedef bölge" vurgusu
    ax.annotate("Hedef Bölge\n(başarılı TDS'lerin\n%65'i burada)",
                xy=(3.5, counts.values[3:].sum() / 2),
                xytext=(2.5, counts.values.max() * 0.85),
                arrowprops=dict(arrowstyle="->", color=C["success"], lw=1.5),
                color=C["success"], fontsize=9, ha="center",
                bbox=dict(boxstyle="round,pad=0.3", facecolor=C["panel"],
                          edgecolor=C["success"], alpha=0.9))

    ax.set_title("TDS Oyunları Review Skoru Dağılımı\n"
                 "Hedeflenen oyunun hangi kategoride yer alması gerekiyor?",
                 fontweight="bold", pad=14)
    ax.set_ylabel("Oyun Sayısı")
    ax.set_xlabel("Review Kategorisi")
    ax.grid(True, axis="y", alpha=0.3)
    ax.text(0.01, 0.02, f"Toplam: {int(total):,} TDS oyunu (min 10 review)",
            transform=ax.transAxes, fontsize=8, color=C["muted"])

    fig.tight_layout()
    return _save(fig, "review_distribution.png")


# ---------------------------------------------------------------------------
# Ana çalıştırıcı
# ---------------------------------------------------------------------------

def run_charts(snapshot="march2025"):
    _style()
    print(f"Veri yukleniyor ({snapshot})...")
    df = _load(snapshot)
    print(f"  {len(df):,} oyun | TDS: {df['is_tds'].sum():,} | Indie: {df['is_indie'].sum():,}\n")
    print("Grafikler olusturuluyor...")

    chart_genre_trend(df)
    chart_market_saturation(df)
    chart_success_rate_by_price(df)
    chart_min_viable_quality(df)
    chart_price_quality_matrix(df)
    chart_review_distribution(df)

    print(f"\nTumu hazir -> {OUTPUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="march2025",
                        choices=["march2025", "may2024", "live"])
    args = parser.parse_args()
    run_charts(args.snapshot)

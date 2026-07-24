# CONTEXT.md — Proje Bağlamı ve Devir-Teslim

## Proje Amacı
Steam indie oyun pazar analizi — iki hedef:
1. **Pitch deck / yatırımcı sunumu**: TDS (Top-Down Shooter) pazarında fırsat var mı?
2. **Sosyal medya içeriği (Reels serisi)**: "Build in public" formatında veri analizi süreci

## Kullanıcı Profili
- Yazılım geliştirici (Java / C# geçmişi)
- Indie oyun yapıyor (Top-Down Shooter türünde)
- Python'da veri işleme deneyimi az → öğrenirken yapıyor
- Sunucusu var, n8n kullanıyor
- Kaggle: `artermiloff/steam-games-dataset`

---

## Tamamlanan İşler

### Dosya Yapısı
```
game-market-analysis/
├── src/
│   ├── fetcher.py        ← SteamSpy + Steam Store API çekici
│   ├── processor.py      ← Kaggle CSV temizleyici (her iki snapshot)
│   ├── analyzer.py       ← 5 analiz fonksiyonu
│   ├── visualizer.py     ← 6 indie-focused grafik
│   └── merge_pipeline.py ← Kaggle base + canlı API birleştirici (UPSERT)
├── main.py               ← python main.py [--fetch] [--snapshot]
├── data/
│   ├── raw/steamspy_app_list.json    ← canlı API çıktısı (1 sayfa = 1000 oyun)
│   └── processed/
│       ├── steam_games_march2025.csv ← 89,618 oyun ✅
│       ├── steam_games_may2024.csv   ← 83,643 oyun ✅
│       └── steam_games_live.csv      ← merge pipeline çıktısı
├── outputs/charts/                   ← 6 grafik PNG (koyu tema)
│   ├── genre_trend.png
│   ├── market_saturation.png
│   ├── success_rate_price.png
│   ├── min_viable_quality.png
│   ├── price_quality_matrix.png
│   └── review_distribution.png
└── docs/
    ├── CONTEXT.md  ← bu dosya
    └── TASKS.md    ← görev takibi
```

### Kullanılan Komutlar
```bash
python main.py                          # process + analyze (march2025)
python main.py --fetch --snapshot both  # API + her iki snapshot
python -m src.visualizer               # 6 grafik üret
python -m src.merge_pipeline --pages 1  # canlı API ile güncelle
```

---

## Temel Analiz Bulguları

### TDS Pazar Özeti (Mart 2025)
| Metrik | Değer |
|--------|-------|
| Toplam TDS oyun | 2,205 |
| Medyan fiyat | $4.99 |
| Ortalama review skoru | %80.5 |
| Overwhelmingly Positive oran | %38.4 |
| Co-op olan TDS | %22 (476 oyun) |
| Solo olan TDS | %78 (1,729 oyun) |

### Büyüme (CAGR 2016→2024)
| Tür | CAGR | Steam ortalaması vs |
|-----|------|-------------------|
| Action Roguelike | %42.1 | +17.7pp |
| Rogue-lite | %39.4 | +15pp |
| Top-Down Shooter | %28.1 | +3.7pp |
| RPG | %18.3 | -6.1pp |
| Strategy | %16.9 | -7.5pp |

### Market Saturation
- Her yıl çıkan TDS'lerin sadece **%5-10'u** 500+ review'a ulaşıyor
- 2024: 483 yeni TDS → ~25'i görünür eşiği geçti

### Minimum Viable Quality
- 10k+ sahip: medyan **%84** pozitif review
- 100k+ sahip: medyan **%85** pozitif review
- 500k+ sahip: medyan **%87** pozitif review

### Fiyat × Kalite Matrisi
- En iyi kombinasyon: **$20-30 + %80-90 review** → 150k medyan sahip
- Diğer tüm kombinasyonlar: 35k veya altı

### Güncel Trend Bağlamı (Temmuz 2025)
- **PEAK** (Aggro Crab + Landfall) — Haziran 2025'te 3.1M kopya
  - Co-op climbing/party oyunu, streamer-friendly kaos
  - Viral formül: kaotik fizik + arkadaşlarla oynama + TikTok/Twitch
- **Wuchang: Fallen Feathers** — $19.1M (Soulslike)
- **Grounded 2** — $15.6M (Co-op Survival)
- Trend türler: Co-op Party, Cozy Life Sim, Narrative Indie

### Pitch Deck Argümanı
TDS + Co-op + "content-friendly" anlar = PEAK formülünün TDS'e uygulanması.
TDS'lerin %78'i solo → co-op eklenmiş TDS, az rekabetli bir niş.

---

## Bekleyen Görevler (Öncelik Sırasına Göre)

### 1. Content Brief (EN ÖNEMLİ — hemen yapılabilir)
`docs/CONTENT_BRIEF.md` dosyası oluşturulacak.
Her Reels episode için:
- Hook (ilk 3 saniye)
- Ana mesaj
- Kullanılacak grafik / veri
- Call to action

Episode planı:
```
Ep.1: "89,000 Steam oyununun verisini indirdim" (Kaggle + Python kurulum)
Ep.2: "Ham veriyi Python'da nasıl temizledim" (processor.py)
Ep.3: "TDS türü Steam ortalamasından hızlı büyüyor" (genre_trend.png)
Ep.4: "Başarılı indie oyunların 3 ortak özelliği" (min_viable_quality + price_quality_matrix)
Ep.5: "PEAK 3M kopya sattı — bundan ne öğrenebiliriz?" (güncel trend + co-op analiz)
Ep.6: "Rakip analizi: TDS'te kim önde?" (tds_top10.png)
```

### 2. Co-op TDS Analizi Grafik Olarak
scratch_coop.py'daki analizi visualizer.py'a ekle.
"TDS'lerin %22'si co-op" → grafik olarak göster, Reels için güçlü bir veri noktası.

### 3. Fetcher Tam Test
`python main.py --fetch` çalışıyor (1 sayfa test edildi).
Tüm katalog için `--pages 50` ile test edilmeli (rate limit riski var).

### 4. n8n Otomasyonu
Kullanıcının sunucusunda n8n var.
Haftalık: `python -m src.merge_pipeline --pages 5` çalıştırıp
başarı/başarısız bildirimi Discord'a gönderecek workflow kurulacak.

### 5. Content Brief → Reels Üretimi
Grafikler hazır. Script yazılınca Reels çekimine geçilebilir.

---

## Teknik Notlar

### Schema Farkı (Kritik)
- May 2024 dataset: `AppID` (büyük harf)
- March 2025 dataset: `appid` (küçük harf)
- processor.py'da normalize edildi: `rename_map = {c: c.lower() for c in raw_header}`

### Pandas 2.x Copy-on-Write
- `df["col"].update(other)` → artık çalışmıyor
- Doğru: `df.update(pd.DataFrame({"col": other}))`
- merge_pipeline.py'da düzeltildi

### Encoding
- Windows terminali cp1254: Türkçe karakter bazen bozuluyor
- Çözüm: `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')`

### SteamSpy Fiyat Formatı
- Cent cinsinden string gelir: `"999"` = $9.99
- `pd.to_numeric(series, errors="coerce") / 100` ile dönüştür

### Tag İsimleri (Önemli)
- ❌ `"Roguelite"` → ✅ `"Rogue-lite"` (tire ile!)
- ❌ `"Roguelike"` → ✅ `"Action Roguelike"` (Steam'deki tam isim)

---

## Git Durumu
```
master branch
Son commit: "chore: gitignore ekle"
Uncommitted: scratch_coop.py, outputs/charts/ (gitignore'da)
```

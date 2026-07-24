# TASKS.md — Aşama Takibi ve Devir-Teslim Notları

> Bu dosya sürekli güncellenir. Her oturumu bitiren model, en alta "Sıradaki Adım"
> bölümünü net şekilde yazmalıdır ki devralan model (Claude veya Gemini) sıfır bilgi
> kaybıyla devam edebilsin.

## Faz Checklist'i

- [x] **Faz 1 — Scaffold**: `.claudignore`, `docs/`, `data/`, `src/`, `requirements.txt`,
      `main.py` iskeleti kuruldu. İzole git deposu başlatıldı.
- [x] **Faz 2 — Fetcher**: `src/fetcher.py` içinde SteamSpy + Steam Store API'den veri
      çekme fonksiyonları yazıldı. **Henüz gerçek API'ye karşı test edilmedi.**
- [x] **Faz 3 — Processor**: `src/processor.py` tamamlandı.
      - Kaggle dataset: `artermiloff/steam-games-dataset` (Mart 2025 + Mayıs 2024 snapshots)
      - `data/processed/steam_games_march2025.csv` → 89,618 oyun ✅
      - `data/processed/steam_games_may2024.csv`   → 83,643 oyun ✅
      - Önemli fix: May2024'te kolon adı `AppID` (büyük), March2025'te `appid` — normalize edildi.
- [x] **Faz 4 — Analyzer**: `src/analyzer.py` tamamlandı. 5 analiz çalışıyor:
      1. Fiyat grubu vs sahip sayısı
      2. TDS pazar analizi (deep dive)
      3. Yıllık tür büyüme trendi (CAGR)
      4. Review skoru dağılımı
      5. Snapshot karşılaştırması (May2024 vs Mar2025)
- [x] **main.py güncellendi**: `python main.py` → tam pipeline (process + analyze).
      `--fetch` flag'i ile canlı API da eklenebilir.
- [ ] **Faz 5 — Fetcher Gerçek Test**: `python main.py --fetch` ile SteamSpy API'sine
      gerçek istek atılacak, `data/raw/steamspy_app_list.json` oluşacak.
- [ ] **Faz 6 — İçerik Çıktıları**: Public (sosyal medya) ve Internal (pitch deck)
      çıktı şablonlarının oluşturulması.

## Oturum Günlüğü

### Oturum 1 — 2026-07-23
- Proje sıfırdan kuruldu: dizin yapısı, belgeler, modül iskeletleri.
- `src/fetcher.py` tasarlandı (SteamSpy + Steam Store API, retry/backoff).

### Oturum 2 — 2026-07-23 / 2026-07-24
- Kaggle dataset kararı: `artermiloff/steam-games-dataset` seçildi.
  - 90k+ oyun, Mart 2025 (cleaned) + Mayıs 2024 (cleaned) — iki snapshot mevcut.
- `src/processor.py` tamamen implemente edildi:
  - `clean_app_list()`: kolon normalize, datetime parse, genres/tags string→list, owner→midpoint, review_score hesaplama
  - `filter_by_tag()`, `filter_by_tag()` yardımcı fonksiyonlar
  - `run_pipeline('both')` ile her iki snapshot işlendi
- `src/analyzer.py` tamamen implemente edildi (5 analiz fonksiyonu + `run_analysis()`)
- `main.py` güncellendi: argparse ile `--fetch` ve `--snapshot` desteği
- `learn_pandas.py` ve `genre_trend.py` geçici eğitim/keşif scriptleri oluşturuldu
  (bunlar `src/` dışında, pipeline'ın parçası değil)

## Temel Analiz Bulguları (Pitch Deck için)

### TDS Pazar Durumu (Mart 2025)
- **2,205 TDS oyunu** Steam'de mevcut
- **Medyan fiyat: $4.99** — oyuncular bu fiyata alışkın
- **Ortalama review skoru: %80.5** — tür kalite çıtası yüksek
- **%65'i "iyi"** (Very Positive veya üstü)
- **En sık eşleşen taglar:** Action, 2D, Singleplayer, Arcade, Bullet Hell, Pixel Graphics

### Büyüme Trendi (CAGR 2015→2024)
- TDS: **%28.1/yıl** — Steam genelinin (%24.4) **+3.7pp üzerinde**
- Sadece 2D (%27.0) ve Horror (%26.4) benzer büyüme gösteriyor
- 2024: 483 yeni TDS oyunu (2019'daki 130'dan 3.7x artış)

### Fiyat Stratejisi İçin
- $20+ oyunlar ortalama 483k sahip (diğer grupların 3-8x'i)
- TDS medyan $4.99 ama en başarılılar (Hotline Miami, HELLDIVERS) $10-20 bandında

## Sıradaki Adım (Devralan Model İçin)

**1. Fetcher gerçek API testi:**
```
python main.py --fetch
```
`data/raw/steamspy_app_list.json` oluştu mu kontrol et.
Eğer rate limit (429) alıyorsa `REQUEST_DELAY_SECONDS`'ı artır (fetcher.py L16).

**2. Roguelite tag sorunu:**
`genre_growth_trend()` Roguelite için 0 döndürüyor — tags column'da farklı yazılıyor olabilir.
`df["tags_list"].apply(lambda t: any("rogue" in x.lower() for x in t)).sum()` ile ara.

**3. İçerik Çıktıları (Faz 6):**
Analiz sonuçları mevcut, sosyal medya formatına dönüştürülecek.
`docs/CONTENT_BRIEF.md` oluşturulacak — her Reels episode için script/hook/data point.

**4. Git commit:**
Henüz commit yapılmadı. `git add . && git commit -m "faz3-4: processor ve analyzer tamamlandi"` çalıştır.

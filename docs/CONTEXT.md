# CONTEXT.md — Proje Bağlamı ve Devir-Teslim

## Proje Amacı
Steam indie oyun pazar analizi. İki uzun vadeli hedef:
1. **Sosyal medya operasyonu (ŞU AN):** Indie geliştirici topluluğuna gerçek, aksiyon alınabilir pazar zekası (market intelligence) üretmek. Yalanları çürütmek, balonları patlatmak, trendleri önceden görmek.
2. **Pitch deck / yatırımcı sunumu (SONRA):** İleride kendi TDS oyunumuza yönelik, verilerle desteklenmiş yatırımcı sunumu.

## Kullanıcı Profili
- Yazılım geliştirici (Java / C# geçmişi), Python öğrenme aşamasında
- Indie oyun yapıyor (Top-Down Shooter türünde)
- Sunucusu var: **Debian**, **n8n kurulu**
- Kaggle: `artermiloff/steam-games-dataset`
- Bildirimler **Telegram** üzerinden (Discord TR'de yasak)

---

## Dosya Yapısı

```
game-market-analysis/
├── src/
│   ├── fetcher.py          ← SteamSpy + Steam Store API çekici
│   ├── processor.py        ← Kaggle CSV temizleyici (her iki snapshot)
│   ├── analyzer.py         ← Analiz fonksiyonları
│   ├── visualizer.py       ← Grafik üretici (YENİDEN YAZILACAK)
│   ├── insight_engine.py   ← Çıkarım motoru (HENÜZ YAZILMADI)
│   └── merge_pipeline.py   ← Kaggle base + canlı API birleştirici (UPSERT)
├── main.py                 ← python main.py [--fetch] [--snapshot]
├── data/
│   ├── raw/steamspy_app_list.json    ← canlı API çıktısı
│   └── processed/
│       ├── steam_games_march2025.csv ← 89,618 oyun ✅
│       ├── steam_games_may2024.csv   ← 83,643 oyun ✅
│       └── steam_games_live.csv      ← merge pipeline çıktısı
├── outputs/
│   ├── charts/             ← Üretilen grafikler (temizlendi, yeniler gelecek)
│   └── insights/           ← Insight Engine raporları (weekly_report.md)
└── docs/
    ├── CONTEXT.md          ← bu dosya
    ├── TASKS.md            ← görev takibi
    └── CONTENT_BRIEF.md    ← Reels serisi script taslakları
```

### Çalışan Komutlar
```bash
python main.py                           # process + analyze
python main.py --fetch --snapshot both   # API + her iki snapshot
python -m src.visualizer                 # grafik üret (YENİDEN YAZILACAK)
python -m src.merge_pipeline --pages 1   # canlı API ile güncelle (test: 1 sayfa)
python -m src.merge_pipeline --pages 50 --add-new  # tam güncelleme
```

---

## 📌 ORTAK VİZYON VE KURALLAR

### Sosyal Medya Operasyonu İçin Temel Prensipler

1. **TDS Saplantısına Son:** Grafikler ve analizler sadece "Top-Down Shooter" değil, **Tüm Indie Pazarı** ölçeğinde yapılacak.

2. **Arz Değil, Başarı Gösterilecek:** Sadece "pazarın yüzde kaçı X" demek yetmez. "X yapanların medyan satışı vs Y yapanların medyan satışı" gibi *sonuç odaklı* veriler sunulacak.

3. **Örneklem (n) Her Zaman Belirtilecek:** Her grafiğin altında `n=X oyun` notu zorunlu. Veri gazeteciliği etiği.

4. **Medyan, Ortalama Değil:** CS2 / PUBG gibi devler ortalamayı mahveder. Medyan = "sıraya diz, ortadakini al" = gerçekçi veri.

5. **"Kalite" Kelimesini Doğru Kullan:** Bizim verimizde "kalite" = oyuncu memnuniyet skoru (review %), AAA prodüksiyon değeri değil. İçerikte bunu her zaman açıkla.

6. **Veri Kaynağı Her Zaman Belirtilecek:** Her içerikte (grafik, video, post) verinin nereden geldiği şeffaf biçimde gösterilecek:
   - 📦 **Statik veri:** Kaggle — `artermiloff/steam-games-dataset` (Mart 2025 snapshot, ~90k oyun)
   - 🔴 **Canlı veri:** SteamSpy API (`steamspy.com/api.php`) — haftalık güncelleme
   - ⚠️ **Kısıtlar:** SteamSpy verileri tahminidir. Gerçek satış rakamları Valve tarafından açıklanmaz.

7. **Yatırımcı Sunumu Ayrıdır:** Pitch deck zamanı geldiğinde TDS verileri kullanılacak. Şimdilik bu kapsama girmiyor.

---

## 🔍 Insight Engine — Soru Havuzu

`src/insight_engine.py` bu soruları otomatik tarayacak.
Çıktı: `outputs/insights/weekly_report.md` — video hook'larına hazır rapor.

### Pazar Dinamikleri
- Hangi türlerde **Hype Balonu** var? (oyun sayısı ↑ ama başarı oranı ↓)
- Hangi türler **Gizli Altın Madeni**? (oyun sayısı düşük ama başarı oranı yüksek)
- Hangi türler **Kırmızı Okyanus**? (hem arz çok, hem başarı düşük)
- Hangi türler **yeni çıkıyor ama henüz kimse fark etmedi**? (son 1 yılda ilk kez görünen tag'ler)

### Fiyatlandırma
- Hangi türlerde pahalı satmak daha çok sahip getiriyor?
- Hangi türlerde ucuz satmak mantıklı, hangisinde intihar?

### Kalite / Review
- %80 uçurumu her türde aynı mı, bazı türler %70'te de iyi satıyor mu?
- Hangi türlerde oyuncular daha affedici? (Mixed review'la bile satış var)
- Çıkışta düşük review alıp sonradan toparlayanlar? (Slow burn oyunlar)
- "Review bomb" anomalisi: Çok sahip ama çok düşük skor

### Zamanlama
- Hangi ay en az rakip var? (çıkış için en iyi zaman penceresi)
- Hangi ayda çıkan oyunlar en çok başarılı?
- Early Access → Full Launch vs direkt çıkış: hangisi daha başarılı?

### Çarpan Analizleri
- **Co-op çarpanı:** Hangi türlerde co-op eklemek başarıyı en çok artırıyor?
- **Lokalizasyon çarpanı:** Kaç dilli olan oyunlar daha çok sahip ediniyor?
- **Platform çarpanı:** Mac/Linux desteği satışı gerçekten artırıyor mu?

### Tür Kombinasyonları (Tag Sinerjisi)
- Hangi iki tag bir arada olduğunda başarı oranı en çok artıyor?
- Hangi tag kombinasyonu "ölüm öpücüğü"?

### İlginç Anomaliler
- "Underrated Gems": Çok ucuz ama çok memnun bırakmış oyunlar
- "Dead on Arrival": Sahip var ama review yok
- "Değer Algısı": Pahalı ama çok sahip kazanmış tür anomalileri

---

## 🎨 Yeni Visualizer — Grafik Seti

`visualizer.py` yeniden yazılacak. Üretilecek grafikler:

| Grafik | Mesaj | Metodoloji |
|--------|-------|------------|
| `hype_vs_reality.png` | "Herkesin koştuğu türler tuzak" | Tür başına oyun sayısı ↑ vs başarı oranı ↓ |
| `the_80pct_cliff.png` | "%80 review uçurumu" | Review skoru vs medyan sahip, tüm indie |
| `price_sweet_spot.png` | "Ucuz satmak intihar" | Medyan sahip, fiyat bandına göre, ücretsiz ayrı |
| `tag_synergy.png` | "Bu iki tür kombinasyonu altın" | En iyi 2-tag kombinasyonları |
| `top10_paid_indie.png` | "Başarının anatomisi" | Ücretsiz filtreli, ücretli top 10 |

---

## 🚧 Yapılacaklar (Sırasıyla)

- [x] Eski grafikler silindi
- [x] CONTEXT.md güncellendi
- [ ] `visualizer.py` yeniden yaz (5 yeni grafik)
- [ ] `insight_engine.py` yaz (soru havuzunu koda çevir)
- [ ] Visualizer'ı insight engine'e bağla (dinamik grafik)
- [ ] `run_pipeline.sh` (Debian bash script)
- [ ] n8n workflow JSON (Telegram bildirimi dahil)

---

## Teknik Notlar

### Pandas 2.x Copy-on-Write
- `df["col"].update(other)` → çalışmıyor
- Doğru: `df.update(pd.DataFrame({"col": other}))`

### Encoding (Windows Terminal)
- `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')`

### SteamSpy Fiyat Formatı
- Cent cinsinden string: `"999"` = $9.99
- `pd.to_numeric(series, errors="coerce") / 100`

### Steam Tag İsimleri (Kritik)
- ❌ `"Roguelite"` → ✅ `"Rogue-lite"` (tire ile!)
- ❌ `"Roguelike"` → ✅ `"Action Roguelike"`

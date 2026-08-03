# 🎮 Ribat Veri Motoru — Steam Indie Pazar Analizi & Otonom İçerik Üretimi

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/n8n-Workflow_Automation-orange?style=for-the-badge&logo=n8n&logoColor=white" alt="n8n">
  <img src="https://img.shields.io/badge/Anthropic-Claude_Sonnet_5-purple?style=for-the-badge&logo=anthropic&logoColor=white" alt="Claude">
  <img src="https://img.shields.io/badge/Data-Kaggle_%26_SteamSpy-green?style=for-the-badge&logo=steam&logoColor=white" alt="Data">
  <img src="https://img.shields.io/badge/Tests-24_passing-brightgreen?style=for-the-badge" alt="Tests">
</div>

<br>

> **"Veriyi okuyan pazarı yönetir — ama önce veriyi doğru okumak lazım."**
> Bu proje, Steam'deki 90.000'den fazla oyunun verisini analiz edip, **istatistiksel olarak kanıtlanmış** pazar bulgularını otomatik olarak Reels/TikTok video senaryolarına dönüştüren bir veri motorudur.

---

## 🚀 Projenin Amacı

Bağımsız oyun geliştiricileri (indie devs) genellikle hangi etiketlerin gerçekten sattığını, hangi tür kombinasyonlarının işe yaradığını veya hangi özelliklerin görünürlüğü artırdığını bilmeden karar veriyor. **Ribat Veri Motoru** bu kör noktaları veriyle dolduruyor — ama bunu yaparken **her iddianın gerçekten kanıtlanmış olmasını** merkezi tasarım ilkesi haline getiriyor.

Bu proje bir kere ciddi bir dönüşümden geçti: ilk versiyonu tag bazlı, sabit sayıda hipotez test eden ve istatistiksel doğrulaması olmayan bir sistemdi. Gerçek veriyle denetlendiğinde, ürettiği "bulguların" büyük kısmının **SteamSpy'ın veri çözünürlüğü sınırlamasından kaynaklanan bir yanılsama** olduğu ortaya çıktı (bkz. [Mimarinin Hikayesi](#-mimarinin-hikayesi-neden-böyle-tasarlandı) bölümü). Şu anki mimari bu dersten doğdu.

---

## ⚙️ Sistem Mimarisi

```
data/raw/ (Kaggle CSV)
        │
        ▼
src/processor.py ──► data/processed/ (temiz CSV, önbellekli)
        │
        ▼
src/metrics.py ──► visibility_pct (yaş-normalize görünürlük metriği)
        │
        ▼
src/discovery/  ──► GENEL hipotez üretimi + istatistiksel geçit
   ├── generators.py       (kolon-agnostik jeneratörler: tag, sayısal, boolean, entity)
   ├── families/           (özel evrenli aileler: temporal, studio_repeat, quality_cliff)
   ├── gate.py             (Mann-Whitney U + Benjamini-Hochberg FDR + etki büyüklüğü + bootstrap)
   └── run_all.py          (tüm aileleri TEK istatistik havuzunda birleştiren orkestratör)
        │
        ▼
src/narrative/  ──► Finding → video script + otomatik grafik seçimi
        │
        ▼
src/contracts.py ──► outputs/insights/findings.json  (n8n'e giden kanıt sözleşmesi)
        │
        ▼
      n8n  ──► Claude Sonnet 5 (video blueprint üretir) ──► Telegram
```

### 1. Veri Katmanı (`src/processor.py`, `src/metrics.py`)

- Kaggle'daki `artermiloff/steam-games-dataset` anlık görüntülerini (Mart 2025, Mayıs 2024) işler, MD5 tabanlı önbellekleme ile aynı veriyi tekrar işlemez.
- **`estimated_owners` (SteamSpy'ın sahip sayısı tahmini) kullanılmıyor.** SteamSpy bu alanı kova/aralık formatında verir (`"0 - 20000"` gibi) ve indie oyunların **%66'sı tek kovaya düşüyor** — yani bu sayı bir ölçüm değil, veri çözünürlüğünün sınırı.
- Bunun yerine `visibility_pct`: review sayısının **yıl-içi (kohort-normalize) percentile'ı**. Her oyun sadece kendi çıkış yılındaki rakipleriyle kıyaslanır — eski oyunların review biriktirmek için daha çok zamanı olduğu yanılgısını (2014 medyan review: 363, 2024: 4) ortadan kaldırır.

### 2. Keşif Motoru (`src/discovery/`)

Sistemin kalbi burası. Sabit, elle yazılmış hipotezler yerine **genel jeneratörler** var:

| Jeneratör | Ne yapar | Örnek |
|---|---|---|
| `generate_categorical_group_hypotheses` | Herhangi bir liste-tipi kolonun (tag, kategori) her değerini tek başına test eder | "City Builder" etiketi görünürlüğü etkiliyor mu? |
| `generate_pairwise_hypotheses` | En sık geçen değerlerin ikili kombinasyonlarını test eder | "Anime + Psychological Horror" birlikte iyi mi çalışıyor? |
| `generate_numeric_split_hypotheses` | Herhangi bir sayısal kolonu medyandan ikiye böler | Achievements sayısı fazla olan oyunlar daha mı görünür? |
| `generate_boolean_flag_hypotheses` | 0/1 kolonları var/yok olarak karşılaştırır | Mac/Linux desteği fark yaratıyor mu? |
| `families/studio_repeat.py` | Bir stüdyonun ilk oyunu ile sonraki oyunlarını kıyaslar | Deneyim kazanmak otomatik olarak daha görünür oyun mu yapıyor? |
| `families/temporal.py` | Bir tag'in yıllar içindeki trendini **pazarın genel trendinden arındırarak** ölçer | Bu tür pazardan daha mı hızlı büyüyor/küçülüyor? |

**Yeni bir kolon eklendiğinde insan hiçbir kod yazmadan** o kolon otomatik keşif havuzuna girer (`feature_registry.py`'ye bir satır eklemek yeterli).

### 3. İstatistiksel Geçit (`src/discovery/gate.py`)

Kaç hipotez üretilirse üretilsin (bugün 715, yarın binlerce), hepsi **aynı tek kapıdan** geçer:

1. **Minimum örneklem büyüklüğü** (aile bazında ayarlanmış)
2. **Mann-Whitney U testi** — "bu fark tesadüf mü?" (dağılım varsayımsız, review sayısı aşırı çarpık olduğu için)
3. **Benjamini-Hochberg FDR düzeltmesi** — yüzlerce test birden yapıldığında ortaya çıkan yanlış-pozitifleri eler
4. **Etki büyüklüğü eşiği (≥0.20)** — asıl filtre burası; büyük örneklemde p-değeri neredeyse her zaman "anlamlı" çıkar, pratik önemi olan farkı ayıran etki büyüklüğüdür
5. **Bootstrap %95 güven aralığı** — sıfırı kesen bulgular (yön belirsizse) elenir

Gerçek veride: **715 aday hipotezden 277'si bu geçidi geçti.**

### 4. Anlatı ve Rapor Katmanı (`src/narrative/`, `src/contracts.py`)

- Her bulgu (`Finding` nesnesi) **yön-nötr şablonlardan** cümleye dönüştürülür — veri pozitif çıkarsa "daha yüksek", negatif çıkarsa "daha düşük" cümlesi otomatik seçilir. Hiçbir metin elle yazılmaz.
- `chart_selector.py`, bulgunun tipine göre otomatik doğru grafiği üretir (bar karşılaştırma, kutu grafiği, öncesi/sonrası, trend çizgisi).
- `contracts.py`, en güçlü 5 bulguyu deterministik olarak seçip (`|etki|`'ye göre sıralı) `findings.json`'a yazar — n8n buradan LLM'e veri gönderir.

### 5. Otomasyon (n8n + Claude Sonnet 5)

n8n haftalık/aylık tetiklenip pipeline'ı çalıştırır, üretilen `findings.json`'u Claude'a (`claude-sonnet-5`) gönderir. Claude, **zaten kanıtlanmış** bulguları alıp video blueprint'lerine (hook, sahne sahne script, SFX notları, caption) çevirir ve Telegram'a yollar. Sistem promptu [`docs/n8n_system_prompt.md`](docs/n8n_system_prompt.md) dosyasında belgelenmiştir.

---

## 🔍 Mimarinin Hikayesi: Neden Böyle Tasarlandı

Bu projenin ilk versiyonu (`anomaly_detector.py`, hâlâ repoda duruyor ama pipeline'a bağlı değil) sabit tag'leri tarayıp `estimated_owners` üzerinden "anomali" tespit ediyordu. Denetim sırasında şu bulundu:

- **Owners kova formatı yüzünden 399 tag'in 370'inin medyan "sahip sayısı" tam olarak aynı değerdi** (10.000) — yani sistem farklı tag'ler arasında hiçbir gerçek ayrım yapamıyordu, sadece SteamSpy'ın veri kovasının sınırlarını yansıtıyordu.
- "Optimal fiyat bandı" olarak sunulan değer, aslında satışla hiç ilişkilendirilmemiş, sadece fiyatın 60-80. yüzdelik dilimiydi.
- Tag kombinasyonu bulguları (örn. "Visual Novel + FPS") **confounding** (karıştırıcı değişken) etkisiydi: çok tag taşıyan oyunlar zaten geliştiricisinin daha çok ilgilendiği oyunlardı, tag kombinasyonunun kendisi değil.

Yeni sistem bu üç sorunu da doğrudan hedef aldı: owners bırakıldı, her iddia gerçek istatistiksel teste tabi tutuldu, ve confounding etkisi (`total_reviews >= 10` tabanı ile) ölçülüp düzeltildi.

**Karşılaştırma:** Eski sistemin ürettiği 10 "anomali"den **8'i yeni istatistiksel geçitten geçemedi** — sistematik olarak yanlış bulgular üretiyordu, tek seferlik bir hata değildi.

---

## 📊 Veri Kaynağı ve Sınırlamalar

- **Kaynak:** Kaggle `artermiloff/steam-games-dataset` (Mart 2025 anlık görüntüsü, ~90.000 oyun) + SteamSpy API.
- **Kullanılan:** `positive`/`negative` review sayıları, `price`, `discount`, `achievements`, `dlc_count`, `playtime`, `developers`, `metacritic_score`, `categories`, `tags`, `genres`.
- **Kullanılmayan:** `estimated_owners` (yukarıda açıklanan çözünürlük sorunu nedeniyle).
- **Bilinen sınır:** Canlı SteamSpy güncellemesi (`merge_pipeline.py`) şu an sadece en popüler ~1000 oyunu tazeliyor — indie kuyruğuna dokunmuyor. Bu, projenin bir sonraki geliştirme alanı.

---

## 🧪 Test

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

24 test — istatistiksel geçidin rastgele veride yanlış-pozitif üretmediğini (`test_gate_rejects_noise`), yaş normalizasyonunun doğru çalıştığını, ve üretilen metinlerin gerçekten `Finding` nesnesinden türediğini (hiçbir sabit/hardcoded iddia sızmadığını) doğruluyor.

## ▶️ Çalıştırma

```bash
# Tam pipeline (n8n'in tetiklediği ile aynı giriş noktası)
python -m src.main

# Sadece keşif motorunu çalıştır
python -m src.discovery.run_all
```

---

## 🛡️ Güvenlik Notu

Proje, API anahtarlarını, SSH bağlantı bilgilerini ve yerel ortam değişkenlerini (`.env`, `scratch/`) açık kaynak reposundan korumak amacıyla yapılandırılmıştır. Otonom işlemler kapalı bir sunucuda (VPS) çalışır.

---

<div align="center">
  <i>Developed by <b>Ribat Games Studio</b></i>
</div>

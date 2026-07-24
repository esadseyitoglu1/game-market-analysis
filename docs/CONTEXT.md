# CONTEXT.md — Proje Anayasası

> Bu dosya, projenin "neden var olduğunu" ve "nasıl işlediğini" açıklar.
> `TASKS.md` ile birlikte, model geçişlerinde (Claude ↔ Gemini/Antigravity) sıfır bilgi
> kaybıyla devam edebilmek için ORTAK HAFIZA görevi görür. Her yeni oturuma başlayan
> model (insan ya da AI), önce bu iki dosyayı okumalıdır.

## 1. Proje Adı
Steam Indie Game Market Analysis

## 2. Çift Yönlü Hedef (Dual-Output Framework)

Bu proje tek bir çıktı üretmiyor, iki farklı paydaş için iki farklı çıktı üretiyor:

### A) Public / Content Output
Gamedev topluluğuna (Reddit, Twitter/X, YouTube Shorts, Instagram Reels) fayda
sağlayacak, Steam pazar verisine dayalı içerikler:
- "Bu türde en çok satan 10 indie oyunun ortak özellikleri"
- "Fiyat noktası X ile satış arasındaki ilişki"
- "2D Top-Down Shooter türünün son 2 yıldaki büyümesi/doygunluğu"

### B) Internal / Game Positioning Output
Ribat Games'in kendi geliştirdiği **2D Top-Down Shooter** oyunu için:
- Yatırımcı/yayıncı sunumlarında (Pitch Deck) kullanılacak pazar doğrulaması
- Rakip analizi ve fiyatlandırma stratejisi
- Risk analizi (pazar doygunluğu, rekabet yoğunluğu)

**Önemli:** Aynı ham veri (Steam/SteamSpy) her iki çıktı için de kaynak. Fark, veri
işlendikten sonra hangi mercekten (topluluk-faydası vs. iş-stratejisi) sunulduğunda.

## 3. Model Devir-Teslim Protokolü

Proje sahibi (Ribat Games kurucusu, Bilgisayar Mühendisliği öğrencisi) okul döneminde
Claude kotası bittiğinde Antigravity içindeki Gemini'ye geçiyor. Bu yüzden:

- **`docs/CONTEXT.md`** (bu dosya): Değişmeyen mimari/hedef bilgisi. Nadiren güncellenir.
- **`docs/TASKS.md`**: Değişken durum — hangi fazdayız, ne tamamlandı, sıradaki model
  için ilk adım ne. Her oturum sonunda güncellenir.

Her oturumu bitiren model, `TASKS.md`'ye şunu net yazmalı: "Sıradaki model ilk olarak
şunu yapmalı: ...". Bu olmadan devir-teslim bilgi kaybına uğrar.

## 4. Mimari Genel Bakış

```
Steam Store API + SteamSpy API
        │
        ▼
  src/fetcher.py       → Ham veriyi çeker, data/raw/ altına JSON olarak kaydeder
        │
        ▼
  src/processor.py     → Ham veriyi temizler/normalize eder, data/processed/ altına
        │                 CSV/DataFrame olarak kaydeder (pandas)
        ▼
  src/analyzer.py       → İşlenmiş veri üzerinde analiz yapar (istatistik, NLP sentiment,
        │                 trend analizi) — hem public hem internal çıktılar için taban
        ▼
  main.py                → Tüm pipeline'ı orkestra eder (fetch → process → analyze)
```

- **`data/raw/`**: API'den gelen ham, işlenmemiş veri (JSON). Tekrar üretilebilir,
  git'e eklenmez.
- **`data/processed/`**: Temizlenmiş, analiz-hazır veri (CSV). Bu da tekrar üretilebilir,
  git'e eklenmez.
- **`src/`**: Tüm Python modülleri.

## 5. Teknik Notlar (Öğretici Bağlam)

Proje sahibi veri analizi/mühendisliğine yeni. Kod yazılırken şu kavramlar
açıklanarak ilerlenir:
- API rate limiting / retry-backoff mantığı
- Pandas DataFrame ile ham veri işleme
- Data cleaning (eksik veri, aykırı değer, tip dönüşümü)
- NLP sentiment analizi (Steam yorumları üzerinden, ileri fazda)

## 6. Dış Veri Kaynakları
- **SteamSpy API**: `https://steamspy.com/api.php` — sahiplik/oyuncu sayısı tahminleri,
  resmi olmayan ama toplu veri için pratik.
- **Steam Store API**: `https://store.steampowered.com/api/appdetails` — resmi, tekil
  oyun detayı (fiyat, tür, açıklama, çıkış tarihi).

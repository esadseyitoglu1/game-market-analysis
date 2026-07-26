# 🎮 Steam Market Analysis & Autonomous Reels Generator

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/n8n-Workflow_Automation-orange?style=for-the-badge&logo=n8n&logoColor=white" alt="n8n">
  <img src="https://img.shields.io/badge/Anthropic-Claude_3.5_Sonnet-purple?style=for-the-badge&logo=anthropic&logoColor=white" alt="Claude">
  <img src="https://img.shields.io/badge/Data-Steam_API_%26_SteamSpy-green?style=for-the-badge&logo=steam&logoColor=white" alt="Data">
</div>

<br>

> **"Veriyi okuyan pazarı yönetir."**  
> Bu proje, Steam'deki 90.000'den fazla bağımsız (indie) oyunun verilerini kazıyıp istatistiksel analizler yapan ve bulduğu pazar boşluklarını (anomalileri) **tamamen otonom bir şekilde** viral Instagram Reels / TikTok senaryolarına dönüştüren bir yapay zeka & veri madenciliği motorudur.

---

## 🚀 Projenin Amacı

Bağımsız oyun geliştiricileri (Indie Devs) genellikle oyunlarını tutkuyla geliştirir ancak pazarın ne istediğini, hangi etiketlerin (tags) gerçekten sattığını veya hangi fiyat bandının kârlı olduğunu görmekte zorlanırlar.

**Ribat Veri Motoru**, bu kör noktaları yok etmek için tasarlandı:
1. Oyun etiketlerindeki **"Kalite Tuzakları"**nı bulur (Örn: İncelemeleri %93 olan ama kimsenin satın almadığı oyun türleri).
2. Fiyatın satışlara etkisindeki **mantıksızlıkları** (Correlation Flippers) tespit eder.
3. Yıllar içinde kalitesi sistematik olarak düşen türleri (**Çöküş Trendi**) hesaplar.
4. Bu devasa teknik verileri, **Claude 3.5 Sonnet** (LLM) aracılığıyla sokaktaki insanın bile anlayacağı şok edici, viral potansiyeli yüksek video kurgu şablonlarına (Blueprint) çevirir.

---

## ⚙️ Sistem Mimarisi (Nasıl Çalışıyor?)

Sistem 3 temel bileşenden oluşan, kusursuz bir otomasyon döngüsüne (Pipeline) sahiptir:

### 1. Veri Madenciliği ve Hafıza Motoru (Python)
- `anomaly_detector.py` scripti, Kaggle üzerinden çekilen temel Steam Store API verilerini ve SteamSpy satış istatistiklerini (Median Owners) birleştirir.
- 130'dan fazla "Anomali" (Pazar açığı) tespit eder. Her anomali için başarılı oyunların fiyat kuşağını (`optimal_price_band`) hesaplar.
- **Akıllı Hafıza (Memory):** Daha önce LLM'e yolladığı konuları `used_tags.txt` dosyasında tutar ve bir daha asla aynı konuyu önermez. Seçtiği rastgele 10 "taze" veriyi JSON olarak sunucuya kaydeder.

### 2. Otonom Tetikleyici (n8n)
- Sistem bir n8n sunucusuna bağlıdır ve her hafta belirlenen gün/saatte **cron job** ile uyanır.
- Python veri motorunu tetikler, üretilen en güncel 10'lu JSON dosyasını SSH üzerinden çeker ve LLM (Anthropic) node'una iletir.

### 3. Yapay Zeka İçerik Yönetmeni (Claude 3.5 Sonnet)
- İletilen 10 rastgele anomali arasından en ilginç olanı seçer.
- Özel yazılmış **Identity Disruption (Kimlik Sarsma)** ve **Loop Hook** prompt mühendisliği kuralları sayesinde, veriyi akademik bir dille değil; şok edici bir kanca, net bir çözüm önerisi ve saniye saniye görsel/ses efekti (SFX) notlarıyla bir senaryoya çevirir.
- Üretilen kurgu hazır şablonu (Blueprint) doğrudan geliştiricinin Telegram'ına iletilir.

---

## 📊 Çıktı Örneği (Blueprint Formatı)

Sistemin Telegram'a otomatik olarak gönderdiği tipik bir çıktı şablonu:

```markdown
🔥 HAFTANIN RİBAT VERİ ANOMALİSİ: NOSTALJİ SATAR DEDİLER. YALAN.

🎬 [EDİTÖRE NOT]: Bu video şunu anlatıyor: Steam'deki Nostalji etiketli oyunlar çok seviliyor ama satmıyor. Çözüm, bu etiketi daha geniş kitlesi olan bir mekanikle birleştirmek.

[00-03sn - HOOK]
GÖRSEL: Eski GameBoy esintili, 8-bit oyun ekranı. Karakterin cüzdanı alev alıyor.
EKRAN YAZISI: NOSTALJİ YAPIYORSUN. VE SANA BİR KURUŞ KAZANDIRMIYOR.
SFX/MÜZİK: Retro melodi kesilir. Cam kırılma sesi.
SESLENDİRME: Sen şu an nostaljiye güveniyorsun. O his seni değil, oyuncuyu mutlu ediyor.

[...Veri Gerçeği, Re-Hook ve Ribat Analizi Bölümleri...]
```

---

## 🛡️ Güvenlik Notu

Proje, kişisel API anahtarlarını, SSH bağlantı şifrelerini ve yerel ortam değişkenlerini (`.env`) açık kaynak reposundan korumak amacıyla yapılandırılmıştır. Tüm otonom işlemler kapalı sunucuda (Docker/VPS) çalışmak üzere tasarlanmıştır.

---

<div align="center">
  <i>Developed by <b>Ribat Games Studio</b></i>
</div>

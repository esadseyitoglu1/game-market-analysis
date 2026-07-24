# Reels Content Brief: Indie Game Market Analysis

Bu belge, "Steam Verilerini İndirip Kendi Oyunumun Pazarını Analiz Ettim" temalı 6 bölümlük Reels/TikTok serisinin script taslaklarını içerir.

**Hedef Kitle:** Indie oyun geliştiricileri, oyun sektörüne meraklı oyuncular, yatırımcılar.
**Format:** Build-in-public, şeffaf veri paylaşımı, "beraber öğreniyoruz" tonu.

---

## 🎬 Episode 1: The Hook & Data
**Ana Mesaj:** "Veri olmadan pazar kararı vermek körlüktür. Steam'in röntgenini çektim."
**Kullanılacak Görsel/Veri:** Kaggle dataset ekran görüntüsü, Python terminalinde akan yazılar.

**Script Taslağı:**
> **[0:00 - 0:03 - HOOK]** Kendi oyunumu yaparken en büyük korkum şuydu: "Ya kimsenin oynamak istemediği bir türde oyun yapıyorsam?"
> **[0:03 - 0:15]** Çoğu indie geliştirici sadece hisleriyle hareket ediyor. Ben bunu yapmak istemedim. Gittim Steam'deki 89,000 oyunun tüm verisini indirdim.
> **[0:15 - 0:25]** Kaggle'dan ham veriyi çektim, Python'da temizledim. Hangi türler büyüyor, hangi fiyat bandı daha çok satıyor, başarılı oyunların sırrı ne?
> **[0:25 - 0:35 - CTA]** Kendi oyunumun pazarını (Top-Down Shooter) adım adım analiz edeceğim. Verilerle oyun geliştirmek istiyorsan seriyi takip et.

---

## 🎬 Episode 2: Is Top-Down Shooter Dead? (Genre Trend)
**Ana Mesaj:** "TDS türü sanılanın aksine çok hızlı büyüyor."
**Kullanılacak Görsel/Veri:** `genre_trend.png` (TDS vs Steam Ortalaması)

**Script Taslağı:**
> **[0:00 - 0:03 - HOOK]** Herkes "Top-Down Shooter pazarı doydu, oyun yapılmaz" diyor. Veriler öyle demiyor.
> **[0:03 - 0:15]** 89,000 oyunluk datasetimi analiz ettiğimde şok edici bir şey gördüm. 2016'dan beri Steam genel pazarı %300 büyürken...
> **[0:15 - 0:25]** *(Grafik Ekrana Gelir)* Top-Down Shooter türü tam %519 büyümüş! Hatta yan türleri olan Action Roguelike'ın büyümesi inanılmaz seviyelerde.
> **[0:25 - 0:35 - CTA]** Yani pazar ölü değil, tam tersine oyuncu iştahı artıyor. Peki bu pazarda başarılı olmak için oyununuzun ne kadar "kaliteli" olması lazım? Bir sonraki bölümde review skorlarını açıyoruz.

---

## 🎬 Episode 3: The Brutal Truth About Quality (Min Viable Quality)
**Ana Mesaj:** "10,000 satmak istiyorsan %84 pozitif review sınırını geçmek ZORUNDASIN."
**Kullanılacak Görsel/Veri:** `min_viable_quality.png`

**Script Taslağı:**
> **[0:00 - 0:03 - HOOK]** Steam'de oyununuzun başarılı olması için review skorunuzun en az kaç olması lazım? Cevap sandığınızdan daha yüksek.
> **[0:03 - 0:15]** TDS pazarındaki oyunları başarı seviyelerine göre böldüm. 10 bin sahibe ulaşan oyunların medyan review skoru kaç biliyor musunuz? Tam %84!
> **[0:15 - 0:25]** *(Grafik Vurgulanır)* Yani oyununuz %70'lerde kalırsa, o 10 bin barajını geçmeniz neredeyse imkansız. 500 bin satmak istiyorsanız %87'yi görmek zorundasınız.
> **[0:25 - 0:35 - CTA]** Pazar büyüyor ama kalite standartları acımasız. Peki fiyatı ne yapacağız? $5 dolar mı daha güvenli, $20 dolar mı? Yarınki videoda çok şaşıracaksınız.

---

## 🎬 Episode 4: The Pricing Cheat Code (Price x Quality Matrix)
**Ana Mesaj:** "Ucuza satmak sizi kurtarmaz. Kaliteyi verip hakkını almak en kârlısı."
**Kullanılacak Görsel/Veri:** `price_quality_matrix.png` (Isı haritası)

**Script Taslağı:**
> **[0:00 - 0:03 - HOOK]** Indie oyununuzu ucuza satarsanız daha çok kişiye ulaşırsınız değil mi? Veriler "Hayır" diyor.
> **[0:03 - 0:15]** Fiyat ve Kalite matrisini çıkardım. Çoğu geliştirici 5-10 dolar bandına sıkışıp kalıyor. Ortalama 10-35 bin sahibe ulaşıyorlar.
> **[0:15 - 0:25]** *(Isı Haritası Ekranda)* Ama asıl altın madeni nerede biliyor musunuz? 20-30 dolar fiyat etiketi koyup, %80-90 arası review alan oyunlarda! Medyan sahip sayıları 150 BİN!
> **[0:25 - 0:35 - CTA]** Kaliteli oyun yapıp cesur fiyatlamak aslında en çok kazandıran strateji. Peki 2025'in en büyük fırsatı nerede? Sıradaki videoda "Co-op" boşluğunu konuşuyoruz.

---

## 🎬 Episode 5: The Co-op Gap (Market Opportunity)
**Ana Mesaj:** "TDS oyunlarının %78'i solo. Co-op, rekabetin en az olduğu altın madeni."
**Kullanılacak Görsel/Veri:** Co-op vs Solo analiz verileri. (TDS'lerin sadece %22'si Co-op)

**Script Taslağı:**
> **[0:00 - 0:03 - HOOK]** Bu yaz "PEAK" isimli basit bir co-op party oyunu 1 ayda 3.1 MİLYON sattı. Kendi oyunumuz için buradan ne öğrenebiliriz?
> **[0:03 - 0:15]** Steam'de yayınlanan 2,205 TDS (Top-Down Shooter) oyununu inceledim. Ne kadarında arkadaşlarınızla oynayabileceğiniz Co-op özelliği var dersiniz?
> **[0:15 - 0:25]** Sadece %22'sinde! Pazarın %78'i tamamen tek kişilik (solo) oyunlardan oluşuyor. 
> **[0:25 - 0:35 - CTA]** Twitch ve TikTok çağındayız. İnsanlar arkadaşlarıyla kaos yaşayıp gülmek istiyor. Eğer oyununuza co-op eklerseniz, rekabetin çok düşük olduğu bir nişe giriyorsunuz.

---

## 🎬 Episode 6: Who is Winning? (TDS Top 10)
**Ana Mesaj:** "Rakiplerimiz kim ve neden bu kadar büyükler?"
**Kullanılacak Görsel/Veri:** `tds_top10.png`

**Script Taslağı:**
> **[0:00 - 0:03 - HOOK]** Kendi pazarınızı analiz etmeden o pazarda oyun yapmak intihardır. İşte TDS türünün kralları.
> **[0:03 - 0:15]** Datasetimde Top 10'a baktığımda, Brotato ve Hotline Miami gibi devlerin 3.5 Milyon barajını geçtiğini görüyoruz.
> **[0:15 - 0:25]** *(Grafik Üzerinde)* Ortak noktaları? Basit görünen ama mekanik olarak inanılmaz derin bir gameplay loop'u ve %95 üzeri Overwhelmingly Positive skorlar.
> **[0:25 - 0:35 - CTA]** Veriler ortada. Pazarda yer var, kalite şart, co-op büyük fırsat. Oyunumu geliştirmeye devam ediyorum, serüvene ortak olmak için takipte kalın!

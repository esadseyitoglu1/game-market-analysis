# Proje Özeti: Otonom Steam Pazar Analizi (Reels Üreticisi)

## 1. Sistemin Amacı
Bu proje, Steam'deki oyun verilerini analiz ederek bağımsız oyun geliştiricileri (indie dev) için ezber bozan pazar fırsatları (anomaliler) bulan ve bunu otomatik olarak Instagram Reels/TikTok senaryolarına (Blueprint) dönüştüren otonom bir sistemdir.

## 2. Mimari ve İşleyiş (Boru Hattı)
Sistem 3 ana ayaktan oluşur:
1. **Python (Veri Madenciliği - anomaly_detector.py):** Kaggle'dan alınan 90.000 oyunluk veri setini ve SteamSpy tahminlerini işler. Oyun etiketlerini (tags) analiz eder. "Çok sevilen ama satmayan (Quality Trap)", "Kötü olup çok satan (Hype Balloon)" gibi 131 farklı istatistiksel anomali tespit eder. "used_tags.txt" üzerinden hafıza tutarak daha önce LLM'e yollanan konuları eler, kalan taze konulardan rastgele 10 tanesini seçip bir JSON dosyasına yazar.
2. **n8n (Otomasyon):** Her Pazartesi tetiklenir. Sunucudaki Python kodunu çalıştırır (hafızayı günceller), yeni JSON'ı okur ve içindeki 10 taze veriyi Anthropic (Claude) node'una gönderir.
3. **LLM (İçerik Yönetmeni):** LLM, çok katı kurallarla donatılmış "Ribat Games Studio Yönetmeni" system promptunu kullanarak bu 10 veriden rastgele birini seçer. Akademik terimleri atarak, "00-15 sn Kanca, 15-35 sn Analiz, Görsel Notlar, SFX (Ses) Notları" içeren hazır bir video kurgu şablonu (Görsel Blueprint) üretir ve Telegram'a yollar.

## 3. Senin (Claude) Görevin
Şu anda proje harika çalışıyor ve vizyoner Reels kurguları üretiyor. Senden istediğim **YENİ BİR FAZA (Phase) GEÇMEMEK**. Sadece mevcut süreci ve çıktıları nasıl daha da "kusursuz, viral potansiyeli yüksek ve optimize" hale getirebileceğimizi tartışmak istiyorum.

Lütfen bana şu konularda ufkumu açacak tavsiyeler ver:
1. **İçerik Kalitesi:** n8n LLM Prompt'umuzda, Reels senaryosunun kancasını (hook) veya hikaye anlatımını bir üst seviyeye taşıyacak, eksik gördüğün bir psikolojik tetikleyici (marketing trigger) var mı?
2. **Kurgu Şablonu:** Editörün işini daha da kolaylaştırmak veya videonun izlenme süresini (retention) artırmak için çıktı şablonunda (Blueprint) yapılabilecek minik iyileştirmeler nelerdir?
3. **Veri Çeşitliliği:** Python tarafındaki anomali tespit mantığını (Quality Trap, Hype Balloon vs.) bozmadan, veriyi daha ilginç kılacak veya anlatımı güçlendirecek küçük dokunuşlar ne olabilir?

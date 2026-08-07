# n8n LLM Node — System Prompt (Tek-Bulgu Blueprint Üretici, Foto Destekli)

Bu dosya, n8n workflow'undaki "Message a model" (Claude/Anthropic) node'unun
system prompt'unun **2026-08-04 itibariyle güncel** hâlidir. Kod repoda değil,
n8n'in kendi arayüzünde saklanıyor — buraya sadece referans ve devir teslim
amacıyla kopyalandı.

## Bu sürümde ne değişti (bir önceki "çoklu bulgu" sürümüne göre)

**Kök neden:** Her `Finding`'in artık kendi grafiği var (`chart_selector.py` →
`Finding.chart_path`, bkz. plan). Telegram'a görsel eklemek istiyorsak, n8n'in
hangi video script'inin hangi resme ait olduğunu bilmesi gerekiyor. Bunu tek
bir LLM çağrısıyla 5 bulguyu birden işleyip TEK metin bloğu üretirsek
yapamayız — metin ile resim arasındaki bağ kaybolur. Çözüm: **LLM'i
`findings[]` dizisi üzerinde `Loop Over Items` (Split In Batches, batch
size=1) ile döndür, her turda SADECE BİR bulgu gönder, SADECE BİR blueprint
üret.** n8n tarafındaki tam akış için bu dosyanın sonundaki "n8n workflow
yapısı" bölümüne bak.

1. **Dizi (`findings[]`) yerine TEK bulgu (`{{ $json }}`) işleniyor.** Eski
   prompt "findings dizisinin TAMAMINI işle, her biri için ayrı blueprint
   üret" diyordu — bu, tek mesajda 4-5 blueprint art arda üretiyordu ve
   hiçbiri kendi resmine bağlanamıyordu. Yeni prompt SADECE bir `Finding`
   nesnesi alıyor, SADECE bir blueprint üretiyor.
2. **"ÇOKLU BULGU FORMATI" kuralı ve genel rapor başlığı kaldırıldı.** Artık
   n8n tarafı zaten döngüyü yönetiyor, LLM'in "sıradaki bulguya geç" diye
   bir derdi yok.
3. **Caption/mesaj ayrımı netleşti.** Telegram'ın "Send Photo" operasyonunda
   caption limiti **1024 karakter** (normal mesaj limiti olan 4096'dan farklı
   ve daha küçük) — bu yüzden prompt artık iki ayrı çıktı alanı üretmeye
   zorlanıyor: kısa bir CAPTION (resmin altına, ≤1000 karakter) ve tam
   SCRIPT (ayrı text mesajı olarak, ≤3500 karakter).
4. Geri kalan kurallar (VERİYE SADAKAT, UYARI ZORUNLULUĞU, IDENTITY
   DISRUPTION, TELEGRAM KORUMASI/yıldız yasağı) **aynen korundu** — bunlar
   tek/çoklu bulgu ayrımından bağımsız, hâlâ geçerli.
6. **Script canlı testte cümlenin ORTASINDA kesiliyordu (2026-08-04 bulundu).**
   Kullanıcı gerçek Telegram çıktısını paylaştı — "[25-40sn - RİBAT ANALİZİ /
   ÇÖZÜM] GÖRSEL" yazıp orada duruyordu, [40-50sn - CTA] bölümü hiç yoktu.
   İki ayrı sebep: (a) "Message a model" node'unda `maxTokensToSample`
   ayarlanmamıştı — n8n'in Anthropic node'u düşük bir varsayılanla
   sınırlıyordu, LLM'in kendi cevabı fiziksel olarak kesiliyordu (finish_reason
   max_tokens). `options.maxTokensToSample: 2048` eklendi. (b) "Split Caption
   Script" node'undaki `.slice(0, 3200)` de karakter sayısına göre kör kesim
   yapıyordu — bir cümlenin ortasında bile durabiliyordu. `trimToBoundary()`
   yardımcı fonksiyonu eklendi: son `\n\n`/`. `/`\n` sınırını bulup ORADA
   kesiyor (limitin yarısından sonraki bir sınır varsa), script limiti de
   3200'den 3800'e çıkarıldı (Telegram'ın gerçek sınırı 4096, biraz daha pay
   bırakıldı).
5. **`{{ $json }}` → `{{ JSON.stringify($json, null, 2) }}` (2026-08-04 bulundu).**
   n8n, expression içinde bir objeyi (`$json`) düz metne gömerken JavaScript'in
   varsayılan `toString()`'ini kullanıyor — bu bir obje için `[object Object]`
   üretir, JSON içeriğini DEĞİL. LLM'e giden mesajda bulgunun tüm alanları
   kayboluyordu; LLM de bunu fark edip "elimde işlenebilir veri yok" diye
   cevap veriyordu (canlı örnekte görüldü). `JSON.stringify` ile açıkça
   metne çevirmek zorunlu — n8n'de obje enjekte ederken bu HER ZAMAN
   yapılmalı, `{{ $json }}` tek başına asla kullanılmamalı.

## n8n workflow yapısı (özet — detaylar aşağıda)

```
Execute Command (python -m src.main → pipeline'ı çalıştırır)
  → Read File (outputs/insights/findings.json'u oku, JSON parse et)
  → Split Out (findings alanını ayrı item'lara böl — her item tek bir Finding)
  → Loop Over Items (Split In Batches, batch size = 1)
      → Message a Model (BU DOSYADAKİ prompt, girdi: {{ $json }} = tek Finding)
      → Read/Write File (Read Binary File) — path: findings.json'daki
        chart_path GÖRELİ bir yol olduğu için başına repo kökünü ekle:
        ={{ "/root/game-market-analysis/" + $json.chart_path }}
      → Telegram: Send Photo (Binary Data, caption = LLM çıktısındaki
        CAPTION bölümü, ≤1024 karakter)
      → Telegram: Send Message (LLM çıktısındaki SCRIPT bölümü, ≤3500 karakter,
        yıldız/markdown KAPALI — bkz. TELEGRAM KORUMASI kuralı)
  → (Loop bitince) isteğe bağlı özet mesajı
```

**Not — path birleştirme (2026-08-04 güncellendi, /srv mount'u):**
`findings.json`'daki `chart_path` repo-köküne göreli (`outputs/charts/...`),
çünkü `chart_selector.py` bunu böyle üretiyor (bkz. `render_chart_for_finding`).

n8n container'ı (`services-n8n-1`) Docker içinde `node` kullanıcısıyla (uid
1000, root DEĞİL) çalışıyor. İlk denemede mount hedefi `/root/game-market-analysis/outputs`
olarak ayarlanmıştı — bu **ÇALIŞMADI**: `EACCES: permission denied`. Kök
neden `/root` klasörünün kendisinin `700` (sadece gerçek root erişebilir)
olması — bu Linux'ta standart ve GÜVENLİK GEREĞİ böyle kalmalı, `/root`'u
`chmod` ile açmak yanlış çözüm olurdu. Bunun yerine `docker-compose.yml`'deki
mount hedefi `/root` dışına, `/srv` altına taşındı:

```yaml
volumes:
  - /root/game-market-analysis/outputs/charts:/srv/charts:ro
  - /root/game-market-analysis/outputs/insights:/srv/insights:ro
```

Yani n8n'in "Read Binary File" node'unda path artık:
`={{ "/srv/" + $json.chart_path.replace("outputs/", "") }}`
(`chart_path` = `outputs/charts/finding_x.png` → `.replace("outputs/","")` =
`charts/finding_x.png` → sonuç `/srv/charts/finding_x.png`.)

Doğrulandı: `docker exec services-n8n-1 cat /srv/insights/findings.json`
sunucuda hatasız çalıştı, `/srv/charts/` altındaki PNG'ler container içinden
görünüyor.

**İKİNCİ İZİN KATMANI (n8n'in KENDİ dosya erişim kısıtlaması):** Mount
düzeltildikten sonra "Read Chart Image" node'u hâlâ hata verdi — bu sefer
Docker/Linux izni değil, n8n'in kendi güvenlik özelliği:
`Access to the file is not allowed. Allowed paths: /home/node/.n8n-files`.
n8n, `Read/Write File` gibi node'ların rastgele host path'i okumasını
varsayılan olarak sadece `/home/node/.n8n-files`'a kısıtlıyor. Çözüm,
`docker-compose.yml`'e `N8N_RESTRICT_FILE_ACCESS_TO` ortam değişkeni eklemek:

```yaml
environment:
  - N8N_RESTRICT_FILE_ACCESS_TO=/home/node/.n8n-files;/srv/charts;/srv/insights
```

**DİKKAT — AYRAÇ VİRGÜL DEĞİL, NOKTALI VİRGÜL (`;`).** İlk denemede virgülle
(`,`) ayrılmış path listesi kullanıldı, bu n8n 2.x'te ÇALIŞMADI — hata aynen
devam etti, `printenv` değişkeni doğru gösterse bile n8n içeride bunu tek bir
path olarak yorumluyordu (bkz. n8n community forum:
`N8N_RESTRICT_FILE_ACCESS_TO in 2.0`). n8n 2.0'daki breaking change'den beri
çoklu dizin ayracı `;`. Sunucuda `sed` ile virgül → noktalı virgül değiştirilip
`docker compose up -d --force-recreate n8n` ile container yeniden oluşturuldu,
`docker exec services-n8n-1 printenv | grep N8N_RESTRICT` ile doğrulandı.

**Özet: bu path'e erişmek için üç ayrı izin katmanı vardı — (1) Docker bind
mount, (2) Linux dosya izinleri (`/root` sorunu), (3) n8n'in kendi
`N8N_RESTRICT_FILE_ACCESS_TO` allowlist'i (VİRGÜL değil NOKTALI VİRGÜL ile
ayrılmalı) — üçü de ayrı ayrı çözülmesi gerekiyordu.**

Bu path'ler ayrıca artık HER ZAMAN `/` ayracı ve SADECE ASCII karakter
içeriyor (Windows'ta üretilse bile) — `chart_selector.py`'deki `.as_posix()`
ve `unicodedata`-tabanlı dosya adı temizliği bunu garanti ediyor.

## n8n tarafında yapman gerekenler

1. **"Message a model" node'unun modelini `claude-sonnet-5` olarak ayarla**
   (zaten öyleyse dokunma).
2. **System prompt'u aşağıdaki güncel metinle değiştir.**
3. **`findings.json`'u okuyan node'dan sonra bir "Split Out" node'u ekle**
   (Field to Split Out: `findings`) — böylece Loop Over Items her turda tek
   bir `Finding` nesnesiyle çalışır.
4. **Loop Over Items (Split In Batches, batch size=1) içine LLM node'unu al**
   — her turda `{{ $json }}` o turun tek `Finding`'ini temsil eder.
5. **LLM'den sonra bir "Read Binary File" node'u ekle**, path yukarıdaki
   expression'la ayarlanmalı.
6. **Telegram node'unu ikiye böl: "Send Photo" + "Send Message"** — LLM'in
   çıktısını CAPTION ve SCRIPT olarak iki ayrı bölüme ayırman gerekiyor (aşağıdaki
   ÇIKTI FORMATI'na bak); bunu n8n'de bir "Code"/"Set" node'uyla regex/split
   ile ayırabilirsin (örn. `---CAPTION_END---` ayracından böl).

---

## Güncel prompt (n8n'e bu şekilde girilecek)

```
Rolün: Sen, "Ribat Games Studio" markasının veri odaklı, hyper-fast ve görsel hikaye anlatımında usta Reels Yönetmenisin. Görevin; sana iletilen KANITLANMIŞ TEK BİR Steam veri bulgusunu (JSON), bir video editörünün anında kurguya başlayabileceği, SFX (Ses Efekti) notları içeren, saniye saniye planlanmış vurucu bir Görsel Blueprint'e (Çekim Listesi/Senaryo) çevirmek. Bu bulgunun kendine ait bir grafiği zaten üretildi ve Telegram'a AYRICA fotoğraf olarak gönderilecek — sen sadece metni üret, resmi sen eklemiyorsun.

Aşağıda, veri motorumuzun bulduğu ve istatistiksel olarak DOĞRULANMIŞ (Mann-Whitney U testi + Benjamini-Hochberg FDR düzeltmesi + etki büyüklüğü eşiği + bootstrap güven aralığı) TEK bir bulgu var. Gerçek, ham veriden hesaplanmıştır — hiçbir sayıyı sen uydurmuyorsun, sadece anlatıyorsun:

{{ JSON.stringify($json, null, 2) }}

Bu bulgu şu alanları taşır: "baslik" (bulgunun konusu), "claim" (veriden üretilmiş kanıtlı cümle — bunu OLDUĞU GİBİ kullan, sayıları değiştirme), "evidence" (n=örneklem büyüklüğü, effect=etki büyüklüğü, effect_ci=güven aralığı, q_value=istatistiksel güven — effect_ci "NaN" ise bu alanı YOK SAY, sadece effect ve claim'e odaklan), "hook" (video açılışı için öneri), "confidence" ("high" veya "medium" — medium ise videoda belirsizlik ifade et), "exemplars" (varsa gerçek oyun adı örnekleri — SADECE bunları kullan, oyun adı UYDURMA), "chart_path" (bu alanı YOK SAY, sadece n8n kullanıyor, sen metinde bahsetme).

Ribat Games Studio Tonu: Otoriter ama cool. Asla ders vermez, "ezber bozar". Cümleler kısa, kelimeler şamar gibi olmalı. Akademik laf salatası (Z-skor, p-değeri gibi teknik terimler doğrudan) YASAK — ama bulgunun GÜCÜNÜ ("129 oyun üzerinden test edildi", "çok net bir fark") günlük dille aktarmak SERBEST ve TEŞVİK EDİLİR.

KATI KURALLAR:

VERİYE SADAKAT (EN ÖNEMLİ KURAL): Sana verilen "claim" alanındaki cümle zaten doğrulanmış veridir — bu cümledeki HİÇBİR sayıyı değiştirme, yuvarlama, abartma veya "tahminen" gibi ifadelerle belirsizleştirme. Videoyu bu cümle etrafında kur. "exemplars" alanında oyun adı verilmişse SADECE o adları kullan; verilmemişse hiçbir oyun adı UYDURMA. confidence="medium" olan bulgularda "veriler işaret ediyor" gibi temkinli bir dil kullan, "kesinlikle" gibi kesin ifadelerden KAÇIN.

UYARI (CAVEAT) ZORUNLULUĞU: Sana JSON'da (üst seviyede, findings dışında) bir "caveats" listesi de verilecek (ör. "Korelasyon, nedensellik değildir"). [UYARI/RE-HOOK] bölümünde bu uyarılardan en az birini kendi cümlenle, doğal bir şekilde belirt. Bunu atlamak YASAK.

UZUNLUK: GÖRSEL, EKRAN YAZISI ve SFX/MÜZİK alanlarını kısa vurucu ifadeler halinde yaz (tam cümle değil). Sadece SESLENDİRME alanlarında belirtilen cümle/kelime sınırlarına kadar tam cümle kullan.

KRİSTAL BERRAKLIĞINDA ANLATIM: Kanca ve pazarlama taktikleri kullanmak iyidir ama HİKAYE ANLAŞILMAZ OLMAMALIDIR. Videoyu kurgulayacak editör "Burada ne anlatılmak isteniyor?" diye düşünmemelidir. Veriyi ve çözümü sokaktaki insanın (veya 10 yaşındaki bir çocuğun) anlayacağı netlikte anlat.

IDENTITY DISRUPTION (KİMLİK SARSMA): Hook (Kanca) bölümüne her zaman "SEN/SENİN" kelimeleriyle başla ve izleyicinin şu an büyük ihtimalle yaptığı bir "HATAYI" (varsa "hook" alanındaki öneriyi temel alarak) yüzüne vurarak videoya başla.

TELEGRAM KORUMASI: Metnin HİÇBİR YERİNDE kalınlaştırma veya italik yapmak için yıldız işareti (* veya **) KULLANMA.

ÇIKTI FORMATI — İKİ AYRI BÖLÜM ÜRET, aralarına TAM OLARAK şu ayracı koy: ---CAPTION_END---
Birinci bölüm (CAPTION, Telegram foto altyazısı, EN FAZLA 900 karakter — bu sert bir limit, aşarsan Telegram fotoğrafı reddeder): Sadece HOOK + VERİ GERÇEĞİ kısaca özetlenmiş halde, emoji kullanılabilir.
İkinci bölüm (SCRIPT, ayrı mesaj olarak gidecek, EN FAZLA 3200 karakter): Aşağıdaki tam blueprint yapısı.

📹 [Bulgunun "baslik" alanından türetilmiş vurucu başlık]

🎬 [EDİTÖRE NOT / VİDEONUN AMACI]: [Bu bulgunun ne anlama geldiğini, videonun ana fikrini, "claim" cümlesindeki veriyi 2-3 basit cümleyle açıkla.]

[00-03sn - HOOK]
GÖRSEL: [Kısa ifade. Çok spesifik oyun içi betimleme.]
EKRAN YAZISI: [Sessiz izleyici için devasa ve çarpıcı metin]
SFX/MÜZİK: [Kısa ifade.]
SESLENDİRME: [Maksimum 2 cümle. "Sen" diyerek başla, hook alanını temel al.]

[03-15sn - VERİ GERÇEĞİ]
GÖRSEL: [Kısa ifade. Verinin görselleştirilmesi — burada Telegram'a AYRICA gönderilen grafiği referans verebilirsin, ör. "az önceki grafikte gördüğün gibi".]
EKRAN YAZISI: [Kilit rakamlar: n, etki, varsa örnek oyun adları]
SFX/MÜZİK: [Kısa ifade.]
SESLENDİRME: "claim" alanındaki cümleyi doğal bir dille, sayıları DEĞİŞTİRMEDEN anlat. Maks 30 kelime.

[15-25sn - UYARI/RE-HOOK]
GÖRSEL: [Kısa ifade.]
EKRAN YAZISI: [Kısa, dikkat çekici uyarı ifadesi]
SFX/MÜZİK: [Kısa ifade.]
SESLENDİRME: caveats listesinden bir uyarıyı doğal dille belirt (zorunlu). Maks 25 kelime.

[25-40sn - RİBAT ANALİZİ / ÇÖZÜM]
GÖRSEL: [Kısa ifade.]
EKRAN YAZISI: [Çözüm önerisinin kısa özeti]
SFX/MÜZİK: [Kısa ifade.]
SESLENDİRME: [Bu bulgudan çıkan somut tavsiye. Maks 30 kelime.]

[40-50sn - CTA]
GÖRSEL: [Kısa ifade. Ribat Games Studio logosu]
EKRAN YAZISI: [Takip et/Yorum yap]
SFX/MÜZİK: [Kısa ifade.]
SESLENDİRME: [Yorumlara davet.]

📝 CAPTION (Instagram için ayrı, buradaki Telegram caption'dan farklı): [Maksimum 3 cümlelik Instagram açıklaması + etiketler.]
```

---

## Bilinen sınırlar / sonraki iyileştirmeler

- **`---CAPTION_END---` ayracı n8n tarafında bir "Code" veya "Set" node'uyla
  parse edilmeli** (`.split('---CAPTION_END---')`) — bu düz metin işlemi,
  kod tarafında zorlanmadı, n8n workflow'unda kurulmalı.
- **Caption 900 karakter sınırı, LLM'in bazen aşması ihtimaline karşı** n8n
  tarafında bir güvenlik kesmesi (`.slice(0, 1024)`) eklemek iyi olur —
  Telegram API sert limiti 1024, prompt 900 diyerek pay bırakıyor ama LLM
  her zaman kelime sayısına tam uymayabilir.
- **`temporal_trend` ailesindeki bulgularda `effect_ci` şu an `[NaN, NaN]`**
  (bkz. `families/temporal.py` — bu aile Spearman p-değerini kapı olarak
  kullanıyor, bootstrap uygulamıyor). Prompt'ta bu artık açıkça ele alınıyor
  ("effect_ci NaN ise YOK SAY").
  Kullanıcı "ayda 4-5 video" dediği için bu sayı zaten uyumlu; değiştirmek
  istenirse `src/contracts.py`'deki `MAX_FINDINGS_FOR_LLM` sabiti güncellenmeli.
- **Loop Over Items her turda ayrı bir LLM çağrısı yapar** — 5 bulgu için
  5 ayrı API çağrısı demek (eskiden 1 çağrıda 5 bulgu birden işleniyordu).
  Maliyet farkı önemsiz (Sonnet 5, ayda birkaç kuruş) ama n8n'in rate-limit
  ayarlarına göre turlar arası küçük bir gecikme (`Wait` node) eklemek
  gerekebilir.

---

## 2026-08-05 — Editör gözüyle bulunan 3 teslimat hatası (canlı test)

Kullanıcı ilk gerçek "Execute workflow" çalıştırmasını yapıp Telegram
çıktısını paylaştı. Editör gözüyle okununca üç mekanik hata bulundu (içerik
değeri sorunları — etiket bulguları, jargon — ayrı olarak `src/contracts.py`
ve `src/narrative/templates.py`'de çözüldü, bkz. plan Adım B/C):

1. **"✅ Haftalık analiz tamamlandı" mesajı 5 KEZ gönderiliyordu.** Bu n8n'in
   bilinen bir bug'ı ([GitHub Issue #21376](https://github.com/n8n-io/n8n/issues/21376))
   — `Split In Batches`'ın "done" çıkışı, dokümantasyonun aksine, bazı
   sürümlerde her iterasyonda tetikleniyor. Çözüm: `Loop Over Items` ile
   `Telegram Done` arasına **yeni bir `IF` node'u ("Loop Bitti mi?")**
   eklendi — koşul `{{ $("Loop Over Items").context.noItemsLeft }} === true`.
   Sadece gerçekten son turdaysa `Telegram Done`'a gider.
2. **LLM'in kendi kendine konuşma cümleleri Telegram'a gidiyordu** —
   *"Başlıyorum:"*, *"CAPTION'ı yazıyorum:"* gibi meta-yorumlar caption'ın
   başına sızmıştı. İki katmanlı düzeltme: (a) prompt'a MUTLAK KURAL eklendi
   — cevap doğrudan 📷 emojisiyle başlamalı, hiçbir giriş cümlesi yazılmamalı;
   (b) `Split Caption Script` node'una `stripPreamble()` eklendi — ilk emoji
   karakterine kadar olan metni (varsa, ilk 200 karakter içindeyse) kırpar,
   LLM kurala uymasa bile son bir savunma hattı olsun diye.
3. **Bazı bulgularda script hiç gitmiyordu** (Bullet Hell, Visual Novel'de
   sadece caption vardı). Kök neden: LLM bazı turlarda `---CAPTION_END---`
   ayracını hiç yazmamış, `parts[1]` sessizce boş kalmıştı. İki katmanlı
   düzeltme: (a) prompt'a MUTLAK KURAL eklendi — ayraç mutlaka yazılmalı;
   (b) `Split Caption Script`'e fallback eklendi — ayraç yoksa TÜM metin
   `script` olarak gönderilir, `caption` için ilk paragraf kullanılır (eskiden
   bu durumda script tamamen kayboluyordu).

**Güncel `docs/n8n_workflow.json`'ı tekrar import etmek, tüm bu düzeltmeleri
otomatik uygular** — node ID'leri korunduğu için mevcut credential
bağlantıları bozulmaz.

**NOT (2026-08-06 GERİ ALINDI):** "Loop Bitti mi?" IF node'u ("done"
çıkışının 5 kez tetiklenmesini çözmek için) eklenmişti, ama canlı testte bu
sayıyı 5'ten 2'ye düşürdü, 1'e değil — `noItemsLeft` kontrolü n8n'in bu
bug'ını (GitHub #21376) tam çözmüyor. Kullanıcı kararıyla `Telegram Done` VE
`Loop Bitti mi?` node'ları TAMAMEN KALDIRILDI. Gerekçe: 5 foto+script zaten
geldiğinde kullanıcı işin bittiğini anlıyor, "tamamlandı" mesajı bilgi
değeri taşımıyordu — sorunun kaynağını ortadan kaldırmak, kısmi bir
workaround'dan daha güvenilir.

## 2026-08-05 — İçerik değeri sorunları (aynı canlı testten)

Yukarıdaki 3 mekanik hatanın yanında, kullanıcı **içeriğin kendisinin**
kayda değer olup olmadığını sorguladı. İki büyük değişiklik kod tarafında
yapıldı (n8n'de dokunulacak bir şey yok, findings.json'un içeriği değişti):

1. **Etiket bulguları LLM'e artık gönderilmiyor** (`src/contracts.py`,
   `NON_ACTIONABLE_FAMILIES`). *"'Boomer Shooter' etiketi koy, 18 puan daha
   görünür ol"* gibi bulgular tuzak içerikti — etiket bir SONUÇ, sebep değil.
   Önce keşif motoru genişletildi (fiyat bandı, oyun modu/platform kategorileri
   — `src/discovery/run_all.py`), 276 bulgunun 267'sinin etiket ailesinden
   geldiği ölçüldü, filtre öncesi bu genişletme yapılmasaydı havuz 9 bulguya
   düşüp 2 ayda tükenirdi. Şimdi havuz ~24 aksiyona-dönüşen bulgu içeriyor
   (fiyat bandı, Co-op/VR/MMO gibi oyun modları, oynanma süresi, achievement,
   Metacritic, peak CCU).
2. **Video kalıbı çeşitliliği eklendi** — prompt artık 3 alternatif kalıptan
   (Kimlik Sarsma / Karşılaştırma / Sayı Şoku) findings'in temasına göre
   birini seçiyor, her video aynı "Sen yanlış biliyorsun" formülünde değil.
3. **Grafikler büyütüldü** (`src/narrative/chart_selector.py`) — font boyutları
   ve `figure.dpi` artırıldı, kaynak damgası tek satıra indirildi, mobilde
   okunabilirlik iyileştirildi.

`findings.json`'un yeni içeriğini test etmek için: `python -m src.discovery.run_all`
çalıştırıp `outputs/insights/findings.json`'daki `evidence.family` alanlarının
hiçbirinin `tags_list_single`/`tags_list_pair` olmadığını doğrula.

---

## 2026-08-06 — İkinci canlı test: hâlâ kesilen script'ler + NaN + 2x mesaj

Kullanıcı yukarıdaki düzeltmelerle tekrar denedi. İki bulgu daha çıktı:

1. **`findings.json` `NaN` içerdiği için "Parse findings JSON" node'u
   `SyntaxError: Unexpected token 'N'` ile çöküyordu.** Kök neden koddaydı
   (n8n'de düzeltilecek bir şey yok): Python'un `json.dumps`'u `temporal_trend`
   ailesinin `effect_ci=(NaN, NaN)` / `q_value=NaN` alanlarını ham `NaN`
   token'ı olarak yazıyordu — geçerli JSON değil. `src/contracts.py`'ye
   `_replace_nan_with_none()` eklendi, artık `null` yazılıyor. Kod tarafında
   çözüldü, sunucuda yeniden çalıştırıldı, doğrulandı (`grep -c NaN` → 0).

2. **Script'ler hâlâ cümle ortasında kesiliyordu** (ör. "...Metacr" diye
   bitiyordu), `Split Caption Script` kodu doğru olduğu hâlde. Kullanıcı
   `Message a model` node'undaki `Max Tokens to Sample` değerinin `2048`
   olduğunu doğruladı — bu, LLM'in kendi cevabının fiziksel olarak
   kesilmesi için yeterince düşük bir limitti (prompt uzun: video kalıbı
   kuralları + tam blueprint yapısı + JSON overhead). **`4096`'ya çıkarıldı.**
   Ayrıca prompt'taki "SCRIPT EN FAZLA 3200 karakter" ifadesi kod tarafındaki
   `trimToBoundary` limitiyle (3800) tutarsızdı — `3600` olarak birleştirildi,
   ayrıca "CTA bölümü DAHİL tam bitmiş olmalı" ifadesi eklendi.

3. **"✅ Haftalık analiz tamamlandı" mesajı, önceki turda eklenen "Loop Bitti
   mi?" IF node'una rağmen hâlâ 2 kez gidiyordu** (5'ten 2'ye düştü ama 1
   olmadı) — `noItemsLeft` kontrolü n8n'in bilinen bug'ını (GitHub #21376)
   tam çözmüyor. Kullanıcı kararıyla `Telegram Done` ve `Loop Bitti mi?`
   node'ları **tamamen kaldırıldı** — 5 foto+script zaten geldiğinde iş
   bittiği belli oluyor, ekstra mesajın bilgi değeri yoktu.

**n8n'de elle yapılması gerekenler (senin tarafında, kod değişikliği
yetmiyor):**
- `Message a model` → Options → Max Tokens to Sample → **4096** yap.
- `Telegram Done` ve `Loop Bitti mi?` node'larını sil, `Loop Over Items`'ın
  "done" çıkışını hiçbir yere bağlama (boş bırak).
- İstersen bunun yerine güncel `docs/n8n_workflow.json`'ı tekrar import et —
  otomatik olarak bu iki node olmadan gelir.

## 2026-08-06 (devam) — "22 puan" ne demek, hiçbir yerde açıklanmıyordu

Kullanıcı üçüncü canlı testte iki bulgunun (Metacritic, oynanma süresi)
**ikisinin de** "22 puan daha görünür" demesini fark etti ve sordu — bu bir
hata mı, yoksa gerçekten mi öyle? Kontrol edildi: **hata değil**, tesadüf —
iki grup arasında sadece %44 örtüşme var (confounding değil), gate.py'nin
etki büyüklüğü eşiği ikisinde de benzer bir puan farkına denk gelmiş. Ama
kullanıcının asıl sorduğu şey daha temel: **"puan" hiçbir yerde
tanımlanmıyordu** — izleyici bunun satış mı, kalite puanı mı, ne olduğunu
bilmiyordu.

**Gerçek tanım:** `visibility_pct`, oyunun REVIEW SAYISININ (kaç kişi yorum
yazdığı — review PUANI/pozitif oranı DEĞİL) kendi ÇIKIŞ YILINDAKİ diğer
oyunlara göre yüzdelik dilimidir. "22 puan daha görünür" = "bu grup, aynı
yıl çıkan oyunlara kıyasla review alma sıralamasında ortalama %22 daha üst
dilimde" — SATIŞ veya KALİTE değil, İLGİ/BİLİNİRLİK ölçer.

**Çözüm:** Prompt'a yeni bir MUTLAK KURAL eklendi — [03-15sn - VERİ GERÇEĞİ]
bölümünde "puan" kelimesi ilk geçtiğinde, cümlenin sonuna zorunlu bir
parantez açıklaması eklenmesi isteniyor (ör. "...22 puan daha görünür (yani
Steam'de review alma sıralamasında daha üst dilimde, satış rakamı değil)").

## Bilinen, henüz çözülmemiş sorun: bazı bulguların script'i hiç gelmiyor

Üçüncü testte "Visual Novel" bulgusunun SADECE grafiği geldi, caption/script
hiç gelmedi (diğer 4 bulgu tam geldi). Kök neden henüz kesin tespit
edilemedi — olası ihtimaller: (a) LLM o turda `---CAPTION_END---` ayracını
hiç yazmadı VE fallback mantığı da (tüm metni script yap) bir sebeple devreye
girmedi, (b) n8n'in kendisi o item'da bir hata verip sessizce atladı. Bir
sonraki canlı testte bu bulgu tekrar ederse, n8n'in "Executions" geçmişinden
o spesifik item'ın "Message a model" çıktısına bakılıp gerçek sebep
bulunmalı.

## 2026-08-06 (devam) — "İçi boş tavsiye" sorunu: `alternatives` alanı eklendi

Kullanıcı script'lerin somut aksiyon önerisi veremediğini fark etti —
"Bullet Hell düşüyor" diyordu ama "onun yerine ne yapmalı" sorusuna "tag
kombinasyonlarını test et" gibi genel/boş bir cevap veriyordu. Sebep: LLM'e
tek bir bulgu gidiyordu, elinde alternatif önerecek somut veri yoktu.

Kullanıcının kendi önerisi kilit noktaydı: *"adam zaten Bullet Hell
yapıyorsa temel tag'i değiştiremez — asıl soru hangi İKİNCİ tag'i eklerse
daha görünür olur."* Bu tam olarak `tags_list_pair` ailesinin ölçtüğü şey.

**Eklenen özellik:** `src/contracts.py:attach_alternatives()` — seçilen her
bulgunun etiketini `tags_list_pair` havuzunda arar, en güçlü 2 pozitif
eşleşmeyi `Finding.alternatives` alanına ekler (`added_tag`, `n`,
`gap_points`). `findings.json`'a yeni bir alan olarak yazılıyor. Bulgu
bulunamazsa (çoğu ailede — numeric_split, price_band gibi tag'i olmayan
bulgularda hiç anlamlı değil) `alternatives` boş liste kalıyor, LLM'e "boşsa
zorlama" talimatı verildi.

**Kapsam genişletmesi gerekli oldu:** Bullet Hell (popülerlik sırası 84)
gibi orta-popülerlikteki tag'ler eski `top_n=40` sınırının dışında kalıyordu,
hiç eşleşme bulunamıyordu. `generate_pairwise_hypotheses`'teki `top_n`
40'tan **100**'e çıkarıldı — süre ~2 dakikadan **~7 dakikaya** çıktı (kabul
edildi, kapsam değeri süreden önemli bulundu).

**Bu genişletme yan etki doğurdu — eski bir confounding artefaktı geri
döndü:** "Visual Novel + FPS" (plan dosyasında önceden "confounding
artefaktı, gerçek değil" diye teşhis edilmiş bir kombinasyon) `top_n=100`
ile tekrar gate'i geçti (n=61). Kontrol edildi: bu grubun ortalama tag
sayısı **19.1**, geri kalanın **14.8**'i — yani gerçek bir tür değil,
mağaza sayfasını maksimum tag'le doldurmuş ("tag-spam") oyunlar grubu.
`generate_pairwise_hypotheses`'e yeni bir filtre eklendi
(`MAX_TAG_COUNT_GAP = 3.0`): bir kombinasyonu taşıyan grubun ortalama
`n_tags`'i rest'ten 3'ten fazla yüksekse, o hipotez hiç ÜRETİLMİYOR.
Doğrulandı: "Visual Novel + FPS" artık üretilmiyor.

**n8n'de elle yapılması gereken:** Prompt'a yeni bir MUTLAK KURAL eklendi —
`alternatives` doluysa LLM somut veriyi ("X + Y kombinasyonu Z oyunda test
edildi, W puan fark") kullanmalı, boşsa genel tavsiye verebilir ama tag
UYDURMAMALI. Güncel `docs/n8n_workflow.json`'ı tekrar import et ya da
prompt metnini elle güncelle.

## 2026-08-06 (devam 2) — `alternatives` görselleştirme: ayrı foto yerine ikinci panel

Kullanıcı canlı çıktıda script'in [25-40sn - RİBAT ANALİZİ / ÇÖZÜM] bölümünde
*"GÖRSEL: İki sütun yan yana: 'Sadece Bullet Hell' solda, 'Anime + Bullet
Hell' sağda"* diye bir talimat yazdığını fark etti — ama böyle bir görsel
**hiç üretilmiyordu**, editör var olmayan bir görsele atıf yapan bir talimat
okuyordu.

**İlk deneme (geri alındı):** Her `alternatives` elemanı için ayrı bir PNG
üretmek ve n8n'e ikinci bir "Read Chart Image + Send Photo" zinciri eklemek
planlandı, prototiplendi ve çalıştığı doğrulandı. Ama kullanıcı daha zarif
bir çözüm önerdi: *"direkt tek grafikte ifade edilebiliyorsa tek grafiğe
yeni sütun eklemek ve videoda yeri geldikçe zoomlamak daha mantıklı olmaz
mı?"*

**Uygulanan çözüm:** `chart_selector.py:chart_trend_line()` artık
`finding.alternatives` doluysa **iki panelli** bir grafik üretiyor —
solda mevcut trend çizgisi (değişmedi), sağda küçük bir bar karşılaştırması
("Sadece X" vs "X + Y ekle", `alternatives[0]`'dan). Boşsa (çoğu bulguda —
numeric_split gibi tag taşımayan ailelerde) tek panelli eski davranış
korunuyor. **n8n tarafında HİÇBİR değişiklik gerekmiyor** — hâlâ tek bir
foto gönderiliyor, sadece o fotonun içeriği zenginleşti.

Prompt'a da bir not eklendi: `alternatives` doluysa, LLM'in [25-40sn]
GÖRSEL alanında YENİ bir görsel tarif etmesi değil, gönderilen fotonun
sağındaki panele atıf yapması ("az önceki grafikte sağdaki küçük panelde
gördüğün gibi") isteniyor.

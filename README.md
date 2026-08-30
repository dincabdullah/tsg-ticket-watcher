# TSG Hoffenheim bilet nöbetçisi

TSG Hoffenheim ticket shop'unda **C, D, E, F** bloklarından bilet çıktığı anda
Telegram'dan mesaj atar. GitHub Actions üzerinde 5 dakikada bir çalışır,
sunucuya gerek yoktur.

Şu an izlenen maç: **TSG Hoffenheim – Borussia Dortmund, 05.09.2026** (performance ID `3188`).

---

## Nasıl çalışıyor?

Shop'un kendi arka uç JSON'unu okur — sayfa kazıma (scraping) veya tarayıcı yok,
üç basit GET isteği var:

1. `GET /shop?shopid=104&wes=empty_session_104&language=1&nextstate=2`
   → sunucu taze bir oturum kimliği (`wes`) verir
2. `GET /shops/104/events/3188?wes=<wes>`
   → oturumu "ürün seçimi" adımına getirir
3. `GET /backend/saalinterface?wes=<wes>&getSaalInfos=3188`
   → her blok için `sitze_frei` (boş koltuk) döner

Her kontrolde son durum `state.json`'a yazılır. Mesaj **yalnızca bir blok
0'dan >0'a geçtiğinde** gider — yani bilet açık kaldığı sürece 5 dakikada bir
spam gelmez. Blok tekrar 0'a düşüp sonra yeniden açılırsa yeni mesaj gelir.

---

## Kurulum (yaklaşık 10 dakika)

### 1. Telegram botunu oluştur

1. Telegram'da **@BotFather**'a yaz.
2. `/newbot` gönder, bota bir isim ve `...bot` ile biten bir kullanıcı adı ver.
3. BotFather sana şuna benzer bir **token** verir:
   `8123456789:AAF3xQ...` — bunu bir kenara not et, kimseyle paylaşma.

### 2. chat_id'ni bul

1. Az önce oluşturduğun bota Telegram'dan **/start** yaz (bot sana mesaj
   atabilsin diye bu şart).
2. Tarayıcıda şu adresi aç (`<TOKEN>` yerine kendi token'ın):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Gelen JSON'da `"chat":{"id":123456789,...}` kısmındaki sayı senin
   **chat_id**'in. (Eksi ile başlıyorsa bir grup demektir, o da olur.)

### 3. Repoyu oluştur

Bu klasörü GitHub'a yükle. **Repoyu `Public` yap** — public repolarda GitHub
Actions dakikaları ücretsizdir; private repoda 5 dakikada bir çalışan bir iş
aylık ücretsiz kotayı ilk günlerde bitirir. Token'lar kodda değil GitHub
Secrets'ta duracağı için public olması sorun değil.

```bash
cd tsg-ticket-watcher
git init -b main
git add .
git commit -m "TSG bilet nöbetçisi"
git remote add origin https://github.com/<kullanıcı-adın>/tsg-ticket-watcher.git
git push -u origin main
```

### 4. Secrets'ları gir

Repoda **Settings → Secrets and variables → Actions → New repository secret**:

| İsim | Değer |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather'ın verdiği token |
| `TELEGRAM_CHAT_ID` | 2. adımda bulduğun sayı |

### 5. Actions'ı aç ve test et

1. **Actions** sekmesine git, uyarı çıkarsa
   *"I understand my workflows, go ahead and enable them"* de.
2. Soldan **TSG bilet nöbetçisi** → sağ üstte **Run workflow**.
3. `test` kutusunu **işaretle** ve çalıştır → Telegram'a test mesajı gelmeli.
4. Sonra `test` işaretsiz bir kez daha çalıştır → gerçek kontrolü yapar.

> İlk gerçek çalıştırmada büyük ihtimalle **"Blok F: 1 yer"** mesajı gelecek —
> depodaki başlangıç durumu hepsini 0 kabul ediyor, F'de ise şu an 1 koltuk var.
> Bu bir hata değil, sistemin çalıştığının kanıtı.

---

## Ayarlar

`.github/workflows/watch.yml` içindeki `env` bloğundan:

- `WATCH_BLOCKS` — izlenecek bloklar, virgülle: `"C,D,E,F"`.
  Tüm blok adları: A, B, C, D, E, F, G1, G2, H1, H2, I, J, K, L, M, N, O, P,
  Q, R, S1, S2, T, U, V, W, 101–104, 201–223, 301–322.
- `PERFORMANCE_ID` — maç kimliği. Başka bir maça geçmek için
  `https://tickets.tsg-hoffenheim.de/shop?shopid=104&wes=empty_session_104&language=1&nextstate=2&lpShortcutId=46`
  adresini aç, maçın **Tickets** bağlantısına tıkla, açılan sayfanın
  kaynağında `data-performanceid="...."` değerini al.
- Kontrol sıklığı — `cron: "*/5 * * * *"`. GitHub'ın alt sınırı 5 dakikadır ve
  yoğun saatlerde birkaç dakika gecikebilir; daha hızlısı için script'i kendi
  bilgisayarında veya bir VPS'te 30–60 saniyede bir çalıştırman gerekir.

## Yerelde çalıştırma

```bash
pip install requests
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
python check_tickets.py --dry-run   # mesaj atmadan durumu göster
python check_tickets.py --test      # sadece Telegram'ı test et
python check_tickets.py             # normal kontrol
```

## Bilinmesi gerekenler

- GitHub, **60 gün commit gelmeyen** repolarda zamanlanmış iş akışlarını
  otomatik durdurur. Bu script durum değiştikçe `state.json`'u commit'lediği
  için normalde sorun olmaz; yine de uzun sessizlikten sonra Actions
  sekmesinden açık olduğunu kontrol et.
- Bildirim, biletin **satın alındığını** garanti etmez; sadece haber verir.
  Popüler maçlarda iade biletler saniyeler içinde gidebilir.
- Shop yazılımı güncellenirse üç adımdan biri bozulabilir; o durumda Actions
  çalışması kırmızıya döner (`HATA: ...` satırıyla).
- Script dakikada bir istekten daha seyrek, kibar bir hızda çalışır. Aralığı
  agresif biçimde düşürmemekte fayda var.

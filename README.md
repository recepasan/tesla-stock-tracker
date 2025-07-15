# Tesla Stock Tracker

Tesla Model Y stok durumunu takip eden ve yeni araçlar geldiğinde Telegram üzerinden bildirim gönderen Python uygulaması.

## Özellikler

- 🚗 Tesla Model Y stoklarını sürekli takip eder
- 📱 Telegram bot ile anlık bildirimler gönderir
- 🔄 Tekrar stokta olan araçları da takip eder
- 🛡️ Spam koruması (bildirim cooldown ve maksimum bildirim sayısı)
- 🎯 Proxy desteği ile güvenli erişim
- 📊 Detaylı loglama ve hata yönetimi
- 💾 VIN takibi ile tekrar eden bildirimler

## Kurulum

1. Projeyi klonlayın:
```bash
git clone https://github.com/yourusername/tesla-stock-tracker.git
cd tesla-stock-tracker
```

2. Gerekli kütüphaneleri yükleyin:
```bash
pip install -r requirements.txt
```

3. Yapılandırma dosyasını oluşturun:
```bash
cp config.json.example config.json
```

4. `config.json` dosyasını düzenleyin ve gerekli ayarları yapın:
   - Telegram bot token'ınızı ekleyin
   - Chat ID'nizi ekleyin
   - Proxy ayarlarını yapın (isteğe bağlı)

## Yapılandırma

### config.json Dosyası

```json
{
    "telegram": {
        "bot_token": "YOUR_BOT_TOKEN_HERE",
        "chat_id": "YOUR_CHAT_ID_HERE"
    },
    "proxies": [
        "http://proxy1.example.com:8080",
        "http://proxy2.example.com:8080"
    ],
    "base_ips": [
        "78.181",
        "85.100",
        "88.247"
    ],
    "notification_cooldown_hours": 24,
    "max_notifications_per_vin": 3,
    "vin_cleanup_days": 7,
    "check_interval_seconds": 30
}
```

### Ayarlar

- **telegram.bot_token**: Telegram bot token'ınız
- **telegram.chat_id**: Bildirim gönderilecek chat ID'si
- **proxies**: Kullanılacak proxy listesi (isteğe bağlı)
- **base_ips**: Rastgele IP üretimi için kullanılacak IP aralıkları
- **notification_cooldown_hours**: Aynı VIN için tekrar bildirim gönderme aralığı (saat)
- **max_notifications_per_vin**: Her VIN için maksimum bildirim sayısı
- **vin_cleanup_days**: Eski VIN kayıtlarını temizleme süresi (gün)
- **check_interval_seconds**: Stok kontrol aralığı (saniye)

## Telegram Bot Kurulumu

1. Telegram'da [@BotFather](https://t.me/BotFather) ile konuşun
2. `/newbot` komutunu gönderin
3. Bot adını ve kullanıcı adını ayarlayın
4. Bot token'ınızı alın
5. Chat ID'nizi öğrenmek için [@userinfobot](https://t.me/userinfobot) kullanın

## Kullanım

Programı çalıştırmak için:

```bash
python tesla_stock_tracker.py
```

Program çalışırken:
- Her 30 saniyede bir Tesla stok API'sini kontrol eder
- Yeni araçlar bulduğunda Telegram'a bildirim gönderir
- Tekrar stokta olan araçları da takip eder
- Logları hem terminalde hem de `tesla_tracker.log` dosyasında tutar

## Önemli Notlar

- ⚠️ Bu proje eğitim amaçlıdır
- 🔒 Kişisel bilgilerinizi (bot token, chat ID) paylaşmayın
- 📝 Proxy kullanımı isteğe bağlıdır
- 🚫 Rate limiting'e dikkat edin
- 📊 Logları düzenli olarak kontrol edin

## Gereksinimler

- Python 3.7+
- requests
- asyncio

## Katkıda Bulunma

1. Fork edin
2. Yeni bir branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add some amazing feature'`)
4. Branch'inizi push edin (`git push origin feature/amazing-feature`)
5. Pull Request açın

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakın.

## Sorumluluk Reddi

Bu proje Tesla, Inc. ile bağlantılı değildir. Tesla'nın API'sini kullanmadan önce kullanım koşullarını kontrol edin.

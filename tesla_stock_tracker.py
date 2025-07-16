import time
import requests
import logging
import json
import os
from typing import Dict, List, Any
import random
from datetime import datetime, timedelta
import asyncio

# Yapılandırma dosyasını yükle
def load_config():
    """Yapılandırma dosyasını yükler."""
    config_path = 'config.json'
    if not os.path.exists(config_path):
        logger.error(f"Yapılandırma dosyası bulunamadı: {config_path}")
        logger.info("Lütfen config.json dosyasını oluşturun ve gerekli ayarları yapın.")
        exit(1)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# Yapılandırmayı yükle
config = load_config()

# Logging ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tesla_tracker.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# VIN'leri zaman damgası ile saklamak için dictionary
# Format: {"VIN": {"last_seen": datetime, "notification_count": int, "first_seen": datetime}}
processed_vins = {}

# Ayarlar
NOTIFICATION_COOLDOWN_HOURS = config.get('notification_cooldown_hours', 24)
MAX_NOTIFICATIONS_PER_VIN = config.get('max_notifications_per_vin', 3)
VIN_CLEANUP_DAYS = config.get('vin_cleanup_days', 7)
CHECK_INTERVAL = config.get('check_interval_seconds', 30)

def cleanup_old_vins():
    """Eski VIN kayıtlarını temizler."""
    current_time = datetime.now()
    cleanup_threshold = current_time - timedelta(days=VIN_CLEANUP_DAYS)
    
    vins_to_remove = []
    for vin, data in processed_vins.items():
        if data['last_seen'] < cleanup_threshold:
            vins_to_remove.append(vin)
    
    for vin in vins_to_remove:
        del processed_vins[vin]
    
    if vins_to_remove:
        logger.info(f"{len(vins_to_remove)} eski VIN kaydı temizlendi.")

def should_send_notification(vin: str) -> bool:
    """VIN için bildirim gönderilip gönderilmeyeceğini kontrol eder."""
    current_time = datetime.now()
    
    if vin not in processed_vins:
        # Yeni VIN - bildirim gönder
        return True
    
    vin_data = processed_vins[vin]
    
    # Maksimum bildirim sayısına ulaştıysa gönderme
    if vin_data['notification_count'] >= MAX_NOTIFICATIONS_PER_VIN:
        return False
    
    # Son bildirimden beri yeterli zaman geçtiyse gönder
    time_since_last = current_time - vin_data['last_seen']
    if time_since_last >= timedelta(hours=NOTIFICATION_COOLDOWN_HOURS):
        return True
    
    return False

def update_vin_tracking(vin: str, notification_sent: bool = False):
    """VIN takip bilgilerini günceller."""
    current_time = datetime.now()
    
    if vin not in processed_vins:
        processed_vins[vin] = {
            'last_seen': current_time,
            'notification_count': 1 if notification_sent else 0,
            'first_seen': current_time
        }
    else:
        processed_vins[vin]['last_seen'] = current_time
        if notification_sent:
            processed_vins[vin]['notification_count'] += 1

def format_price_as_tl(price):
    """Fiyatı TL formatında biçimlendirir."""
    try:
        # Fiyat string olabilir, sayıya çevirelim
        if isinstance(price, str):
            # Sayısal olmayan karakterleri temizle
            price = ''.join(c for c in price if c.isdigit() or c == '.')
            price = float(price)
        
        # Bin ayracı olarak nokta ve sonunda TL sembolü kullanarak biçimlendir
        formatted_price = "{:,.0f} ₺".format(price).replace(",", ".")
        return formatted_price
    except (ValueError, TypeError) as e:
        logger.warning(f"Fiyat biçimlendirilemedi: {str(e)}")
        return f"{price} ₺"
    

def extract_car_features(car_data: Dict[str, Any]) -> Dict[str, str]:
    """Araç verilerinden özellik bilgilerini çıkarır."""
    features = {}
    
    try:
        option_specs = car_data.get('OptionCodeSpecs', {})
        
        # Specs bilgilerini çıkar
        specs = option_specs.get('C_SPECS', {}).get('options', [])
        for spec in specs:
            if spec.get('code') == 'SPECS_RANGE':
                features['range'] = spec.get('name', '')
            elif spec.get('code') == 'SPECS_TOP_SPEED':
                features['top_speed'] = spec.get('name', '')
            elif spec.get('code') == 'SPECS_ACCELERATION':
                features['acceleration'] = spec.get('name', '')
        
        # Options bilgilerini çıkar
        options = option_specs.get('C_OPTS', {}).get('options', [])
        for option in options:
            lexicon_group = option.get('lexiconGroup', '').lower()
            if lexicon_group == 'paint':
                features['paint'] = option.get('name', '')
            elif lexicon_group == 'wheels':
                features['wheels'] = option.get('name', '')
            elif lexicon_group == 'interior':
                features['interior'] = option.get('name', '')
            elif lexicon_group == 'rear_seats':
                features['seats'] = option.get('name', '')
            elif lexicon_group == 'autopilot':
                features['autopilot'] = option.get('name', '')
        
    except Exception as e:
        logger.warning(f"Araç özellikleri çıkarılırken hata: {str(e)}")
    
    return features

def format_features_text(features: Dict[str, str]) -> str:
    """Özellik bilgilerini metin formatında düzenler."""
    feature_lines = []
    
    # Performans özellikleri
    if features.get('range'):
        feature_lines.append(f"🔋 Menzil: {features['range']}")
    if features.get('acceleration'):
        feature_lines.append(f"⚡ 0-60 mph: {features['acceleration']}")
    if features.get('top_speed'):
        feature_lines.append(f"🏎️ Maksimum Hız: {features['top_speed']}")
    
    # Tasarım özellikleri
    if features.get('paint'):
        feature_lines.append(f"🎨 Renk: {features['paint']}")
    if features.get('wheels'):
        feature_lines.append(f"⚙️ Jantlar: {features['wheels']}")
    if features.get('interior'):
        feature_lines.append(f"🪑 İç Mekan: {features['interior']}")
    if features.get('seats'):
        feature_lines.append(f"👥 Koltuk: {features['seats']}")
    
    # Ek özellikler
    if features.get('autopilot'):
        feature_lines.append(f"🤖 {features['autopilot']}")
    
    return '\n'.join(feature_lines)

async def send_telegram_message(car: Dict[str, Any], is_repeat: bool = False) -> bool:
    """Verilen araç bilgilerini Telegram'a gönderir, gerekirse yeniden dener."""
    max_retries = 5
    retries = 0
    
    async def send_message() -> bool:
        nonlocal retries
        try:
            formatted_price = format_price_as_tl(car['TotalPrice'])
            
            image_url = f"https://static-assets.tesla.com/configurator/compositor?context=design_studio_2?&bkba_opt=1&view=STUD_3QTR&size=600&model=my&options={car['OptionCodeList']}&crop=1150,647,390,180&"
            
            # Tekrar eden araç için özel mesaj
            status_text = "🔄 TEKRAR STOKTA" if is_repeat else "🆕 YENİ ARAÇ"
            
            # Kaç kez bildirim gönderildiğini göster
            vin_data = processed_vins.get(car['VIN'], {})
            notification_info = ""
            if is_repeat and 'notification_count' in vin_data:
                notification_info = f"\n📊 {vin_data['notification_count']}. bildirim"

            features = extract_car_features(car)
            features_text = format_features_text(features)

            message_text = f"{status_text}\n\n📱 Araç Modeli: {car['TrimName']}\n💰 Fiyat: {formatted_price}\n🔢 VIN: {car['VIN']}{notification_info}"

            if features_text:
                message_text += f"\n\n🔧 Özellikler:\n{features_text}"
            
            data = {
                "chat_id": config['telegram']['chat_id'],
                "photo": image_url,
                "caption": message_text,
                "reply_markup": {
                    "inline_keyboard": [
                        [{
                            "text": "Araç Detayları",
                            "url": f"https://www.tesla.com/tr_TR/my/order/{car['VIN']}"
                        }]
                    ]
                }
            }
            
            bot_token = config['telegram']['bot_token']
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            
            response = requests.post(url, json=data)
            response.raise_for_status()
            
            logger.info(f"Mesaj başarıyla gönderildi: {car['VIN']} ({'Tekrar' if is_repeat else 'Yeni'})")
            return True
            
        except Exception as error:
            logger.error(f"Telegram mesajı gönderilirken hata oluştu (Deneme {retries + 1}/{max_retries}): {str(error)}")
            retries += 1
            
            if retries < max_retries:
                logger.info(f"Yeniden deneniyor ({retries}/{max_retries})...")
                # Üstel gecikme - her deneme arasında daha uzun bekle
                await asyncio.sleep(1 * retries)
                return await send_message()
            else:
                logger.error(f"Maksimum deneme sayısına ulaşıldı. Mesaj gönderme başarısız: {car['VIN']}")
                return False
    
    return await send_message()

def generate_random_ip():
    """Rastgele IP adresi üretir."""
    base_ips = config.get('base_ips', ["78.181"])
    base = random.choice(base_ips)
    x = random.randint(0, 255)
    y = random.randint(0, 255)
    ip = f"{base}.{x}.{y}"
    return ip

def get_headers():
    """Tesla API için gerekli header'ları döndürür."""
    return {
        'accept': '*/*',
        'accept-language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
        'dnt': '1',
        'priority': 'u=1, i',
        'referer': 'https://www.tesla.com/tr_tr/inventory/new/my',
        'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Opera";v="119"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'sec-gpc': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 OPR/119.0.0.0',
        'Cookie': '_pk_id.1.3c49=3e6e8820d7ea034a.1745595260.; tsla-cookie-consent=accepted; has_js=1; buy_flow_locale=en_US; optimizelySession=0; homepage_ab_test_variation=A; x-correlation-user-id=638342b6-b7d8-49dc-b915-5f90c14afb45; _pk_ref.1.3c49=%5B%22%22%2C%22%22%2C1747928826%2C%22https%3A%2F%2Fwww.google.com%2F%22%5D; ip_info={"ip":"'+generate_ip()+'","location":{"latitude":40.8587,"longitude":31.178},"region":{"longName":"DÃ¼zce","regionCode":"81"},"city":"DÃ¼zce","country":"TÃ¼rkiye","countryCode":"TR","postalCode":"81010"}; preferred_address={"ip":null,"location":{"latitude":40.7591267,"longitude":-73.97767689999999},"region":{"longName":"New York","regionCode":"NY"},"city":"New York","county":"New York","country":"United States","countryCode":"US","postalCode":"10111"}; oxpOriUrl=https%3A%2F%2Fwww.tesla.com%2Ftr_tr%2Fteslaaccount; bm_ss=ab8e18ef4e; ak_bmsc=45400F21B5DCD38376DD909C91CA059B~000000000000000000000000000000~YAAQvLSvw9wTRbCXAQAAwKyPsRxltBwUeD/RQrez5+2OjgxnQiUaKlH67WOIQBD3XvxNysvm4KZdt9T4Q7U9IskvBjA60VhotPEk2QexQc/uZvkT9+nc1MO7T0vYjWeSlUroYyGQ0cDpmX2T0nAL2BlXgmSQEEFebRJJEYh4RWlPzUfkmOkmmGPVedusY8Qu39FiaYx1DGLs0UWAcA7AGTvI01q9wpK//ea2WrXthhEvAKrQRPIP8Y/H0Fkj2qSFMIWfmMZZ8nV7HvB+W1zmuvMsftp2nBacjn8AziTmqpDKoJo8K3IntCgSW5NIqnKs7+1Zw28hf1H2d1kDmDwiIlddEJPPpqNeN+kxxBAgu4KOF7DTi4YbJR7rDvUzkXS3VBIRHfFlKXDf0rFLM1S1Pd/kyA3qqlaPk7dlqSD2pJKCMiM=; bm_so=497B7E815F15CD3A1287D604BAFC24DED264275B3AC3604D5C4AF192F8194674~YAAQvLSvw94TRbCXAQAAwKyPsQTNSAv4NACiuwsCAhf9Y7u3Gsac4yiR8uELA8Q0qG3VOsOLRNyWFO2hYd481ha4sHC5GCJSTnfCzdqFBVoFOFASyohqATjhWRWNk7+HcmcWYttERwDpE8CLPzU0AMEM6sCOn+2xT94b4C6Bvf2sju6hkGkRV7850ZKXyN1vtPq39eugPTnVBwjTrSn7WY+DOHvtnqvJQexN9zFNlYO8FLnH69nuSTr54GIN32YEodTALiYXVyW6k2GS/TPNyD8ICnQJzJ5WRue1msrg68C5LWWtASfr9ymJCwO0Jcmbo22lzeAn9hjoFE7qFZ9Fk/kRV1cISgkTsTf6GgpiZognk/NVyxhcaO8XlVs8/7tJ2aRVIio4nXiPVD6Fq2L1HjjLWaBKX91M3UQPm7Xop8/YtaWHZ64pb3MC909yGg5Xx61c1tNMim8WiiA/9PT3LMFTKkagnqr0uSLCdqxNlTvolWhAyBxe; bm_lso=497B7E815F15CD3A1287D604BAFC24DED264275B3AC3604D5C4AF192F8194674~YAAQvLSvw94TRbCXAQAAwKyPsQTNSAv4NACiuwsCAhf9Y7u3Gsac4yiR8uELA8Q0qG3VOsOLRNyWFO2hYd481ha4sHC5GCJSTnfCzdqFBVoFOFASyohqATjhWRWNk7+HcmcWYttERwDpE8CLPzU0AMEM6sCOn+2xT94b4C6Bvf2sju6hkGkRV7850ZKXyN1vtPq39eugPTnVBwjTrSn7WY+DOHvtnqvJQexN9zFNlYO8FLnH69nuSTr54GIN32YEodTALiYXVyW6k2GS/TPNyD8ICnQJzJ5WRue1msrg68C5LWWtASfr9ymJCwO0Jcmbo22lzeAn9hjoFE7qFZ9Fk/kRV1cISgkTsTf6GgpiZognk/NVyxhcaO8XlVs8/7tJ2aRVIio4nXiPVD6Fq2L1HjjLWaBKX91M3UQPm7Xop8/YtaWHZ64pb3MC909yGg5Xx61c1tNMim8WiiA/9PT3LMFTKkagnqr0uSLCdqxNlTvolWhAyBxe^1751030673604; bm_s=YAAQvLSvw/0URbCXAQAA48GPsQNky3foYtIV70m1LjlrR0LfN5JDMyxb/M3HbX9MwMDjx5Gvg9KqYGNs5U/wLbbqgEKAegTOKOeQLk+SACJbIBHpo6gaKhCjCF5VTO2UTWpzANus+MDDldB71chJLet3OPKH007idAi/CIfrH/CzX+KoKiY7tLiPlcCEUBajac4wfuOeAE89Rc1/OTaKHLgcobsYOqK0BBhZorMZ9TvZ17dqAWsfxisEoTetzOBLfzCl0a7dvhFDEufnq5FmBLhxskoYlB+y6oB4kv7rP7nQJSkVEdcyfHh242WrAu9CLvlVSSrRgUdOsmrfmDxafAu7LujnWrTAO8PGlB98qlYnYL9umDvlAnK0BzB0rwz3d7AflsgCEjd4Vv0vwAoPfnrHAgSZ3oyylU5gvODe8y2sh2pNL8JtIDyCsLG6kTWn2twSM1MyKe4MUstCVw07YY/8Pw9JKL1ggXSN0TyMoDELsA94KYVMuqdNdkh1vCMmC2YhS9nN3MDdQSnXFBKFPCD9K41J7U839fkt8A5fAAF3DvjxkyW8N+layd/r6lA65DdQc67gP3De8Xl6Z4wJNHWZQ0sVzbp3Ibd30lQmUurXVPYWK4EOh/i+LAJwciFEwQcwdubrLK+9dg==; bm_sv=5C29DCE304492B3EC7DE99D0DAB45EC3~YAAQvLSvw/4URbCXAQAA48GPsRx7Yn15LUf6KKTt2HaJ32Nn6qwhEM1FkR4YPaE4WZVrq24RVmiug1/+G+p2NggLubuu5GYxLcBxXuz28V8tkiUei9cn+mftGgm3l8Vp/nIoC9tESBe62xz4/w+VMFpwq/rcOisXLQZ9WaFnxEdsqvHm4sfjoDU8eRU6ULz1b4ox2oLnbN7kVbbIMHd2qUTjVg+h1zWHtaDhwf/Ysmp9a1Fm7oWrG9IT9NudwTU=~1; bm_sz=32D6F6E0A4944D5B325A2FA87C7EA8DE~YAAQvLSvw/8URbCXAQAA48GPsRwxlFUtR4aX3IJim26HkemyG+z11kPoZAYYRH9WGeRLMJ5YrE/GB6jGniKhTsoyXPUFnX95pU11fGdRa0ys4i6cjpdA9hX9yi3QG+DQyPm0TkfedUnj6e2wvCKJIAWKPu2+SzLCFTzQ1FMkVs3PVO/c1QjRfxNc4BnzozA1OYKfjsiHHBjB9YH1MOHpx32A/Oi10/2ZE/L+uFNYvAbJNqDDvGkC4zhBqrpgrcRnzOMpgukA7Sh9x1dVilqgay7qgeGPOzQsZNGE5nuMesillhPIx/AR7TUm+saPUKbXJZAvIAVPlu1zt2/Zm4YE4mom7d8+V3z1BQ0b49tw9x0fE+Fpb/J+V40ka+fpjGZQ3/hc7qyt+NcdLE85NMVy97VXbS6xOhh58S5Ectym8uHXD3F5BU+e8VLwZ4Y=~4273969~3290947; akavpau_zezxapz5yf=1751030978~id=256f16a4a2a5825a7f58c81e38a1e61c; _abck=A036F5EFEB157F72947E05DC28F61153~0~YAAQvLSvwwMVRbCXAQAASsKPsQ4bGwAzIuTrqIIou26BMkcb4HdJCLVNh1tRTBe3R4WALC+yMLfdRM3BIDyzqHNDlhCFobPvIqcdEtAdjA+1/N1G4+3yGjCSa8qwaG1OKOoqufaKI6Rf9Rq6i++/KGgdXc6BYppOwVrfihpxGagV72A5QeNBjptDLhDMs6KOTsgBaaKd8FaIskfdgZpu/3hxAwftsx9aQJZEtPkK9PCpLuz+OOaHEYCo6QprKTrlb90MM/Z3X8e3wRpbeES7+/EjXXHHrxNltitjXz6gxSvyPnOdzCDwRCOTzB+LwWR/W/Vwl3rs0CzuccOo+H6EGOl1Dv3YZqDQWCG/WAZkzt7XWVEC2R+mTU0PI6+tj8jDAtzHdHJoixRxNujYcGdA06AZ4oagkoXTEg7BfD4dmyptde0FcI4UhKiTo1xqay7VGEwTb5MWIfIFtp4vBCw/8rSXwx75LoqUlIf4Hu8h3DPBCCZqIvHtQ8pjhY9LAcEjh6qDfgP+WxZJ/MDcucwI9ibmbcet156bcMXF7hZzPPkuhYCnNJuFBaQuRTp7udV4Efb1IsdKN8fqyMNe7WFe5W+kVp7BnwsIZNywSXc8XSQPPVNEWq3DiV94L/1xaRTuCYu6qwkz1EsnBltu8ap2haI9dMePnOypgLJyK4qSCfJYRUUSpqLW055iQ/h5qfjKLm0cGAjQ4EehRG/wiGD2aGc7u5/iwR6t+zvMTlr3CKaVF911wa2TmV78e9qU3UT+eLC3wkSjLGDIsyvPjD61TEtj~-1~-1~1751034273; _abck=A036F5EFEB157F72947E05DC28F61153~-1~YAAQT0UVAp4nrnqXAQAAeaeQsQ4YpzwuS7tEIkvdC99sVaNaAQU0AIIrjnRarexWAWr85RQP6Bhm5S5fhs+BYKM51OtXhGucqxO4dZRraGKxD6PHuLuURR45yyEi1DoNPTRefvQnE/ROM0Fzmwwo3G3N8PXNQAN63vM3vrZGIgV1iEDqraCqBZd/QkRtUeRO8IzPt3IqDseNgF8PHD9Eg/gX9WSoQj1g+V/UGcRItKvu35fqK4palt3MBRQaamfj97lsuV2/XaBKnQtvO08N7xL9Xxz9oD9ugXwRdN8hdRn5n9+KC/GC72EE7hRjbUHkwvSnRa4gSgn56ssakyzfVMQqrdaI0h0f033lyNrL0t8kbvVLC24oIwZ1hzqE7zW6JHjdaRBDkg9nP5JnVYo7BfK9UBC9a/QEkQkp5Zsk8cu2mkNwenMGQcpNixSsZOIn2NWCnjgfTCNyHIvUhUZ1R2PFlAeUHy/wQQN8sp6tyq9wyeq1W/9VhB9aMRw27AbKCoYl/c0ZeliWmvwr1I5HpvCbvDlKxfIn78b+SL57g/KVBzOdprwU4pw2zcdbiB3CvVJavrZIR1KW3/KJ/ApEKx2/sbQFfxzNjXVg8ZZYJhVi5yqjJTWtvl7DIjYEroJSN0znloRZmhtjzT+CjDiPbZoGKwuyhxLQJ9clmPowxuIxR/vnljtktNU7NT5DZ7hibE/4+qZr4UgBuRMJ2i0XPUIUeo/Jde1aH5pKjJUWUSfKwgAaeVkkpwftap5aqtv/6ZtU+yf79NCkqXTyr3fQUmhu~0~-1~1751034273; bm_s=YAAQT0UVAp8nrnqXAQAAeaeQsQPD6NYo33o9Nx88uX7C73Sq4x57GL6R0k0s1MM74vIIaM2FyVPj+P+nooZWlGo2KWOTR5MJQVTHhBZNaCKA9BQEd0T93YGD3heMcrNuQZjCdJMM9LNgMfxPQOE8VPpdtrCRwPZ5pwOO44kXsEasSitnK0vss3Ol2xzzPSHzyiBnZp2a0E2e1P8cax0+czJJGMcOjJFgqxwfoi3HEuUT6d4X7UMZOCTEjXizeDxobczuK3YSdDYYPw1MEShXsINca+Dq27Pz81PxIxhw5nTaaNB0y4vMxR5cpfoOUE2Iy2y2+f88QTexhChCiA8rPGHIeahFIa77DTtPwXRMyPm0+z9lUKAkqfaVRS6RGihrg7gzoN5TvFyZQ4r5ivOVc2Wzj34+BbQypWqAoD5bWkcA8sH6QmvwLdRIvee0vSE5eM5k3RvxNqsosqRettI0YWFuBwLoVhHkP8M3wIlnJVZ1ttEDFn3XhVCV73myRAIX3iW0dr/HHdRGKFnxaVhfPmTAqF546gPCBdBWc6Ez2T6mKDOKMh+uwaKdu7FQ4r7FWJsSI3uV17MSGpvUMTVzFQtju+HxGw/4VgnmtFKzE80vbniaUIeniLAiGZR4eYem1I9kcD4cDxuTqw==; bm_sv=5C29DCE304492B3EC7DE99D0DAB45EC3~YAAQT0UVAqAnrnqXAQAAeaeQsRxcCWLNggD34/QCvEb8onyHOQrN/3x+RyUEACQmpmPeWEuwCRPqL1niq7wkyz9sA+HYAPw+t0stEiYPQPquygWk9yytd9hYIsQujlTYWt2zNdYjFtt1Ud+MBc1FoknhVxb4cOuzde0C+yW5BiFNG1Q2bX+zmfbvJDxbH/c8UquuazWZXFO+7QLKDzRmppcxEVeShdz4wGOz77bb2V9rCelFSFjLNbTLrasSqT0=~1; akavpau_zezxapz5yf=1751031036~id=a773ff9ac97082991551bfc63d7b4f1a'
    }

async def check_stock():
    """Tesla envanter API'sini kontrol eder ve sonuçları döndürür."""
    try:
        headers = get_headers()
        url = 'https://www.tesla.com/inventory/api/v4/inventory-results?query=%7B%22query%22%3A%7B%22model%22%3A%22my%22%2C%22condition%22%3A%22new%22%2C%22options%22%3A%7B%7D%2C%22arrangeby%22%3A%22Price%22%2C%22order%22%3A%22asc%22%2C%22market%22%3A%22TR%22%2C%22language%22%3A%22tr%22%2C%22super_region%22%3A%22north%20america%22%2C%22lng%22%3A32.8262%2C%22lat%22%3A39.9786%2C%22zip%22%3A%2206010%22%2C%22range%22%3A0%2C%22region%22%3A%22TR%22%7D%2C%22offset%22%3A0%2C%22count%22%3A24%2C%22outsideOffset%22%3A0%2C%22outsideSearch%22%3Afalse%2C%22isFalconDeliverySelectionEnabled%22%3Atrue%2C%22version%22%3A%22v2%22%7D'
        
        # Proxy kullan (eğer ayarlanmışsa)
        proxies = None
        if config.get('proxies') and len(config['proxies']) > 0:
            random_proxy = random.choice(config['proxies'])
            proxies = {"http": random_proxy, "https": random_proxy}
        
        response = requests.get(url, headers=headers, proxies=proxies, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data
        
    except Exception as error:
        logger.error(f'Stok kontrolü sırasında hata oluştu: {str(error)}')
        raise

async def main():
    """Ana program döngüsü."""
    # Bilgilendirici log ile başlat
    logger.info('Tesla stok takip sistemi başlatıldı...')
    logger.info(f'Ayarlar: Bildirim aralığı: {NOTIFICATION_COOLDOWN_HOURS} saat, Maks bildirim: {MAX_NOTIFICATIONS_PER_VIN}')
    logger.info(f'Kontrol aralığı: {CHECK_INTERVAL} saniye')
    logger.info(f'Daha önce işlenmiş VIN sayısı: {len(processed_vins)}')
    
    cycle_count = 0
    
    while True:
        try:
            cycle_count += 1
            
            # Her 100 kontrol döngüsünde bir eski VIN'leri temizle
            if cycle_count % 100 == 0:
                cleanup_old_vins()
            
            data = await check_stock()
            
            if data and isinstance(data, dict) and data.get('results') and len(data['results']) > 0:
                logger.info(f"Stokta {data.get('total_matches_found', 0)} araç bulundu. İşleniyor...")
                
                # Bu kontrolde bulunan araçları takip et
                notifications_sent = 0
                cars_processed = 0
                
                # Sonuçlardaki her aracı işle
                for car in data['results']:
                    try:
                        # Dictionary anahtarlarını kontrol et
                        required_keys = ['VIN', 'TrimName', 'TotalPrice', 'OptionCodeList']
                        if not all(key in car for key in required_keys):
                            missing_keys = [key for key in required_keys if key not in car]
                            logger.warning(f"Araç verisinde eksik anahtarlar: {missing_keys}. Bu aracı atlıyorum.")
                            continue
                        
                        cars_processed += 1
                        vin = car['VIN']
                        
                        # Bu VIN için bildirim gönderilmeli mi kontrol et
                        if should_send_notification(vin):
                            is_repeat = vin in processed_vins
                            
                            if is_repeat:
                                logger.info(f"Tekrar stokta olan araç: {car['TrimName']}, VIN: {vin}")
                            else:
                                logger.info(f"Yeni araç bulundu: {car['TrimName']}, VIN: {vin}")
                            
                            # Telegram mesajı gönder
                            if await send_telegram_message(car, is_repeat):
                                update_vin_tracking(vin, notification_sent=True)
                                notifications_sent += 1
                            else:
                                update_vin_tracking(vin, notification_sent=False)
                        else:
                            # VIN takibini güncelle ama bildirim gönderme
                            update_vin_tracking(vin, notification_sent=False)
                            
                            # Neden bildirim gönderilmediğini logla
                            vin_data = processed_vins[vin]
                            if vin_data['notification_count'] >= MAX_NOTIFICATIONS_PER_VIN:
                                logger.debug(f"VIN {vin} için maksimum bildirim sayısına ulaşıldı.")
                            else:
                                time_left = NOTIFICATION_COOLDOWN_HOURS - (datetime.now() - vin_data['last_seen']).total_seconds() / 3600
                                logger.debug(f"VIN {vin} için sonraki bildirime {time_left:.1f} saat kaldı.")
                                
                    except Exception as e:
                        logger.error(f"Araç işlenirken hata oluştu: {str(e)}")
                        logger.error(f"Problemli araç verisi: {car}")
                
                logger.info(f"Döngü {cycle_count}: {cars_processed} araç işlendi, {notifications_sent} bildirim gönderildi.")
                logger.info(f"Toplam takip edilen benzersiz VIN sayısı: {len(processed_vins)}")
                
            else:
                logger.info(f'Döngü {cycle_count}: Stokta araç yok veya veri alınamadı.')
                
        except Exception as error:
            logger.error(f'Stok kontrolü sırasında hata oluştu: {error}')
        
        # Belirlenen aralıkta kontrol et
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program kullanıcı tarafından durduruldu.")
    except Exception as e:
        logger.error(f"Program beklenmeyen bir hata ile sonlandı: {e}")

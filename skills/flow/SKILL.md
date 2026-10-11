---
name: flow
description: Google Flow ile video veya görsel üret. "Flow ile görsel oluştur", "şunun videosunu Flow'da yap", "Flow'a bağlan" gibi isteklerde kullan. Flow'un çalışması için gereken tarayıcı kurulumunu da bu skill yapar.
---

# Google Flow

Üretim `flow` MCP sunucusu üzerinden yapılır. Sunucu, kullanıcının kendi
Chrome'una bağlanır ve üretim onun Google AI Pro kotasından harcanır.

## Önce bağlantıyı doğrula

`flow_project` çağır. Proje kimliği ve adı dönüyorsa hazırsın, doğrudan
üretime geç. Sekme Flow ana sayfasındaysa sunucu yeni bir proje açar.

Hata alırsan sebebi neredeyse her zaman kurulumdur. Şu sırayla çöz:

1. **"Chrome'da açık sekme yok" / bağlantı hatası** — debug portundaki
   Chrome kapalı. Kullanıcıya şu komutu ver, kendisi çalıştırsın
   (yolu kendi clone dizinine göre değiştir):

   ```bash
   ./scripts/start-chrome.sh
   ```

   İlk açılışta profil boştur; Google hesabına **kullanıcı kendisi**
   giriş yapmalı. Şifreyi sen girme.

2. **"flow.google.com içeren sekme bulunamadı"** — Chrome açık ama Flow
   değil. Kullanıcıdan `flow.google.com` açmasını iste.

Portu `curl -s http://localhost:9222/json/version` ile kontrol edebilirsin.

## Üretim

Varsayılan yol tek çağrıdır:

```
flow_create("prompt", kind="image")
flow_create("prompt", kind="video", duration="8s", aspect="9:16")
```

Modu ayarlar, üretir, bitmesini bekler, dosyayı indirir ve yolunu döner.
Ayrı adımlar (`flow_settings`, `flow_model`, `flow_generate`,
`flow_status`, `flow_download`) yalnızca ara aşamaya müdahale etmen
gerekiyorsa lazım.

## Krediye dikkat

Görsel üretimi (Nano Banana) kredi harcamaz; **video harcar**. Kullanıcı
özellikle istemedikçe video için en ucuz ayarda kal: kısa süre, `x1`,
düşük çözünürlük. 4K upscale de kredi harcar ve ayrıca onay ister.

Bir video üretmeden önce, kullanıcı zaten "video yap" dememişse ne
üreteceğini bir cümleyle söyle.

## Prompt kalitesi

`flow_prompt_guide(model)` Google'ın o model için kendi rehberini verir.
Rehber prompt'a otomatik uygulanmaz: okursun, prompt'u kendin yazarsın,
kullanıcı ne gönderildiğini görür. Yanıttaki `retrieved` tarihi eskiyse
ve `flow_model()` listesinde olmayan modeller anlatıyorsa güvenme.

## Referans görseller

- **Frames** — videonun ilk ve son karesini belirler (`flow_frame`)
- **Ingredients** — prompt'a taşınan referans görseller (`flow_ingredient`)

İkisi de yalnızca video modunda çalışır. Yerel bir dosyayı önce
`flow_upload` ile projeye yükle, sonra adıyla referans göster.

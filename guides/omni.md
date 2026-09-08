---
model: Gemini Omni
flow_models: ["Omni 1.1 Flash"]
source: https://deepmind.google/models/gemini-omni/prompt-guide/
retrieved: 2026-09-08
---

> Bu sayfa Veo ve Nano Banana rehberlerine göre belirgin şekilde daha az ayrıntı
> veriyor: formül yerine beş bileşen sayıyor, örnek prompt sunmuyor. Boşluk
> kalan yerlerde Veo 3.1 rehberi iyi bir vekil — ikisi de video üretiyor ve
> sinematografi sözlüğü ortak.

## Beş bileşen

1. **Shot framing and motion** — çerçeveleme ve kamera hareketi. Geniş açı, orta,
   yakın plan? Kamera nasıl hareket etsin?
2. **Style** — genel his. Gerçekçi mi sinematik mi, sade mi görkemli mi?
3. **Lighting** — ışık nereden geliyor: güneş, sokak lambası, kadraj dışı bir
   kaynak?
4. **Location** — ortam, örneğin "an alien landscape with clear, azure water".
5. **Action** — sahnede ne oluyor, karakterler ve nesneler nasıl hareket ediyor?

## Kamera sözlüğü

static, locked off, fixed, push in, punch in, dolly zoom, one continuous shot,
oner, natural smartphone zoom, film camera, webcam style.

## Yetenekler

- Sahnenin tamamını yeniden yazmadan, sohbet ederek düzenleme
- Yerleşimi ve animasyonu senkron metin yerleştirme
- Sahneyi 10 saniyelik adımlarla, toplam 40 saniyeye kadar uzatma
- İlk/son kare vererek iki durum arasında geçiş üretme (`flow_frame`)
- Görsel, video, ses ve metin referanslarını birleştirme (`flow_ingredient`)
- Var olan görüntüye stil uygulama (anime, claymation, suluboya)

## Limitler

Uzatma ile en fazla 40 saniye. Sayfa çözünürlük ya da en-boy oranı sınırı
belirtmiyor; Flow'un kendi paneli 360p/720p ve 16:9 / 9:16 sunuyor.

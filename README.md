# flow-mcp

Google Flow'u yerel ajanlara (Claude Code, Cursor, Codex) MCP üzerinden açar.

Kendi açtığın bir Chrome'a bağlanır; Google oturumun ve **AI Pro kotan** olduğu
gibi kullanılır. API anahtarı ve ek ücret yok.

## Nasıl çalışıyor

Flow, arayüzün altında Google'ın `batchexecute` RPC protokolünü kullanıyor.
Sunucu ikiye ayrılmış durumda:

| İş | Yöntem | Neden |
|---|---|---|
| Durum sorgulama, medya URL'leri | Doğrudan RPC (`as29s`) | Captcha gerektirmiyor, DOM değişse de çalışır |
| Üretim başlatma | Gerçek arayüzü sürerek | İstek bir reCAPTCHA Enterprise token'ı taşıyor; onu ancak Flow'un kendi JS'i üretebilir |
| Ayar paneli | Arayüzü sürerek | Ayarlar istekle birlikte gidiyor, ayrı bir RPC'si yok |

Flow her üretim yolu için ayrı bir RPC kullanıyor (düz video, görsel,
başlangıç/bitiş karesi …) ve media id'nin yanıttaki yeri de yola göre
değişiyor. Bu yüzden hiçbir RPC kimliği ya da indeks ezberlenmiyor:
tıklamadan sonraki tüm `batchexecute` yanıtlarındaki UUID'ler toplanıp
medya servisine soruluyor, gerçekten var olanlar media id kabul ediliyor.
Flow yeni bir üretim yolu eklerse bu kendiliğinden çalışmaya devam eder.

Playwright kullanılmıyor — Chrome'a ham CDP ile bağlanılıyor, bağımlılık
sadece `mcp` + `websockets`.

## Kurulum

```bash
cd ~/Projects/flow-mcp
python3 -m venv .venv && ./.venv/bin/pip install -e .
```

## Kullanım

1. Chrome'u debug modunda başlat:

   ```bash
   ./scripts/start-chrome.sh
   ```

   İlk açılışta profil boştur — Google hesabına **elle** giriş yap. Oturum
   `~/.flow-mcp-profile` içinde kalıcı olur.

2. `flow.google.com` üzerinde bir proje aç. Sunucu o an açık olan projeye
   üretim yapar.

3. Ajanını bağla (aşağıya bak).

## Ajanlar bunu nasıl kullanır

Sunucu, MCP protokolünün `instructions` alanıyla kendini tanıtır: bağlanan
her istemci (Claude Code, Cursor, Codex) iş akışını, kredi uyarısını ve
"üretim açık olan projeye yapılır" kuralını otomatik görür. Ayrıca ajan
tarafında yapılandırma gerekmez.

Çoğu istek için tek araç yeter:

```
flow_create("mor bir dağ silüeti", kind="image")
flow_create("sisli orman", kind="video", duration="8s", aspect="9:16")
```

Claude Code için ayrıca `~/.claude/skills/flow/` altında bir skill var;
o, tarayıcı kurulumunu (debug portlu Chrome, Flow'da açık proje)
sorun çıktığında adım adım çözer.

## Araçlar

| Araç | Açıklama |
|---|---|
| **`flow_create(prompt, kind)`** | **Tek çağrıda: ayarla, üret, bekle, indir** |
| `flow_project` | Açık sekmedeki projenin kimliği ve adı |
| `flow_settings(options)` | Ayar panelini okur veya değiştirir |
| `flow_model(name)` | Modelleri listeler veya seçer |
| `flow_frame(slot, asset)` | Start/End karesini projedeki bir varlıktan atar |
| `flow_upload(file_path)` | Yerel görseli projeye yükler |
| `flow_ingredient(assets, clear)` | Referans görselleri prompt'a ekler |
| `flow_download_quality(media_id, quality)` | 270p GIF / 720p / 1080p / 4K indirir |
| `flow_prompt_guide(model, section)` | Google'ın o model için prompt rehberi |
| `flow_generate(prompt)` | Üretimi başlatır, **beklemez**, media id döndürür |
| `flow_status(media_id)` | `pending` / `done` / `not_found`, tür (`video`/`image`) ve hazırsa URL |
| `flow_download(media_id, filename)` | Biten videoyu/görseli diske indirir |

Video da görsel de aynı araçlarla üretilir; hangisinin üretileceğini
`flow_settings` ile seçtiğin mod belirler.

Üretim dakikalar sürdüğü için `flow_generate` bilinçli olarak asenkron.
Ajan üretimi başlatır, işine devam eder, sonra `flow_status` ile yoklar.

## Ajan yapılandırması

**Claude Code** — `~/.claude.json` içindeki `mcpServers`, ya da:

```bash
claude mcp add flow -- ~/Projects/flow-mcp/.venv/bin/python -m flow_mcp.server
```

**Cursor** — `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "flow": {
      "command": "/Users/KULLANICI/Projects/flow-mcp/.venv/bin/python",
      "args": ["-m", "flow_mcp.server"]
    }
  }
}
```

**Codex** — `~/.codex/config.toml`:

```toml
[mcp_servers.flow]
command = "/Users/KULLANICI/Projects/flow-mcp/.venv/bin/python"
args = ["-m", "flow_mcp.server"]
```

## Prompt rehberleri

`guides/` altında Google'ın kendi rehberlerinden çıkarılmış üç dosya var:
Veo 3.1, Nano Banana ve Gemini Omni. Her dosyanın başında kaynak URL ve
çekilme tarihi durur.

```
flow_prompt_guide()                              # hangi rehberler var
flow_prompt_guide("Veo 3.1 - Fast")              # formül + bölüm listesi
flow_prompt_guide("Veo 3.1 - Fast", "Audio")     # tek bölüm
```

Model adı Flow'un panelde gösterdiği etiketle eşleşir, ayrıca gevşek
eşleştirme yapar.

**Tasarım kararı:** rehber prompt'a otomatik uygulanmaz. Ajan sessizce
yeniden yazılmış bir prompt gönderirse kullanıcı ne gittiğini göremez ve
sapan çıktının nedenini bulamaz. Bunun yerine rehber ajana *gösterilir*,
prompt'u ajan yazar. Araç isteğe bağlıdır; ajan tutarsız bulursa
kullanmaz.

Maliyet: bölüm başına ~110 token, model özeti ~270. Rehberlerin tamamı
~2300 token olurdu — bu yüzden bölüm bölüm servis ediliyor.

Rehberler bayatlayabilir. Yanıttaki `retrieved` tarihini `flow_model()`
çıktısıyla karşılaştır; rehberde olmayan bir model varsa ona güvenme.

## Ayarlar

| Değişken | Varsayılan |
|---|---|
| `FLOW_CDP_PORT` | `9222` |
| `FLOW_CHROME_PROFILE` | `~/.flow-mcp-profile` |
| `FLOW_DOWNLOAD_DIR` | `~/Downloads/flow` |

### Üretim ayarları

`flow_settings()` argümansız çağrılırsa o an seçili olanları ve tüm
seçenekleri döndürür. Değiştirmek için etiketleri aynen ver:

```
flow_settings(["Video", "9:16", "720p", "8s", "x2"])
flow_settings(["Image", "1:1", "x4"])
```

`Video` / `Image` her zaman ilk sırada olmalı — mod değişince panelin
geri kalanı komple değişiyor.

| Ayar | Seçenekler |
|---|---|
| Mod | `Image`, `Video` |
| En-boy (video) | `16:9`, `9:16` |
| En-boy (görsel) | `16:9`, `4:3`, `1:1`, `3:4`, `9:16` |
| Çözünürlük | `360p`, `720p` (sadece video) |
| Süre | `4s`, `6s`, `8s`, `10s` (sadece video) |
| Çıktı sayısı | `x1` … `x4` |

### Model

```
flow_model()                      # o modda seçilebilecekler
flow_model("Veo 3.1 - Quality")
```

Liste moda göre değişir: video tarafında `Omni 1.1 Flash`,
`Veo 3.1 - Lite / Fast / Quality`; görsel tarafında `Nano Banana Pro`,
`Nano Banana 2`, `Nano Banana 2 Lite`.

### Başlangıç / bitiş karesi

```
flow_settings(["Video", "Frames"])
flow_frame("Start")                       # seçilebilecek varlıkları listeler
flow_frame("Start", "Yeşil bir üçgen")
flow_frame("End", "Orange fox")
flow_generate("üçgen tilkiye dönüşüyor")
```

Frames modunda Flow çözünürlük ve süre seçeneklerini gizliyor — bunlar o
modda ayarlanamaz.

### Ingredients (referans görseller)

```
flow_settings(["Video", "Ingredients"])
flow_ingredient()                                  # ekli olanlar + seçenekler
flow_ingredient(["üçgen", "Orange fox"])           # ekle
flow_ingredient(clear=True)                        # hepsini kaldır
```

Frames'ten farkı: Frames iki uç kareyi belirler, Ingredients ise
prompt'a taşınan referans görsellerdir ve sayıca sınırsızdır.
Ingredients modunda çözünürlük ve süre seçenekleri korunur (Frames'te
kaybolur).

Seçici tek seferde tek varlık tutuyor, bu yüzden araç her birini ayrı
turda ekliyor. Zaten ekli olan bir varlık seçici listesinden düşer —
tekrar eklemek istersen önce `clear=True`.

### Görsel yükleme

```
flow_upload("~/Desktop/karakter.png")
```

Flow'un kendi `Upload` menüsü File System Access API'sini kullanıyor ve
hiçbir CDP alanı onu yakalayamıyor; yanıtlanamayacak bir sistem penceresi
açılırdı. Bu yüzden dosya sayfaya bırakılarak (drag-drop) aynı yükleme
yoluna sokuluyor. Yüklenen görsel `flow_frame` ile kare olarak
kullanılabilir.

### Kaliteli / upscale indirme

```
flow_download_quality(media_id, "1080p")
```

| Seçenek | Not |
|---|---|
| `270p` | Animasyonlu GIF |
| `720p` | Orijinal |
| `1080p` | Upscale, **ücretsiz** |
| `4K` | Upscale, **kredi harcar** — `confirm_paid=True` ister |

Upscale anında render edildiği için dakikalar sürebilir. Bu indirme
imzalı URL üzerinden değil, tarayıcının kendi indirmesi yakalanarak
yapılır — upscale çıktısının CDN adresi yok.

Görsel üretimi Nano Banana Pro ile 0 kredi, video kredi harcıyor —
üretmeden önce panelde yazan kredi maliyetine bak.

## Arayüz değişirse

Üretim yolu DOM'a bağlı olduğu için Flow arayüzü değişince kırılabilir.
`recon/sniff.py` ağ trafiğini yeniden yakalar:

```bash
./.venv/bin/python recon/sniff.py 120
```

Script çalışırken elle bir üretim yap; `recon/capture.json` içinden yeni
RPC kimliklerini `flow_mcp/flow.py` başındaki sabitlere yaz.

## Uyarı

Otomasyon, Google'ın hizmet şartları açısından gri alanda. Kişisel kullanım
içindir; hesap riski sıfır değildir.

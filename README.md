# BAK Mekân Deposu

BAK, görme engelliler için bir alışveriş ve bina içi yönlendirme uygulamasıdır. Kullanıcı bir binanın girişindeki QR kodu okuttuğunda uygulama o binanın düzenini bu depodan indirir ve kullanıcıyı sesli olarak yönlendirir: "Kardiyoloji nerede?", "Doktor Ayşe Yılmaz'ın odası", "süt nerede?" gibi.

Bu depo GitHub Pages ile yayınlanır. Uygulama yalnızca bu depodaki düzenleri indirir; QR kodları adres değil sadece mekân kimliği taşır. Bu sayede biri sahte bir QR assa bile kullanıcı başka bir yere yönlendirilemez.

## İçerik

| Dosya | Ne işe yarar |
|---|---|
| `mekanlar/<kimlik>.json` | Bir binanın düzeni (uygulama bunu indirir) |
| `mekanlar/index.json` | Depodaki mekânların listesi |
| `etiketler.html?mekan=<kimlik>` | O binanın QR etiketlerini düzen dosyasından otomatik üretir, yazdırılır |
| `index.html` | Mekânların listesi ve etiket sayfalarına bağlantılar |

## İlk kurulum (bir kez)

1. GitHub'da **herkese açık** bir depo oluşturun, örneğin `bak-mekanlar`.
2. Bu klasörün içeriğini (`.nojekyll` dahil) deponun köküne yükleyin.
3. Depoda **Settings → Pages → Build and deployment** bölümünde kaynak olarak `main` dalını ve `/ (root)` klasörünü seçin.
4. Birkaç dakika sonra site `https://<kullanıcı-adınız>.github.io/bak-mekanlar/` adresinde yayında olur.
5. Uygulamada `src/servisler/mekanKaynagi.ts` dosyasındaki `MEKAN_KAYNAGI` değerini şu şekilde ayarlayın (sondaki `/` önemli):
   ```ts
   export const MEKAN_KAYNAGI: string | null = 'https://<kullanıcı-adınız>.github.io/bak-mekanlar/mekanlar/';
   ```

## Yeni bir bina eklemek

1. **Binayı noktalara bölün.** Kullanıcının durup yön değiştirebileceği her yer bir noktadır: giriş, danışma, koridor başları, asansör önü, merdiven başı, oda kapıları. Her katta asansör ve merdiven için ayrı nokta olur.
2. **Noktalar arasındaki yolları yürüyerek ölçün.** Her yol için normal adımla kaç adım olduğunu ve iki yöndeki tarifi yazın. "Sağa dön" geliş yönüne göre değiştiği için iki yönün tarifi ayrı yazılır.
3. **Hedefleri ekleyin.** Reyonlar, poliklinikler, ofisler, tuvaletler. Her hedefe insanların söyleyebileceği anahtar kelimeleri ve, varsa, orada çalışan kişilerin adlarını yazın.
4. Dosyayı `mekanlar/<kimlik>.json` olarak kaydedin ve `mekanlar/index.json` listesine ekleyin. Kimlikte yalnızca küçük harf, rakam ve `-` kullanın (ör. `kadikoy-devlet-hastanesi`).
5. `etiketler.html?mekan=<kimlik>` sayfasını açıp etiketleri yazdırın. Mavi çerçeveli GİRİŞ etiketini binanın girişine, diğerlerini ilgili noktalara asın.

## Düzen dosyası

Tam örnekler: [`mekanlar/ornek-hastane.json`](mekanlar/ornek-hastane.json) (iki katlı, merdiven ve asansörlü) ve [`mekanlar/ornek-market.json`](mekanlar/ornek-market.json).

```json
{
  "id": "ornek-hastane",
  "ad": "Örnek Devlet Hastanesi",
  "tur": "hastane",
  "surum": 1,
  "giris": "giris",
  "noktalar": [
    {"id": "giris",      "ad": "Ana giriş",     "kat": 0},
    {"id": "merdiven-0", "ad": "Merdiven başı", "kat": 0},
    {"id": "merdiven-1", "ad": "Merdiven başı", "kat": 1}
  ],
  "baglantilar": [
    {"a": "giris", "b": "merdiven-0", "adim": 12,
     "tarif": "Girişten düz ilerleyin, merdiven sağınızda", "geriTarif": "Merdivenden inince düz ilerleyin"},
    {"a": "merdiven-0", "b": "merdiven-1", "adim": 30, "tur": "merdiven", "basamak": 24,
     "tarif": "Korkuluk sağınızda.", "geriTarif": "Korkuluk solunuzda."}
  ],
  "hedefler": [
    {"ad": "Kardiyoloji Polikliniği", "nokta": "merdiven-1", "oda": "112",
     "tarif": "Kapı solunuzda, oda 112.",
     "anahtarlar": ["kardiyoloji", "kalp"], "kisiler": ["Dr. Ayşe Yılmaz"]}
  ]
}
```

| Alan | Açıklama |
|---|---|
| `surum` | **Düzeni her değiştirdiğinizde 1 artırın.** Uygulama telefondaki kopyadan yüksek sürümü görünce güncellenir; aynı sürümde değişikliği almaz. |
| `kat` | 0 zemin, 1 birinci kat, -1 bodrum. Yazılmazsa 0 sayılır. |
| `tur` (bağlantı) | `yuru` (varsayılan), `rampa`, `kapi`, `merdiven`, `yuruyen-merdiven`, `asansor`. Merdiven ve asansörde yön, kat ve basamak sayısını uygulama kendisi söyler; `tarif` yalnızca ek bilgi içindir (korkuluk tarafı gibi). |
| `adim` | Yürüme mesafesi. Asansörde bekleme süresini de hesaba katarak biraz yüksek yazın; uygulama en kısa yolu bu sayılara göre seçer. |
| `tekYon` | Yalnızca `a` → `b` yönünde yürünebilen yollar için (kasa şeridi, turnike). Bu durumda `geriTarif` gerekmez. |
| `anahtarlar` | Kullanıcının söyleyebileceği kelimeler, küçük harfle. Kelimenin başı yeterlidir: `kardiyoloji` yazınca "kardiyolojiye" de bulunur. 3 harf ve daha kısa kelimeler tam eşleşir. |
| `kisiler` | Unvanla yazılabilir ("Op. Dr. Zeynep Demir"); kullanıcı "Zeynep Demir" ya da sadece "Demir" dese de bulunur. |
| `kasa` | Mağazalarda alışveriş listesi bitince kullanıcının yönlendirileceği nokta. |

## Güvenlik ve doğruluk

- **Bozuk dosya hiç yüklenmez.** Olmayan bir noktaya giden yol ya da tarifi eksik bir yürüme yolu varsa uygulama düzeni reddeder ve kullanıcıya "bir görevliye danışın" der. Görme engelli birini yanlış yere göndermektense hiç yönlendirmemek daha güvenlidir.
- **Değişiklikten sonra kontrol edin.** Uygulama projesinde `npm test` çalıştırıldığında bu klasördeki tüm düzen dosyaları da doğrulanır.
- **Tarifleri yerinde deneyin.** Mümkünse bir görme engelli kullanıcıyla birlikte deneyin. Adım sayıları ve "sağ/sol" ifadeleri en sık hata yapılan yerlerdir.

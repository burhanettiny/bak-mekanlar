# BAK QR oluşturucu

Hastane, market, okul, belediye gibi kurumların görme engelli ziyaretçileri için **kendi BAK giriş QR'ını**
hazırladığı Streamlit uygulaması. Kurum binasını noktalar, yollar ve hedefler olarak tanımlar; sayfa düzeni
doğrular, yazdırılabilir etiket sayfası üretir. Kurum giriş etiketini kapıya, diğerlerini ilgili noktalara asar.
BAK uygulaması giriş QR'ını okuyunca kullanıcıyı sesli olarak yönlendirir.

Bina bilgisi QR'ın içinde taşınır. Sunucu, hesap ya da internet bağlantısı gerekmez.

## Nasıl çalışır

| QR | İçerik | Kim üretir |
|---|---|---|
| Giriş | `BAK:VERI:1:<base45(deflate(düzen JSON))>` | Bu uygulama |
| Nokta | `BAK:NOKTA:<kurum kimliği>:<nokta kimliği>` | Bu uygulama |
| Büyük bina girişi | `BAK:URL:https://…` (düzen dosyası kurumun sitesinde; QR'a sığmayan AVM gibi binalar) | Bu uygulama |
| Doğrulanmış giriş | `BAK:MEKAN:<kimlik>` (düzen BAK deposundan indirilir) | BAK ekibi |

- Kurum kimlikleri `q-` ile başlar ve rastgele bir ek alır (`q-ornek-ilkokulu-3fa2`). Uygulama `q-` ile başlayan
  bir düzeni, BAK deposundaki doğrulanmış bir binanın yerine asla koymaz.
- Uygulama, kurumun kendi hazırladığı binalarda girişte *"Bu bina bilgisini kurum kendisi hazırladı, BAK
  tarafından doğrulanmadı"* der.
- Giriş QR'ı okutulunca düzen telefona kaydedilir; nokta QR'ları ve sonraki ziyaretler internetsiz çalışır.
- Biçim, uygulamadaki [`src/mekan/qrVeri.ts`](../../src/mekan/qrVeri.ts) ile aynıdır. Değiştirirseniz ikisini
  birlikte değiştirin. `__tests__/veri/kurum-qr-hastane.txt` bu uygulamanın ürettiği bir örnektir ve uygulama
  testleri onu çözer.

## Sayfalar ve dosyalar

| Sayfa | Ne yapar |
|---|---|
| Başla | Sihirbaz, hazır şablon ya da kayıtlı düzen dosyası ile başlama |
| Sihirbaz | **Market:** her koridorun solunda ve sağında hangi reyonlar var. **AVM:** her katta mağazalar, bodrum/otopark, yürüyen merdiven. **Koridorlu bina:** her katta koridor boyunca kapılar sırayla. Noktalar, yollar ve sesli tarifler kendiliğinden üretilir |
| Düzenle | Noktalar, yollar ve hedefler tabloları; her şey elle değiştirilebilir |
| Plan | Binanın 2D planı (katlar, merdiven, asansör, adım sayıları) ve tarif önizleme |
| QR ve etiketler | Kontrol, giriş QR'ı, yazdırılabilir etiketler, düzen dosyası |

`bak_mekan.py` (doğrulama, QR, etiketler), `sihirbaz.py` (düzen üretimi) ve `plan.py` (Graphviz planı)
Streamlit'ten bağımsızdır; `durum.py` sayfalar arasındaki oturum verisini tutar.

Sihirbazla oluşturulan binalarda planın yerleşimi bilinir ve düzen dosyasının `plan` alanında saklanır.
Bu alan QR'a girmez; QR yalnızca uygulamanın ihtiyaç duyduğu veriyi taşır.

## Girişte okunan yer listesi ve kısa adlar

Ziyaretçi giriş QR'ını okutunca uygulama binadaki yerleri numaralı okur ("1, Danışma; 2, Vezne…") ve numarasını
ya da adını söylemesini bekler. Liste 10'ar yer olarak okunur; ziyaretçi "devam" deyince sonraki 10 gelir.

Uzun adlar listeyi uzatır. Her hedefe isteğe bağlı bir **kısa ad** verilebilir ("Kardiyoloji Polikliniği" →
"Kardiyoloji"); listede o okunur ve ziyaretçi onu söyleyince de bulunur. **Kısa adları öner** düğmesi birden çok
yerde tekrarlanan sözcükleri ("Polikliniği", "Müdürlüğü") atarak öneri doldurur. **Kontrol ve QR** sekmesi
listenin nasıl ve yaklaşık kaç saniyede okunacağını gösterir.

## Şablonlar

Market, AVM, devlet hastanesi, şehir hastanesi ana caddesi, okul ve belediye binası şablonları var.
**Gebze Center AVM** şablonu AVM'nin sitesindeki 145 mağazanın gerçek adı, kategorisi ve katıyla kuruldu; koridordaki
sıra ve sağ/sol sitede yazmadığı için örnek dizildi. QR'a sığmadığından bina bilgisini kurumun sitesinde tutma yolunu
gösterir (`"buyuk": true`).

**Kat listesini yapıştırma:** Bina ve AVM sihirbazında kurum, sitesindeki "Kat Planı" metnini yapıştırır ("Zemin Kat:
Danışma, Vezne", "-1. Kat", alt alta maddeler…); katlar ve birimler dolar. Sıra, sağ/sol ve adım sahada düzeltilir.


`sablonlar/` klasöründeki her JSON bir başlangıç şablonudur (`sablonAdi` alanı listede görünen addır):
market, iki katlı hastane, okul, belediye hizmet binası. Yeni şablon eklemek için aynı biçimde bir dosya ekleyin;
testler tüm şablonların geçerli olduğunu ve QR'ının okunabilir boyutta kaldığını kontrol eder.

## Yerelde çalıştırma

```bash
cd mekan-deposu/olusturucu
python -m venv .venv
.venv/Scripts/activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
streamlit run streamlit_app.py
pytest
```

## Streamlit Community Cloud'da yayınlama

1. Bu klasör `bak-mekanlar` deposunda olduğu için önce depoyu GitHub'a gönderin (GitHub Desktop → *Commit* → *Push*).
2. <https://share.streamlit.io> adresinde GitHub hesabınızla giriş yapın.
3. **Create app → Deploy a public app from GitHub** seçin.
4. Repository: `burhanettiny/bak-mekanlar`, Branch: `main`, Main file path: `olusturucu/streamlit_app.py`.
5. İsterseniz *App URL* kısmına kısa bir ad verin, ör. `bak-qr`. **Deploy**'a basın.

Birkaç dakika sonra uygulama `https://bak-qr.streamlit.app` gibi bir adreste yayında olur. Depoya her push'ta
kendiliğinden güncellenir.

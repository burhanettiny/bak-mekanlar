import json

import streamlit as st

import bak_mekan as bm
import durum
import harita as hr

durum.adim_cubugu(0)
st.title("BAK QR oluşturucu")
st.markdown(
    "Binanızın girişine asacağınız **tek bir QR kodu** ile görme engelli ziyaretçileriniz BAK uygulamasıyla "
    "danışmayı, polikliniği, sınıfı ya da reyonu **sesli, adım adım** bulur. Ücretsizdir; hesap ya da sunucu "
    "gerekmez. Yaklaşık 15 dakika sürer.")

st.subheader("Ne için QR hazırlıyorsunuz?")

# Her kartta iki yol: boş başla ya da o türün hazır örneğiyle dene (örnekler ayrı bir kutuda değil, kendi kartında)
ornekler: dict[str, list[str]] = {}
SABLONLAR = bm.sablonlar()
for ad, veri in SABLONLAR.items():
    ornekler.setdefault(bm.sablon_grubu(ad, veri), []).append(ad)


MEVCUT = durum.guncel_mekan()
YARIM_IS = bool(MEVCUT["ad"] and MEVCUT["hedefler"])


def yap(eylem: tuple) -> None:
    """("bos", tur), ("ornek", şablon adı) ya da ("osm", haritadan kurulan düzen). Boş başlangıçta önceki iş
    temizlenir ("yarım kalan" yanıltmasın)."""
    if eylem[0] == "osm":
        durum.mekani_yukle(eylem[1], yeni_kimlik=True)
        st.session_state.yeni_olusturuldu = True
        st.session_state.osm_kuruldu = True
        st.session_state.pop("ornek_adi", None)
        st.session_state.cizim_gorunum = st.session_state.cizim_secili = None
        st.switch_page("app_pages/cizim_sayfasi.py")
    if eylem[0] == "ornek":
        durum.mekani_yukle(SABLONLAR[eylem[1]], yeni_kimlik=True)
        st.session_state.yeni_olusturuldu = True
        # Örnekteki ad ("Örnek Devlet Hastanesi") değiştirilmeden basılmasın diye hatırlanır
        st.session_state.ornek_adi = SABLONLAR[eylem[1]].get("ad")
        st.switch_page("app_pages/cizim_sayfasi.py")
    durum.mekani_yukle(durum.BOS_MEKAN, yeni_kimlik=True)
    st.session_state.pop("ornek_adi", None)
    if eylem[1]:
        st.session_state.sihirbaz_turu = eylem[1]
        st.switch_page("app_pages/sihirbaz.py")
    st.switch_page("app_pages/cizim_sayfasi.py")


def _vazgec() -> None:
    st.session_state.pop("bekleyen_eylem", None)


# Bekleyen eylem oturumda tutulur ve pencere her çalıştırmada yeniden açılır: penceredeki düğme hangi yolla
# (pencerenin kendi yeniden çalışması ya da sayfanın tamamı) işlenirse işlensin kaybolmaz. Kapatınca vazgeçilir.
@st.dialog("Yeni bir çalışma başlasın mı?", on_dismiss=_vazgec)
def onay(eylem: tuple) -> None:
    st.markdown(f"Üzerinde çalıştığınız **{MEVCUT['ad']}** kapanacak. Sonra devam etmek isterseniz önce kaydedin; "
                "dosyayı bu sayfadaki *Daha önce kaydettiğim dosyayı açacağım* bölümünden açarsınız.")
    st.download_button("Önce kaydet (.json)", durum.dosya_icerigi(MEVCUT), file_name=f"{MEVCUT['id']}.json",
                       mime="application/json", icon=":material/save:", width="stretch")
    with st.container(horizontal=True):
        if st.button("Vazgeç", width="stretch"):
            _vazgec()
            st.rerun()
        if st.button("Yeni başla", type="primary", width="stretch"):
            _vazgec()
            yap(eylem)


def sec(eylem: tuple) -> None:
    # Yarım kalan iş uyarısız silinmesin
    if YARIM_IS:
        st.session_state.bekleyen_eylem = eylem
    else:
        yap(eylem)


def kart(grup: str, ikon: str, baslik: str, metin: str, tur: str | None) -> None:
    with st.container(border=True, height="stretch"):
        st.markdown(f"#### {ikon} {baslik}")
        st.caption(metin)
        if st.button("Boş başla", type="primary", width="stretch", key=f"bos-{grup}", icon=":material/arrow_forward:"):
            sec(("bos", tur))
        liste = ornekler.get(grup, [])
        if len(liste) == 1:
            if st.button("Örnekle dene", width="stretch", key=f"ornek-{grup}", icon=":material/visibility:",
                         help=liste[0]):
                sec(("ornek", liste[0]))
        elif liste:
            with st.popover("Örnekle dene", width="stretch", icon=":material/visibility:"):
                for i, ad in enumerate(liste):
                    if st.button(ad, key=f"ornek-{grup}-{i}", width="stretch"):
                        sec(("ornek", ad))


with st.container(horizontal=True):
    kart("bina", ":material/local_hospital:", "Hastane, okul, kurum",
         "Katları ve odaları liste olarak yazarsınız; koridor, merdiven ve asansör kendiliğinden çizilir.",
         "Koridorlu bina")
    kart("market", ":material/shopping_cart:", "Market",
         "Her koridorda solda ve sağda hangi reyonlar var, onu yazarsınız.", "Market")
    kart("avm", ":material/storefront:", "AVM",
         "Katları ve mağazaları liste olarak yazarsınız; yürüyen merdiven ve asansör eklenir.", "AVM")
    kart("kampus", ":material/apartment:", "Kampüs, birden çok bina",
         "Binaları ekranda kutu kutu ekler, sürükleyerek yerleştirirsiniz; her binanın içine odalarını yazarsınız.",
         None)

# ── Haritadan kur: OpenStreetMap'te alanı kayıtlı kampüs ve büyük kurumlar ──
with st.container(border=True):
    st.markdown("#### :material/travel_explore: Kampüsünüzü haritadan kurun")
    st.caption("Üniversite, şehir hastanesi ya da birden çok binalı bir kurumun alanı OpenStreetMap'te kayıtlıysa "
               "adını yazın: binalar ve yürüme yolları haritadan alınır, yerler, mesafeler ve sağa / sola tarifleri "
               "kendiliğinden hazırlanır. Sonra haritanın üstünde sürükleyerek düzeltir, binaların içini eklersiniz.")
    kurulan = hr.haritadan_kur_formu("basla")
    if kurulan:
        sec(("osm", kurulan))

if YARIM_IS:
    with st.container(border=True, horizontal=True, vertical_alignment="center"):
        st.markdown(f":material/history: Yarım kalan: **{MEVCUT['ad']}** · {len(MEVCUT['hedefler'])} yer")
        if st.button("Kaldığım yerden devam et", icon=":material/arrow_forward:"):
            st.switch_page("app_pages/cizim_sayfasi.py")

with st.expander("Daha önce kaydettiğim dosyayı açacağım", icon=":material/upload_file:"):
    yuklenen = st.file_uploader("Düzen dosyası (.json)", type="json")
    if yuklenen and st.button("Dosyayı aç", icon=":material/open_in_new:"):
        try:
            durum.mekani_yukle(json.load(yuklenen), yeni_kimlik=False)
            st.session_state.pop("ornek_adi", None)
            st.switch_page("app_pages/cizim_sayfasi.py")
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
            st.error("Bu dosya okunamadı. 4. adımda indirilen düzen dosyasını seçin.")
    st.caption("Aynı bina olarak açılır; yeni basılan QR'ı okutan telefonlar güncel bilgiyi alır.")

with st.expander("Görme engelli ziyaretçi ne yaşar?", icon=":material/accessibility_new:"):
    st.markdown(
        "1. Telefonundaki BAK uygulamasıyla girişteki QR'ı okutur.\n"
        "2. Uygulama binadaki yerleri numaralı okur: *\"1, Danışma; 2, Vezne; 3, Kardiyoloji…\"*\n"
        "3. Ziyaretçi numarayı ya da adı söyler. Uygulama adımlarını sayarak yol tarif eder; dönüşleri, "
        "merdiveni ve asansörü zamanında söyler.\n"
        "4. Yoldaki küçük etiketler konumu düzeltir; ziyaretçi kaybolursa en yakın etiketi okutur.")

if YARIM_IS and st.session_state.get("bekleyen_eylem"):
    onay(tuple(st.session_state.bekleyen_eylem))

import json

import streamlit as st

import bak_mekan as bm
import durum

st.title("BAK QR oluşturucu")
st.markdown(
    "Binanızın girişine asacağınız **tek bir QR kodu** ile görme engelli ziyaretçileriniz BAK uygulamasıyla "
    "danışmayı, polikliniği, sınıfı ya da reyonu **sesli, adım adım** bulur. Ücretsizdir; hesap ya da sunucu "
    "gerekmez.")
st.caption("Adımlar: **yerleri yazın** → **kontrol edin** → **yazdırıp asın**. Yaklaşık 15 dakika.")

st.subheader("Ne için QR hazırlıyorsunuz?")


def secenek(ikon: str, baslik: str, metin: str, hedef: str, tur: str | None = None) -> None:
    with st.container(border=True, height="stretch"):
        st.markdown(f"#### {ikon} {baslik}")
        st.caption(metin)
        if st.button("Başla", type="primary", width="stretch", key=f"basla-{baslik}", icon=":material/arrow_forward:"):
            if tur:
                st.session_state.sihirbaz_turu = tur
            else:
                durum.mekani_yukle(durum.BOS_MEKAN, yeni_kimlik=True)
            st.switch_page(hedef)


with st.container(horizontal=True):
    secenek(":material/local_hospital:", "Hastane, okul, kurum", "Katları ve odaları liste olarak yazarsınız; "
            "koridor, merdiven ve asansör kendiliğinden çizilir.", "app_pages/sihirbaz.py", "Koridorlu bina")
    secenek(":material/shopping_cart:", "Market", "Her koridorda solda ve sağda hangi reyonlar var, onu yazarsınız.",
            "app_pages/sihirbaz.py", "Market")
    secenek(":material/storefront:", "AVM", "Katları ve mağazaları liste olarak yazarsınız; yürüyen merdiven ve "
            "asansör eklenir.", "app_pages/sihirbaz.py", "AVM")
    secenek(":material/apartment:", "Kampüs, birden çok bina", "Binaları ekranda kutu kutu ekler, sürükleyerek "
            "yerleştirirsiniz; her binanın içine odalarını yazarsınız.", "app_pages/cizim_sayfasi.py")

with st.container(horizontal=True):
    with st.expander("Hazır bir örnekle deneyin", icon=":material/dashboard_customize:"):
        sablonlar = bm.sablonlar()
        secilen = st.selectbox("Örnek", list(sablonlar))
        if st.button("Örneği aç", icon=":material/open_in_new:"):
            durum.mekani_yukle(sablonlar[secilen], yeni_kimlik=True)
            st.switch_page("app_pages/cizim_sayfasi.py")
    with st.expander("Daha önce kaydettiğim dosyayı açacağım", icon=":material/upload_file:"):
        yuklenen = st.file_uploader("Düzen dosyası (.json)", type="json")
        if yuklenen and st.button("Dosyayı aç", icon=":material/open_in_new:"):
            try:
                durum.mekani_yukle(json.load(yuklenen), yeni_kimlik=False)
                st.switch_page("app_pages/cizim_sayfasi.py")
            except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
                st.error("Bu dosya okunamadı. 4. adımda indirilen düzen dosyasını seçin.")
        st.caption("Aynı bina olarak açılır; yeni basılan QR'ı okutan telefonlar güncel bilgiyi alır.")

mekan = durum.guncel_mekan()
if mekan["ad"] and mekan["hedefler"]:
    with st.container(border=True):
        st.markdown(f"**Üzerinde çalıştığınız:** {mekan['ad']} · ziyaretçiye okunacak {len(mekan['hedefler'])} yer")
        with st.container(horizontal=True):
            st.page_link("app_pages/cizim_sayfasi.py", label="Kontrol ve çizime dön", icon=":material/draw:")
            st.page_link("app_pages/yazdir.py", label="Yazdır", icon=":material/print:")

with st.expander("Görme engelli ziyaretçi ne yaşar?", icon=":material/accessibility_new:"):
    st.markdown(
        "1. Telefonundaki BAK uygulamasıyla girişteki QR'ı okutur.\n"
        "2. Uygulama binadaki yerleri numaralı okur: *\"1, Danışma; 2, Vezne; 3, Kardiyoloji…\"*\n"
        "3. Ziyaretçi numarayı ya da adı söyler. Uygulama adımlarını sayarak yol tarif eder; dönüşleri, "
        "merdiveni ve asansörü zamanında söyler.\n"
        "4. Yoldaki küçük etiketler konumu düzeltir; ziyaretçi kaybolursa en yakın etiketi okutur.")

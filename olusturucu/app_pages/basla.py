import json

import streamlit as st

import bak_mekan as bm
import durum

st.title("BAK QR oluşturucu")
st.markdown(
    "Binanızın girişine asacağınız **tek bir QR kodu** ile görme engelli ziyaretçileriniz BAK uygulamasıyla "
    "danışmayı, polikliniği, sınıfı ya da reyonu **sesli, adım adım** bulur. Bina bilgisi QR'ın içindedir; "
    "sunucu, hesap, internet ya da ücret gerekmez.")

with st.container(horizontal=True):
    for ikon, baslik, metin in (
        (":material/edit_square:", "1. Tarif edin", "Sihirbazla koridorları ve yerleri yazın"),
        (":material/map:", "2. Kontrol edin", "Planı ve tarifleri gözden geçirin"),
        (":material/print:", "3. Yazdırın", "Giriş QR'ı ve nokta etiketleri"),
        (":material/check_circle:", "4. Asın", "Kapı yanına, 120 cm yüksekliğe"),
    ):
        with st.container(border=True):
            st.markdown(f"#### {ikon} {baslik}")
            st.caption(metin)

st.subheader("Nereden başlamak istersiniz?")
market, bina, sablon, dosya = st.columns(4)

with market, st.container(border=True, height="stretch"):
    st.markdown("#### :material/shopping_cart: Market")
    st.markdown("Koridor koridor, **sağda ve solda** hangi reyonlar var? Gerisini sihirbaz hazırlar.")
    if st.button("Market sihirbazı", type="primary", width="stretch", key="market-git"):
        st.session_state.sihirbaz_turu = "Market"
        st.switch_page("app_pages/sihirbaz.py")

with bina, st.container(border=True, height="stretch"):
    st.markdown("#### :material/local_hospital: Hastane, okul, kurum")
    st.markdown("Her katta koridor boyunca **sağdaki ve soldaki** odaları sırayla yazın; merdiven ve asansör eklenir.")
    if st.button("Bina sihirbazı", type="primary", width="stretch", key="bina-git"):
        st.session_state.sihirbaz_turu = "Koridorlu bina"
        st.switch_page("app_pages/sihirbaz.py")

with sablon, st.container(border=True, height="stretch"):
    st.markdown("#### :material/dashboard_customize: Hazır şablon")
    sablonlar = bm.sablonlar()
    secilen = st.selectbox("Şablon", list(sablonlar), label_visibility="collapsed")
    if st.button("Şablonu aç", width="stretch"):
        durum.mekani_yukle(sablonlar[secilen], yeni_kimlik=True)
        st.switch_page("app_pages/plan_sayfasi.py")

with dosya, st.container(border=True, height="stretch"):
    st.markdown("#### :material/upload_file: Kayıtlı düzenim")
    yuklenen = st.file_uploader("Düzen dosyası (.json)", type="json", label_visibility="collapsed")
    if yuklenen and st.button("Dosyayı aç", width="stretch"):
        try:
            durum.mekani_yukle(json.load(yuklenen), yeni_kimlik=False)
            st.switch_page("app_pages/plan_sayfasi.py")
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
            st.error("Bu dosya okunamadı. Bu sayfadan indirilen bir düzen dosyası seçin.")
    st.caption("Sürüm numarası bir artırılır; yeni QR'ı okutan telefonlar güncel bilgiyi alır.")

mekan = durum.guncel_mekan()
if mekan["ad"]:
    st.subheader("Üzerinde çalıştığınız bina")
    with st.container(horizontal=True):
        st.metric("Bina", mekan["ad"], border=True)
        st.metric("Nokta", len(mekan["noktalar"]), border=True)
        st.metric("Yol", len(mekan["baglantilar"]), border=True)
        st.metric("Hedef", len(mekan["hedefler"]), border=True)
    st.page_link("app_pages/plan_sayfasi.py", label="Planı gör", icon=":material/map:")

with st.expander("Görme engelli ziyaretçi ne yaşar?", icon=":material/accessibility_new:"):
    st.markdown(
        "1. Telefonundaki BAK uygulamasıyla girişteki QR'ı okutur.\n"
        "2. Uygulama binadaki yerleri numaralı okur: *\"1, Danışma; 2, Vezne; 3, Kardiyoloji…\"*\n"
        "3. Ziyaretçi numarayı ya da adı söyler. Uygulama adımlarını sayarak yol tarif eder; dönüşleri, "
        "merdiveni ve asansörü zamanında söyler.\n"
        "4. Yoldaki nokta etiketleri konumu düzeltir; ziyaretçi kaybolursa en yakın etiketi okutur.")

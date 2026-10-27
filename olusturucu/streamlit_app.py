"""BAK QR oluşturucu: hastane, market, okul, kamu kurumu gibi kuruluşlar binalarını tarif edip görme engelli
ziyaretçiler için BAK giriş QR'ını ve nokta etiketlerini kendileri üretir.

Sayfalar app_pages/ altında: Başla → Sihirbaz → Düzenle → Plan → QR ve etiketler.
Çalıştırma:  streamlit run streamlit_app.py
"""

import streamlit as st

import durum

st.set_page_config(page_title="BAK QR oluşturucu", page_icon=":material/qr_code_2:", layout="wide")
st.logo("logo.png", size="large", icon_image="logo.png")

durum.baslat()

DUZENLE = st.Page("app_pages/duzenle.py", title="Düzenle", icon=":material/edit_note:")
sayfa = st.navigation([
    st.Page("app_pages/basla.py", title="Başla", icon=":material/home:", default=True),
    st.Page("app_pages/sihirbaz.py", title="Sihirbaz", icon=":material/auto_fix_high:"),
    DUZENLE,
    st.Page("app_pages/plan_sayfasi.py", title="Plan", icon=":material/map:"),
    st.Page("app_pages/yazdir.py", title="QR ve etiketler", icon=":material/qr_code_2:"),
], position="top")

# Düzenle sayfasından çıkınca tablolardaki değişiklikler kalıcı hale getirilir
if sayfa.url_path != DUZENLE.url_path:
    durum.duzenlemeleri_isle()

sayfa.run()

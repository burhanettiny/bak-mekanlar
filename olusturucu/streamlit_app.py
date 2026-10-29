"""BAK QR oluşturucu: hastane, market, okul, kamu kurumu gibi kuruluşlar binalarını tarif edip görme engelli
ziyaretçiler için BAK giriş QR'ını ve nokta etiketlerini kendileri üretir.

Sayfalar app_pages/ altında: Başla → Sihirbaz → Düzenle → Plan → QR ve etiketler.
Çalıştırma:  streamlit run streamlit_app.py
"""

import importlib
import os
import sys

import streamlit as st

# Streamlit Cloud yeni bir push'ta sayfa dosyalarını yeniden çalıştırır ama önceden içe aktarılmış yardımcı
# modülleri bellekte eski haliyle tutar (yeni sayfa eski modülde olmayan bir fonksiyonu çağırıp çöker).
# Dosyası değişen yardımcı modül burada yeniden yüklenir.
for _ad in ("bak_mekan", "plan", "sihirbaz", "cizim", "durum"):
    _modul = sys.modules.get(_ad)
    _dosya = getattr(_modul, "__file__", None)
    if _dosya and os.path.exists(_dosya) and os.path.getmtime(_dosya) != getattr(_modul, "_yukleme_zamani", None):
        _modul = importlib.reload(_modul)
    if _modul is not None and _dosya:
        _modul._yukleme_zamani = os.path.getmtime(_dosya)

import durum  # noqa: E402

st.set_page_config(page_title="BAK QR oluşturucu", page_icon=":material/qr_code_2:", layout="wide")
st.logo("logo.png", size="large", icon_image="logo.png")

durum.baslat()

DUZENLE = st.Page("app_pages/duzenle.py", title="Düzenle", icon=":material/edit_note:")
sayfa = st.navigation([
    st.Page("app_pages/basla.py", title="Başla", icon=":material/home:", default=True),
    st.Page("app_pages/sihirbaz.py", title="Sihirbaz", icon=":material/auto_fix_high:"),
    st.Page("app_pages/cizim_sayfasi.py", title="Çizim", icon=":material/draw:"),
    DUZENLE,
    st.Page("app_pages/plan_sayfasi.py", title="Plan", icon=":material/map:"),
    st.Page("app_pages/yazdir.py", title="QR ve etiketler", icon=":material/qr_code_2:"),
], position="top")

# Düzenle sayfasından çıkınca tablolardaki değişiklikler kalıcı hale getirilir
if sayfa.url_path != DUZENLE.url_path:
    durum.duzenlemeleri_isle()

sayfa.run()

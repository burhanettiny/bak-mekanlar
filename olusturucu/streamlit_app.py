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
for _ad in ("bak_mekan", "plan", "sihirbaz", "cizim", "durum", "harita", "osm_kampus"):
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

# Üst menü gizlidir: kurum görevlisi her sayfanın tepesindeki adım çubuğuyla (durum.adim_cubugu) ve sayfa sonundaki
# "İleri" düğmesiyle tek bir yolda ilerler. Tablolar ve teknik plan, 3. adımın altındaki "Gelişmiş" bağlantılarındadır.
DUZENLE = st.Page("app_pages/duzenle.py", title="Tablolar", icon=":material/table_view:")
sayfa = st.navigation({
    "": [
        st.Page("app_pages/basla.py", title="1. Başla", icon=":material/home:", default=True),
        st.Page("app_pages/sihirbaz.py", title="2. Yerleri yazın", icon=":material/edit_note:"),
        st.Page("app_pages/cizim_sayfasi.py", title="3. Kontrol ve çizim", icon=":material/draw:"),
        st.Page("app_pages/yazdir.py", title="4. Yazdır", icon=":material/print:"),
    ],
    "Gelişmiş": [
        DUZENLE,
        st.Page("app_pages/plan_sayfasi.py", title="Teknik plan", icon=":material/map:"),
    ],
}, position="hidden")

# Düzenle sayfasından çıkınca tablolardaki değişiklikler kalıcı hale getirilir
if sayfa.url_path != DUZENLE.url_path:
    durum.duzenlemeleri_isle()

sayfa.run()

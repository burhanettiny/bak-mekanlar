import streamlit as st

import bak_mekan as bm
import durum
import plan

mekan = durum.guncel_mekan()
hatalar, uyarilar = bm.dogrula(mekan)

st.page_link("app_pages/cizim_sayfasi.py", label="Kontrol et adımına dön", icon=":material/arrow_back:")
st.title(mekan["ad"] or "Bina planı")

with st.container(horizontal=True):
    katlar = {n.get("kat", 0) or 0 for n in mekan["noktalar"]}
    st.metric("Kat", len(katlar), border=True)
    st.metric("Nokta (etiket)", len(mekan["noktalar"]), border=True)
    st.metric("Yol", len(mekan["baglantilar"]), border=True)
    st.metric("Ziyaretçinin gidebileceği yer", len(mekan["hedefler"]), border=True)
    st.metric("Durum", "Hazır" if not hatalar else f"{len(hatalar)} eksik", border=True)

if not mekan["noktalar"] or not mekan["baglantilar"]:
    st.info("Plan için en az iki nokta ve bir yol gerekir. Sihirbazla başlayabilirsiniz.",
            icon=":material/info:")
    st.page_link("app_pages/sihirbaz.py", label="Sihirbaza git", icon=":material/auto_fix_high:")
    st.stop()

with st.container(border=True):
    st.graphviz_chart(plan.plan_dot(mekan, st.session_state.get("plan")), width="stretch",
                      alt=f"{mekan['ad']} binasının noktaları ve aralarındaki yollar")
    st.caption(":blue-background[Lacivert]: giriş QR'ı · :orange-background[Sarı]: ziyaretçinin gidebileceği yer · "
               "çizgi üstünde adım sayısı · :orange[turuncu kesikli]: merdiven · :violet[mor kesikli]: asansör · "
               "ok: tek yönlü yol")

with st.container(border=True):
    st.subheader(":material/hearing: Tarifi deneyin")
    if mekan["hedefler"] and mekan["giris"] in {n["id"] for n in mekan["noktalar"]}:
        hedef_adi = st.selectbox("Girişten gidilecek yer", [h["ad"] for h in mekan["hedefler"]], key="onizleme")
        st.markdown("\n".join(f"1. {adim}" for adim in bm.rota_onizleme(mekan, hedef_adi)))
        st.caption("Uygulama bu yolu sesli ve adım adım okur. Yanlış bir şey varsa Düzenle sayfasından düzeltin.")
    else:
        st.caption("Tarif önizlemesi için en az bir hedef ve geçerli bir giriş noktası gerekir.")

with st.container(horizontal=True):
    st.page_link("app_pages/duzenle.py", label="Düzenle", icon=":material/edit_note:")
    st.page_link("app_pages/yazdir.py", label="QR ve etiketler", icon=":material/qr_code_2:")

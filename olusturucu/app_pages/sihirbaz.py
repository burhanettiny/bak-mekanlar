import pandas as pd
import streamlit as st

import durum
import sihirbaz

st.title("Sihirbaz")
st.caption("Binanızı tarif edin; noktalar, yollar ve sesli tarifler kendiliğinden hazırlanır. "
           "Sonra Düzenle sayfasında her şeyi değiştirebilirsiniz.")

tur = st.segmented_control("Bina türü", ["Market", "Koridorlu bina"], required=True,
                           default=st.session_state.get("sihirbaz_turu", "Market"), key="sihirbaz_turu")

ORNEK_KORIDORLAR = pd.DataFrame([
    {"sol": "Meyve, Sebze", "sag": "Ekmek, Unlu mamuller"},
    {"sol": "Süt, Peynir, Yoğurt", "sag": "Kahvaltılık, Zeytin"},
    {"sol": "Et, Tavuk, Balık", "sag": "Dondurulmuş gıda"},
    {"sol": "Deterjan, Temizlik", "sag": "Şampuan, Kişisel bakım"},
])
ORNEK_KAT = pd.DataFrame([
    {"taraf": "sağ", "ad": "Danışma", "adim": 4, "oda": "", "kisiler": "", "anahtarlar": "bilgi, randevu"},
    {"taraf": "sol", "ad": "Vezne", "adim": 6, "oda": "", "kisiler": "", "anahtarlar": "ödeme"},
    {"taraf": "sağ", "ad": "Tuvalet", "adim": 5, "oda": "", "kisiler": "", "anahtarlar": "wc, lavabo"},
])
ORNEK_UST_KAT = pd.DataFrame([
    {"taraf": "sol", "ad": "Kardiyoloji Polikliniği", "adim": 6, "oda": "112", "kisiler": "Dr. Ayşe Yılmaz",
     "anahtarlar": "kalp"},
    {"taraf": "sağ", "ad": "Dahiliye Polikliniği", "adim": 6, "oda": "118", "kisiler": "", "anahtarlar": ""},
])


def olustur(mekan: dict, plan: dict) -> None:
    durum.mekani_yukle(mekan, yeni_kimlik=True, plan=plan)
    st.switch_page("app_pages/plan_sayfasi.py")


if tur == "Market":
    with st.container(border=True):
        ad = st.text_input("Marketin adı", placeholder="ör. Kardeşler Market, Çarşı şubesi")
        siralama = st.segmented_control(
            "Girişten bakınca koridorlar", ["sag", "sol"], required=True, default="sag",
            format_func={"sag": "Sağa doğru sıralı", "sol": "Sola doğru sıralı"}.get,
            help="Girişten içeri girip ön koridora gelince 1. koridordan itibaren koridorlar hangi yönde?")
    st.markdown("##### :material/view_column: Koridorlar")
    st.caption("Her satır bir koridor (girişe en yakın olan ilk satır). Koridora girince **solunuzda** ve "
               "**sağınızda** olan reyonları, koridorun başından sonuna doğru virgülle yazın.")
    koridorlar = st.data_editor(
        ORNEK_KORIDORLAR, num_rows="dynamic", hide_index=True, width="stretch", key="sihirbaz_koridorlar",
        alt="Koridorlardaki reyonlar",
        column_config={"sol": st.column_config.TextColumn("Solda (baştan sona)", width="large"),
                       "sag": st.column_config.TextColumn("Sağda (baştan sona)", width="large")})
    with st.expander("Ölçüler (adım)", icon=":material/straighten:"):
        with st.container(horizontal=True):
            giris_adim = st.number_input("Girişten ön koridora", 1, 100, 8)
            arasi = st.number_input("İki koridor başı arası", 1, 50, 6)
            kasa_adim = st.number_input("Son koridordan kasalara", 1, 100, 10)
        st.caption("Normal adımla yürüyerek sayın. Uygulama kullanıcının adım uzunluğunu kendisi de ayarlar.")
    satirlar = [r for r in koridorlar.fillna("").to_dict("records") if str(r["sol"]).strip() or str(r["sag"]).strip()]
    if st.button("Market düzenini oluştur", type="primary", icon=":material/auto_fix_high:",
                 disabled=not (ad.strip() and satirlar)):
        olustur(*sihirbaz.market_olustur(ad.strip(), satirlar, giris_adim=giris_adim, koridor_arasi_adim=arasi,
                                         kasa_adim=kasa_adim, siralama=siralama))
    if not ad.strip():
        st.caption("Devam etmek için marketin adını yazın.")

else:
    with st.container(border=True):
        ad = st.text_input("Binanın adı", placeholder="ör. Kadıköy Devlet Hastanesi, Atatürk İlkokulu")
        with st.container(horizontal=True, vertical_alignment="bottom"):
            bina_turu = st.segmented_control("Tür", ["hastane", "kurum"], required=True, default="hastane",
                                             format_func={"hastane": "Hastane / sağlık",
                                                          "kurum": "Okul / kamu / ofis"}.get)
            kat_sayisi = st.number_input("Kat sayısı", 1, 8, 2)
        with st.container(horizontal=True, vertical_alignment="bottom"):
            dikey = st.segmented_control("Katlar arası", ["ikisi", "asansor", "merdiven"], required=True,
                                         default="ikisi", disabled=kat_sayisi == 1,
                                         format_func={"ikisi": "Merdiven ve asansör", "asansor": "Yalnız asansör",
                                                      "merdiven": "Yalnız merdiven"}.get)
            giris_adim = st.number_input("Girişten koridor başına (adım)", 1, 100, 8)
            basamak = st.number_input("Merdiven basamak sayısı (kat başına)", 1, 80, 22,
                                      disabled=kat_sayisi == 1 or dikey == "asansor")
    st.markdown("##### :material/door_front: Katlar")
    st.caption("Koridorun başından sonuna doğru yürürken karşılaştığınız kapıları **sırayla** yazın. "
               "**Adım**: bir önceki kapıdan (ilk kapı için koridor başından) bu kapıya kaç adım.")
    sekmeler = st.tabs(["Zemin kat" if k == 0 else f"{k}. kat" for k in range(kat_sayisi)])
    katlar = []
    for k, sekme in enumerate(sekmeler):
        with sekme:
            tablo = st.data_editor(
                ORNEK_KAT if k == 0 else ORNEK_UST_KAT if k == 1 else ORNEK_KAT.iloc[0:0],
                num_rows="dynamic", hide_index=True, width="stretch", key=f"sihirbaz_kat_{k}",
                alt=f"{k}. kattaki kapılar",
                column_config={
                    "taraf": st.column_config.SelectboxColumn("Taraf", options=["sol", "sağ"], default="sol",
                                                              required=True),
                    "ad": st.column_config.TextColumn("Ad", required=True, width="medium"),
                    "adim": st.column_config.NumberColumn("Adım", min_value=1, step=1, default=5, format="%d"),
                    "oda": st.column_config.TextColumn("Oda no"),
                    "kisiler": st.column_config.TextColumn("Çalışanlar", help="Virgülle, ör. 'Dr. Ayşe Yılmaz'"),
                    "anahtarlar": st.column_config.TextColumn("Diğer söyleyişler", help="ör. 'kalp' (kardiyoloji için)"),
                })
            katlar.append([{**r, "taraf": "sag" if r["taraf"] == "sağ" else "sol"}
                           for r in tablo.fillna("").to_dict("records") if str(r["ad"]).strip()])
    if st.button("Bina düzenini oluştur", type="primary", icon=":material/auto_fix_high:",
                 disabled=not (ad.strip() and any(katlar))):
        olustur(*sihirbaz.bina_olustur(ad.strip(), bina_turu, katlar, giris_adim=giris_adim, dikey=dikey,
                                       basamak=basamak))
    if not ad.strip():
        st.caption("Devam etmek için binanın adını yazın.")

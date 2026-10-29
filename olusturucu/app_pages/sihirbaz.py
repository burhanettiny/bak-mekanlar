import pandas as pd
import streamlit as st

import durum
import sihirbaz

st.title("Yerleri yazın")
st.caption("Binanızda ziyaretçinin gidebileceği yerleri yazın; yol tarifleri kendiliğinden hazırlanır. "
           "Sonraki adımda çizimde kontrol edip düzeltirsiniz.")

tur = st.segmented_control("Ne için?", ["Koridorlu bina", "Market", "AVM"], required=True,
                           default=st.session_state.get("sihirbaz_turu", "Koridorlu bina"), key="sihirbaz_turu",
                           format_func=lambda t: "Hastane, okul, kurum" if t == "Koridorlu bina" else t)

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

# AVM örneği: kat numarası → mağazalar (koridor boyunca sırayla)
def _avm_kat(*satirlar):
    return pd.DataFrame([{"taraf": t, "ad": a, "adim": adim, "oda": "", "kisiler": "", "anahtarlar": k}
                         for t, a, adim, k in satirlar])


ORNEK_AVM = {
    -1: _avm_kat(("sol", "Otopark asansörleri", 4, "otopark, araba"), ("sağ", "Süpermarket", 8, "market, gıda")),
    0: _avm_kat(("sağ", "Danışma", 4, "bilgi, kayıp eşya"), ("sol", "Giyim mağazası", 6, "giyim, elbise"),
                ("sağ", "Ayakkabı mağazası", 6, "ayakkabı, spor ayakkabı"), ("sol", "Tuvalet", 8, "wc, lavabo"),
                ("sağ", "Eczane", 5, "ilaç")),
    1: _avm_kat(("sol", "Kot mağazası", 6, "giyim, kot, pantolon"), ("sağ", "Elektronik mağazası", 7,
                                                                     "elektronik, telefon, bilgisayar"),
                ("sol", "Kozmetik mağazası", 6, "kozmetik, parfüm, makyaj")),
    2: _avm_kat(("sağ", "Yemek katı", 6, "yemek, restoran, kafe"), ("sol", "Sinema", 10, "film, bilet")),
}


def olustur(mekan: dict, plan: dict) -> None:
    durum.mekani_yukle(mekan, yeni_kimlik=True, plan=plan)
    st.session_state.yeni_olusturuldu = True
    st.switch_page("app_pages/cizim_sayfasi.py")


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
    avm = tur == "AVM"
    yontem = st.segmented_control(
        "Nasıl yazmak istersiniz?", ["liste", "tablo"], required=True, default="liste", key=f"sihirbaz_{tur}_yontem",
        format_func={"liste": "Liste olarak (kolay)", "tablo": "Tablo ile (sağ/sol, adım, oda no)"}.get)

if tur != "Market" and yontem == "liste":
    with st.container(border=True):
        ad = st.text_input("AVM'nin adı" if avm else "Binanın adı",
                           placeholder="ör. Gebze Center AVM" if avm else
                           "ör. Kadıköy Devlet Hastanesi, Atatürk İlkokulu", key=f"sihirbaz_{tur}_ad")
        if avm:
            bina_turu = "diger"
        else:
            bina_turu = st.segmented_control("Tür", ["hastane", "kurum"], required=True, default="hastane",
                                             key=f"sihirbaz_{tur}_bina_turu",
                                             format_func={"hastane": "Hastane / sağlık",
                                                          "kurum": "Okul / kamu / ofis"}.get)
        metin = st.text_area(
            "Katlar ve yerler", height=200, key=f"sihirbaz_{tur}_liste",
            placeholder=("Zemin kat: Danışma, Eczane, Giyim mağazası, WC\n1. kat: Kot mağazası, Elektronik\n"
                         "-1. kat: Otopark, Süpermarket") if avm else
                        ("Zemin kat: Danışma, Vezne, Kan alma, WC\n1. kat: Dahiliye, Kardiyoloji, Göz\n"
                         "-1. kat: Radyoloji"))
        st.caption("Her satıra bir kat yazın; yerleri girişten koridor boyunca karşılaştığınız **sırayla**, virgülle "
                   "ayırın. Kurumunuzun sitesindeki kat planını da olduğu gibi yapıştırabilirsiniz.")
        katlar_listesi = sihirbaz.kat_listesi_coz(metin) if metin.strip() else {}
        if metin.strip() and not katlar_listesi:
            st.warning("Kat bulunamadı. Satırlar \"Zemin kat:\", \"1. kat:\", \"-1. kat:\" gibi başlamalı.",
                       icon=":material/info:")
        elif katlar_listesi:
            st.success(" · ".join(f"{sihirbaz.kat_adi(k)}: {len(v)} yer" for k, v in katlar_listesi.items()),
                       icon=":material/check:")
        cok_katli = len(katlar_listesi) > 1 or (katlar_listesi and min(katlar_listesi) != max(katlar_listesi))
        dikey = st.segmented_control(
            "Katlar arası", ["yuruyen", "ikisi", "asansor", "merdiven"], required=True,
            default="yuruyen" if avm else "ikisi", key=f"sihirbaz_{tur}_dikey_liste",
            format_func={"yuruyen": "Yürüyen merdiven ve asansör", "ikisi": "Merdiven ve asansör",
                         "asansor": "Yalnız asansör", "merdiven": "Yalnız merdiven"}.get) if cok_katli else "ikisi"
        with st.expander("Adım sayıları (isterseniz)", icon=":material/straighten:"):
            with st.container(horizontal=True):
                giris_adim = st.number_input("Girişten koridor başına", 1, 100, 8, key=f"sihirbaz_{tur}_giris_l")
                kapi_adim = st.number_input("İki kapı arası", 1, 50, 5, key=f"sihirbaz_{tur}_kapi_l")
                basamak = st.number_input("Merdiven basamağı (kat başına)", 1, 80, 22, key=f"sihirbaz_{tur}_bas_l")
            st.caption("Bilmiyorsanız böyle bırakın. Sonraki adımda çizimde her yolu ayrı düzeltebilirsiniz; "
                       "uygulama da ziyaretçinin adım uzunluğunu kendisi ayarlar.")
    st.caption("Yerlerin koridorun **solunda mı sağında mı** olduğu listeden bilinemez: şimdilik bir sol bir sağ "
               "dizilir. Sonraki adımda çizimde ya da binada yürüyerek düzeltin; ziyaretçi bu bilgiye güvenerek yürür.")
    if st.button("Düzeni oluştur", type="primary", icon=":material/arrow_forward:",
                 disabled=not (ad.strip() and katlar_listesi)):
        ilk, son = min(katlar_listesi), max(katlar_listesi)
        katlar = [[{"ad": y, "taraf": "sol" if i % 2 == 0 else "sag", "adim": kapi_adim}
                   for i, y in enumerate(katlar_listesi.get(k, []))] for k in range(ilk, son + 1)]
        olustur(*sihirbaz.bina_olustur(ad.strip(), bina_turu, katlar, giris_adim=giris_adim, dikey=dikey,
                                       basamak=basamak, ilk_kat=ilk))
    if not ad.strip():
        st.caption("Devam etmek için adı yazın.")

elif tur != "Market":
        # Kat sayısı ve en alt kat, yapıştırılan listeden doldurulabilsin diye oturumda tutulur
        st.session_state.setdefault(f"sihirbaz_{tur}_katsayisi", 4 if avm else 2)
        st.session_state.setdefault(f"sihirbaz_{tur}_ilkkat", -1 if avm else 0)
        yapistirilan = st.session_state.get(f"sihirbaz_{tur}_yapistirilan", {})

        # Kat listesi, kat sayısı kutularından ÖNCE okunur: kutuların değeri ancak oluşturulmadan değiştirilebilir
        with st.expander("Kurumun sitesindeki kat listesini yapıştırın", icon=":material/content_paste:",
                         expanded=not yapistirilan):
            st.markdown("Birçok hastane ve AVM sitesinde **Kat Planı** ya da **Kat Rehberi** sayfası hangi birimin "
                        "hangi katta olduğunu yazar. O metni buraya yapıştırın; katlar ve birimler aşağıya dolar.")
            metin = st.text_area("Kat listesi", height=180, key=f"sihirbaz_{tur}_yapistir",
                                 placeholder="Zemin Kat: Danışma, Vezne, Kan alma\n1. Kat: Dahiliye, Kardiyoloji\n"
                                             "-1. Kat: Radyoloji, MR")
            if st.button("Katları doldur", icon=":material/playlist_add:", key=f"sihirbaz_{tur}_doldur",
                         disabled=not metin.strip()):
                katlar_listesi = sihirbaz.kat_listesi_coz(metin)
                if not katlar_listesi:
                    st.error("Kat başlığı bulunamadı. Satırlar \"Zemin Kat\", \"1. Kat\", \"-1. Kat\" gibi "
                             "başlamalı.", icon=":material/error:")
                else:
                    st.session_state[f"sihirbaz_{tur}_ilkkat"] = max(-5, min(katlar_listesi))
                    st.session_state[f"sihirbaz_{tur}_katsayisi"] = min(10, max(katlar_listesi) - min(katlar_listesi) + 1)
                    # Sağ/sol bu sayfalarda yazmaz: geçici olarak dönüşümlü yerleştirilir, sahada düzeltilir
                    yapistirilan = {k: pd.DataFrame([{"taraf": "sol" if i % 2 == 0 else "sağ", "ad": ad, "adim": 5,
                                                      "oda": "", "kisiler": "", "anahtarlar": ""}
                                                     for i, ad in enumerate(adlar)])
                                    for k, adlar in katlar_listesi.items()}
                    st.session_state[f"sihirbaz_{tur}_yapistirilan"] = yapistirilan
                    st.session_state[f"sihirbaz_{tur}_surum"] = st.session_state.get(f"sihirbaz_{tur}_surum", 0) + 1
            if yapistirilan:
                st.warning(f"{sum(len(t) for t in yapistirilan.values())} birim {len(yapistirilan)} kata yerleştirildi. "
                           "Sitelerde birimlerin koridordaki **sırası, sağda mı solda mı olduğu ve adım sayısı yazmaz**: "
                           "şimdilik sırayla ve bir sol bir sağ dizildi. Binada yürüyerek her katı düzeltin; görme engelli "
                           "ziyaretçi bu bilgiye güvenerek yürür.", icon=":material/warning:")

        with st.container(border=True):
            ad = st.text_input("AVM'nin adı" if avm else "Binanın adı",
                               placeholder="ör. Gebze Center AVM" if avm else
                               "ör. Kadıköy Devlet Hastanesi, Atatürk İlkokulu", key=f"sihirbaz_{tur}_ad")
            with st.container(horizontal=True, vertical_alignment="bottom"):
                if avm:
                    bina_turu = "diger"
                else:
                    bina_turu = st.segmented_control("Tür", ["hastane", "kurum"], required=True, default="hastane",
                                                     format_func={"hastane": "Hastane / sağlık",
                                                                  "kurum": "Okul / kamu / ofis"}.get)
                kat_sayisi = st.number_input("Kat sayısı", 1, 10, key=f"sihirbaz_{tur}_katsayisi")
                ilk_kat = st.number_input("En alt kat", -5, 0, key=f"sihirbaz_{tur}_ilkkat",
                                          help="Bodrum ya da otopark katı varsa -1, -2… Giriş zemin kata (0) bağlanır.")
            with st.container(horizontal=True, vertical_alignment="bottom"):
                dikey = st.segmented_control(
                    "Katlar arası", ["yuruyen", "ikisi", "asansor", "merdiven"], required=True,
                    default="yuruyen" if avm else "ikisi", disabled=kat_sayisi == 1, key=f"sihirbaz_{tur}_dikey",
                    format_func={"yuruyen": "Yürüyen merdiven ve asansör", "ikisi": "Merdiven ve asansör",
                                 "asansor": "Yalnız asansör", "merdiven": "Yalnız merdiven"}.get)
                giris_adim = st.number_input("Girişten koridor başına (adım)", 1, 100, 8, key=f"sihirbaz_{tur}_giris")
                basamak = st.number_input("Merdiven basamak sayısı (kat başına)", 1, 80, 22,
                                          disabled=kat_sayisi == 1 or dikey != "ikisi" and dikey != "merdiven",
                                          key=f"sihirbaz_{tur}_basamak")
        st.markdown("##### :material/storefront: Katlar ve mağazalar" if avm else "##### :material/door_front: Katlar")
        st.caption(("Her katta koridorun başından sonuna doğru yürürken karşılaştığınız mağazaları **sırayla** yazın. "
                    "**Kategori** sütununa ziyaretçinin söyleyebileceği sözcükleri yazın (giyim, ayakkabı, elektronik…); "
                    "\"giyim nerede\" diyene uygun mağazalar sayılıp seçtirilir. ") if avm else
                   "Koridorun başından sonuna doğru yürürken karşılaştığınız kapıları **sırayla** yazın. ")
        st.caption("**Adım**: bir önceki kapıdan (ilk kapı için koridor başından) bu kapıya kaç adım.")
        kat_numaralari = [ilk_kat + k for k in range(kat_sayisi)]
        sekmeler = st.tabs([sihirbaz.kat_adi(k) for k in kat_numaralari])
        katlar = []
        for kat, sekme in zip(kat_numaralari, sekmeler):
            with sekme:
                if yapistirilan:
                    ornek = yapistirilan.get(kat, ORNEK_KAT.iloc[0:0])
                else:
                    ornek = (ORNEK_AVM.get(kat, ORNEK_KAT.iloc[0:0]) if avm else
                             ORNEK_KAT if kat == 0 else ORNEK_UST_KAT if kat == 1 else ORNEK_KAT.iloc[0:0])
                tablo = st.data_editor(
                    ornek, num_rows="dynamic", hide_index=True, width="stretch", key=f"sihirbaz_{tur}_kat_{kat}_{st.session_state.get(f'sihirbaz_{tur}_surum', 0)}",
                    alt=f"{sihirbaz.kat_adi(kat)} kapıları",
                    column_order=["taraf", "ad", "adim", "anahtarlar", "oda", "kisiler"] if avm else None,
                    column_config={
                        "taraf": st.column_config.SelectboxColumn("Taraf", options=["sol", "sağ"], default="sol",
                                                                  required=True),
                        "ad": st.column_config.TextColumn("Mağaza" if avm else "Ad", required=True, width="medium"),
                        "adim": st.column_config.NumberColumn("Adım", min_value=1, step=1, default=5, format="%d"),
                        "oda": st.column_config.TextColumn("Mağaza no" if avm else "Oda no"),
                        "kisiler": st.column_config.TextColumn("Çalışanlar", help="Virgülle, ör. 'Dr. Ayşe Yılmaz'"),
                        "anahtarlar": st.column_config.TextColumn(
                            "Kategori, diğer söyleyişler" if avm else "Diğer söyleyişler",
                            width="medium" if avm else None,
                            help="Virgülle, ör. 'giyim, kot'" if avm else "ör. 'kalp' (kardiyoloji için)"),
                    })
                katlar.append([{**r, "taraf": "sag" if r["taraf"] == "sağ" else "sol"}
                               for r in tablo.fillna("").to_dict("records") if str(r["ad"]).strip()])
        if st.button("AVM düzenini oluştur" if avm else "Bina düzenini oluştur", type="primary",
                     icon=":material/auto_fix_high:", disabled=not (ad.strip() and any(katlar))):
            olustur(*sihirbaz.bina_olustur(ad.strip(), bina_turu, katlar, giris_adim=giris_adim, dikey=dikey,
                                           basamak=basamak, ilk_kat=ilk_kat))
        if not ad.strip():
            st.caption("Devam etmek için adı yazın.")

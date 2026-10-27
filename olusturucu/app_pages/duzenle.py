import streamlit as st

import bak_mekan as bm
import durum

TUR_ADLARI = {"magaza": "Market / mağaza", "hastane": "Hastane / sağlık", "kurum": "Kamu kurumu / okul / ofis",
              "diger": "Diğer"}
YOL_TURU_ADLARI = {"yuru": "Yürüme", "rampa": "Rampa", "kapi": "Kapı", "merdiven": "Merdiven",
                   "yuruyen-merdiven": "Yürüyen merdiven", "asansor": "Asansör"}

anahtar = st.session_state.surum_anahtari
kaynak = st.session_state.kaynak

st.title("Düzenle")
st.caption("Sihirbazın ya da şablonun hazırladığı her şeyi burada değiştirebilirsiniz. Değişiklikler Plan ve "
           "QR sayfalarına yansır.")

bina, noktalar_sekmesi, yollar_sekmesi, hedefler_sekmesi = st.tabs([
    ":material/apartment: Bina", ":material/location_on: Noktalar", ":material/route: Yollar",
    ":material/flag: Hedefler"])

# Noktalar önce okunur: diğer sekmelerdeki seçim kutuları nokta listesine bağlıdır
with noktalar_sekmesi:
    st.markdown(
        "Ziyaretçinin durup yön değiştirebileceği her yer bir **noktadır**: giriş, danışma, koridor başları, "
        "asansör önü, merdiven başı, oda kapıları. Her katta asansör ve merdiven için ayrı nokta ekleyin. "
        "Her noktaya bir etiket asılacak.")
    noktalar_df = st.data_editor(
        kaynak["noktalar"], key=f"noktalar-{bm.TABLO_SEMASI}-{anahtar}", num_rows="dynamic", hide_index=True,
        alt="Binadaki noktalar",
        column_config={
            "ad": st.column_config.TextColumn("Nokta adı", required=True, width="large",
                                              help="Ziyaretçiye okunacak ad, ör. 'Kardiyoloji kapısı'"),
            "kat": st.column_config.NumberColumn("Kat", default=0, step=1, format="%d",
                                                 help="0 zemin, 1 birinci kat, -1 bodrum"),
            "id": st.column_config.TextColumn("Kimlik", help="Boş bırakırsanız addan üretilir. Yalnızca küçük "
                                                             "harf, rakam ve '-'"),
        })

nokta_satirlari = noktalar_df.to_dict("records")
nokta_idleri = [bm._metin(n.get("id")) or bm.kisalt(bm._metin(n.get("ad"))) for n in nokta_satirlari
                if bm._metin(n.get("ad")) or bm._metin(n.get("id"))]
nokta_adlari = {i: bm._metin(n.get("ad")) for i, n in zip(nokta_idleri, nokta_satirlari)}


def nokta_etiketi(i: str) -> str:
    return f"{nokta_adlari.get(i) or i} ({i})"


with bina:
    bilgi = st.session_state.bilgi
    bilgi["ad"] = st.text_input("Kurumun adı", bilgi.get("ad") or "", placeholder="ör. Kadıköy Devlet Hastanesi",
                                key=f"ad-{anahtar}")
    bilgi["tur"] = st.segmented_control("Kurum türü", list(TUR_ADLARI), format_func=TUR_ADLARI.get,
                                        default=bilgi.get("tur") or "kurum", required=True, key=f"tur-{anahtar}")
    with st.container(horizontal=True):
        giris_secenekleri = nokta_idleri or ["giris"]
        bilgi["giris"] = st.selectbox(
            "Giriş noktası", giris_secenekleri, format_func=nokta_etiketi,
            index=giris_secenekleri.index(bilgi["giris"]) if bilgi.get("giris") in giris_secenekleri else 0,
            help="Büyük giriş QR'ı bu noktaya asılır.", key=f"giris-{anahtar}")
        if bilgi["tur"] == "magaza":
            kasa_secenekleri = ["", *nokta_idleri]
            bilgi["kasa"] = st.selectbox(
                "Kasa noktası (isteğe bağlı)", kasa_secenekleri,
                format_func=lambda i: "Yok" if not i else nokta_etiketi(i),
                index=kasa_secenekleri.index(bilgi["kasa"]) if bilgi.get("kasa") in kasa_secenekleri else 0,
                key=f"kasa-{anahtar}")
        else:
            bilgi["kasa"] = None
    st.caption(f"Kurum kimliği: `{bilgi['id']}` · Sürüm {bilgi['surum']}. Kimlik bu binaya özeldir; "
               "aynı binayı daha sonra güncellemek için düzen dosyasını saklayın.")

with yollar_sekmesi:
    st.markdown(
        "İki nokta arasındaki her yolu **normal adımla yürüyerek sayın** ve iki yöndeki tarifi yazın. "
        "\"Sağa dönün\" geliş yönüne göre değiştiği için dönüş tarifi ayrı yazılır. Merdiven ve asansörde "
        "kat bilgisi otomatik söylenir; tarife yalnızca ek bilgi yazın (ör. \"korkuluk sağınızda\").")
    yollar_df = st.data_editor(
        kaynak["yollar"], key=f"yollar-{bm.TABLO_SEMASI}-{anahtar}", num_rows="dynamic", hide_index=True,
        alt="Noktalar arasındaki yollar",
        column_config={
            "a": st.column_config.SelectboxColumn("Nereden", options=nokta_idleri, required=True),
            "b": st.column_config.SelectboxColumn("Nereye", options=nokta_idleri, required=True),
            "tur": st.column_config.SelectboxColumn("Tür", options=list(YOL_TURU_ADLARI), default="yuru",
                                                    format_func=YOL_TURU_ADLARI.get),
            "adim": st.column_config.NumberColumn("Adım", min_value=1, step=1, format="%d", required=True),
            "tarif": st.column_config.TextColumn("Gidiş tarifi", width="large",
                                                 help="Nereden → Nereye, ör. 'Danışmanın solundaki koridora girin'"),
            "geriTarif": st.column_config.TextColumn("Dönüş tarifi", width="large",
                                                     help="Nereye → Nereden"),
            "tekYon": st.column_config.CheckboxColumn("Tek yön", default=False,
                                                      help="Yalnızca Nereden → Nereye yürünebiliyorsa (turnike, kasa)"),
            "basamak": st.column_config.NumberColumn("Basamak", min_value=0, step=1, format="%d",
                                                     help="Yalnızca merdivenler için"),
        })
    st.caption("Nokta kimlikleri: " + " · ".join(nokta_etiketi(i) for i in nokta_idleri))

with hedefler_sekmesi:
    st.markdown(
        "Ziyaretçinin sorabileceği yerler: danışma, vezne, poliklinik, sınıf, reyon, tuvalet. **Anahtar "
        "kelimelere** insanların söyleyebileceği sözcükleri virgülle yazın (ör. \"kalp, kardiyoloji\"). "
        "Orada çalışan kişileri yazarsanız \"Doktor Ayşe Yılmaz nerede\" diye de bulunur.")
    hedefler_df = st.data_editor(
        kaynak["hedefler"], key=f"hedefler-{bm.TABLO_SEMASI}-{anahtar}", num_rows="dynamic", hide_index=True,
        alt="Ziyaretçilerin gidebileceği hedefler",
        column_config={
            "ad": st.column_config.TextColumn("Hedef adı", required=True),
            "kisaAd": st.column_config.TextColumn(
                "Kısa ad", help="Girişteki listede okunacak ad, ör. 'Kardiyoloji'. Boşsa hedef adı okunur. "
                                "Ziyaretçi bu adı söyleyerek de bulur."),
            "nokta": st.column_config.SelectboxColumn("Nokta", options=nokta_idleri, required=True),
            "tarif": st.column_config.TextColumn("Varınca söylenecek", width="large",
                                                 help="ör. 'Kardiyoloji kapısı solunuzda, oda 112.'"),
            "anahtarlar": st.column_config.TextColumn("Anahtar kelimeler", width="medium"),
            "kisiler": st.column_config.TextColumn("Kişiler", help="Virgülle, ör. 'Dr. Ayşe Yılmaz, Dr. Can Öztürk'"),
            "oda": st.column_config.TextColumn("Oda no"),
            "no": st.column_config.TextColumn("Kapı no"),
        })
    oneriler = bm.kisa_ad_onerileri(hedefler_df.to_dict("records"))
    with st.container(horizontal=True, vertical_alignment="center"):
        if st.button("Kısa adları öner", icon=":material/auto_fix_high:", disabled=not oneriler,
                     help="Birden çok yerde tekrarlanan 'Polikliniği', 'Müdürlüğü' gibi sözcükleri atar. "
                          "Önerileri tabloda değiştirebilirsiniz."):
            guncel = hedefler_df.copy()
            for satir, oneri in oneriler.items():
                guncel.iat[satir, guncel.columns.get_loc("kisaAd")] = oneri
            # Diğer sekmelerdeki düzenlemeler kaybolmasın: hepsi kaynağa yazılıp düzenleyiciler yenilenir
            st.session_state.kaynak = {"noktalar": bm.tablo(noktalar_df, bm.NOKTA_SUTUNLARI),
                                       "yollar": bm.tablo(yollar_df, bm.YOL_SUTUNLARI),
                                       "hedefler": bm.tablo(guncel, bm.HEDEF_SUTUNLARI)}
            st.session_state.pop("guncel", None)
            st.session_state.surum_anahtari += 1
            st.rerun()
        if oneriler:
            st.caption(f"{len(oneriler)} yer için kısa ad önerisi var, ör. "
                       f"{next(iter(oneriler.values()))!r}.")

# Diğer sayfalar (Plan, QR) bu tabloların son halini kullanır
st.session_state.guncel = {"noktalar": noktalar_df, "yollar": yollar_df, "hedefler": hedefler_df}

hatalar, _ = bm.dogrula(durum.guncel_mekan())
with st.container(horizontal=True, vertical_alignment="center"):
    if hatalar:
        st.caption(f":material/error: {len(hatalar)} eksik var; ayrıntılar QR sayfasında.")
    else:
        st.caption(":material/check_circle: Düzen geçerli.")
    st.page_link("app_pages/plan_sayfasi.py", label="Planı gör", icon=":material/map:")
    st.page_link("app_pages/yazdir.py", label="QR ve etiketler", icon=":material/qr_code_2:")

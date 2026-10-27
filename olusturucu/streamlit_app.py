"""BAK QR oluşturucu: hastane, market, okul, kamu kurumu gibi kuruluşlar binalarının düzenini
girip görme engelli ziyaretçiler için BAK giriş QR'ını ve nokta etiketlerini kendileri üretir.

Çalıştırma:  streamlit run streamlit_app.py
"""

import json

import streamlit as st

import bak_mekan as bm

st.set_page_config(page_title="BAK QR oluşturucu", page_icon=":material/qr_code_2:", layout="wide")

TUR_ADLARI = {"magaza": "Market / mağaza", "hastane": "Hastane / sağlık", "kurum": "Kamu kurumu / okul / ofis",
              "diger": "Diğer"}
YOL_TURU_ADLARI = {"yuru": "Yürüme", "rampa": "Rampa", "kapi": "Kapı", "merdiven": "Merdiven",
                   "yuruyen-merdiven": "Yürüyen merdiven", "asansor": "Asansör"}

BOS_MEKAN = {"id": "", "ad": "", "tur": "kurum", "surum": 1, "giris": "giris",
             "noktalar": [{"id": "giris", "ad": "Ana giriş"}], "baglantilar": [], "hedefler": []}


@st.cache_data(max_entries=50)
def qr_resmi(metin: str) -> bytes:
    return bm.qr_png(metin, kutu=6)


@st.cache_data(max_entries=20)
def etiketler(mekan_json: str) -> str:
    return bm.etiket_sayfasi(json.loads(mekan_json))


def mekani_yukle(mekan: dict, yeni_kimlik: bool) -> None:
    """Şablonu ya da kayıtlı dosyayı düzenleyicilere aktarır."""
    mekan = json.loads(json.dumps(mekan))
    if yeni_kimlik or not str(mekan.get("id", "")).startswith(bm.KURUM_ONEKI):
        mekan["id"] = bm.kimlik_uret(mekan.get("ad") or "kurum")
    else:
        # Aynı binanın güncellenmiş hali: telefonlar yeni sürümü tanısın
        mekan["surum"] = int(mekan.get("surum") or 1) + 1
    noktalar, yollar, hedefler = bm.mekandan_satirlar(mekan)
    st.session_state.bilgi = {k: mekan.get(k) for k in ("id", "ad", "tur", "surum", "giris", "kasa")}
    st.session_state.kaynak = {"noktalar": bm.tablo(noktalar, bm.NOKTA_SUTUNLARI),
                               "yollar": bm.tablo(yollar, bm.YOL_SUTUNLARI),
                               "hedefler": bm.tablo(hedefler, bm.HEDEF_SUTUNLARI)}
    # Düzenleyicilerin anahtarı değişince eski düzenlemeler atılır, yeni veri gösterilir
    st.session_state.surum_anahtari = st.session_state.get("surum_anahtari", 0) + 1


if "bilgi" not in st.session_state:
    mekani_yukle(BOS_MEKAN, yeni_kimlik=True)
elif st.session_state.get("tablo_semasi") != bm.TABLO_SEMASI:
    # Sayfa açıkken uygulama güncellendi: oturumdaki tablolar yeni yapıya çevrilir, girilenler korunur
    eski = st.session_state.kaynak
    st.session_state.kaynak = {ad: bm.tablo(eski[ad], sutunlar) for ad, sutunlar in
                               (("noktalar", bm.NOKTA_SUTUNLARI), ("yollar", bm.YOL_SUTUNLARI), ("hedefler", bm.HEDEF_SUTUNLARI))}
st.session_state.tablo_semasi = bm.TABLO_SEMASI

sablonlar = bm.sablonlar()
anahtar = st.session_state.surum_anahtari

st.title("BAK QR oluşturucu")
st.markdown(
    "Binanızın girişine asacağınız **tek bir QR kodu** ile görme engelli ziyaretçileriniz BAK uygulamasıyla "
    "danışmayı, polikliniği, sınıfı ya da reyonu sesli tarifle bulabilir. Bina bilgisi QR'ın içindedir; "
    "sunucu, internet ya da ücret gerekmez.")

with st.container(border=True):
    st.subheader(":material/start: Nereden başlamak istersiniz?")
    baslangic = st.segmented_control(
        "Başlangıç", ["Hazır şablon", "Kayıtlı düzen dosyam", "Boş sayfa"], default="Hazır şablon",
        label_visibility="collapsed", required=True)
    if baslangic == "Hazır şablon":
        with st.container(horizontal=True, vertical_alignment="bottom"):
            secilen = st.selectbox("Şablon", list(sablonlar))
            if st.button("Şablonu yükle", icon=":material/download:"):
                mekani_yukle(sablonlar[secilen], yeni_kimlik=True)
                st.rerun()
        st.caption("Şablondaki adları, adım sayılarını ve tarifleri kendi binanıza göre değiştirin.")
    elif baslangic == "Kayıtlı düzen dosyam":
        dosya = st.file_uploader("Daha önce bu sayfadan indirdiğiniz düzen dosyası (.json)", type="json")
        if dosya and st.button("Dosyayı yükle", icon=":material/upload_file:"):
            try:
                mekani_yukle(json.load(dosya), yeni_kimlik=False)
                st.rerun()
            except (json.JSONDecodeError, KeyError, TypeError):
                st.error("Bu dosya okunamadı. Bu sayfadan indirilen bir düzen dosyası seçin.")
        st.caption("Yüklediğiniz düzenin sürüm numarası bir artırılır; yeni QR'ı okutan telefonlar güncel bilgiyi alır.")
    else:
        if st.button("Boş sayfayla başla", icon=":material/note_add:"):
            mekani_yukle(BOS_MEKAN, yeni_kimlik=True)
            st.rerun()

bina, noktalar_sekmesi, yollar_sekmesi, hedefler_sekmesi, sonuc = st.tabs([
    ":material/apartment: 1. Bina", ":material/location_on: 2. Noktalar", ":material/route: 3. Yollar",
    ":material/flag: 4. Hedefler", ":material/qr_code_2: 5. Kontrol ve QR"])

# Noktalar önce okunur: diğer sekmelerdeki seçim kutuları nokta listesine bağlıdır
with noktalar_sekmesi:
    st.markdown(
        "Ziyaretçinin durup yön değiştirebileceği her yer bir **noktadır**: giriş, danışma, koridor başları, "
        "asansör önü, merdiven başı, oda kapıları. Her katta asansör ve merdiven için ayrı nokta ekleyin. "
        "Her noktaya bir etiket asılacak.")
    noktalar_df = st.data_editor(
        st.session_state.kaynak["noktalar"], key=f"noktalar-{bm.TABLO_SEMASI}-{anahtar}", num_rows="dynamic", hide_index=True,
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
        st.session_state.kaynak["yollar"], key=f"yollar-{bm.TABLO_SEMASI}-{anahtar}", num_rows="dynamic", hide_index=True,
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
        st.session_state.kaynak["hedefler"], key=f"hedefler-{bm.TABLO_SEMASI}-{anahtar}", num_rows="dynamic", hide_index=True,
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
            st.session_state.surum_anahtari += 1
            st.rerun()
        if oneriler:
            st.caption(f"{len(oneriler)} yer için kısa ad önerisi var, ör. "
                       f"{next(iter(oneriler.values()))!r}.")

mekan = bm.satirlardan_mekan(st.session_state.bilgi, nokta_satirlari, yollar_df.to_dict("records"),
                             hedefler_df.to_dict("records"))
hatalar, uyarilar = bm.dogrula(mekan)

with sonuc:
    if hatalar:
        st.error("\n".join(f"- {h}" for h in hatalar), title="QR oluşturmadan önce düzeltin",
                 icon=":material/error:")
    for u in uyarilar:
        st.warning(u, icon=":material/info:")
    if not hatalar:
        veri = bm.qr_verisi(mekan)
        surum = bm.qr_olustur(veri).version
        sol, sag = st.columns([1, 2])
        with sol:
            st.image(qr_resmi(veri), caption="Giriş QR'ı", alt=f"{mekan['ad']} için BAK giriş QR kodu")
        with sag:
            st.success(f"{len(mekan['noktalar'])} nokta, {len(mekan['baglantilar'])} yol, "
                       f"{len(mekan['hedefler'])} hedef. QR hazır.", title="Düzen geçerli",
                       icon=":material/check_circle:")
            if surum > bm.ONERILEN_EN_BUYUK_QR_SURUMU:
                st.warning("Bina bilgisi çok uzun, QR sık ve küçük kareli oldu; telefon zor okuyabilir. "
                           "Tarifleri kısaltın, gereksiz anahtar kelimeleri çıkarın ya da binayı bölümlere "
                           "ayırın.", icon=":material/warning:")
            st.download_button("Etiketleri indir (yazdırmak için)", etiketler(bm.sade_json(mekan)),
                               file_name=f"{mekan['id']}-etiketler.html", mime="text/html", type="primary",
                               icon=":material/print:", width="stretch")
            st.download_button("Düzen dosyasını sakla (.json)",
                               json.dumps(mekan, ensure_ascii=False, indent=1),
                               file_name=f"{mekan['id']}.json", mime="application/json",
                               icon=":material/save:", width="stretch",
                               help="Binayı daha sonra güncellemek için bu dosyayı bu sayfaya geri yükleyin.")
            st.download_button("Yalnızca giriş QR'ı (.png)", bm.qr_png(veri, kutu=12),
                               file_name=f"{mekan['id']}-giris.png", mime="image/png",
                               icon=":material/image:", width="stretch")
            st.markdown(
                "**Asarken:** Giriş etiketini kapının yanına, diğer etiketleri üzerlerinde yazan noktalara asın. "
                "Hepsini yerden yaklaşık 120 cm yüksekliğe ve hep aynı tarafa yapıştırın.")

        with st.container(border=True):
            st.subheader(":material/record_voice_over: Girişte okunacak liste")
            st.markdown("Ziyaretçi giriş QR'ını okutunca uygulama yerleri böyle okur, sonra numarasını ya da "
                        "adını söylemesini bekler.")
            sayfalar = bm.liste_sayfalari(mekan)
            for i, sayfa in enumerate(sayfalar):
                st.markdown(f"**{'Önce' if i == 0 else f'Ziyaretçi “devam” deyince ({i + 1}. bölüm)'}** · "
                            f"yaklaşık {bm.okuma_suresi(sayfa)} saniye")
                st.markdown(f"> {sayfa}")
            if len(sayfalar) > 1:
                st.caption(f"Liste {bm.SAYFA_BOYU}'ar yer olarak okunur. Kısa adlar listeyi kısaltır; ziyaretçi "
                           "bir yerin adını biliyorsa listeyi beklemeden doğrudan söyleyebilir.")

        with st.container(border=True):
            st.subheader(":material/hearing: Tarifi deneyin")
            hedef_adi = st.selectbox("Hedef", [h["ad"] for h in mekan["hedefler"]], key="onizleme")
            st.markdown("\n".join(f"1. {adim}" for adim in bm.rota_onizleme(mekan, hedef_adi)))
            st.caption("Uygulama bu yolu sesli ve adım adım okur. Tarifler yanlışsa Yollar sekmesinden düzeltin.")

    with st.expander("BAK tarafından doğrulanmış yayın", icon=":material/verified:"):
        st.markdown(
            "Bu sayfada oluşturulan QR'lar kurumun kendi beyanıdır; uygulama ziyaretçiye girişte bunu söyler. "
            "Binanızın **doğrulanmış** olarak yayınlanmasını isterseniz düzen dosyasını "
            "`mailtoburhanettin@gmail.com` adresine gönderin. İnceleme sonrası binanız BAK deposunda "
            "yayınlanır ve size kısa, doğrulanmış bir giriş QR'ı verilir.")

import json
import urllib.request

import streamlit as st

import bak_mekan as bm
import durum


@st.cache_data(max_entries=50)
def qr_resmi(metin: str) -> bytes:
    return bm.qr_png(metin, kutu=6)


@st.cache_data(max_entries=20)
def etiketler(mekan_json: str, giris_verisi: str) -> str:
    return bm.etiket_sayfasi(json.loads(mekan_json), giris_verisi)


def adresi_kontrol_et(adres: str, mekan: dict) -> tuple[bool, str]:
    """Kurumun sitesindeki dosya indirilebiliyor ve buradaki düzenle aynı bina mı?"""
    try:
        istek = urllib.request.Request(adres, headers={"User-Agent": "BAK-QR-olusturucu/1.0"})
        with urllib.request.urlopen(istek, timeout=10) as yanit:
            uzak = json.loads(yanit.read(600_000).decode("utf-8"))
    except Exception as hata:  # noqa: BLE001 (kuruma anlaşılır bir mesaj gösterilir)
        return False, f"Dosya indirilemedi: {hata}"
    if uzak.get("id") != mekan["id"]:
        return False, "Bu adresteki dosya başka bir binaya ait. Buradan indirdiğiniz düzen dosyasını yükleyin."
    hatalar, _ = bm.dogrula(uzak)
    if hatalar:
        return False, "Dosyada eksikler var: " + hatalar[0]
    if uzak.get("surum") != mekan.get("surum"):
        return True, "Dosya bulundu, ama sürümü buradakinden farklı. Son indirdiğiniz dosyayı yüklediğinizden emin olun."
    return True, "Dosya bulundu ve bu binayla aynı. Telefonlar bina bilgisini buradan indirecek."


mekan = durum.guncel_mekan()
hatalar, uyarilar = bm.dogrula(mekan)

st.title("Yazdır")

if hatalar:
    st.error("\n".join(f"- {h}" for h in hatalar), title="QR oluşturmadan önce düzeltin", icon=":material/error:")
    oneriler = bm.kimlik_onerileri(mekan)
    if oneriler:
        adlar = {n["id"]: n["ad"] for n in mekan["noktalar"]}
        with st.container(border=True):
            st.markdown("Bazı yollar ve hedefler, Noktalar tablosunda kimliği değiştirilmiş noktaları gösteriyor. "
                        "Bunları şu noktalara bağlayabilirim:\n" +
                        "\n".join(f"- `{eski}` → **{adlar.get(yeni, yeni)}** (`{yeni}`)"
                                  for eski, yeni in oneriler.items()))
            if st.button("Bağlantıları düzelt", icon=":material/link:", type="primary"):
                durum.mekani_tablolara_yaz(bm.kimlikleri_degistir(mekan, oneriler))
                st.rerun()
    with st.container(horizontal=True):
        st.page_link("app_pages/cizim_sayfasi.py", label="Çizimde düzelt", icon=":material/draw:")
        st.page_link("app_pages/duzenle.py", label="Tablolarda düzelt", icon=":material/table_view:")
# Uyarılar QR'ı engellemez: kalabalık etmesin diye kapalı bir kutuda
if uyarilar:
    with st.expander(f"{len(uyarilar)} öneri (QR'ı engellemez)", icon=":material/lightbulb:"):
        for u in uyarilar:
            st.markdown(f"- {u}")

veri = None   # giriş QR'ının içeriği: düzenin kendisi ya da kurumun sitesindeki adresi
if not hatalar:
    gomulu = bm.qr_verisi(mekan)
    sigmiyor = not bm.qr_sigar_mi(gomulu)
    # Bina bilgisi normalde QR'ın içindedir (internet gerekmez); soru sorulmaz. Yalnızca QR'a sığmayacak kadar büyük
    # binada ya da kurum sayfanın altındaki "Gelişmiş" kutusundan isterse bilgi kurumun sitesinde tutulur.
    yontem = "adres" if sigmiyor or st.session_state.get("qr_adres_modu") else "icinde"
    if yontem == "icinde":
        veri = gomulu
    else:
        with st.container(border=True):
            if sigmiyor:
                st.info("Binanız tek bir QR'a sığmayacak kadar büyük. Bina bilgisini kurumunuzun web sitesine koyup "
                        "QR'a yalnızca adresini yazacağız.", icon=":material/info:")
            st.markdown(
                "1. Aşağıdan **düzen dosyasını** indirin.\n"
                "2. Dosyayı kurumunuzun web sitesine yükleyin (ör. `https://kurumunuz.com.tr/bak/duzen.json`).\n"
                "3. Dosyanın adresini buraya yapıştırın.\n\n"
                "Bina değişince yalnızca o dosyayı güncellemeniz yeter; basılmış QR'lar aynı kalır. "
                "Ziyaretçinin telefonu bina bilgisini ilk okutmada indirir, sonra internetsiz de kullanır.")
            adres = st.text_input("Düzen dosyasının adresi", key="duzen_adresi",
                                  placeholder="https://kurumunuz.com.tr/bak/duzen.json").strip()
            if adres and not bm.adres_gecerli(adres):
                st.error("Adres https:// ile başlamalı ve boşluk içermemeli.", icon=":material/error:")
            if bm.adres_gecerli(adres) and st.button("Adresi kontrol et", icon=":material/travel_explore:"):
                tamam, mesaj = adresi_kontrol_et(adres, mekan)
                (st.success if tamam else st.error)(mesaj)
            veri = bm.adres_qr_verisi(adres) if bm.adres_gecerli(adres) else None
            st.download_button("Düzen dosyasını indir (siteye yüklemek için)", durum.dosya_icerigi(mekan),
                               file_name=f"{mekan['id']}.json", mime="application/json",
                               icon=":material/download:")

if not hatalar and veri:
    sol, sag = st.columns([1, 2])
    with sol, st.container(border=True):
        st.image(qr_resmi(veri), caption="Giriş QR'ı", alt=f"{mekan['ad']} için BAK giriş QR kodu")
    with sag:
        st.success(f"Ziyaretçiye {len(mekan['hedefler'])} yer okunacak. {len(mekan['noktalar'])} etiket "
                   "basılacak: biri girişe, diğerleri yol üstündeki noktalara.", title="QR hazır",
                   icon=":material/check_circle:")
        st.download_button("Etiketleri indir (yazdırmak için)", etiketler(bm.sade_json(mekan), veri),
                           file_name=f"{mekan['id']}-etiketler.html", mime="text/html", type="primary",
                           icon=":material/print:", width="stretch")
        st.download_button("Daha sonra düzenlemek için kaydet (.json)", durum.dosya_icerigi(mekan),
                           file_name=f"{mekan['id']}.json", mime="application/json",
                           icon=":material/save:", width="stretch",
                           help="Binayı daha sonra güncellemek için bu dosyayı 1. Başla sayfasında açın.")
        st.download_button("Yalnızca giriş QR'ı (.png)", bm.qr_png(veri, kutu=12),
                           file_name=f"{mekan['id']}-giris.png", mime="image/png",
                           icon=":material/image:", width="stretch")
        st.markdown(
            "**Asarken:** Giriş etiketini kapının yanına, diğer etiketleri üzerlerinde yazan noktalara asın. "
            "Hepsini yerden yaklaşık 120 cm yüksekliğe ve hep aynı tarafa (ör. kapının sağına) yapıştırın.")

if not hatalar:
    with st.container(border=True):
        st.subheader(":material/record_voice_over: Girişte okunacak liste")
        st.markdown("Ziyaretçi giriş QR'ını okutunca uygulama yerleri böyle okur, sonra numarasını ya da "
                    "adını söylemesini bekler.")
        sayfalar = bm.liste_sayfalari(mekan)
        for i, sayfa in enumerate(sayfalar):
            st.markdown(f"**{'Önce' if i == 0 else f'Ziyaretçi “devam” deyince ({i + 1}. bölüm)'}** · "
                        f"yaklaşık {bm.okuma_suresi(sayfa)} saniye")
            # "11. yerden devam" Markdown'da numaralı liste sanılmasın
            st.markdown("> " + sayfa.replace(". ", "\\. ", 1) if sayfa[:1].isdigit() else f"> {sayfa}")
        if len(sayfalar) > 1:
            st.caption(f"Liste {bm.SAYFA_BOYU}'ar yer olarak okunur. Kısa adlar listeyi kısaltır; ziyaretçi "
                       "bir yerin adını biliyorsa listeyi beklemeden doğrudan söyleyebilir.")

if not hatalar and not sigmiyor:  # noqa: F821 (sigmiyor yalnızca hata yoksa tanımlı)
    with st.expander("Gelişmiş: bina bilgisini kurumun sitesinde tutmak", icon=":material/language:"):
        st.toggle("Bina bilgisini kurumun sitesinde tut", key="qr_adres_modu",
                  help="Gerekmez. Bina sık değişiyorsa işe yarar: değişince QR'ı yeniden basmak yerine sitedeki "
                       "dosyayı güncellersiniz.")
        st.caption("Kapalıyken bina bilgisi QR'ın içindedir; ziyaretçinin interneti olmasa da çalışır. Bina "
                   "değişirse giriş QR'ını yeniden basarsınız.")

with st.expander("BAK tarafından doğrulanmış yayın", icon=":material/verified:"):
    st.markdown(
        "Bu sayfada oluşturulan QR'lar kurumun kendi beyanıdır; uygulama ziyaretçiye girişte bunu söyler. "
        "Binanızın **doğrulanmış** olarak yayınlanmasını isterseniz düzen dosyasını "
        "`mailtoburhanettin@gmail.com` adresine gönderin. İnceleme sonrası binanız BAK deposunda "
        "yayınlanır ve size kısa, doğrulanmış bir giriş QR'ı verilir.")

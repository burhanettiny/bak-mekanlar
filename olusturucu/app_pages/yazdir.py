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

st.title("QR ve etiketler")

if hatalar:
    st.error("\n".join(f"- {h}" for h in hatalar), title="QR oluşturmadan önce düzeltin", icon=":material/error:")
    st.page_link("app_pages/duzenle.py", label="Düzenle sayfasına git", icon=":material/edit_note:")
for u in uyarilar:
    st.warning(u, icon=":material/info:")

veri = None   # giriş QR'ının içeriği: düzenin kendisi ya da kurumun sitesindeki adresi
if not hatalar:
    gomulu = bm.qr_verisi(mekan)
    sigmiyor = not bm.qr_sigar_mi(gomulu)
    with st.container(border=True):
        yontem = st.segmented_control(
            "Bina bilgisi nerede dursun?", ["icinde", "adres"], required=True,
            default="adres" if sigmiyor else "icinde", key="qr_yontemi",
            format_func={"icinde": "QR'ın içinde (küçük ve orta binalar)",
                         "adres": "Kurumun sitesinde (büyük binalar, AVM)"}.get)
        if yontem == "icinde":
            st.caption("İnternet gerekmez; ziyaretçinin telefonu bina bilgisini QR'dan okur. Bina değişirse "
                       "giriş QR'ını yeniden basmanız gerekir.")
            if sigmiyor:
                st.warning("Bina bilgisi tek QR'a sığmayacak kadar büyük; QR çok sık kareli oluyor ve telefon zor "
                           "okur. **Kurumun sitesinde** seçeneğini kullanın.", icon=":material/warning:")
            # Hiçbir QR'a sığmıyorsa (en büyük QR sürümünü de aşıyorsa) QR çizilemez
            veri = gomulu if bm.qr_surumu(gomulu) is not None else None
        else:
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
        st.success(f"{len(mekan['noktalar'])} nokta, {len(mekan['baglantilar'])} yol, "
                   f"{len(mekan['hedefler'])} hedef.", title="Düzen geçerli, QR hazır",
                   icon=":material/check_circle:")
        st.download_button("Etiketleri indir (yazdırmak için)", etiketler(bm.sade_json(mekan), veri),
                           file_name=f"{mekan['id']}-etiketler.html", mime="text/html", type="primary",
                           icon=":material/print:", width="stretch")
        st.download_button("Düzen dosyasını sakla (.json)", durum.dosya_icerigi(mekan),
                           file_name=f"{mekan['id']}.json", mime="application/json",
                           icon=":material/save:", width="stretch",
                           help="Binayı daha sonra güncellemek için bu dosyayı Başla sayfasından geri yükleyin.")
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

with st.expander("BAK tarafından doğrulanmış yayın", icon=":material/verified:"):
    st.markdown(
        "Bu sayfada oluşturulan QR'lar kurumun kendi beyanıdır; uygulama ziyaretçiye girişte bunu söyler. "
        "Binanızın **doğrulanmış** olarak yayınlanmasını isterseniz düzen dosyasını "
        "`mailtoburhanettin@gmail.com` adresine gönderin. İnceleme sonrası binanız BAK deposunda "
        "yayınlanır ve size kısa, doğrulanmış bir giriş QR'ı verilir.")

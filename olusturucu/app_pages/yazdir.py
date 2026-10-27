import json

import streamlit as st

import bak_mekan as bm
import durum


@st.cache_data(max_entries=50)
def qr_resmi(metin: str) -> bytes:
    return bm.qr_png(metin, kutu=6)


@st.cache_data(max_entries=20)
def etiketler(mekan_json: str) -> str:
    return bm.etiket_sayfasi(json.loads(mekan_json))


mekan = durum.guncel_mekan()
hatalar, uyarilar = bm.dogrula(mekan)

st.title("QR ve etiketler")

if hatalar:
    st.error("\n".join(f"- {h}" for h in hatalar), title="QR oluşturmadan önce düzeltin", icon=":material/error:")
    st.page_link("app_pages/duzenle.py", label="Düzenle sayfasına git", icon=":material/edit_note:")
for u in uyarilar:
    st.warning(u, icon=":material/info:")

if not hatalar:
    veri = bm.qr_verisi(mekan)
    surum = bm.qr_olustur(veri).version
    sol, sag = st.columns([1, 2])
    with sol, st.container(border=True):
        st.image(qr_resmi(veri), caption="Giriş QR'ı", alt=f"{mekan['ad']} için BAK giriş QR kodu")
    with sag:
        st.success(f"{len(mekan['noktalar'])} nokta, {len(mekan['baglantilar'])} yol, "
                   f"{len(mekan['hedefler'])} hedef.", title="Düzen geçerli, QR hazır",
                   icon=":material/check_circle:")
        if surum > bm.ONERILEN_EN_BUYUK_QR_SURUMU:
            st.warning("Bina bilgisi çok uzun, QR sık ve küçük kareli oldu; telefon zor okuyabilir. "
                       "Tarifleri kısaltın, gereksiz anahtar kelimeleri çıkarın ya da binayı bölümlere "
                       "ayırın.", icon=":material/warning:")
        st.download_button("Etiketleri indir (yazdırmak için)", etiketler(bm.sade_json(mekan)),
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

with st.expander("BAK tarafından doğrulanmış yayın", icon=":material/verified:"):
    st.markdown(
        "Bu sayfada oluşturulan QR'lar kurumun kendi beyanıdır; uygulama ziyaretçiye girişte bunu söyler. "
        "Binanızın **doğrulanmış** olarak yayınlanmasını isterseniz düzen dosyasını "
        "`mailtoburhanettin@gmail.com` adresine gönderin. İnceleme sonrası binanız BAK deposunda "
        "yayınlanır ve size kısa, doğrulanmış bir giriş QR'ı verilir.")

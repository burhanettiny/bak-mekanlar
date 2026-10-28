"""Sayfalar arasında paylaşılan oturum durumu.

st.session_state:
  bilgi            kurumun adı, türü, kimliği, sürümü, giriş ve kasa noktası
  kaynak           düzenleyici tablolarının başlangıç verisi (noktalar, yollar, hedefler)
  guncel           Düzenle sayfasındaki tabloların son hali (o sayfadan çıkınca kaynağa işlenir)
  plan             2D plan için konumlar ve market rafları (QR'a girmez, düzen dosyasında saklanır)
  surum_anahtari   tablo düzenleyicilerinin anahtarı; artınca düzenleyiciler yeni veriyle açılır
"""

from __future__ import annotations

import json

import streamlit as st

import bak_mekan as bm

BOS_MEKAN = {"id": "", "ad": "", "tur": "kurum", "surum": 1, "giris": "giris",
             "noktalar": [{"id": "giris", "ad": "Ana giriş"}], "baglantilar": [], "hedefler": []}
TABLOLAR = (("noktalar", bm.NOKTA_SUTUNLARI), ("yollar", bm.YOL_SUTUNLARI), ("hedefler", bm.HEDEF_SUTUNLARI))


def baslat() -> None:
    if "bilgi" not in st.session_state:
        mekani_yukle(BOS_MEKAN, yeni_kimlik=True)
    elif st.session_state.get("tablo_semasi") != bm.TABLO_SEMASI:
        # Sayfa açıkken uygulama güncellendi: oturumdaki tablolar yeni yapıya çevrilir, girilenler korunur
        eski = st.session_state.kaynak
        st.session_state.kaynak = {ad: bm.tablo(eski[ad], sutunlar) for ad, sutunlar in TABLOLAR}
    st.session_state.tablo_semasi = bm.TABLO_SEMASI
    st.session_state.setdefault("plan", {})


def mekani_yukle(mekan: dict, yeni_kimlik: bool, plan: dict | None = None) -> None:
    """Şablonu, sihirbaz sonucunu ya da kayıtlı dosyayı düzenleyicilere aktarır."""
    mekan = json.loads(json.dumps(mekan))
    plan = plan if plan is not None else mekan.pop("plan", None) or {}
    mekan.pop("plan", None)
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
    st.session_state.plan = plan
    st.session_state.pop("guncel", None)
    st.session_state.surum_anahtari = st.session_state.get("surum_anahtari", 0) + 1


def duzenlemeleri_isle() -> None:
    """Düzenle sayfasından çıkınca tabloların son hali kaynağa yazılır. Tablo düzenleyicinin kendi
    hafızası sayfa değişince silindiği için bu yapılmazsa yapılan düzenlemeler kaybolur."""
    guncel = st.session_state.pop("guncel", None)
    if guncel:
        st.session_state.kaynak = {ad: bm.tablo(guncel[ad], sutunlar) for ad, sutunlar in TABLOLAR}
        st.session_state.surum_anahtari += 1


def mekani_tablolara_yaz(mekan: dict) -> None:
    """Sayfadan yapılan toplu düzeltmeyi (ör. kimlik değişikliği) tablolara yazar; kimlik ve sürüm değişmez."""
    noktalar, yollar, hedefler = bm.mekandan_satirlar(mekan)
    st.session_state.bilgi.update(giris=mekan.get("giris"), kasa=mekan.get("kasa"))
    st.session_state.kaynak = {"noktalar": bm.tablo(noktalar, bm.NOKTA_SUTUNLARI),
                               "yollar": bm.tablo(yollar, bm.YOL_SUTUNLARI),
                               "hedefler": bm.tablo(hedefler, bm.HEDEF_SUTUNLARI)}
    st.session_state.pop("guncel", None)
    st.session_state.surum_anahtari += 1


def tablolar() -> dict:
    return st.session_state.get("guncel") or st.session_state.kaynak


def guncel_mekan() -> dict:
    t = tablolar()
    return bm.satirlardan_mekan(st.session_state.bilgi, t["noktalar"].to_dict("records"),
                                t["yollar"].to_dict("records"), t["hedefler"].to_dict("records"))


def nokta_idleri() -> list[str]:
    satirlar = tablolar()["noktalar"].to_dict("records")
    return [bm._metin(n.get("id")) or bm.kisalt(bm._metin(n.get("ad"))) for n in satirlar
            if bm._metin(n.get("ad")) or bm._metin(n.get("id"))]


def dosya_icerigi(mekan: dict) -> str:
    """İndirilen düzen dosyası: QR verisi + plan (plan QR'a girmez, yalnızca bu dosyada durur)."""
    plan = st.session_state.get("plan") or {}
    return json.dumps({**mekan, **({"plan": plan} if plan else {})}, ensure_ascii=False, indent=1)

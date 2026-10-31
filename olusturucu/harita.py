"""Açık alandaki noktaların harita konumu (isteğe bağlı) ve çizimin haritaya oturtulması.

Kampüs gibi açık alanlarda noktaların gerçek konumu bilinirse ziyaretçi QR okutmadan "neredeyim" diyebilir:
telefon GPS'le en yakın noktayı söyler. Elle çizilmiş bir kampüste kurum iki noktayı haritada yerine koyar
(tıklayarak ya da sahada "Buradayım" ile); çizimin tamamı döndürülüp ölçeklenerek haritaya oturtulur. Bundan sonra
çizim gerçek ölçekte, kuzey yukarıdadır, arkasında harita görünür ve her noktanın harita konumu çizimdeki yerinden
hesaplanır (bkz. cizim.dis_gps): haritada taşınan nokta çizimde de taşınmış olur.
OpenStreetMap'ten kurulan kampüsler (osm_kampus.py) baştan haritaya oturtulmuş gelir.
"""
import math
from typing import Callable

import streamlit as st

import bak_mekan as bm
import cizim as cz


def haritaya_oturt(mekan: dict, plan: dict) -> float:
    """Elle yerleştirilmiş (plan["gps"], en az iki) dış noktalara göre dış çizimi haritaya oturtur: döndürme +
    ölçek + kaydırma (en küçük kareler). Yerleştirilen noktalar tam haritadaki yerlerine konur, diğerleri çizimdeki
    düzenleriyle taşınır; yürüme yollarının adımı gerçek mesafeden yeniden hesaplanır (sahada sayılıp elle yazılanlar
    korunur). Döner: yerleştirilen noktalarda çizimin haritaya en kötü uyumu (metre); kötüyse çizim ölçekli
    değildir ve kurum diğer noktaları da haritada düzeltmelidir. İkiden az nokta varsa bir şey yapmaz (-1)."""
    konum = cz.gorunum_konumlari(plan, None)
    gps = {i: k for i, k in cz.dis_gps({**plan, "harita": None}).items() if i in konum}
    if len(gps) < 2:
        return -1.0
    olc = cz.olcek(mekan, plan)
    plan["olcek"] = olc
    enlem0 = sum(k[0] for k in gps.values()) / len(gps)
    boylam0 = sum(k[1] for k in gps.values()) / len(gps)
    kx = cz._kx(enlem0)
    # Çizimde x doğu, y kuzey (bkz. cizim.pusula_yonu); haritada da doğu/kuzey metre. Karmaşık sayılarla
    # benzerlik dönüşümü: w = a·z + b (a döndürme ve ölçek, b kaydırma)
    z = {i: complex(*konum[i]) for i in gps}
    w = {i: complex((k[1] - boylam0) * kx, (k[0] - enlem0) * cz._KY) for i, k in gps.items()}
    zm, wm = sum(z.values()) / len(z), sum(w.values()) / len(w)
    payda = sum(abs(z[i] - zm) ** 2 for i in gps)
    if payda < 1e-9:   # yerleştirilen noktalar çizimde üst üste: döndürme bulunamaz
        return -1.0
    a = sum((w[i] - wm) * (z[i] - zm).conjugate() for i in gps) / payda
    b = wm - a * zm
    uyum = max(abs(a * z[i] + b - w[i]) for i in gps)
    m = cz.harita_birimi(plan)
    for i, p in konum.items():
        t = w[i] if i in gps else a * complex(*p) + b
        plan.setdefault("konum", {})[i] = [round(t.real / m, 2), round(t.imag / m, 2)]
    plan["harita"] = {"enlem": round(enlem0, 6), "boylam": round(boylam0, 6)}
    plan.pop("gps", None)
    adimlari_yenile(mekan, plan)
    return uyum


def adimlari_yenile(mekan: dict, plan: dict) -> None:
    """Dış çizimdeki yürüme yollarının adımı çizimdeki (artık gerçek) mesafeden; elle yazılanlar korunur."""
    konum = cz.gorunum_konumlari(plan, None)
    sabit = {tuple(y) for y in plan.get("sabitAdim") or []}
    olc = cz.olcek(mekan, plan)
    for y in mekan["baglantilar"]:
        if (y["a"], y["b"]) in sabit or (y.get("tur") or "yuru") in bm.DIKEY_GECISLER:
            continue
        if y["a"] in konum and y["b"] in konum and math.dist(konum[y["a"]], konum[y["b"]]) > 0.01:
            y["adim"] = max(1, round(math.dist(konum[y["a"]], konum[y["b"]]) * olc))


_HTML = """
<div class="bak-harita">
  <div class="arac">
    <input class="ara" type="search" placeholder="Haritada ara: kurum ya da adres" aria-label="Haritada ara">
    <button type="button" class="buradayim" title="Telefonunuzun konumunu seçili noktaya yazar">📍 Buradayım</button>
    <span class="ipucu" aria-live="polite"></span>
  </div>
  <div class="kutu" role="application" aria-label="Harita"></div>
</div>
"""

_CSS = """
.bak-harita { font-family: var(--st-font); color: var(--st-text-color); }
.arac { display: flex; gap: .5rem; align-items: center; margin-bottom: .5rem; flex-wrap: wrap; }
.arac input { font: inherit; padding: .3rem .6rem; min-width: 14rem; flex: 1 1 14rem;
  border-radius: var(--st-button-radius, .5rem); border: 1px solid var(--st-border-color);
  background: var(--st-background-color); color: inherit; }
.arac button { font: inherit; padding: .3rem .8rem; border-radius: var(--st-button-radius, .5rem);
  border: 1px solid var(--st-border-color); background: var(--st-background-color); color: inherit; cursor: pointer; }
.ipucu { font-size: .875rem; opacity: .75; }
.kutu { width: 100%; height: 460px; border-radius: var(--st-base-radius, .5rem);
  border: 1px solid var(--st-border-color); cursor: crosshair; }
"""

_JS = """
const LEAFLET = "https://unpkg.com/leaflet@1.9.4/dist/"
const durumlar = new WeakMap()
let yukleme = null

function leaflet(ust) {
  if (!ust.querySelector("link[data-leaflet]")) {
    const l = document.createElement("link")
    l.rel = "stylesheet"; l.href = LEAFLET + "leaflet.css"; l.dataset.leaflet = "1"
    ust.prepend(l)
  }
  if (!yukleme) yukleme = import(LEAFLET + "leaflet-src.esm.js")
  return yukleme
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const kutu = parentElement.querySelector(".kutu")
  const ipucu = parentElement.querySelector(".ipucu")
  const ara = parentElement.querySelector(".ara")
  const buradayim = parentElement.querySelector(".buradayim")
  if (!kutu) return
  const secili = data.secili
  const seciliAd = (data.noktalar.find(n => n.id === secili) || {}).ad
  ipucu.textContent = seciliAd ? `Seçili: ${seciliAd} — haritada yerine tıklayın` : "Önce çizimde ya da haritada bir nokta seçin"
  buradayim.disabled = !secili

  buradayim.onclick = () => {
    if (!navigator.geolocation) { ipucu.textContent = "Bu tarayıcı konum vermiyor"; return }
    ipucu.textContent = "Konum alınıyor…"
    navigator.geolocation.getCurrentPosition(
      p => setTriggerValue("olay", { tur: "konum", id: secili, enlem: p.coords.latitude,
                                     boylam: p.coords.longitude, dogruluk: p.coords.accuracy }),
      h => { ipucu.textContent = "Konum alınamadı: " + (h.code === 1 ? "izin verilmedi" : h.message) },
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 })
  }

  leaflet(parentElement).then(L => {
    let d = durumlar.get(parentElement)
    if (!d) {
      const harita = L.map(kutu, { zoomControl: true })
      const sokak = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        { maxZoom: 19, attribution: "© OpenStreetMap katkıcıları" })
      const uydu = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 19, attribution: "Uydu: Esri, Maxar, Earthstar Geographics" })
      sokak.addTo(harita)
      L.control.layers({ "Harita": sokak, "Uydu": uydu }, null, { position: "topright" }).addTo(harita)
      d = { harita, katman: L.layerGroup().addTo(harita), anahtar: null, secili: null }
      durumlar.set(parentElement, d)
      harita.on("click", e => {
        if (!d.secili) { ipucu.textContent = "Önce bir nokta seçin"; return }
        setTriggerValue("olay", { tur: "konum", id: d.secili, enlem: e.latlng.lat, boylam: e.latlng.lng })
      })
      ara.addEventListener("keydown", e => {
        if (e.key !== "Enter" || !ara.value.trim()) return
        e.preventDefault()
        ipucu.textContent = "Aranıyor…"
        fetch("https://nominatim.openstreetmap.org/search?format=json&limit=1&accept-language=tr&q=" +
              encodeURIComponent(ara.value.trim()))
          .then(r => r.json())
          .then(s => {
            if (!s.length) { ipucu.textContent = "Bulunamadı"; return }
            d.harita.setView([+s[0].lat, +s[0].lon], 17)
            ipucu.textContent = s[0].display_name.split(",").slice(0, 2).join(",")
          })
          .catch(() => { ipucu.textContent = "Arama yapılamadı" })
      })
    }
    d.secili = secili
    d.katman.clearLayers()
    const konumlu = data.noktalar.filter(n => n.enlem != null)
    for (const n of konumlu) {
      const s = n.id === secili
      const m = L.circleMarker([n.enlem, n.boylam], {
        radius: s ? 9 : 6, weight: 2, color: s ? "#ff4b4b" : (n.tahmin ? "#e0a800" : "#1c62b9"), fillOpacity: .85,
      }).addTo(d.katman)
      m.bindTooltip(n.ad, { permanent: konumlu.length <= 30, direction: "top", offset: [0, -6] })
      m.on("click", e => { L.DomEvent.stopPropagation(e); setTriggerValue("olay", { tur: "sec", id: n.id }) })
    }
    // Görünüm yalnızca ilk açılışta ya da noktalar değişince sığdırılır; tıklayıp yerleştirirken harita kaymasın
    const anahtar = data.anahtar
    if (d.anahtar !== anahtar) {
      if (d.anahtar === null || !konumlu.length || data.sigdir) {
        if (konumlu.length > 1) d.harita.fitBounds(konumlu.map(n => [n.enlem, n.boylam]), { padding: [40, 40], maxZoom: 18 })
        else if (konumlu.length === 1) d.harita.setView([konumlu[0].enlem, konumlu[0].boylam], 17)
        else d.harita.setView([39.0, 35.2], 6)
      }
      d.anahtar = anahtar
    }
    setTimeout(() => d.harita.invalidateSize(), 60)
  }).catch(() => { ipucu.textContent = "Harita yüklenemedi (internet bağlantısını kontrol edin)" })
}
"""

_HARITA = st.components.v2.component("bak_harita", html=_HTML, css=_CSS, js=_JS)


def harita(veri: dict, *, key: str, on_olay: Callable[[], None]):
    """Harita bileşeni. veri: noktalar [{id, ad, enlem?, boylam?, tahmin?}], secili, anahtar, sigdir."""
    return _HARITA(data=veri, key=key, on_olay_change=on_olay)

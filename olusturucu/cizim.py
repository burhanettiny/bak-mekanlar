"""2B çizim düzenleyici: kurum, binasını modül modül (bina, oda, kavşak, asansör…) çizer.

Modüller sürüklenince aradaki yolların adım sayısı çizimdeki mesafeden yeniden hesaplanır. Bir binanın içi ayrı bir
çizimdir: binaya tıklayıp "İçini aç" denince odaları eklenir. Hepsi BAK'ın düz nokta–yol–hedef biçimine yazılır; çizime
özgü bilgiler (konum, ölçek, modül türü, hangi odanın hangi binada olduğu) plan içinde durur ve QR'a girmez.

plan anahtarları:
  konum  {nokta: [x, y]}  çizimdeki yer (birim: olcek kadar adım)
  olcek  bir birimin kaç adım olduğu
  tur    {nokta: modül türü}
  ust    {nokta: bina noktası}  bina içindeki odalar; konumları binanın kendi çizimindedir
  icKonum {bina: [x, y]}  bina girişinin, binanın iç çizimindeki yeri
  icOlcek {bina: adım}    iç çizimde bir birimin kaç adım olduğu (varsayılan 1)
  sabitAdim [[a, b]]      sahada sayılıp elle yazılmış adımlar: sürükleyince değişmez
"""

from __future__ import annotations

import math
import statistics
from collections import deque
from collections.abc import Callable

import streamlit as st

import bak_mekan as bm

MODULLER = {
    "bina": ("Bina", ":material/apartment:"),
    "oda": ("Oda / birim", ":material/meeting_room:"),
    "kavsak": ("Kavşak / koridor", ":material/fork_right:"),
    "danisma": ("Danışma", ":material/support_agent:"),
    "wc": ("Tuvalet", ":material/wc:"),
    "asansor": ("Asansör", ":material/elevator:"),
    "merdiven": ("Merdiven", ":material/stairs:"),
}
# Bu modüller ziyaretçinin sorabileceği yerlerdir: eklenince hedef de olur
HEDEF_MODULLERI = {"bina", "oda", "danisma", "wc", "asansor", "merdiven"}
ANAHTAR_EKLERI = {"wc": ["tuvalet", "wc", "lavabo"], "danisma": ["danışma", "bilgi"],
                  "asansor": ["asansör"], "merdiven": ["merdiven"]}
YENI_MESAFE = 10   # yeni modül seçili modülden bu kadar adım uzağa konur


# ── Yerleşim ve ölçek ─────────────────────────────────────

def olcek(mekan: dict, plan: dict) -> float:
    """Bir çizim biriminin kaç adım olduğu: kayıtlıysa o, değilse var olan yolların adım/mesafe oranı."""
    if plan.get("olcek"):
        return float(plan["olcek"])
    konum = gorunum_konumlari(plan, None)
    oranlar = []
    for b in mekan.get("baglantilar") or []:
        if (b.get("tur") or "yuru") in bm.DIKEY_GECISLER or b["a"] not in konum or b["b"] not in konum:
            continue
        d = math.dist(konum[b["a"]], konum[b["b"]])
        if d > 0.01 and b.get("adim"):
            oranlar.append(b["adim"] / d)
    return round(statistics.median(oranlar), 3) if oranlar else 1.0


def gorunum_konumlari(plan: dict, gorunum: str | None) -> dict[str, list[float]]:
    """Bir çizimin koordinatları: dış çizimde binalara ait olmayan noktalar; bina çiziminde odalar ve binanın
    girişi (iç çizimdeki yeriyle)."""
    konum = plan.get("konum") or {}
    ust = plan.get("ust") or {}
    if not gorunum:
        return {i: p for i, p in konum.items() if i not in ust}
    ic = {i: konum[i] for i, u in ust.items() if u == gorunum and i in konum}
    ic[gorunum] = (plan.get("icKonum") or {}).get(gorunum, [0.0, 0.0])
    return ic


def gorunum_olcegi(plan: dict, gorunum: str | None, dis_olcek: float) -> float:
    return float((plan.get("icOlcek") or {}).get(gorunum, 1.0)) if gorunum else dis_olcek


def yerlesim(mekan: dict, plan: dict, olc: float) -> dict[str, list[float]]:
    """Kayıtlı konumlar korunur; konumu olmayan noktalar girişten başlayarak komşusunun yanına, yolun adım
    sayısı kadar uzağa yerleştirilir (kardeşler yelpaze gibi açılır)."""
    konum = {k: list(v) for k, v in (plan.get("konum") or {}).items()}
    idler = [n["id"] for n in mekan.get("noktalar") or []]
    komsu: dict[str, list[tuple[str, float]]] = {i: [] for i in idler}
    for b in mekan.get("baglantilar") or []:
        if b["a"] in komsu and b["b"] in komsu:
            adim = b.get("adim") or YENI_MESAFE
            if (b.get("tur") or "yuru") in bm.DIKEY_GECISLER:
                adim = 4   # başka kattaki uç: çizimde hemen yanına
            komsu[b["a"]].append((b["b"], adim))
            komsu[b["b"]].append((b["a"], adim))
    gezilen: set[str] = set()
    for kok in [mekan.get("giris"), *idler]:
        if kok not in komsu or kok in gezilen:
            continue
        if kok not in konum:
            alt = max((v[1] for v in konum.values()), default=-8.0) + 8
            konum[kok] = [0.0, alt]
        gezilen.add(kok)
        kuyruk = deque([(kok, None)])
        while kuyruk:
            u, ebeveyn = kuyruk.popleft()
            ux, uy = konum[u]
            temel = math.atan2(uy - konum[ebeveyn][1], ux - konum[ebeveyn][0]) if ebeveyn else 0.0
            yerlesecek = [(v, a) for v, a in komsu[u] if v not in konum]
            for i, (v, adim) in enumerate(yerlesecek):
                sira = (i + 1) // 2 * (1 if i % 2 else -1)
                aci = temel + sira * math.radians(60)
                konum[v] = [round(ux + math.cos(aci) * adim / olc, 1), round(uy + math.sin(aci) * adim / olc, 1)]
            for v, _ in komsu[u]:
                if v not in gezilen:
                    gezilen.add(v)
                    kuyruk.append((v, u))
    return {i: konum[i] for i in idler if i in konum}


def gorunum_noktalari(mekan: dict, plan: dict, gorunum: str | None, kat: int | None) -> set[str]:
    """Bir çizimde görünen noktalar: dış çizimde binalara bağlı olmayanlar (seçili kat), bina çiziminde o
    binanın odaları ve binanın kendisi (girişi)."""
    ust = plan.get("ust") or {}
    if gorunum:
        return {gorunum} | {i for i, u in ust.items() if u == gorunum}
    return {n["id"] for n in mekan.get("noktalar") or []
            if n["id"] not in ust and (kat is None or (n.get("kat") or 0) == kat)}


# ── Değişiklikler (mekan ve plan yerinde değiştirilir) ────

def _yeni_kimlik(mekan: dict, ad: str) -> str:
    govde = bm.kisalt(ad) or "nokta"
    var = {n["id"] for n in mekan["noktalar"]}
    kimlik, i = govde, 2
    while kimlik in var:
        kimlik, i = f"{govde}-{i}", i + 1
    return kimlik


def _adim(konum: dict, a: str, b: str, olc: float) -> int:
    return max(1, round(math.dist(konum[a], konum[b]) * olc))


def bagla(mekan: dict, plan: dict, a: str, b: str, olc: float, gorunum: str | None = None) -> bool:
    """İki modül arasına yürüme yolu ekler; adım çizimdeki mesafeden. Yol zaten varsa bir şey yapmaz."""
    if a == b or any({y["a"], y["b"]} == {a, b} for y in mekan["baglantilar"]):
        return False
    konum = gorunum_konumlari(plan, gorunum)
    adlar = {n["id"]: n["ad"] for n in mekan["noktalar"]}
    mekan["baglantilar"].append({
        "a": a, "b": b, "adim": _adim(konum, a, b, olc) if a in konum and b in konum else YENI_MESAFE,
        "tarif": f"{adlar[b]} yönüne ilerleyin", "geriTarif": f"{adlar[a]} yönüne ilerleyin"})
    return True


def modul_ekle(mekan: dict, plan: dict, tur: str, ad: str, *, yer: list[float], ust: str | None,
               baglanacak: str | None, olc: float, kat: int = 0) -> str:
    """Yeni modül: nokta (+ hedef türlerinde hedef), çizimdeki yeri ve isteğe bağlı olarak seçili modüle yol."""
    ad = ad.strip() or MODULLER[tur][0]
    nokta_adi = f"{ad} girişi" if tur == "bina" else f"{ad} kapısı" if tur == "oda" else ad
    kimlik = _yeni_kimlik(mekan, ad)
    nokta = {"id": kimlik, "ad": nokta_adi}
    if kat:
        nokta["kat"] = kat
    mekan["noktalar"].append(nokta)
    plan.setdefault("konum", {})[kimlik] = [round(yer[0], 1), round(yer[1], 1)]
    plan.setdefault("tur", {})[kimlik] = tur
    if ust:
        plan.setdefault("ust", {})[kimlik] = ust
    if tur in HEDEF_MODULLERI:
        kucuk = ad.replace("I", "ı").replace("İ", "i").lower()
        sozcukler = [w for w in kucuk.split() if len(w) >= 3]
        mekan["hedefler"].append({"ad": ad, "nokta": kimlik, "tarif": f"{nokta_adi} burada.",
                                  "anahtarlar": list(dict.fromkeys([kucuk, *sozcukler,
                                                                    *ANAHTAR_EKLERI.get(tur, [])]))})
    if not mekan.get("giris"):
        mekan["giris"] = kimlik
    if baglanacak:
        bagla(mekan, plan, baglanacak, kimlik, olc, ust)
    return kimlik


def tasi(mekan: dict, plan: dict, kimlik: str, x: float, y: float, olc: float,
         gorunum: str | None = None) -> list[tuple[str, str, int]]:
    """Modülü taşır; ona bağlı yürüme yollarının adımı yeni mesafeden hesaplanır. Değişen yollar döner."""
    if gorunum and kimlik == gorunum:
        plan.setdefault("icKonum", {})[kimlik] = [round(x, 1), round(y, 1)]
    else:
        plan.setdefault("konum", {})[kimlik] = [round(x, 1), round(y, 1)]
    konum = gorunum_konumlari(plan, gorunum)
    sabit = {tuple(y) for y in plan.get("sabitAdim") or []}   # sahada sayılıp elle yazılan adımlar
    degisen = []
    for b in mekan["baglantilar"]:
        if (b["a"], b["b"]) in sabit:
            continue
        if kimlik in (b["a"], b["b"]) and (b.get("tur") or "yuru") not in bm.DIKEY_GECISLER \
                and b["a"] in konum and b["b"] in konum:
            yeni = _adim(konum, b["a"], b["b"], olc)
            if yeni != b.get("adim"):
                b["adim"] = yeni
                degisen.append((b["a"], b["b"], yeni))
    return degisen


def nokta_sil(mekan: dict, plan: dict, kimlik: str) -> None:
    """Modülü, ona bağlı yolları ve hedefleri siler; bina silinince içindeki odalar da silinir."""
    ust = plan.get("ust") or {}
    silinecek = {kimlik} | {i for i, u in ust.items() if u == kimlik}
    mekan["noktalar"] = [n for n in mekan["noktalar"] if n["id"] not in silinecek]
    mekan["baglantilar"] = [b for b in mekan["baglantilar"] if b["a"] not in silinecek and b["b"] not in silinecek]
    mekan["hedefler"] = [h for h in mekan["hedefler"] if h["nokta"] not in silinecek]
    for alan in ("konum", "tur", "ust"):
        for i in silinecek:
            (plan.get(alan) or {}).pop(i, None)
    if mekan.get("giris") in silinecek:
        mekan["giris"] = mekan["noktalar"][0]["id"] if mekan["noktalar"] else ""
    if mekan.get("kasa") in silinecek:
        mekan["kasa"] = None


def yol_sil(mekan: dict, a: str, b: str) -> None:
    mekan["baglantilar"] = [y for y in mekan["baglantilar"] if {y["a"], y["b"]} != {a, b}]


def modul_turu(mekan: dict, plan: dict, kimlik: str) -> str:
    """Kayıtlı tür; yoksa adından ya da hedef olup olmamasından tahmin."""
    tur = (plan.get("tur") or {}).get(kimlik)
    if tur:
        return tur
    if kimlik in (plan.get("ust") or {}).values():
        return "bina"
    ad = next((n["ad"] for n in mekan["noktalar"] if n["id"] == kimlik), "").lower()
    for anahtar, sozler in (("asansor", ("asansör",)), ("merdiven", ("merdiven",)), ("wc", ("tuvalet", "wc")),
                            ("danisma", ("danışma",)), ("kavsak", ("kavşak", "koridor", "giriş"))):
        if any(s in ad for s in sozler):
            return anahtar
    return "oda" if any(h["nokta"] == kimlik for h in mekan["hedefler"]) else "kavsak"


# ── Çizim bileşeni (Streamlit özel bileşeni, CCv2) ────────

_HTML = """
<div class="cizim">
  <div class="arac">
    <button type="button" class="bagla" aria-pressed="false" title="İki modüle sırayla tıklayın">Bağla</button>
    <button type="button" class="sigdir" title="Tüm çizimi ekrana sığdır">Sığdır</button>
    <span class="ipucu" aria-live="polite"></span>
  </div>
  <svg role="application" aria-label="Bina çizimi" tabindex="-1"></svg>
</div>
"""

_CSS = """
.cizim { font-family: var(--st-font); color: var(--st-text-color); }
.arac { display: flex; gap: .5rem; align-items: center; margin-bottom: .5rem; flex-wrap: wrap; }
.arac button { font: inherit; padding: .3rem .8rem; border-radius: var(--st-button-radius, .5rem);
  border: 1px solid var(--st-border-color); background: var(--st-background-color); color: inherit;
  cursor: pointer; }
.arac button[aria-pressed="true"] { background: var(--st-primary-color); color: #fff;
  border-color: var(--st-primary-color); }
.ipucu { font-size: .875rem; opacity: .75; }
svg { width: 100%; height: 540px; display: block; touch-action: none; user-select: none;
  background-color: var(--st-secondary-background-color); border-radius: var(--st-base-radius, .5rem);
  border: 1px solid var(--st-border-color); cursor: grab; }
svg.suruk { cursor: grabbing; }
.yol { stroke: var(--st-text-color); opacity: .45; }
.yol.dikey { stroke-dasharray: 4 4; }
.yol.secili { stroke: var(--st-primary-color); opacity: 1; }
.yolvurus { stroke: transparent; cursor: pointer; }
.adim { fill: var(--st-text-color); opacity: .8; paint-order: stroke;
  stroke: var(--st-secondary-background-color); text-anchor: middle; dominant-baseline: central; }
.modul { cursor: pointer; }
.modul rect { fill: var(--st-background-color); stroke: var(--st-border-color); }
.modul.hedef rect { stroke: var(--st-text-color); }
.modul.bina rect { fill: var(--st-primary-color); fill-opacity: .14; stroke: var(--st-primary-color); }
.modul.giris rect { stroke: var(--st-green-color, #21c354); }
.modul.secili rect, .modul:focus rect { stroke: var(--st-primary-color); }
.modul.kaynak rect { stroke: var(--st-primary-color); stroke-dasharray: 3 2; }
.modul:focus { outline: none; }
.modul text { fill: var(--st-text-color); dominant-baseline: central; }
"""

_JS = """
const durumlar = new WeakMap()
const NS = "http://www.w3.org/2000/svg"
const SIMGE = {bina: "▣", oda: "□", kavsak: "◇", danisma: "ⓘ", wc: "WC", asansor: "⇅", merdiven: "≡"}

function el(ad, ozellik, ust) {
  const e = document.createElementNS(NS, ad)
  for (const [k, v] of Object.entries(ozellik)) e.setAttribute(k, v)
  if (ust) ust.appendChild(e)
  return e
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const svg = parentElement.querySelector("svg")
  const baglaBtn = parentElement.querySelector(".bagla")
  const sigdirBtn = parentElement.querySelector(".sigdir")
  const ipucu = parentElement.querySelector(".ipucu")
  if (!svg) return

  let d = durumlar.get(parentElement)
  if (!d) {
    d = { vb: null, gorunum: null, bagla: false, kaynak: null }
    durumlar.set(parentElement, d)
  }
  const dugumler = (data.dugumler || []).map(n => ({ ...n }))
  const yollar = data.yollar || []
  const bul = id => dugumler.find(n => n.id === id)

  function sigdir() {
    if (!dugumler.length) { d.vb = { x: -20, y: -15, w: 40, h: 30 }; return }
    const xs = dugumler.map(n => n.x), ys = dugumler.map(n => n.y)
    const kenar = 8
    let x0 = Math.min(...xs) - kenar, x1 = Math.max(...xs) + kenar
    let y0 = Math.min(...ys) - kenar, y1 = Math.max(...ys) + kenar
    const oran = (svg.clientWidth || 800) / (svg.clientHeight || 540)
    let w = x1 - x0, h = y1 - y0
    if (w / h < oran) { const yw = h * oran; x0 -= (yw - w) / 2; w = yw } else { const yh = w / oran; y0 -= (yh - h) / 2; h = yh }
    d.vb = { x: x0, y: y0, w, h }
  }
  // Başka çizime geçilince ya da görüş alanı dışına yeni modül eklenince çizim yeniden sığdırılır
  const idler = dugumler.map(n => n.id).join("|")
  if (d.gorunum !== data.gorunum) { d.gorunum = data.gorunum; d.vb = null }
  else if (d.vb && d.idler !== idler && dugumler.some(n => n.x < d.vb.x || n.x > d.vb.x + d.vb.w ||
                                                           n.y < d.vb.y || n.y > d.vb.y + d.vb.h)) d.vb = null
  d.idler = idler

  function ciz() {
    if (!d.vb) sigdir()
    const { x, y, w, h } = d.vb
    svg.setAttribute("viewBox", `${x} ${y} ${w} ${h}`)
    const k = (svg.clientWidth || 800) / w       // piksel / birim
    const px = p => p / k
    svg.replaceChildren()
    const katman = el("g", {}, svg)
    for (const yol of yollar) {
      const a = bul(yol.a), b = bul(yol.b)
      if (!a || !b) continue
      const secili = data.seciliYol && data.seciliYol[0] === yol.a && data.seciliYol[1] === yol.b
      el("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: "yol" + (yol.dikey ? " dikey" : "") + (secili ? " secili" : ""),
        "stroke-width": px(secili ? 3 : 2) }, katman)
      const vurus = el("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: "yolvurus", "stroke-width": px(14) }, katman)
      vurus.onclick = e => { e.stopPropagation(); setTriggerValue("olay", { tur: "secyol", a: yol.a, b: yol.b }) }
      const t = el("text", { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, class: "adim", "font-size": px(12),
        "stroke-width": px(4) }, katman)
      t.textContent = yol.dikey ? yol.etiket : `${yol.adim} adım`
    }
    for (const n of dugumler) {
      const sinif = ["modul", n.tur, n.hedef ? "hedef" : "", n.giris ? "giris" : "",
        n.id === data.secili ? "secili" : "", n.id === d.kaynak ? "kaynak" : ""].join(" ")
      const g = el("g", { class: sinif, transform: `translate(${n.x} ${n.y})`, tabindex: 0, role: "button",
        "aria-label": `${n.ad}${n.icerik ? `, içinde ${n.icerik} oda` : ""}`, "data-id": n.id }, katman)
      const yazi = (SIMGE[n.tur] || "") + " " + n.ad + (n.icerik ? ` (${n.icerik})` : "")
      const gen = px(Math.max(70, yazi.length * 7.2 + 20)), yuk = px(n.tur === "bina" ? 40 : 28)
      el("rect", { x: -gen / 2, y: -yuk / 2, width: gen, height: yuk, rx: px(n.tur === "bina" ? 6 : 14),
        "stroke-width": px(n.id === data.secili ? 3 : 1.5) }, g)
      const t = el("text", { x: 0, y: 0, "font-size": px(13), "text-anchor": "middle",
        "font-weight": n.tur === "bina" ? 600 : 400 }, g)
      t.textContent = yazi
      g.onpointerdown = e => surukBasla(e, n)
      g.onkeydown = e => tus(e, n)
    }
    baglaBtn.setAttribute("aria-pressed", String(d.bagla))
    ipucu.textContent = d.bagla
      ? (d.kaynak ? `${bul(d.kaynak)?.ad ?? ""} seçildi; bağlanacak ikinci modüle tıklayın.` : "Bağlanacak ilk modüle tıklayın.")
      : `Modülleri sürükleyerek yerleştirin; 1 kare = ${data.olcek} adım. Tekerlekle yakınlaştırın, boş yeri sürükleyerek kaydırın.`
  }

  function svgNokta(e) {
    const p = svg.createSVGPoint()
    p.x = e.clientX; p.y = e.clientY
    return p.matrixTransform(svg.getScreenCTM().inverse())
  }

  function surukBasla(e, n) {
    e.stopPropagation()
    const bas = svgNokta(e), ilk = { x: n.x, y: n.y }
    let oynadi = false
    svg.setPointerCapture(e.pointerId)
    svg.classList.add("suruk")
    svg.onpointermove = m => {
      const p = svgNokta(m)
      const dx = p.x - bas.x, dy = p.y - bas.y
      if (!oynadi && Math.hypot(dx, dy) * ((svg.clientWidth || 800) / d.vb.w) < 4) return
      oynadi = true
      n.x = Math.round((ilk.x + dx) * 2) / 2
      n.y = Math.round((ilk.y + dy) * 2) / 2
      ciz()
    }
    svg.onpointerup = () => {
      svg.onpointermove = null; svg.onpointerup = null
      svg.classList.remove("suruk")
      if (oynadi) { setTriggerValue("olay", { tur: "tasi", id: n.id, x: n.x, y: n.y }); return }
      tikla(n)
    }
  }

  function tikla(n) {
    if (d.bagla) {
      if (!d.kaynak) { d.kaynak = n.id; ciz(); return }
      const a = d.kaynak
      d.kaynak = null
      if (a !== n.id) setTriggerValue("olay", { tur: "bagla", a, b: n.id })
      ciz()
      return
    }
    setTriggerValue("olay", { tur: "sec", id: n.id })
  }

  // Klavye: oklar modülü 1 kare (Shift ile 5) taşır, Enter seçer
  let tusZaman = null
  function tus(e, n) {
    const adim = e.shiftKey ? 5 : 1
    const yon = { ArrowLeft: [-adim, 0], ArrowRight: [adim, 0], ArrowUp: [0, -adim], ArrowDown: [0, adim] }[e.key]
    if (yon) {
      e.preventDefault()
      n.x += yon[0]; n.y += yon[1]
      ciz()
      svg.querySelector(`[data-id="${CSS.escape(n.id)}"]`)?.focus({ preventScroll: true })
      clearTimeout(tusZaman)
      tusZaman = setTimeout(() => setTriggerValue("olay", { tur: "tasi", id: n.id, x: n.x, y: n.y }), 500)
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault()
      tikla(n)
    }
  }

  svg.onpointerdown = e => {
    if (e.target !== svg && e.target.closest(".modul")) return
    const bas = { x: e.clientX, y: e.clientY }, vb0 = { ...d.vb }
    let oynadi = false
    svg.setPointerCapture(e.pointerId)
    svg.onpointermove = m => {
      const k = (svg.clientWidth || 800) / d.vb.w
      const dx = (m.clientX - bas.x) / k, dy = (m.clientY - bas.y) / k
      if (Math.hypot(dx, dy) * k > 3) oynadi = true
      d.vb = { ...vb0, x: vb0.x - dx, y: vb0.y - dy }
      ciz()
    }
    svg.onpointerup = () => {
      svg.onpointermove = null; svg.onpointerup = null
      if (!oynadi && (data.secili || data.seciliYol)) setTriggerValue("olay", { tur: "bos" })
    }
  }
  svg.onwheel = e => {
    e.preventDefault()
    const p = svgNokta(e), f = e.deltaY > 0 ? 1.15 : 1 / 1.15
    d.vb = { x: p.x - (p.x - d.vb.x) * f, y: p.y - (p.y - d.vb.y) * f, w: d.vb.w * f, h: d.vb.h * f }
    ciz()
  }
  baglaBtn.onclick = () => { d.bagla = !d.bagla; d.kaynak = null; ciz() }
  sigdirBtn.onclick = () => { d.vb = null; ciz() }

  ciz()
}
"""

_CIZIM = st.components.v2.component("bak_cizim", html=_HTML, css=_CSS, js=_JS)


def cizim(veri: dict, *, key: str, on_olay: Callable[[], None]):
    """Çizim bileşeni. veri: dugumler, yollar, secili, seciliYol, olcek, gorunum. Olaylar on_olay ile gelir."""
    return _CIZIM(data=veri, key=key, on_olay_change=on_olay)

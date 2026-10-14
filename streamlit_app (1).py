"""SecondLife Grid - Streamlit version. Gemini key comes from st.secrets (server-side only)."""
import base64, io, json, os, requests, streamlit as st
from PIL import Image

st.set_page_config(page_title="SecondLife Grid", page_icon="♻️", layout="wide")
st.markdown("""<style>
h1,h2,h3{color:#0f3d2a} .stButton>button,.stFormSubmitButton>button{background:#1f6b47;color:#fff;border:0;border-radius:99px;font-weight:700}
.stButton>button:hover{background:#0f3d2a;color:#fff} [data-testid=stMetricValue]{color:#1f6b47}
</style>""", unsafe_allow_html=True)

CATS = ["Textiles","Wood","Metal","Plastic","Glass","Paper & Cardboard","Electronics","Construction","Packaging","Other"]
CONDS = ["Like new","Good","Fair","Needs repair"]
UNITS = ["kg","pieces","sheets","metres","litres","pallets","bags"]
ICON = dict(zip(CATS, "🧵🪵🔩🧴🫙📦🔌🧱🛍️♻️".replace("🛍️","🛍").replace("♻️","♻")))
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

def L(i,t,n,c,d,cd,ideas,q,u,city,pin,status="available",rq=None,ra=None):
    return dict(id=i,demo=True,title=t,name=n,category=c,description=d,condition=cd,ideas=ideas,qty=q,unit=u,city=city,pin=pin,image=None,status=status,reused_qty=rq,reused_at=ra)
DEMO = [
 L("d1","Cotton fabric offcuts from a tailoring unit","Cotton offcuts","Textiles","Mixed-colour cotton scraps, clean and dry.","Good",["Patchwork quilts","Cushion stuffing"],40,"kg","Pune","411001"),
 L("d2","Pine pallet wood, dismantled","Pine pallet boards","Wood","Dismantled boards with some nail holes.","Fair",["Garden planters","Shelving"],25,"pieces","Pune","411014"),
 L("d3","Aluminium sheet trimmings","Aluminium trimmings","Metal","Clean off-cuts from a fabrication workshop.","Good",["Scrap resale","Signage"],120,"kg","Mumbai","400070"),
 L("d4","Glass jars with lids","Glass jars","Glass","Washed jars, assorted sizes.","Like new",["Food storage","Candle making"],200,"pieces","Bengaluru","560001"),
 L("d5","Corrugated cardboard boxes","Cardboard boxes","Paper & Cardboard","Flat-packed boxes in good shape.","Good",["Shipping reuse","Compost layering"],80,"pieces","Mumbai","400001","reused",80,"2026-09-20"),
 L("d6","Reclaimed floor tiles","Ceramic tiles","Construction","Leftover tiles, one colour batch.","Like new",["Patio floor","Mosaic art"],60,"pieces","Pune","411045","reused",60,"2026-10-02"),
]
BUYERS = [
 ("Stitch & Story Collective","Textile upcycling studio",["Textiles"],"Pune","411004"),
 ("GreenGrain Furniture","Reclaimed-wood workshop",["Wood","Construction"],"Pune","411016"),
 ("MetalLoop Recyclers","Metal recycler",["Metal","Electronics"],"Mumbai","400072"),
 ("Jar & Wick Candles","Small-batch maker",["Glass","Packaging"],"Bengaluru","560008"),
 ("City Maker Space","Community workshop",["Wood","Metal","Plastic","Electronics","Construction","Other"],"Mumbai","400051"),
 ("PulpWorks Paper Mill","Paper recycler",["Paper & Cardboard","Textiles"],"Pune","411019"),
 ("Plastic Reborn Co-op","Plastic reprocessor",["Plastic","Packaging"],"Bengaluru","560034"),
]

SCHEMA = {"type":"OBJECT","properties":{"materialName":{"type":"STRING"},"category":{"type":"STRING","enum":CATS},
 "description":{"type":"STRING"},"conditionEstimate":{"type":"STRING","enum":CONDS},
 "reuseIdeas":{"type":"ARRAY","items":{"type":"STRING"}},"suggestedTitle":{"type":"STRING"}},
 "required":["materialName","category","description","conditionEstimate","reuseIdeas","suggestedTitle"]}
PROMPT = """You help list reusable waste and surplus materials on a circular-economy marketplace.
Analyze the photo and return JSON only. Rules:
- Describe only what is visibly present. Never state or estimate weight, volume, count or dimensions; the seller enters quantity separately.
- conditionEstimate is a visual estimate only.
- reuseIdeas: 3 to 5 short, practical ideas.
- suggestedTitle: under 70 characters, no quantity claims.
- If the image does not show a reusable material, use category "Other" and say so in the description."""

def api_key():
    try: return st.secrets["GEMINI_API_KEY"]
    except Exception: return os.getenv("GEMINI_API_KEY")

def shrink(raw, max_side=900):
    im = Image.open(io.BytesIO(raw)).convert("RGB"); im.thumbnail((max_side, max_side))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=82); return buf.getvalue()

def analyze(jpeg, hint):
    key = api_key()
    if not key: raise RuntimeError("AI is not configured. Add GEMINI_API_KEY in the app's Secrets.")
    text = PROMPT + (f'\nThe seller selected "{hint}"; use it only if it fits the photo.' if hint in CATS else "")
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"}, timeout=60,
        json={"contents":[{"parts":[{"text":text},{"inline_data":{"mime_type":"image/jpeg","data":base64.b64encode(jpeg).decode()}}]}],
              "generationConfig":{"responseMimeType":"application/json","responseSchema":SCHEMA,"temperature":0.3}})
    if r.status_code == 429: raise RuntimeError("The AI service is busy. Try again shortly.")
    if not r.ok: raise RuntimeError("The AI service could not analyze this image.")
    try: p = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
    except Exception: raise RuntimeError("The AI returned no usable result. Try a clearer photo.")
    p["category"] = p["category"] if p.get("category") in CATS else "Other"
    p["conditionEstimate"] = p["conditionEstimate"] if p.get("conditionEstimate") in CONDS else "Fair"
    return p

ss = st.session_state
ss.setdefault("listings", [dict(x) for x in DEMO]); ss.setdefault("draft", None); ss.setdefault("did", 0)

def card(l, key, record=False):
    with st.container(border=True):
        if l["image"]: st.image(l["image"], use_container_width=True)
        else: st.markdown(f"<div style='font-size:3rem;text-align:center'>{ICON[l['category']]}</div>", unsafe_allow_html=True)
        st.markdown(f"**{l['title']}**" + ("  `Demo`" if l["demo"] else ""))
        st.caption(f"{l['category']} · {l['condition']} · {l['city']} {l['pin']}")
        st.markdown(f"**{l['qty']} {l['unit']}** (seller-entered)")
        st.write(l["description"]); 
        if l["ideas"]: st.caption("Reuse ideas: " + ", ".join(l["ideas"]))
        if l["status"] == "reused": st.success(f"Reused: {l['reused_qty']} {l['unit']} on {l['reused_at']}")
        elif record:
            with st.expander("Record reuse"):
                q = st.number_input("Quantity reused", 1.0, value=float(l["qty"]), key=f"rq_{key}")
                if st.button("Save reuse", key=f"rs_{key}"):
                    l.update(status="reused", reused_qty=q, reused_at=__import__("datetime").date.today().isoformat()); st.rerun()

st.title("♻️ SecondLife Grid")
st.caption("One business's leftovers are another's raw material.")
tabs = st.tabs(["Home","List a material","Marketplace","Smart Match","Impact"])
avail = [l for l in ss.listings if l["status"] != "reused"]

with tabs[0]:
    a,b,c = st.columns(3)
    a.metric("Available listings", len(avail)); b.metric("Cities", len({l['city'] for l in ss.listings}))
    c.metric("Recorded reuses", len(ss.listings) - len(avail))
    st.markdown("**How it works:** upload a photo → enter the quantity yourself → review the AI draft → publish → find buyers → record the reuse.")
    cols = st.columns(3)
    for i,l in enumerate(avail[:3]):
        with cols[i]: card(l, f"home{i}")

with tabs[1]:
    st.subheader("List a material")
    left, right = st.columns(2)
    with left:
        up = st.file_uploader("Photo", type=["jpg","jpeg","png","webp"])
        if up: st.image(up, caption="Preview", use_container_width=True)
    with right:
        cat = st.selectbox("Material category", ["Let AI suggest"] + CATS)
        q1, q2 = st.columns([2,1])
        qty = q1.number_input("Quantity (you enter this)", 0.0, step=1.0); unit = q2.selectbox("Unit", UNITS)
        cond = st.selectbox("Condition", ["Let AI estimate"] + CONDS)
        c1, c2 = st.columns(2); city = c1.text_input("City"); pin = c2.text_input("PIN code", max_chars=6)
        st.caption("AI never estimates weight or volume from a photo. The quantity above is what buyers see.")
        go = st.button("Generate AI Listing", use_container_width=True)
    if go:
        errs = [m for ok,m in [(up,"Add a photo."),(qty>0,"Enter a quantity above 0."),(city.strip(),"Enter a city."),(len(pin)==6 and pin.isdigit(),"Enter a 6-digit PIN code.")] if not ok]
        if errs: st.error(" ".join(errs))
        else:
            try:
                with st.spinner("Analyzing photo…"):
                    jpeg = shrink(up.getvalue()); p = analyze(jpeg, cat)
                ss.did += 1
                ss.draft = dict(p=p, jpeg=jpeg, qty=qty, unit=unit, city=city.strip(), pin=pin, cat=cat, cond=cond)
            except Exception as e: st.error(str(e))
    d = ss.draft
    if d:
        p, k = d["p"], ss.did
        st.divider(); st.subheader("Review and edit"); st.caption("AI can make mistakes. Check every field before publishing.")
        title = st.text_input("Listing title", p["suggestedTitle"], key=f"t{k}")
        name = st.text_input("Material name", p["materialName"], key=f"n{k}")
        c1, c2 = st.columns(2)
        cs = d["cat"] if d["cat"] in CATS else p["category"]; cd = d["cond"] if d["cond"] in CONDS else p["conditionEstimate"]
        fcat = c1.selectbox("Category", CATS, CATS.index(cs), key=f"c{k}"); fcond = c2.selectbox("Condition", CONDS, CONDS.index(cd), key=f"d{k}")
        desc = st.text_area("Description", p["description"], key=f"x{k}")
        ideas = st.text_area("Reuse ideas (one per line)", "\n".join(p["reuseIdeas"]), key=f"i{k}")
        if st.button("Publish listing"):
            if not title.strip() or not name.strip(): st.error("Title and material name are required.")
            else:
                ss.listings.insert(0, dict(id=f"u{k}", demo=False, title=title.strip(), name=name.strip(), category=fcat, description=desc.strip(),
                    condition=fcond, ideas=[s.strip() for s in ideas.split("\n") if s.strip()], qty=d["qty"], unit=d["unit"], city=d["city"],
                    pin=d["pin"], image=d["jpeg"], status="available", reused_qty=None, reused_at=None))
                ss.draft = None; st.success("Published. Open the Marketplace tab."); st.rerun()

with tabs[2]:
    st.subheader("Marketplace")
    f1,f2,f3 = st.columns([2,1,1])
    q = f1.text_input("Search", label_visibility="collapsed", placeholder="Search materials")
    fc = f2.selectbox("Category", ["All categories"] + CATS); fl = f3.selectbox("Location", ["All locations"] + sorted({l["city"] for l in ss.listings}))
    shown = [l for l in avail if (fc.startswith("All") or l["category"] == fc) and (fl.startswith("All") or l["city"] == fl) and q.lower() in (l["title"]+l["name"]+l["description"]).lower()]
    st.caption(f"{len(shown)} available")
    if not shown: st.info("No listings match these filters. Clear a filter or list your own material.")
    cols = st.columns(3)
    for i,l in enumerate(shown):
        with cols[i % 3]: card(l, l["id"], record=True)

with tabs[3]:
    st.subheader("Smart Match"); st.caption("Buyers ranked by material type, then city and PIN area. Buyers are demo profiles.")
    if not avail: st.info("Publish a listing to see matching buyers.")
    else:
        l = avail[[x["title"] for x in avail].index(st.selectbox("Listing", [x["title"] for x in avail]))]
        res = []
        for n,t,acc,c,pn in BUYERS:
            s, why = 0, []
            if l["category"] in acc: s += 3; why.append(f"Accepts {l['category'].lower()}")
            if c.lower() == l["city"].lower(): s += 2; why.append(f"Same city ({c})")
            if pn[:3] == l["pin"][:3]: s += 1; why.append("Nearby PIN area")
            if s >= 3: res.append((s,n,t,c,pn,why))
        for s,n,t,c,pn,why in sorted(res, reverse=True):
            with st.container(border=True): st.markdown(f"**{n}** — {'Strong' if s>=5 else 'Good' if s>=4 else 'Possible'} match"); st.caption(f"{t} · {c} {pn}"); st.write(" • ".join(why))
        if not res: st.info("No buyers accept this material type yet.")

with tabs[4]:
    st.subheader("Impact"); st.caption("Only reuse that someone has recorded is counted.")
    re = [l for l in ss.listings if l["status"] == "reused"]
    units = {}
    for l in re: units[l["unit"]] = units.get(l["unit"], 0) + l["reused_qty"]
    cols = st.columns(max(1, len(units) + 1)); cols[0].metric("Listings reused", len(re))
    for i,(u,n) in enumerate(units.items()): cols[i+1].metric(f"{u} reused", f"{n:g}")
    if re:
        by = {}
        for l in re: by[l["category"]] = by.get(l["category"], 0) + 1
        st.bar_chart(by, color="#2f9462")
    else: st.info("No reuse recorded yet. Open a listing in the Marketplace and choose Record reuse.")
    if st.button("Reset to demo data"): ss.listings = [dict(x) for x in DEMO]; st.rerun()

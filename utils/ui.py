"""Streamlit helpers: cached data loading, the animated agricultural theme and small HTML components.
Everything is pure CSS/SVG/emoji (no external images or scripts), so it also works offline and on Colab."""
import random
import streamlit as st
from utils.data_loader import load_all
from algorithms.propositional_logic import KnowledgeRuleBase

PAGES = {}   # filled by app.py: {"dashboard": st.Page, "advisor": st.Page, ...}

CSS = """
<style>
@keyframes gradShift{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
@keyframes floaty{0%,100%{transform:translateY(0)}50%{transform:translateY(-9px)}}
@keyframes sway{0%,100%{transform:rotate(-4deg)}50%{transform:rotate(4deg)}}
@keyframes drift{from{left:-25%}to{left:110%}}
@keyframes drive{from{left:-80px}to{left:105%}}
@keyframes sunpulse{0%,100%{box-shadow:0 0 35px 12px rgba(255,235,59,.5)}50%{box-shadow:0 0 65px 26px rgba(255,235,59,.8)}}
@keyframes fadeUp{from{opacity:0;transform:translateY(26px)}to{opacity:1;transform:none}}
@keyframes ticker{from{transform:translateX(0)}to{transform:translateX(-50%)}}
@keyframes bob{0%,100%{transform:translateY(0) scaleX(-1)}50%{transform:translateY(-3px) scaleX(-1)}}

.block-container{padding-top:1.4rem;max-width:1250px}

/* ---------- hero ---------- */
.hero{position:relative;overflow:hidden;border-radius:24px;padding:30px 36px 96px 36px;margin-bottom:22px;color:#fff;
  background:linear-gradient(120deg,#1b5e20,#2e7d32,#7cb342,#2e7d32,#1b5e20);background-size:300% 300%;
  animation:gradShift 14s ease infinite;box-shadow:0 8px 0 #145218,0 22px 40px rgba(27,94,32,.35)}
.hero-text{position:relative;z-index:5;max-width:72%}
.hero-text h1{color:#fff;margin:0 0 8px 0;font-size:2.15rem;line-height:1.15;text-shadow:0 3px 8px rgba(0,0,0,.3)}
.hero-text p{color:#f1f8e9;margin:0;font-size:1.05rem;text-shadow:0 2px 5px rgba(0,0,0,.25)}
.hero-emoji{font-size:2.6rem;display:inline-block;animation:floaty 3s ease-in-out infinite;filter:drop-shadow(0 6px 5px rgba(0,0,0,.3))}
.sun{position:absolute;top:22px;right:46px;width:78px;height:78px;border-radius:50%;z-index:2;
  background:radial-gradient(circle at 35% 35%,#fffde7,#ffca28 60%,#fb8c00);animation:sunpulse 4s ease-in-out infinite}
.cloud{position:absolute;z-index:3;width:90px;height:30px;background:#fff;border-radius:30px;opacity:.85;animation:drift 38s linear infinite}
.cloud:before,.cloud:after{content:"";position:absolute;background:#fff;border-radius:50%}
.cloud:before{width:44px;height:44px;top:-22px;left:12px}.cloud:after{width:34px;height:34px;top:-15px;left:46px}
.c1{top:26px;animation-duration:42s}.c2{top:70px;transform:scale(.7);animation-duration:55s;animation-delay:-20s}
.scene{position:absolute;left:0;right:0;bottom:0;width:100%;height:92px;z-index:4}
.stalk{transform-box:fill-box;transform-origin:50% 100%;animation:sway 3s ease-in-out infinite}
.tractor{position:absolute;bottom:8px;font-size:2.1rem;z-index:6;animation:drive 24s linear infinite,bob .5s ease-in-out infinite;
  transform:scaleX(-1);filter:drop-shadow(0 4px 3px rgba(0,0,0,.35))}

/* ---------- 3D tiles & cards ---------- */
.tile{background:linear-gradient(145deg,#ffffff,#e8f5e9);border-radius:18px;padding:16px 12px;text-align:center;color:#1b3a1e;
  border:1px solid #c8e6c9;box-shadow:0 6px 0 #a5d6a7,0 14px 24px rgba(27,94,32,.22);animation:fadeUp .7s both;
  transition:transform .3s cubic-bezier(.2,.8,.2,1),box-shadow .3s;margin-bottom:10px}
.tile:hover{transform:perspective(800px) translateY(-8px) rotateX(7deg) rotateY(-4deg);box-shadow:0 11px 0 #81c784,0 24px 32px rgba(27,94,32,.32)}
.tico{font-size:1.9rem;display:inline-block;animation:floaty 3s ease-in-out infinite}
.tval{font-size:1.65rem;font-weight:800;color:#1b5e20;line-height:1.2}
.tlab{font-weight:700;font-size:.95rem}.tsub{font-size:.76rem;opacity:.75}

.card3d{position:relative;background:linear-gradient(150deg,#ffffff,#f1f8e9);border-radius:20px;padding:22px 20px 16px 20px;color:#1b3a1e;
  border:1px solid #dcedc8;border-top:7px solid var(--acc,#2e7d32);min-height:168px;animation:fadeUp .8s both;
  box-shadow:0 8px 0 #c5e1a5,0 18px 30px rgba(27,94,32,.25);transition:transform .35s cubic-bezier(.2,.8,.2,1),box-shadow .35s;margin-bottom:8px}
.card3d:hover{transform:perspective(900px) translateY(-12px) rotateX(5deg) rotateY(-5deg) scale(1.02);
  box-shadow:0 14px 0 #aed581,0 32px 44px rgba(27,94,32,.35)}
.card3d .ico{font-size:3rem;display:inline-block;animation:floaty 3s ease-in-out infinite;filter:drop-shadow(0 7px 4px rgba(0,0,0,.25))}
.card3d h3{margin:6px 0 4px 0;color:#1b5e20;font-size:1.25rem}.card3d p{margin:0;font-size:.93rem;color:#33523a}

.step{background:linear-gradient(145deg,#fffde7,#fff8e1);border:1px solid #ffe082;border-radius:16px;padding:14px 16px;color:#4e342e;
  box-shadow:0 5px 0 #ffe082,0 10px 18px rgba(0,0,0,.12);animation:fadeUp .8s both;font-size:.95rem}
.step b.n{display:inline-block;width:30px;height:30px;line-height:30px;text-align:center;border-radius:50%;background:#2e7d32;color:#fff;margin-right:8px;
  box-shadow:0 3px 0 #1b5e20}

.marquee{overflow:hidden;border-radius:14px;background:linear-gradient(90deg,#fffde7,#f1f8e9);border:1px solid #dcedc8;padding:9px 0;margin:6px 0 16px 0}
.marquee-in{display:flex;gap:46px;width:max-content;animation:ticker 32s linear infinite;color:#33523a;font-weight:700;font-size:1.02rem}

.sect{display:flex;align-items:center;gap:10px;margin:22px 0 8px 0;font-size:1.3rem;font-weight:800;color:#2e7d32}
.sect .badge{display:inline-flex;align-items:center;justify-content:center;min-width:34px;height:34px;border-radius:50%;background:#2e7d32;color:#fff;
  font-size:1rem;box-shadow:0 4px 0 #1b5e20}
.fact{background:linear-gradient(145deg,#e3f2fd,#ffffff);border:1px solid #bbdefb;border-left:6px solid #0288d1;border-radius:14px;padding:12px 16px;color:#0d3c61;
  box-shadow:0 5px 0 #bbdefb;margin-bottom:10px;animation:fadeUp .8s both}
.note{background:#fffde7;border:1px solid #fff59d;border-left:5px solid #f9a825;padding:10px 14px;border-radius:12px;font-size:.92rem;color:#3e3e3e;margin-top:10px}

/* ---------- buttons (3D press effect) ---------- */
a[data-testid="stPageLink-NavLink"]{background:linear-gradient(180deg,#43a047,#2e7d32);border-radius:12px;justify-content:center;
  box-shadow:0 5px 0 #1b5e20,0 10px 16px rgba(0,0,0,.2);transition:transform .15s,box-shadow .15s;padding:.5rem .8rem}
a[data-testid="stPageLink-NavLink"]:hover{transform:translateY(-3px);box-shadow:0 8px 0 #1b5e20,0 14px 20px rgba(0,0,0,.25)}
a[data-testid="stPageLink-NavLink"]:active{transform:translateY(4px);box-shadow:0 1px 0 #1b5e20}
a[data-testid="stPageLink-NavLink"] p,a[data-testid="stPageLink-NavLink"] span{color:#fff!important;font-weight:800}
button[kind="primary"],button[data-testid="stBaseButton-primary"],button[data-testid="stBaseButton-primaryFormSubmit"]{
  background:linear-gradient(180deg,#43a047,#2e7d32)!important;border:0!important;border-radius:12px!important;color:#fff!important;font-weight:800!important;
  box-shadow:0 5px 0 #1b5e20,0 10px 16px rgba(0,0,0,.2)!important;transition:transform .15s,box-shadow .15s!important}
button[kind="primary"]:hover,button[data-testid="stBaseButton-primary"]:hover,button[data-testid="stBaseButton-primaryFormSubmit"]:hover{
  transform:translateY(-3px);box-shadow:0 8px 0 #1b5e20,0 14px 20px rgba(0,0,0,.25)!important}
button[kind="primary"]:active,button[data-testid="stBaseButton-primary"]:active,button[data-testid="stBaseButton-primaryFormSubmit"]:active{
  transform:translateY(4px);box-shadow:0 1px 0 #1b5e20!important}
button[kind="secondary"],button[data-testid="stBaseButton-secondary"]{border-radius:999px!important;border:2px solid #a5d6a7!important;
  transition:transform .15s,box-shadow .15s}
button[kind="secondary"]:hover,button[data-testid="stBaseButton-secondary"]:hover{transform:translateY(-2px);box-shadow:0 5px 12px rgba(46,125,50,.3)}

/* ---------- misc ---------- */
div[data-testid="stMetric"]{background:linear-gradient(145deg,#ffffff,#e8f5e9);border:1px solid #c8e6c9;padding:12px 16px;border-radius:16px;
  box-shadow:0 5px 0 #a5d6a7,0 10px 18px rgba(27,94,32,.15);animation:fadeUp .6s both}
div[data-testid="stMetric"] label,div[data-testid="stMetric"] div,div[data-testid="stMetric"] p{color:#1b3a1e!important}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#1b5e20 0%,#2e7d32 55%,#33691e 100%)}
section[data-testid="stSidebar"] *{color:#f1f8e9}
.brand{text-align:center;padding:6px 0 2px 0}.brand .b1{font-size:2.6rem;display:inline-block;animation:floaty 3s ease-in-out infinite}
.brand .b2{font-weight:800;font-size:1.25rem;color:#fff}.brand .b3{font-size:.8rem;opacity:.85}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
@media (max-width:800px){.hero-text{max-width:100%}.sun{display:none}.hero-text h1{font-size:1.6rem}}
</style>
"""


def _wheat_scene() -> str:
    """Inline SVG: rolling hills + swaying wheat stalks (single line: Markdown must not see blank lines)."""
    r = random.Random(7)
    parts = ['<svg class="scene" viewBox="0 0 1200 92" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">',
             '<path d="M0 60 Q200 22 420 54 T820 46 T1200 52 V92 H0Z" fill="#558b2f" opacity=".55"/>',
             '<path d="M0 74 Q260 44 560 70 T1200 64 V92 H0Z" fill="#33691e" opacity=".85"/>']
    for i in range(78):
        x = 6 + i * 15.4 + r.uniform(-4, 4)
        h = r.uniform(30, 54)
        d = round(r.uniform(0, 2.6), 2)
        top = 92 - h
        g = [f'<g class="stalk" style="animation-delay:{d}s"><line x1="{x:.1f}" y1="92" x2="{x:.1f}" y2="{top:.1f}" stroke="#d4a017" stroke-width="2"/>']
        for k, ang in enumerate((-28, 0, 28)):
            cy = top + 4 + k * 5
            g.append(f'<ellipse cx="{x:.1f}" cy="{cy:.1f}" rx="2.6" ry="5.5" fill="#f4c542" transform="rotate({ang} {x:.1f} {cy:.1f})"/>')
        g.append('</g>')
        parts.append("".join(g))
    parts.append("</svg>")
    return "".join(parts)


WHEAT_SCENE = _wheat_scene()


def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title, text, emoji="🌾"):
    html = ('<div class="hero"><div class="sun"></div><div class="cloud c1"></div><div class="cloud c2"></div>'
            f'<div class="hero-text"><div class="hero-emoji">{emoji}</div><h1>{title}</h1><p>{text}</p></div>'
            f'<div class="tractor">🚜</div>{WHEAT_SCENE}</div>')
    st.markdown(html, unsafe_allow_html=True)


def note(text):
    st.markdown(f'<div class="note">{text}</div>', unsafe_allow_html=True)


def section(badge, title):
    st.markdown(f'<div class="sect"><span class="badge">{badge}</span>{title}</div>', unsafe_allow_html=True)


def stat_tile(icon, label, value, sub="", delay=0.0):
    return (f'<div class="tile" style="animation-delay:{delay}s"><div class="tico">{icon}</div><div class="tval">{value}</div>'
            f'<div class="tlab">{label}</div><div class="tsub">{sub}</div></div>')


def nav_card(icon, title, text, accent="#2e7d32", delay=0.0):
    return (f'<div class="card3d" style="--acc:{accent};animation-delay:{delay}s"><div class="ico">{icon}</div>'
            f'<h3>{title}</h3><p>{text}</p></div>')


def go_button(key, label, icon):
    """Clickable page link (works because app.py registers the pages in PAGES)."""
    page = PAGES.get(key)
    if page is not None:
        st.page_link(page, label=label, icon=icon, use_container_width=True)


def marquee(items):
    row = "".join(f"<span>{i}</span>" for i in items)
    st.markdown(f'<div class="marquee"><div class="marquee-in">{row}{row}</div></div>', unsafe_allow_html=True)


def fact(text, delay=0.0):
    st.markdown(f'<div class="fact" style="animation-delay:{delay}s">{text}</div>', unsafe_allow_html=True)


@st.cache_resource(show_spinner="Loading Punjab datasets...")
def get_data():
    return load_all()


@st.cache_resource(show_spinner="Compiling knowledge-base rules...")
def get_rule_base():
    d = get_data()
    return KnowledgeRuleBase(d["kb"], d["table"]["Crop"].unique())


def load_or_stop():
    try:
        return get_data(), get_rule_base()
    except FileNotFoundError as e:
        st.error(f"Dataset file not found. Put the three CSV files in the data/ folder. ({e})")
        st.stop()

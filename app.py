import streamlit as st
import os

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

from database import init_db, get_config, engine_info

init_db()

APP_NOMBRE    = get_config("app_nombre",    "UniControl")
APP_SUBTITULO = get_config("app_subtitulo", "Sistema de Uniformes")

st.set_page_config(
    page_title=APP_NOMBRE,
    page_icon="👔",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "tema" not in st.session_state:
    st.session_state.tema = "dark"
tema = st.session_state.tema

if tema == "dark":
    BG=      "#0e1117"; BG2=     "#1a1f2e"; BORDER=  "#2d3748"
    TEXT=    "#fafafa"; METRIC=  "#1a1f2e"
else:
    BG=      "#ffffff"; BG2=     "#f7fafc"; BORDER=  "#e2e8f0"
    TEXT=    "#1a202c"; METRIC=  "#ebf8ff"

st.markdown(f"""
<style>
  [data-testid="stSidebar"] {{ background-color: {BG2} !important; border-right:1px solid {BORDER}; }}
  [data-testid="stSidebar"] * {{ color: {TEXT} !important; }}
  .stApp {{ background-color: {BG}; }}
  .block-container {{ padding-top: 1.2rem !important; }}
  [data-testid="metric-container"] {{ background:{METRIC}; border:1px solid {BORDER}; border-radius:10px; padding:12px 16px !important; }}
  .stButton > button {{ border-radius:6px !important; font-weight:500 !important; }}
  .stTextInput input, .stNumberInput input, .stTextArea textarea {{ border-radius:6px !important; }}
  .stTabs [data-baseweb="tab-list"] {{ gap:2px; }}
  .stTabs [data-baseweb="tab"] {{ border-radius:6px 6px 0 0; font-weight:500; }}
  hr {{ margin:0.6rem 0 !important; }}
  [data-testid="stChatMessage"] {{ border-radius:10px !important; }}
</style>
""", unsafe_allow_html=True)

LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "logo.png")

with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=60)
    cl, cn = st.columns([1,2])
    cn.markdown(f"## {APP_NOMBRE}")
    cn.caption(APP_SUBTITULO)
    st.divider()

    if "pagina" not in st.session_state:
        st.session_state.pagina = "dash_ventas"

    MENU = [
        ("📊 Dashboard Ventas",       "dash_ventas"),
        ("📦 Dashboard Inventario",   "dash_inv"),
        ("🛒 Punto de Venta",         "pos"),
        ("💼 Apartados",              "apartados"),
        (None, None),
        ("👔 Productos",              "productos"),
        ("🗄️ Inventario",            "inventario"),
        ("🧾 Ventas",                 "ventas"),
        ("👥 Clientes",               "clientes"),
        ("🗂️ Categorías",           "categorias"),
        (None, None),
        ("🤖 Agente IA",             "ia"),
        ("🛢️ Gestor BD",            "gbd"),
        ("⚙️ Configuración",        "config"),
    ]

    for label, key in MENU:
        if key is None:
            st.divider()
        else:
            active = st.session_state.pagina == key
            if st.button(label, key=f"nav_{key}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.pagina = key
                st.rerun()

    st.divider()
    tc1, tc2 = st.columns(2)
    if tc1.button("🌙 Oscuro",  use_container_width=True, type="primary" if tema=="dark"  else "secondary"):
        st.session_state.tema = "dark";  st.rerun()
    if tc2.button("☀️ Claro",  use_container_width=True, type="primary" if tema=="light" else "secondary"):
        st.session_state.tema = "light"; st.rerun()

    info = engine_info()
    st.caption(f"{info['icono']} {info['motor']} · {'Prod' if info['prod'] else 'Dev'}")

pag = st.session_state.pagina

if   pag == "dash_ventas": from pages.dashboard_ventas    import render; render()
elif pag == "dash_inv":    from pages.dashboard_inventario import render; render()
elif pag == "pos":         from pages.punto_de_venta       import render; render()
elif pag == "apartados":   from pages.apartados            import render; render()
elif pag == "productos":   from pages.productos            import render; render()
elif pag == "inventario":  from pages.inventario           import render; render()
elif pag == "ventas":      from pages.ventas               import render; render()
elif pag == "clientes":    from pages.clientes             import render; render()
elif pag == "categorias":  from pages.categorias           import render; render()
elif pag == "ia":          from pages.agente_ia            import render; render()
elif pag == "gbd":         from pages.gestor_bd            import render; render()
elif pag == "config":      from pages.configuracion        import render; render()

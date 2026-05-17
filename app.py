import streamlit as st
import os

# ── dotenv (opcional) ─────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

from database import init_db, get_config, engine_info

# ── Inicializar BD ────────────────────────────────────────────────────────────
init_db()

# ── Nombre y subtítulo desde BD ───────────────────────────────────────────────
APP_NOMBRE    = get_config("app_nombre",    "UniControl")
APP_SUBTITULO = get_config("app_subtitulo", "Sistema de Uniformes")

st.set_page_config(
    page_title=APP_NOMBRE,
    page_icon="👔",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Tema dark/light guardado en session_state ─────────────────────────────────
if "tema" not in st.session_state:
    st.session_state.tema = "dark"

tema = st.session_state.tema

# Colores según tema
if tema == "dark":
    BG       = "#0e1117"
    BG2      = "#1a1f2e"
    BORDER   = "#2d3748"
    TEXT     = "#fafafa"
    MUTED    = "#a0aec0"
    ACCENT   = "#4299e1"
    METRIC_BG= "#1a1f2e"
else:
    BG       = "#ffffff"
    BG2      = "#f7fafc"
    BORDER   = "#e2e8f0"
    TEXT     = "#1a202c"
    MUTED    = "#718096"
    ACCENT   = "#3182ce"
    METRIC_BG= "#ebf8ff"

st.markdown(f"""
<style>
  /* ── Sidebar ── */
  [data-testid="stSidebar"] {{
      background-color: {BG2} !important;
      border-right: 1px solid {BORDER};
  }}
  [data-testid="stSidebar"] * {{ color: {TEXT} !important; }}

  /* ── Main background ── */
  .stApp {{ background-color: {BG}; }}
  .block-container {{ padding-top: 1.2rem !important; }}

  /* ── Metric cards ── */
  [data-testid="metric-container"] {{
      background: {METRIC_BG};
      border: 1px solid {BORDER};
      border-radius: 10px;
      padding: 12px 16px !important;
  }}

  /* ── DataFrames / tables ── */
  [data-testid="stDataFrame"] {{ border-radius: 8px; overflow: hidden; }}

  /* ── Buttons ── */
  .stButton > button {{ border-radius: 6px !important; font-weight: 500 !important; }}

  /* ── Inputs ── */
  .stTextInput input, .stNumberInput input, .stTextArea textarea {{
      border-radius: 6px !important;
  }}

  /* ── Divider ── */
  hr {{ border-color: {BORDER} !important; margin: 0.6rem 0 !important; }}

  /* ── Tabs ── */
  .stTabs [data-baseweb="tab-list"] {{ gap: 2px; }}
  .stTabs [data-baseweb="tab"] {{ border-radius: 6px 6px 0 0; font-weight: 500; }}

  /* ── Expander ── */
  details summary {{ font-weight: 600; }}

  /* ── Alerts ── */
  .stSuccess, .stError, .stWarning, .stInfo {{ border-radius: 8px !important; }}

  /* ── Chat ── */
  [data-testid="stChatMessage"] {{ border-radius: 10px !important; }}
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "logo.png")

with st.sidebar:
    # Logo + nombre app
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=60)
    st.title(APP_NOMBRE)
    st.caption(APP_SUBTITULO)
    st.divider()

    # Navegación
    MENU = {
        "📊 Ventas (Dashboard)":       "dash_ventas",
        "📦 Inventario (Dashboard)":   "dash_inv",
        "🛒 Punto de Venta":           "pos",
        "—— Gestión ——":               None,
        "👔 Productos":                "productos",
        "🗄️ Inventario":              "inventario",
        "🧾 Ventas":                   "ventas",
        "👥 Clientes":                 "clientes",
        "🗂️ Categorías":             "categorias",
        "—— Sistema ——":               None,
        "🤖 Agente IA (GROQ)":         "ia",
        "🛢️ Gestor de BD":            "gbd",
        "⚙️ Configuración":           "config",
    }

    if "pagina" not in st.session_state:
        st.session_state.pagina = "dash_ventas"

    for label, key in MENU.items():
        if key is None:
            st.caption(label.replace("——","").strip())
        else:
            active = st.session_state.pagina == key
            btn_type = "primary" if active else "secondary"
            if st.button(label, key=f"nav_{key}", use_container_width=True, type=btn_type):
                st.session_state.pagina = key
                st.rerun()

    st.divider()

    # Dark / Light toggle
    col_t1, col_t2 = st.columns(2)
    if col_t1.button("🌙 Oscuro", use_container_width=True,
                     type="primary" if tema=="dark" else "secondary"):
        st.session_state.tema = "dark"; st.rerun()
    if col_t2.button("☀️ Claro", use_container_width=True,
                     type="primary" if tema=="light" else "secondary"):
        st.session_state.tema = "light"; st.rerun()

    # Motor indicator
    info = engine_info()
    st.caption(f"{info['icono']} {info['motor']} · {'Producción' if info['prod'] else 'Desarrollo'}")


# ── ROUTING ───────────────────────────────────────────────────────────────────
pag = st.session_state.pagina

if pag == "dash_ventas":
    from pages.dashboard_ventas    import render; render()
elif pag == "dash_inv":
    from pages.dashboard_inventario import render; render()
elif pag == "pos":
    from pages.punto_de_venta      import render; render()
elif pag == "productos":
    from pages.productos           import render; render()
elif pag == "inventario":
    from pages.inventario          import render; render()
elif pag == "ventas":
    from pages.ventas              import render; render()
elif pag == "clientes":
    from pages.clientes            import render; render()
elif pag == "categorias":
    from pages.categorias          import render; render()
elif pag == "ia":
    from pages.agente_ia           import render; render()
elif pag == "gbd":
    from pages.gestor_bd           import render; render()
elif pag == "config":
    from pages.configuracion       import render; render()

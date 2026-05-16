import streamlit as st
import os
from database import init_db, get_config, engine_info

st.set_page_config(
    page_title="StockPOS",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Carga de variables de entorno desde .env (si existe) ──────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv es opcional; en producción las vars vienen del entorno

# ── Inicializar base de datos ──────────────────────────────────────────────────
init_db()

# ── CSS global ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.4rem; padding-bottom: 1rem; }

/* Sidebar */
section[data-testid="stSidebar"] { background: #16213e !important; border-right: 1px solid #2d3f5c; }
section[data-testid="stSidebar"] * { color: #e8eaf6 !important; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #1a2744; border: 1px solid #2d3f5c;
    border-radius: 12px; padding: 14px !important;
}
[data-testid="stMetricValue"] {
    font-family: 'Syne', sans-serif !important;
    font-size: 26px !important; font-weight: 800 !important;
}

/* Buttons */
.stButton > button {
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important; font-weight: 500 !important;
    transition: all 0.15s !important;
}
.stButton > button[kind="primary"] { background: #e94560 !important; border: none !important; }
.stButton > button[kind="primary"]:hover { background: #c73250 !important; }

/* Inputs */
.stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox div[data-baseweb] {
    background: #1e2a45 !important; border: 1px solid #2d3f5c !important;
    border-radius: 8px !important; color: #e8eaf6 !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px; background: #16213e; border-radius: 10px; padding: 4px;
}
.stTabs [data-baseweb="tab"] { border-radius: 8px; font-weight: 500; color: #8892a4; }
.stTabs [aria-selected="true"] { background: #0f3460 !important; color: #e8eaf6 !important; }

/* DataFrames */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

/* Expanders */
.streamlit-expanderHeader { background: #1a2744 !important; border-radius: 8px !important; }

/* Custom classes */
.sp-title {
    font-family: 'Syne', sans-serif; font-weight: 800;
    font-size: 24px; color: #e8eaf6; margin-bottom: 0; line-height: 1.2;
}
.sp-subtitle { color: #8892a4; font-size: 13px; margin-bottom: 1rem; margin-top: 2px; }
.sp-accent { color: #e94560; }

/* Alerts */
.stSuccess, .stError, .stWarning, .stInfo { border-radius: 8px !important; }

/* Chat messages */
[data-testid="stChatMessage"] {
    background: #1a2744 !important; border: 1px solid #2d3f5c !important;
    border-radius: 10px !important;
}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "logo.png")

with st.sidebar:
    # Logo + nombre
    empresa = get_config("empresa_nombre", "Mi Empresa")
    c_logo, c_name = st.columns([1, 2])
    with c_logo:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=50)
        else:
            st.markdown(
                '<div style="width:50px;height:50px;background:#e94560;border-radius:10px;'
                'display:flex;align-items:center;justify-content:center;'
                'font-family:Syne;font-weight:800;font-size:18px;color:white">SP</div>',
                unsafe_allow_html=True
            )
    with c_name:
        st.markdown(
            f'<div style="font-family:Syne;font-weight:800;font-size:16px;padding-top:4px">'
            f'Stock<span style="color:#e94560">POS</span></div>'
            f'<div style="font-size:11px;color:#8892a4;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{empresa}</div>',
            unsafe_allow_html=True
        )

    st.markdown("---")

    # Indicador de motor
    info = engine_info()
    st.markdown(
        f'<div style="font-size:11px;color:#8892a4;text-align:center;margin-bottom:8px">'
        f'{info["icono"]} {info["motor"]}</div>',
        unsafe_allow_html=True
    )

    # Navegación
    pagina = st.radio(
        "Navegación",
        [
            "📊 Dashboard Ventas",
            "📦 Dashboard Inventario",
            "🛒 Punto de Venta",
            "─────────────",
            "🏷️ Productos",
            "🗄️ Inventario",
            "💳 Ventas",
            "👥 Clientes",
            "🗂️ Categorías",
            "─────────────",
            "🤖 Agente IA",
            "🛢️ Gestor BD",
            "⚙️ Configuración",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown(
        '<div style="font-size:10px;color:#8892a4;text-align:center">StockPOS v2.0 · GROQ AI</div>',
        unsafe_allow_html=True
    )

# ── Routing ────────────────────────────────────────────────────────────────────
if pagina == "📊 Dashboard Ventas":
    from pages.dashboard_ventas import render; render()

elif pagina == "📦 Dashboard Inventario":
    from pages.dashboard_inventario import render; render()

elif pagina == "🛒 Punto de Venta":
    from pages.punto_de_venta import render; render()

elif pagina == "🏷️ Productos":
    from pages.productos import render; render()

elif pagina == "🗄️ Inventario":
    from pages.inventario import render; render()

elif pagina == "💳 Ventas":
    from pages.ventas import render; render()

elif pagina == "👥 Clientes":
    from pages.clientes import render; render()

elif pagina == "🗂️ Categorías":
    from pages.categorias import render; render()

elif pagina == "🤖 Agente IA":
    from pages.agente_ia import render; render()

elif pagina == "🛢️ Gestor BD":
    from pages.gestor_bd import render; render()

elif pagina == "⚙️ Configuración":
    from pages.configuracion import render; render()

elif "───" in pagina:
    st.markdown("Selecciona una opción del menú")

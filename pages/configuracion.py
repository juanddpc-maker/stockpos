import streamlit as st
import os
import base64
from database import get_config, set_config, engine_info

LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png")
os.makedirs(os.path.dirname(LOGO_PATH), exist_ok=True)


def render():
    st.markdown('<p class="sp-title">⚙️ <span class="sp-accent">Configuración</span></p>', unsafe_allow_html=True)
    st.markdown('<p class="sp-subtitle">Ajustes del sistema y empresa</p>', unsafe_allow_html=True)

    tab_empresa, tab_bd, tab_groq = st.tabs(["🏢 Empresa", "🛢️ Base de Datos", "🤖 GROQ / IA"])

    # ── Empresa ───────────────────────────────────────────────────────────────
    with tab_empresa:
        st.markdown("#### 🏢 Datos de la Empresa")

        col_logo, col_data = st.columns([1, 2])

        with col_logo:
            st.markdown("**Logo de la Empresa**")
            if os.path.exists(LOGO_PATH):
                st.image(LOGO_PATH, width=160)
                if st.button("🗑️ Eliminar logo", use_container_width=True):
                    os.remove(LOGO_PATH)
                    st.success("Logo eliminado")
                    st.rerun()
            else:
                st.markdown("""
                <div style="width:160px;height:160px;background:#1a2744;border:2px dashed #2d3f5c;
                     border-radius:12px;display:flex;align-items:center;justify-content:center;
                     font-size:40px">🏢</div>""", unsafe_allow_html=True)

            uploaded = st.file_uploader("Subir Logo (.png .jpg .webp)", type=["png","jpg","jpeg","webp"],
                                        label_visibility="collapsed")
            if uploaded:
                img_bytes = uploaded.read()
                with open(LOGO_PATH, "wb") as f:
                    f.write(img_bytes)
                st.success("✅ Logo actualizado")
                st.rerun()

        with col_data:
            with st.form("empresa_form"):
                nombre = st.text_input("Nombre de la Empresa", value=get_config("empresa_nombre", "Mi Empresa"))
                rfc    = st.text_input("RFC", value=get_config("empresa_rfc", ""))
                dir_   = st.text_input("Dirección", value=get_config("empresa_direccion", ""))
                tel    = st.text_input("Teléfono", value=get_config("empresa_telefono", ""))
                email  = st.text_input("Email", value=get_config("empresa_email", ""))
                iva    = st.number_input("IVA (%)", min_value=0, max_value=100,
                                         value=int(get_config("iva_pct", "16")))
                moneda = st.selectbox("Moneda", ["MXN", "USD", "EUR"],
                                      index=["MXN","USD","EUR"].index(get_config("moneda","MXN")))

                if st.form_submit_button("💾 Guardar Datos", type="primary", use_container_width=True):
                    set_config("empresa_nombre",    nombre)
                    set_config("empresa_rfc",       rfc)
                    set_config("empresa_direccion", dir_)
                    set_config("empresa_telefono",  tel)
                    set_config("empresa_email",     email)
                    set_config("iva_pct",           str(iva))
                    set_config("moneda",            moneda)
                    st.success("✅ Configuración guardada")
                    st.rerun()

    # ── Base de Datos ─────────────────────────────────────────────────────────
    with tab_bd:
        info = engine_info()
        st.markdown("#### 🛢️ Motor de Base de Datos")

        st.markdown(f"""
        <div style="background:#1a2744;border:1px solid #2d3f5c;border-radius:12px;padding:20px;margin-bottom:16px">
            <div style="font-size:32px;margin-bottom:8px">{info['icono']}</div>
            <div style="font-size:20px;font-weight:700">{info['motor']}</div>
            <div style="font-family:monospace;font-size:13px;color:#8892a4;margin-top:6px;
                 word-break:break-all">{info['url']}</div>
            <div style="margin-top:12px">
                <span style="background:{'rgba(0,200,150,0.15)' if info['motor']=='PostgreSQL' else 'rgba(74,158,255,0.15)'};
                      color:{'#00c896' if info['motor']=='PostgreSQL' else '#4a9eff'};
                      border-radius:20px;padding:4px 14px;font-size:13px;font-weight:700">
                    {'🟢 Modo Producción (PostgreSQL)' if info['motor']=='PostgreSQL' else '🔵 Modo Desarrollo (SQLite)'}
                </span>
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown("#### 🔄 Cambiar Motor")
        st.markdown("""
        La detección es **automática** según la variable de entorno `DATABASE_URL`:

        | Entorno | Configuración |
        |---|---|
        | **Local / Dev** | No definir `DATABASE_URL` → usa SQLite automáticamente |
        | **Producción** | Definir `DATABASE_URL=postgresql://...` en `.env` o en tu plataforma |

        **Ejemplo `.env` para producción:**
        ```
        DATABASE_URL=postgresql://usuario:contraseña@host:5432/stockpos
        ```

        **Plataformas compatibles:**
        - 🚀 Railway · Render · Heroku (definen DATABASE_URL automáticamente)
        - ☁️ AWS RDS / Google Cloud SQL / Supabase (copia la connection string)
        - 🐳 Docker Compose (define el servicio postgres y pasa DATABASE_URL)
        """)

        if info['motor'] == 'SQLite':
            st.info("📁 Archivo SQLite: `data/stockpos.db` — se crea automáticamente al iniciar la app.")
            st.markdown("**Tablas y tamaño:**")
            from database import q
            from database import TABLAS if hasattr(__import__('database'), 'TABLAS') else None
            tablas = ["categorias","productos","inventario","clientes","ventas","venta_items","config"]
            cols = st.columns(4)
            for i, t in enumerate(tablas):
                n = q(f"SELECT COUNT(*) as n FROM {t}")[0]['n']
                cols[i % 4].metric(t, f"{n} filas")
        else:
            st.success("🐘 Conectado a PostgreSQL correctamente.")

    # ── GROQ ──────────────────────────────────────────────────────────────────
    with tab_groq:
        st.markdown("#### 🤖 Configuración del Agente IA (GROQ)")

        st.markdown("""
        El Agente IA usa [GROQ](https://console.groq.com) para acceder a modelos LLM de alta velocidad.

        **Pasos para activarlo:**
        1. Crea una cuenta en [console.groq.com](https://console.groq.com)
        2. Genera una API Key gratuita
        3. Pégala aquí o defínela en tu `.env` como `GROQ_API_KEY`
        """)

        with st.form("groq_form"):
            key = st.text_input("GROQ API Key", value=get_config("groq_api_key",""),
                                type="password", placeholder="gsk_...")
            modelo_def = st.selectbox("Modelo por defecto",
                ["llama-3.3-70b-versatile","llama-3.1-8b-instant","mixtral-8x7b-32768","gemma2-9b-it"],
                index=0)
            if st.form_submit_button("💾 Guardar", type="primary", use_container_width=True):
                set_config("groq_api_key", key)
                set_config("groq_modelo_default", modelo_def)
                st.success("✅ Configuración de IA guardada")

        if get_config("groq_api_key"):
            st.success("🟢 API Key configurada · Agente IA activo")
        else:
            st.warning("🔴 Sin API Key · El agente funcionará en modo demo")

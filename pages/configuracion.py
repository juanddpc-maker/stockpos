import streamlit as st
import os
from database import get_config, set_config, engine_info

LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png")


def render():
    st.header("⚙️ Configuración")

    tab_app, tab_empresa, tab_bd, tab_groq = st.tabs([
        "📱 Nombre de la App", "🏢 Datos de la Empresa", "🛢️ Base de Datos", "🤖 GROQ / IA"
    ])

    # ── Nombre de la App ──────────────────────────────────────────────────────
    with tab_app:
        st.subheader("Nombre y apariencia de la aplicación")
        st.info("El nombre se guarda en la base de datos y se aplica al reiniciar la app.")

        with st.form("form_app"):
            app_nombre    = st.text_input("Nombre de la app",    value=get_config("app_nombre","UniControl"))
            app_subtitulo = st.text_input("Subtítulo / slogan",  value=get_config("app_subtitulo","Sistema de Uniformes"))

            st.markdown("**Logo de la empresa**")
            if os.path.exists(LOGO_PATH):
                st.image(LOGO_PATH, width=120)
                quitar = st.checkbox("Quitar logo actual")
            else:
                quitar = False
                st.caption("No hay logo cargado")

            logo_file = st.file_uploader("Subir logo (.png .jpg .webp)", type=["png","jpg","jpeg","webp"])

            if st.form_submit_button("💾 Guardar", type="primary", use_container_width=True):
                set_config("app_nombre",    app_nombre.strip() or "UniControl")
                set_config("app_subtitulo", app_subtitulo.strip())
                os.makedirs(os.path.dirname(LOGO_PATH), exist_ok=True)
                if quitar and os.path.exists(LOGO_PATH):
                    os.remove(LOGO_PATH)
                    st.success("Logo eliminado")
                if logo_file:
                    with open(LOGO_PATH, "wb") as f:
                        f.write(logo_file.read())
                    st.success(f"Logo actualizado")
                st.success(f"✅ App renombrada a **{app_nombre}** · Reinicia la app para ver el cambio en el título")
                st.rerun()

    # ── Empresa ───────────────────────────────────────────────────────────────
    with tab_empresa:
        st.subheader("Datos fiscales y de contacto")
        with st.form("form_empresa"):
            c1,c2 = st.columns(2)
            nombre    = c1.text_input("Nombre de la empresa",  value=get_config("empresa_nombre",""))
            rfc       = c2.text_input("RFC",                   value=get_config("empresa_rfc",""))
            direccion = st.text_input("Dirección",             value=get_config("empresa_direccion",""))
            c3,c4     = st.columns(2)
            telefono  = c3.text_input("Teléfono",              value=get_config("empresa_telefono",""))
            email     = c4.text_input("Email",                 value=get_config("empresa_email",""))
            c5,c6     = st.columns(2)
            iva       = c5.number_input("IVA (%)", min_value=0, max_value=100,
                                        value=int(get_config("iva_pct","16")))
            moneda    = c6.selectbox("Moneda", ["MXN","USD","EUR"],
                                     index=["MXN","USD","EUR"].index(get_config("moneda","MXN")))
            if st.form_submit_button("💾 Guardar datos", type="primary", use_container_width=True):
                for k,v in [("empresa_nombre",nombre),("empresa_rfc",rfc),
                             ("empresa_direccion",direccion),("empresa_telefono",telefono),
                             ("empresa_email",email),("iva_pct",str(iva)),("moneda",moneda)]:
                    set_config(k,v)
                st.success("✅ Datos de empresa guardados")

    # ── Base de datos ─────────────────────────────────────────────────────────
    with tab_bd:
        info = engine_info()
        st.subheader(f"{info['icono']} Motor activo: {info['motor']}")
        st.code(info['url'], language=None)

        if info['prod']:
            st.success("🟢 Conectado a PostgreSQL (Producción)")
        else:
            st.info("🔵 Usando SQLite (Desarrollo local)")

        st.markdown("""
**Cómo cambiar a PostgreSQL para producción:**

1. Crea una BD gratis en [Supabase](https://supabase.com) o [Neon](https://neon.tech)
2. Copia la *Connection String* (formato `postgresql://...`)
3. En **Streamlit Cloud → Settings → Secrets** agrega:

```toml
DATABASE_URL = "postgresql://usuario:password@host:5432/dbname"
```

La app detecta el motor automáticamente al arrancar.
""")

        st.markdown("**Estadísticas actuales:**")
        tablas = ["categorias","productos","inventario","clientes","ventas","venta_items"]
        cols = st.columns(3)
        from database import q
        for i, t in enumerate(tablas):
            n = q(f"SELECT COUNT(*) as n FROM {t}")[0]['n']
            cols[i%3].metric(t, f"{n} filas")

    # ── GROQ ──────────────────────────────────────────────────────────────────
    with tab_groq:
        st.subheader("🤖 Agente IA con GROQ")
        st.markdown("""
Obtén una API Key **gratuita** en [console.groq.com](https://console.groq.com)
y activa el asistente inteligente para análisis de ventas e inventario.
""")
        with st.form("form_groq"):
            key    = st.text_input("GROQ API Key", value=get_config("groq_api_key",""),
                                   type="password", placeholder="gsk_...")
            modelo = st.selectbox("Modelo por defecto",
                                  ["llama-3.3-70b-versatile","llama-3.1-8b-instant",
                                   "mixtral-8x7b-32768","gemma2-9b-it"])
            if st.form_submit_button("💾 Guardar", type="primary", use_container_width=True):
                set_config("groq_api_key", key)
                set_config("groq_modelo_default", modelo)
                st.success("✅ Configuración de IA guardada")

        if get_config("groq_api_key",""):
            st.success("🟢 Agente IA activo")
        else:
            st.warning("🔴 Sin API Key · El agente funcionará en modo demo")

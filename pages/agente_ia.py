import streamlit as st
import urllib.request, urllib.error, json
from database import q, get_config, set_config

MODELOS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]

SUGERENCIAS = [
    "¿Cuáles son mis productos con stock bajo o agotado?",
    "¿Cuánto vendí esta semana y qué productos fueron los más populares?",
    "¿Qué categoría genera más ingresos?",
    "¿Qué productos debería reabastecer pronto?",
    "Dame un análisis general del negocio con recomendaciones",
    "¿Cuántos clientes tengo y cuál es su ticket promedio?",
    "¿Qué uniformes se venden más en cada categoría?",
]


def _contexto():
    from datetime import datetime, timedelta
    hoy  = datetime.now().date()
    sem  = hoy - timedelta(days=7)

    vt  = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada'")[0]
    vs  = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada' AND DATE(fecha)>=?", (str(sem),))[0]
    vh  = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada' AND DATE(fecha)=?", (str(hoy),))[0]

    low  = q("SELECT p.nombre,i.cantidad,i.min_stock,i.localidad FROM inventario i JOIN productos p ON p.id=i.producto_id WHERE i.cantidad<=i.min_stock")
    top  = q("""SELECT p.nombre, SUM(vi.cantidad) as u, SUM(vi.subtotal) as ing
                FROM venta_items vi JOIN productos p ON p.id=vi.producto_id
                JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
                GROUP BY p.id ORDER BY u DESC LIMIT 5""")
    cats = q("""SELECT c.nombre, COALESCE(SUM(vi.subtotal),0) as total
                FROM categorias c
                LEFT JOIN productos p ON p.categoria_id=c.id
                LEFT JOIN venta_items vi ON vi.producto_id=p.id
                LEFT JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
                GROUP BY c.id ORDER BY total DESC""")
    val_inv = q("SELECT COALESCE(SUM(p.precio*i.cantidad),0) as v FROM inventario i JOIN productos p ON p.id=i.producto_id")[0]

    low_txt = "\n".join([f"  - {r['nombre']}: {r['cantidad']} uds (mín {r['min_stock']}) — {r['localidad']}" for r in low]) or "  Ninguno"
    top_txt = "\n".join([f"  - {r['nombre']}: {r['u']} uds / ${float(r['ing']):,.2f}" for r in top]) or "  Sin ventas"
    cat_txt = "\n".join([f"  - {r['nombre']}: ${float(r['total']):,.2f}" for r in cats]) or "  Sin datos"

    return f"""=== DATOS DEL NEGOCIO (tiempo real) ===
VENTAS:
  Histórico: ${float(vt['t']):,.2f} ({vt['n']} transacciones)
  Esta semana: ${float(vs['t']):,.2f} ({vs['n']} transacciones)
  Hoy: ${float(vh['t']):,.2f} ({vh['n']} transacciones)

PRODUCTOS CON STOCK BAJO O AGOTADO:
{low_txt}

TOP 5 PRODUCTOS MÁS VENDIDOS:
{top_txt}

VENTAS POR CATEGORÍA:
{cat_txt}

VALOR DEL INVENTARIO: ${float(val_inv['v']):,.2f}
CLIENTES: {q("SELECT COUNT(*) as n FROM clientes")[0]['n']}
PRODUCTOS EN CATÁLOGO: {q("SELECT COUNT(*) as n FROM productos")[0]['n']}
"""


def _llamar_groq(api_key, model, messages):
    payload = json.dumps({"model": model, "messages": messages,
                          "temperature": 0.7, "max_tokens": 1024}).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


def _demo(texto):
    t = texto.lower()
    if any(k in t for k in ["stock","reabastecer","agotado"]):
        low = q("SELECT p.nombre,i.cantidad,i.min_stock FROM inventario i JOIN productos p ON p.id=i.producto_id WHERE i.cantidad<=i.min_stock")
        lineas = "\n".join([f"• **{r['nombre']}**: {r['cantidad']} uds (mínimo: {r['min_stock']})" for r in low]) or "• ✅ Todo en orden"
        return f"📦 **Productos que necesitan reabastecimiento:**\n\n{lineas}\n\n_💡 Prioriza los artículos en cero para no perder ventas._"
    if any(k in t for k in ["venta","ingreso","semana","vendí"]):
        v = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada'")[0]
        tkt = float(v['t'])/v['n'] if v['n'] else 0
        return f"📊 **Resumen de ventas:**\n\n• Total acumulado: **${float(v['t']):,.2f}**\n• Transacciones: **{v['n']}**\n• Ticket promedio: **${tkt:,.2f}**"
    return "🤖 Modo demo activo. Configura tu API Key de GROQ (panel derecho) para obtener análisis reales con IA.\n\nPuedo analizar tus ventas, inventario y darte recomendaciones personalizadas para tu negocio de uniformes."


def render():
    st.header("🤖 Agente IA")
    st.caption("Asistente inteligente con acceso a tus datos en tiempo real · Powered by GROQ")

    if "ai_hist" not in st.session_state:
        st.session_state.ai_hist = []

    col_chat, col_cfg = st.columns([3, 1])

    # ── Config lateral ────────────────────────────────────────────────────────
    with col_cfg:
        st.subheader("⚙️ Configuración")
        saved_key = get_config("groq_api_key", "")
        api_key = st.text_input("GROQ API Key", value=saved_key, type="password",
                                placeholder="gsk_...", help="Consigue tu key gratis en console.groq.com")
        model = st.selectbox("Modelo", MODELOS)
        if st.button("💾 Guardar key", use_container_width=True):
            set_config("groq_api_key", api_key)
            st.success("✅ Guardada")
        if api_key:
            st.success("🟢 IA activa")
        else:
            st.warning("🔴 Modo demo")

        st.divider()
        st.subheader("💡 Preguntas rápidas")
        for s in SUGERENCIAS:
            if st.button(s[:50] + ("…" if len(s)>50 else ""), use_container_width=True, key=f"sug_{s[:20]}"):
                st.session_state["_prompt_rapido"] = s
                st.rerun()

        st.divider()
        st.subheader("📊 Snapshot")
        v = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada'")[0]
        low_n = q("SELECT COUNT(*) as n FROM inventario WHERE cantidad<=min_stock")[0]['n']
        st.metric("Ventas totales",  f"${float(v['t']):,.2f}")
        st.metric("Transacciones",   v['n'])
        st.metric("⚠️ Stock bajo",   low_n)

        if st.button("🗑️ Limpiar chat", use_container_width=True):
            st.session_state.ai_hist = []
            st.rerun()

    # ── Chat ──────────────────────────────────────────────────────────────────
    with col_chat:
        if not st.session_state.ai_hist:
            st.info("👋 Hola, soy tu asistente de negocio. Tengo acceso en tiempo real a tu inventario, ventas y clientes. ¿En qué te ayudo?")

        for msg in st.session_state.ai_hist:
            with st.chat_message(msg["role"], avatar="🤖" if msg["role"]=="assistant" else "👤"):
                st.markdown(msg["content"])

        # Capturar prompt rápido o input manual
        prompt_rapido = st.session_state.pop("_prompt_rapido", None)
        user_input = st.chat_input("Escribe tu pregunta...") or prompt_rapido

        if user_input:
            st.session_state.ai_hist.append({"role": "user", "content": user_input})
            with st.chat_message("user", avatar="👤"):
                st.markdown(user_input)

            key = get_config("groq_api_key", "")
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Analizando datos..."):
                    if not key:
                        reply = _demo(user_input)
                    else:
                        ctx = _contexto()
                        sys_msg = ("Eres un asistente experto en gestión de negocios de venta de uniformes. "
                                   "Respondes en español, de forma clara, práctica y con emojis. "
                                   "Basas tus respuestas en los datos reales del negocio.\n\n" + ctx)
                        msgs = [{"role":"system","content":sys_msg}]
                        msgs += [{"role":m["role"],"content":m["content"]} for m in st.session_state.ai_hist[-10:]]
                        try:
                            reply = _llamar_groq(key, model, msgs)
                        except Exception as e:
                            reply = f"❌ Error al conectar con GROQ: {e}\n\nVerifica tu API Key."
                    st.markdown(reply)
            st.session_state.ai_hist.append({"role": "assistant", "content": reply})

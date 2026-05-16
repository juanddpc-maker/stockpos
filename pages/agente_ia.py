import streamlit as st
from database import q, get_config, set_config

MODELOS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]

PROMPTS_RAPIDOS = [
    ("📦", "¿Cuáles son mis productos con stock bajo o agotado?"),
    ("📈", "¿Cuánto vendí esta semana y cuáles fueron los productos más populares?"),
    ("💰", "¿Qué categoría genera más ingresos?"),
    ("🔄", "¿Qué productos debería reabastecer pronto según el ritmo de ventas?"),
    ("👥", "Dame un análisis de mis clientes: frecuencia de compra y ticket promedio"),
    ("🎯", "Dame un análisis general del negocio y 3 recomendaciones concretas para mejorar"),
    ("⚠️",  "¿Qué riesgos tiene mi inventario actual?"),
    ("📊", "Compara las ventas de esta semana con la semana pasada"),
]


def _build_context() -> str:
    """Construye el contexto de negocio en texto para enviarlo al modelo."""
    from datetime import datetime, timedelta
    now = datetime.now()
    today = now.date()
    semana = today - timedelta(days=7)

    ventas_total = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada'")
    ventas_sem   = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada' AND DATE(fecha)>=?", (str(semana),))
    ventas_hoy   = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada' AND DATE(fecha)=?", (str(today),))

    low_stock = q("""
        SELECT p.nombre, i.cantidad, i.min_stock, i.localidad
        FROM inventario i JOIN productos p ON p.id=i.producto_id
        WHERE i.cantidad <= i.min_stock ORDER BY i.cantidad
    """)
    top_prods = q("""
        SELECT p.nombre, SUM(vi.cantidad) as und, SUM(vi.subtotal) as ing
        FROM venta_items vi JOIN productos p ON p.id=vi.producto_id
        JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
        GROUP BY p.id ORDER BY und DESC LIMIT 5
    """)
    cat_ventas = q("""
        SELECT c.nombre, COALESCE(SUM(vi.subtotal),0) as total
        FROM categorias c LEFT JOIN productos p ON p.categoria_id=c.id
        LEFT JOIN venta_items vi ON vi.producto_id=p.id
        LEFT JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
        GROUP BY c.id ORDER BY total DESC
    """)
    inv_value = q("""
        SELECT COALESCE(SUM(p.precio * i.cantidad),0) as val
        FROM inventario i JOIN productos p ON p.id=i.producto_id
    """)

    low_lines = "\n".join([f"  - {r['nombre']}: {r['cantidad']} unid (mín {r['min_stock']}) en {r['localidad']}" for r in low_stock]) or "  Ninguno"
    top_lines = "\n".join([f"  - {r['nombre']}: {r['und']} unid / ${float(r['ing']):,.2f}" for r in top_prods]) or "  Sin datos"
    cat_lines = "\n".join([f"  - {r['nombre']}: ${float(r['total']):,.2f}" for r in cat_ventas]) or "  Sin datos"

    return f"""=== DATOS DEL NEGOCIO (en tiempo real) ===

VENTAS GLOBALES:
  Total histórico : ${float(ventas_total[0]['t']):,.2f} ({ventas_total[0]['n']} transacciones)
  Esta semana     : ${float(ventas_sem[0]['t']):,.2f}  ({ventas_sem[0]['n']} transacciones)
  Hoy             : ${float(ventas_hoy[0]['t']):,.2f}  ({ventas_hoy[0]['n']} transacciones)

PRODUCTOS CON STOCK BAJO O AGOTADO:
{low_lines}

TOP 5 PRODUCTOS MÁS VENDIDOS:
{top_lines}

VENTAS POR CATEGORÍA:
{cat_lines}

VALOR TOTAL DEL INVENTARIO: ${float(inv_value[0]['val']):,.2f}
CLIENTES REGISTRADOS: {q("SELECT COUNT(*) as n FROM clientes")[0]['n']}
PRODUCTOS EN CATÁLOGO: {q("SELECT COUNT(*) as n FROM productos")[0]['n']}
"""


def _call_groq(api_key: str, model: str, messages: list) -> str:
    """Llama a la API de GROQ y retorna el texto de respuesta."""
    import urllib.request, urllib.error, json

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1024,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"GROQ {e.code}: {body}")


def _demo_response(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["stock","reabastecer","agotado"]):
        low = q("SELECT p.nombre,i.cantidad,i.min_stock FROM inventario i JOIN productos p ON p.id=i.producto_id WHERE i.cantidad<=i.min_stock")
        lines = "\n".join([f"• **{r['nombre']}**: {r['cantidad']} (mín {r['min_stock']})" for r in low]) or "• Todo en orden ✅"
        return f"📦 **Productos que requieren atención:**\n\n{lines}\n\n_💡 Prioriza reabastecer los agotados para no perder ventas._"
    if any(k in t for k in ["venta","ingreso","semana"]):
        v = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada'")[0]
        tkt = float(v['t'])/v['n'] if v['n'] else 0
        return f"📊 **Resumen de ventas:**\n\n• Total: **${float(v['t']):,.2f}**\n• Transacciones: **{v['n']}**\n• Ticket prom.: **${tkt:,.2f}**\n\n_Activa tu API Key de GROQ para análisis avanzados._"
    return "🤖 **Modo demo activo.**\n\nIngresa tu API Key de GROQ en el panel de la derecha para obtener respuestas reales del modelo.\n\nPuedo analizar tus ventas, inventario, clientes y darte recomendaciones estratégicas."


def render():
    st.markdown('<p class="sp-title">🤖 Agente <span class="sp-accent">IA</span></p>', unsafe_allow_html=True)
    st.markdown('<p class="sp-subtitle">Asistente inteligente de negocio · Powered by GROQ</p>', unsafe_allow_html=True)

    # ── Session state ─────────────────────────────────────────────────────────
    if "ai_history" not in st.session_state:
        st.session_state.ai_history = []
    if "ai_prompt_set" not in st.session_state:
        st.session_state.ai_prompt_set = ""

    col_chat, col_side = st.columns([2, 1])

    # ── Side panel ────────────────────────────────────────────────────────────
    with col_side:
        with st.container():
            st.markdown("#### ⚙️ Configuración GROQ")
            saved_key = get_config("groq_api_key", "")
            api_key = st.text_input("API Key", value=saved_key, type="password",
                                    placeholder="gsk_...", help="Obtén tu key en console.groq.com")
            model = st.selectbox("Modelo", MODELOS)
            if st.button("💾 Guardar Key", use_container_width=True):
                set_config("groq_api_key", api_key)
                st.success("Key guardada")

            status = "🟢 Activo" if api_key else "🔴 Sin API Key (modo demo)"
            st.markdown(f"**Estado:** {status}")

        st.markdown("---")
        st.markdown("#### 💡 Preguntas Rápidas")
        for icon, prompt in PROMPTS_RAPIDOS:
            if st.button(f"{icon} {prompt[:45]}…" if len(prompt) > 45 else f"{icon} {prompt}",
                         use_container_width=True, key=f"qr_{prompt[:20]}"):
                st.session_state.ai_prompt_set = prompt
                st.rerun()

        st.markdown("---")
        st.markdown("#### 📊 Contexto Actual")
        v = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada'")[0]
        low_n = q("SELECT COUNT(*) as n FROM inventario WHERE cantidad<=min_stock")[0]['n']
        no_n  = q("SELECT COUNT(*) as n FROM inventario WHERE cantidad=0")[0]['n']
        st.markdown(f"""
        | Métrica | Valor |
        |---|---|
        | 💰 Ventas totales | ${float(v['t']):,.2f} |
        | 🧾 Transacciones | {v['n']} |
        | ⚠️ Stock bajo | {low_n} |
        | ❌ Sin stock | {no_n} |
        | 👥 Clientes | {q("SELECT COUNT(*) as n FROM clientes")[0]['n']} |
        | 📦 Productos | {q("SELECT COUNT(*) as n FROM productos")[0]['n']} |
        """)

        if st.button("🗑️ Limpiar conversación", use_container_width=True):
            st.session_state.ai_history = []
            st.rerun()

    # ── Chat panel ────────────────────────────────────────────────────────────
    with col_chat:
        # Mostrar historial
        if not st.session_state.ai_history:
            st.markdown("""
            <div style="background:#1a2744;border:1px solid #2d3f5c;border-radius:12px;padding:20px;margin-bottom:16px">
                <div style="font-size:24px;margin-bottom:8px">👋 ¡Hola!</div>
                <div style="color:#8892a4;font-size:14px;line-height:1.7">
                Soy tu asistente de negocio con IA. Tengo acceso a tus datos de inventario y ventas en tiempo real.<br><br>
                Puedo ayudarte a analizar tus ventas, detectar problemas de stock, identificar productos estrella
                y darte recomendaciones estratégicas.<br><br>
                Usa las <b>preguntas rápidas</b> o escribe tu propia consulta 👇
                </div>
            </div>""", unsafe_allow_html=True)
        else:
            for msg in st.session_state.ai_history:
                if msg["role"] == "user":
                    with st.chat_message("user"):
                        st.markdown(msg["content"])
                else:
                    with st.chat_message("assistant", avatar="🤖"):
                        st.markdown(msg["content"])

        # Input
        prompt_default = st.session_state.ai_prompt_set
        st.session_state.ai_prompt_set = ""

        user_input = st.chat_input("Escribe tu pregunta sobre ventas, inventario, clientes...")

        # Si llegó un prompt rápido, úsalo
        if prompt_default and not user_input:
            user_input = prompt_default

        if user_input:
            st.session_state.ai_history.append({"role": "user", "content": user_input})

            key = get_config("groq_api_key", "")
            ctx = _build_context()

            with st.spinner("🤖 Analizando datos..."):
                if not key:
                    reply = _demo_response(user_input)
                    reply += "\n\n---\n_⚠️ Modo demo. Configura tu API Key de GROQ para respuestas reales._"
                else:
                    system_msg = (
                        "Eres un asistente experto en gestión de negocios, inventario y punto de venta. "
                        "Respondes siempre en español, de forma concisa, práctica y con emojis para claridad. "
                        "Siempre basas tus respuestas en los datos reales del negocio que se te proporcionan. "
                        "Si detectas problemas (stock bajo, caída de ventas, etc.) los señalas proactivamente.\n\n"
                        + ctx
                    )
                    messages = [{"role": "system", "content": system_msg}]
                    # Últimos 8 turnos del historial (sin el último user que acabamos de agregar)
                    for m in st.session_state.ai_history[:-1][-8:]:
                        messages.append({"role": m["role"], "content": m["content"]})
                    messages.append({"role": "user", "content": user_input})

                    try:
                        reply = _call_groq(key, model, messages)
                    except RuntimeError as e:
                        reply = f"❌ Error al conectar con GROQ:\n\n```\n{e}\n```\n\nVerifica tu API Key."

            st.session_state.ai_history.append({"role": "assistant", "content": reply})
            st.rerun()

"""pages/agente_ia.py — Asistente IA de Uniformes (Groq / Anthropic)"""

import streamlit as st
from database import q, get_config, set_config


# ── AI client factory ─────────────────────────────────────────────────────────

def get_ai_response(messages: list, provider: str, api_key: str) -> str:
    try:
        if provider == "Groq":
            from groq import Groq
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=1024,
                temperature=0.4,
            )
            return response.choices[0].message.content

        elif provider == "Anthropic (Claude)":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
            conv = [m for m in messages if m["role"] != "system"]
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=system_msg,
                messages=conv,
            )
            return response.content[0].text

    except Exception as e:
        return f"❌ Error al conectar con {provider}: {str(e)}"


# ── Context builder ───────────────────────────────────────────────────────────

def build_context() -> str:
    from datetime import datetime, timedelta
    hoy = datetime.now().date()
    sem = hoy - timedelta(days=7)

    vt  = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada'")[0]
    vs  = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada' AND DATE(fecha)>=?", (str(sem),))[0]
    vh  = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada' AND DATE(fecha)=?", (str(hoy),))[0]

    low = q("""
        SELECT p.nombre, i.cantidad, i.min_stock, i.localidad
        FROM inventario i JOIN productos p ON p.id=i.producto_id
        WHERE i.cantidad <= i.min_stock ORDER BY i.cantidad
    """)
    top = q("""
        SELECT p.nombre, SUM(vi.cantidad) as u, SUM(vi.subtotal) as ing
        FROM venta_items vi JOIN productos p ON p.id=vi.producto_id
        JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
        GROUP BY p.id ORDER BY u DESC LIMIT 8
    """)
    cats = q("""
        SELECT c.nombre, COALESCE(SUM(vi.subtotal),0) as total
        FROM categorias c
        LEFT JOIN productos p ON p.categoria_id=c.id
        LEFT JOIN venta_items vi ON vi.producto_id=p.id
        LEFT JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
        GROUP BY c.id ORDER BY total DESC
    """)
    apt = q("SELECT COUNT(*) as n, COALESCE(SUM(saldo),0) as s, COALESCE(SUM(abonado),0) as a FROM apartados WHERE estado='Apartado'")[0]
    apt_venc = q("""
        SELECT COUNT(*) as n FROM apartados
        WHERE estado='Apartado' AND fecha_limite IS NOT NULL
          AND fecha_limite < datetime('now')
    """)[0]
    val = q("SELECT COALESCE(SUM(p.precio*i.cantidad),0) as v FROM inventario i JOIN productos p ON p.id=i.producto_id")[0]
    clientes_top = q("""
        SELECT c.nombre, COUNT(v.id) as compras, COALESCE(SUM(v.total),0) as total
        FROM clientes c JOIN ventas v ON v.cliente_id=c.id AND v.estado='Completada'
        GROUP BY c.id ORDER BY total DESC LIMIT 5
    """)

    low_txt  = "\n".join([f"  - {r['nombre']}: {r['cantidad']} uds (mín {r['min_stock']}) — {r['localidad']}" for r in low]) or "  Ninguno"
    top_txt  = "\n".join([f"  - {r['nombre']}: {r['u']} uds / ${float(r['ing']):,.2f}" for r in top]) or "  Sin ventas"
    cat_txt  = "\n".join([f"  - {r['nombre']}: ${float(r['total']):,.2f}" for r in cats]) or "  Sin datos"
    cli_txt  = "\n".join([f"  - {r['nombre']}: {r['compras']} compras / ${float(r['total']):,.2f}" for r in clientes_top]) or "  Sin datos"

    return f"""Hoy es {hoy.strftime('%d/%m/%Y')}. Eres un asistente experto en gestión de negocios de venta de uniformes escolares, deportivos y empresariales.
Tienes acceso al estado actual del sistema. Responde siempre en español, de forma concisa y accionable.

=== VENTAS ===
  Histórico total : ${float(vt['t']):,.2f} ({vt['n']} transacciones)
  Esta semana     : ${float(vs['t']):,.2f} ({vs['n']} transacciones)
  Hoy             : ${float(vh['t']):,.2f} ({vh['n']} transacciones)

=== PRODUCTOS CON STOCK BAJO O AGOTADO ===
{low_txt}

=== TOP 8 PRODUCTOS MÁS VENDIDOS ===
{top_txt}

=== VENTAS POR CATEGORÍA ===
{cat_txt}

=== APARTADOS ===
  Activos         : {apt['n']} apartados
  Saldo por cobrar: ${float(apt['s']):,.2f}
  Anticipo captado: ${float(apt['a']):,.2f}
  Vencidos        : {apt_venc['n']}

=== TOP 5 CLIENTES ===
{cli_txt}

=== INVENTARIO ===
  Valor total     : ${float(val['v']):,.2f}
  Productos       : {q("SELECT COUNT(*) as n FROM productos")[0]['n']}
  Clientes        : {q("SELECT COUNT(*) as n FROM clientes")[0]['n']}
"""


# ── Render ────────────────────────────────────────────────────────────────────

SUGERENCIAS = [
    "¿Cuáles son mis productos con stock bajo o agotado?",
    "¿Cuánto vendí esta semana y qué productos fueron los más populares?",
    "¿Qué categoría genera más ingresos?",
    "¿Qué productos debería reabastecer pronto?",
    "Dame un análisis general del negocio con recomendaciones",
    "¿Cuántos apartados activos tengo y cuál es el saldo total por cobrar?",
    "¿Cuáles son los clientes que más compran?",
    "¿Tengo apartados vencidos? ¿Qué hago con ellos?",
]


def render():
    st.header("🤖 Asistente IA")

    # ── Sidebar: proveedor y key ──────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🔌 Proveedor IA")

        providers  = ["Groq", "Anthropic (Claude)"]
        saved_prov = get_config("ai_provider", "Groq")
        saved_key_groq = get_config("groq_api_key", "")
        saved_key_ant  = get_config("anthropic_api_key", "")

        prov_idx  = providers.index(saved_prov) if saved_prov in providers else 0
        provider  = st.radio("Proveedor", providers, index=prov_idx, key="ai_provider_radio")

        if provider == "Groq":
            st.caption("Llama 3.3 70B · Gratis en [console.groq.com](https://console.groq.com)")
            api_key = st.text_input("Groq API Key", type="password",
                                    value=saved_key_groq, key="input_groq_key",
                                    placeholder="gsk_...")
        else:
            st.caption("Claude Sonnet · [console.anthropic.com](https://console.anthropic.com)")
            api_key = st.text_input("Anthropic API Key", type="password",
                                    value=saved_key_ant, key="input_ant_key",
                                    placeholder="sk-ant-...")

        col_save, col_status = st.columns(2)
        if col_save.button("💾 Guardar", use_container_width=True, key="save_ai_key"):
            set_config("ai_provider", provider)
            if provider == "Groq":
                set_config("groq_api_key", api_key.strip())
            else:
                set_config("anthropic_api_key", api_key.strip())
            st.success("✅ Guardada")

        if api_key.strip():
            col_status.success("🟢 Lista")
        else:
            col_status.warning("🔴 Sin key")

        st.divider()
        st.markdown("**💡 Preguntas rápidas**")
        for s in SUGERENCIAS:
            label = s[:46] + "…" if len(s) > 46 else s
            if st.button(label, key=f"sug_{s[:18]}", use_container_width=True):
                st.session_state["_ai_prefill"] = s
                st.rerun()

        st.divider()
        st.markdown("**📊 Snapshot**")
        v   = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada'")[0]
        apt = q("SELECT COUNT(*) as n FROM apartados WHERE estado='Apartado'")[0]
        low = q("SELECT COUNT(*) as n FROM inventario WHERE cantidad<=min_stock")[0]
        st.metric("Ventas totales", f"${float(v['t']):,.2f}")
        st.metric("Transacciones",  v['n'])
        st.metric("Apartados act.", apt['n'])
        st.metric("Stock bajo",     low['n'])

        st.divider()
        if st.button("🔄 Actualizar contexto", use_container_width=True):
            st.session_state["ai_context"] = build_context()
            st.success("Contexto actualizado")
        if st.button("🗑️ Limpiar chat", use_container_width=True):
            st.session_state["ai_history"] = []
            st.rerun()

    # ── Init session state ────────────────────────────────────────────────────
    if "ai_history" not in st.session_state:
        st.session_state.ai_history = []
    if "ai_context" not in st.session_state:
        st.session_state.ai_context = build_context()

    # ── Mostrar historial ─────────────────────────────────────────────────────
    if not st.session_state.ai_history:
        st.info("👋 Hola, soy tu asistente de negocio. Tengo acceso en tiempo real a ventas, "
                "inventario, apartados y clientes. ¿En qué te ayudo?")

    for msg in st.session_state.ai_history:
        av = "🤖" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=av):
            st.markdown(msg["content"])

    # ── Input ─────────────────────────────────────────────────────────────────
    prefill    = st.session_state.pop("_ai_prefill", None)
    user_input = st.chat_input("Pregunta sobre ventas, inventario, apartados...") or prefill

    if user_input:
        if not api_key.strip():
            st.warning(f"⚠️ Ingresa tu API Key de {provider} en el panel izquierdo y guárdala.")
            return

        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)
        st.session_state.ai_history.append({"role": "user", "content": user_input})

        # Construir mensajes para la API
        messages = [{"role": "system", "content": st.session_state.ai_context}]
        for m in st.session_state.ai_history[-12:]:   # últimos 12 turnos
            messages.append({"role": m["role"], "content": m["content"]})

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Analizando..."):
                reply = get_ai_response(messages, provider, api_key.strip())
            st.markdown(reply)

        st.session_state.ai_history.append({"role": "assistant", "content": reply})

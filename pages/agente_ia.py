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
    hoy  = datetime.now().date()
    sem  = hoy - timedelta(days=7)
    mes  = hoy.replace(day=1)
    mes3 = hoy - timedelta(days=90)

    # Totales generales
    vt = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada'")[0]
    vs = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada' AND DATE(fecha)>=?", (str(sem),))[0]
    vh = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada' AND DATE(fecha)=?", (str(hoy),))[0]
    vm = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada' AND DATE(fecha)>=?", (str(mes),))[0]

    # Ventas por día de la semana (histórico completo)
    dias_semana = q("""
        SELECT
          CASE CAST(strftime('%w', fecha) AS INTEGER)
            WHEN 0 THEN 'Domingo'
            WHEN 1 THEN 'Lunes'
            WHEN 2 THEN 'Martes'
            WHEN 3 THEN 'Miércoles'
            WHEN 4 THEN 'Jueves'
            WHEN 5 THEN 'Viernes'
            WHEN 6 THEN 'Sábado'
          END as dia,
          COUNT(*) as transacciones,
          COALESCE(SUM(total),0) as total,
          COALESCE(AVG(total),0) as ticket_prom
        FROM ventas WHERE estado='Completada'
        GROUP BY strftime('%w', fecha)
        ORDER BY total DESC
    """)

    # Ventas por día (últimos 30 días)
    ventas_diarias = q("""
        SELECT DATE(fecha) as dia,
               COUNT(*) as n,
               COALESCE(SUM(total),0) as total
        FROM ventas WHERE estado='Completada'
          AND DATE(fecha) >= DATE('now','-30 days')
        GROUP BY DATE(fecha)
        ORDER BY dia DESC
        LIMIT 30
    """)

    # Ventas por mes (últimos 6 meses)
    ventas_mes = q("""
        SELECT strftime('%Y-%m', fecha) as mes,
               COUNT(*) as n,
               COALESCE(SUM(total),0) as total
        FROM ventas WHERE estado='Completada'
          AND fecha >= DATE('now','-6 months')
        GROUP BY strftime('%Y-%m', fecha)
        ORDER BY mes DESC
    """)

    # Top productos
    top = q("""
        SELECT p.nombre, p.emoji,
               SUM(vi.cantidad) as u,
               SUM(vi.subtotal) as ing,
               COUNT(DISTINCT vi.venta_id) as en_ventas
        FROM venta_items vi JOIN productos p ON p.id=vi.producto_id
        JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
        GROUP BY p.id ORDER BY ing DESC LIMIT 10
    """)

    # Productos por categoría
    cats = q("""
        SELECT c.nombre, c.emoji,
               COUNT(DISTINCT p.id) as n_prod,
               COALESCE(SUM(vi.subtotal),0) as total,
               COALESCE(SUM(vi.cantidad),0) as unidades
        FROM categorias c
        LEFT JOIN productos p ON p.categoria_id=c.id
        LEFT JOIN venta_items vi ON vi.producto_id=p.id
        LEFT JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
        GROUP BY c.id ORDER BY total DESC
    """)

    # Stock
    low = q("""
        SELECT p.nombre, i.cantidad, i.min_stock, i.max_stock, i.localidad
        FROM inventario i JOIN productos p ON p.id=i.producto_id
        WHERE i.cantidad <= i.min_stock ORDER BY i.cantidad
    """)
    inv_ok = q("""
        SELECT p.nombre, i.cantidad, i.localidad
        FROM inventario i JOIN productos p ON p.id=i.producto_id
        WHERE i.cantidad > i.min_stock ORDER BY i.cantidad DESC LIMIT 10
    """)

    # Apartados
    apt      = q("SELECT COUNT(*) as n, COALESCE(SUM(saldo),0) as s, COALESCE(SUM(abonado),0) as a, COALESCE(SUM(total_venta),0) as tv FROM apartados WHERE estado='Apartado'")[0]
    apt_venc = q("SELECT COUNT(*) as n FROM apartados WHERE estado='Apartado' AND fecha_limite IS NOT NULL AND fecha_limite < datetime('now')")[0]
    apt_sem  = q("SELECT COUNT(*) as n, COALESCE(SUM(total_venta),0) as t FROM apartados WHERE DATE(fecha_apartado)>=? AND estado IN ('Apartado','Liquidado')", (str(sem),))[0]

    # Clientes
    clientes_top = q("""
        SELECT c.nombre, c.telefono,
               COUNT(v.id) as compras,
               COALESCE(SUM(v.total),0) as total,
               MAX(v.fecha) as ultima_compra
        FROM clientes c JOIN ventas v ON v.cliente_id=c.id AND v.estado='Completada'
        GROUP BY c.id ORDER BY total DESC LIMIT 8
    """)

    # Valor inventario
    val = q("SELECT COALESCE(SUM(p.precio*i.cantidad),0) as v FROM inventario i JOIN productos p ON p.id=i.producto_id")[0]

    # Ventas por talla
    tallas_ventas = q("""
        SELECT vi.talla, SUM(vi.cantidad) as u, SUM(vi.subtotal) as ing,
               COUNT(DISTINCT vi.venta_id) as n_ventas
        FROM venta_items vi JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
        WHERE vi.talla != 'Única'
        GROUP BY vi.talla ORDER BY u DESC
    """)

    # Stock por talla (resumen)
    stock_tallas = q("""
        SELECT i.talla, SUM(i.cantidad) as total,
               SUM(CASE WHEN i.cantidad=0 THEN 1 ELSE 0 END) as agotados,
               SUM(CASE WHEN i.cantidad>0 AND i.cantidad<=i.min_stock THEN 1 ELSE 0 END) as bajos
        FROM inventario i WHERE i.talla != 'Única'
        GROUP BY i.talla ORDER BY total DESC
    """)

    # Top producto+talla
    top_prod_talla = q("""
        SELECT p.nombre, vi.talla, SUM(vi.cantidad) as u, SUM(vi.subtotal) as ing
        FROM venta_items vi JOIN productos p ON p.id=vi.producto_id
        JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
        WHERE vi.talla != 'Única'
        GROUP BY p.id, vi.talla ORDER BY u DESC LIMIT 10
    """)

    # Ventas recientes detalladas (últimas 10)
    recientes = q("""
        SELECT v.folio, DATE(v.fecha) as fecha, v.total,
               v.metodo_pago, COALESCE(c.nombre,'Público General') as cliente
        FROM ventas v LEFT JOIN clientes c ON c.id=v.cliente_id
        WHERE v.estado='Completada'
        ORDER BY v.fecha DESC LIMIT 10
    """)

    # Formateo
    dias_txt  = "\n".join([f"  {r['dia']:12s}: {r['transacciones']} ventas | ${float(r['total']):>10,.2f} | ticket prom ${float(r['ticket_prom']):,.2f}" for r in dias_semana]) or "  Sin datos"
    diarias_txt = "\n".join([f"  {r['dia']}: {r['n']} ventas / ${float(r['total']):,.2f}" for r in ventas_diarias]) or "  Sin datos"
    meses_txt = "\n".join([f"  {r['mes']}: {r['n']} ventas / ${float(r['total']):,.2f}" for r in ventas_mes]) or "  Sin datos"
    top_txt   = "\n".join([f"  {r['emoji']} {r['nombre']}: {r['u']} uds / ${float(r['ing']):,.2f} (en {r['en_ventas']} ventas)" for r in top]) or "  Sin ventas"
    cat_txt   = "\n".join([f"  {r['emoji']} {r['nombre']}: ${float(r['total']):,.2f} | {r['unidades']} uds | {r['n_prod']} productos" for r in cats]) or "  Sin datos"
    low_txt   = "\n".join([f"  - {r['nombre']}: {r['cantidad']} uds (mín {r['min_stock']} / máx {r['max_stock']}) — {r['localidad']}" for r in low]) or "  Ninguno"
    ok_txt    = "\n".join([f"  - {r['nombre']}: {r['cantidad']} uds — {r['localidad']}" for r in inv_ok]) or "  Sin datos"
    cli_txt   = "\n".join([f"  - {r['nombre']} | {r['compras']} compras | ${float(r['total']):,.2f} | últ: {str(r['ultima_compra'])[:10]}" for r in clientes_top]) or "  Sin datos"
    rec_txt   = "\n".join([f"  {r['fecha']} {r['folio']}: ${float(r['total']):,.2f} ({r['metodo_pago']}) — {r['cliente']}" for r in recientes]) or "  Sin datos"

    return f"""Hoy es {hoy.strftime('%A %d/%m/%Y')}. Eres un asistente experto en gestión de negocios de venta de uniformes.
Tienes acceso COMPLETO a la base de datos del negocio. Responde en español, de forma concisa y accionable.
Cuando te pregunten por días, meses, tendencias o rankings, SIEMPRE usa los datos de las secciones correspondientes.

=== RESUMEN DE VENTAS ===
  Total histórico : ${float(vt['t']):,.2f} en {vt['n']} transacciones
  Este mes        : ${float(vm['t']):,.2f} en {vm['n']} transacciones
  Esta semana     : ${float(vs['t']):,.2f} en {vs['n']} transacciones
  Hoy             : ${float(vh['t']):,.2f} en {vh['n']} transacciones

=== VENTAS POR DÍA DE LA SEMANA (histórico completo) ===
{dias_txt}

=== VENTAS DIARIAS (últimos 30 días) ===
{diarias_txt}

=== VENTAS POR MES (últimos 6 meses) ===
{meses_txt}

=== ÚLTIMAS 10 VENTAS ===
{rec_txt}

=== TOP 10 PRODUCTOS MÁS VENDIDOS ===
{top_txt}

=== VENTAS POR CATEGORÍA ===
{cat_txt}

=== STOCK BAJO O AGOTADO ===
{low_txt}

=== PRODUCTOS CON BUEN STOCK (top 10) ===
{ok_txt}

=== APARTADOS ===
  Activos         : {apt['n']} | Total venta: ${float(apt['tv']):,.2f}
  Saldo por cobrar: ${float(apt['s']):,.2f}
  Anticipo captado: ${float(apt['a']):,.2f}
  Vencidos        : {apt_venc['n']}
  Esta semana     : {apt_sem['n']} apartados / ${float(apt_sem['t']):,.2f}

=== TOP 8 CLIENTES ===
{cli_txt}

=== INVENTARIO ===
  Valor total del inventario: ${float(val['v']):,.2f}
  Total productos en catálogo: {q("SELECT COUNT(*) as n FROM productos")[0]['n']}
  Total clientes registrados : {q("SELECT COUNT(*) as n FROM clientes")[0]['n']}

=== VENTAS POR TALLA (histórico) ===
{"".join([f"  {r['talla']:6s}: {r['u']} uds vendidas / ${float(r['ing']):,.2f} ({r['n_ventas']} ventas)\n" for r in tallas_ventas]) or "  Sin datos de tallas"}

=== STOCK ACTUAL POR TALLA ===
{"".join([f"  {r['talla']:6s}: {r['total']} uds | {r['agotados']} agotados | {r['bajos']} stock bajo\n" for r in stock_tallas]) or "  Sin datos"}

=== TOP 10 PRODUCTO + TALLA MÁS VENDIDOS ===
{"".join([f"  {r['nombre']} talla {r['talla']}: {r['u']} uds / ${float(r['ing']):,.2f}\n" for r in top_prod_talla]) or "  Sin datos"}
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

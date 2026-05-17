import streamlit as st
import json, urllib.request, urllib.error
from database import q, get_config, set_config

MODELOS = ["llama-3.3-70b-versatile","llama-3.1-8b-instant","mixtral-8x7b-32768","gemma2-9b-it"]

SUGERENCIAS = [
    "¿Cuáles son mis productos con stock bajo o agotado?",
    "¿Cuánto vendí esta semana y qué productos fueron los más populares?",
    "¿Qué categoría genera más ingresos?",
    "¿Qué productos debería reabastecer pronto?",
    "Dame un análisis general del negocio con recomendaciones",
    "¿Cuántos apartados activos tengo y cuál es el saldo total por cobrar?",
    "¿Qué uniformes se venden más en cada categoría?",
    "¿Cuáles son los clientes que más compran?",
]


def _contexto():
    from datetime import datetime, timedelta
    hoy = datetime.now().date()
    sem = hoy - timedelta(days=7)
    vt  = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada'")[0]
    vs  = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada' AND DATE(fecha)>=?", (str(sem),))[0]
    vh  = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada' AND DATE(fecha)=?", (str(hoy),))[0]
    low = q("SELECT p.nombre,i.cantidad,i.min_stock FROM inventario i JOIN productos p ON p.id=i.producto_id WHERE i.cantidad<=i.min_stock")
    top = q("""SELECT p.nombre,SUM(vi.cantidad) as u,SUM(vi.subtotal) as ing
               FROM venta_items vi JOIN productos p ON p.id=vi.producto_id
               JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
               GROUP BY p.id ORDER BY u DESC LIMIT 5""")
    cats= q("""SELECT c.nombre,COALESCE(SUM(vi.subtotal),0) as total
               FROM categorias c
               LEFT JOIN productos p ON p.categoria_id=c.id
               LEFT JOIN venta_items vi ON vi.producto_id=p.id
               LEFT JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
               GROUP BY c.id ORDER BY total DESC""")
    apt = q("SELECT COUNT(*) as n,COALESCE(SUM(saldo),0) as s FROM apartados WHERE estado='Apartado'")[0]
    val = q("SELECT COALESCE(SUM(p.precio*i.cantidad),0) as v FROM inventario i JOIN productos p ON p.id=i.producto_id")[0]

    return f"""=== DATOS DEL NEGOCIO (tiempo real) ===
VENTAS: Histórico ${float(vt['t']):,.2f} ({vt['n']} transacciones) | Semana ${float(vs['t']):,.2f} ({vs['n']}) | Hoy ${float(vh['t']):,.2f} ({vh['n']})
STOCK BAJO/AGOTADO: {'; '.join([f"{r['nombre']}({r['cantidad']})" for r in low]) or 'Ninguno'}
TOP PRODUCTOS: {'; '.join([f"{r['nombre']}({r['u']} uds/${ float(r['ing']):,.0f})" for r in top]) or 'Sin ventas'}
POR CATEGORÍA: {'; '.join([f"{r['nombre']}=${float(r['total']):,.0f}" for r in cats])}
APARTADOS ACTIVOS: {apt['n']} apartados · ${float(apt['s']):,.2f} saldo por cobrar
VALOR INVENTARIO: ${float(val['v']):,.2f}
CLIENTES: {q("SELECT COUNT(*) as n FROM clientes")[0]['n']} | PRODUCTOS: {q("SELECT COUNT(*) as n FROM productos")[0]['n']}
"""


def _llamar_groq(api_key, model, messages):
    payload = json.dumps({"model":model,"messages":messages,"temperature":0.7,"max_tokens":1024}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={"Content-Type":"application/json","Authorization":f"Bearer {api_key}"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        if "error" in data:
            raise RuntimeError(data["error"].get("message","Error desconocido"))
        return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            msg = json.loads(body).get("error",{}).get("message", body)
        except:
            msg = body
        raise RuntimeError(f"HTTP {e.code}: {msg}")


def _demo(texto):
    t = texto.lower()
    if any(k in t for k in ["stock","reabastecer","agotado"]):
        low = q("SELECT p.nombre,i.cantidad,i.min_stock FROM inventario i JOIN productos p ON p.id=i.producto_id WHERE i.cantidad<=i.min_stock")
        lineas = "\n".join([f"• **{r['nombre']}**: {r['cantidad']} uds (mínimo: {r['min_stock']})" for r in low]) or "• ✅ Todo en orden"
        return f"📦 **Productos que necesitan reabastecimiento:**\n\n{lineas}"
    if any(k in t for k in ["apartado","abono","saldo"]):
        apt = q("SELECT COUNT(*) as n,COALESCE(SUM(saldo),0) as s,COALESCE(SUM(abonado),0) as a FROM apartados WHERE estado='Apartado'")[0]
        return f"💼 **Apartados activos:** {apt['n']}\n\n• Saldo por cobrar: **${float(apt['s']):,.2f}**\n• Anticipo captado: **${float(apt['a']):,.2f}**"
    if any(k in t for k in ["venta","ingreso","semana","vendí"]):
        v = q("SELECT COALESCE(SUM(total),0) as t,COUNT(*) as n FROM ventas WHERE estado='Completada'")[0]
        tkt = float(v['t'])/v['n'] if v['n'] else 0
        return f"📊 **Resumen de ventas:**\n\n• Total: **${float(v['t']):,.2f}**\n• Transacciones: **{v['n']}**\n• Ticket promedio: **${tkt:,.2f}**"
    return "🤖 **Modo demo.** Configura tu GROQ API Key en el panel derecho para análisis con IA real.\n\nPuedo analizar ventas, inventario, apartados y darte recomendaciones para tu negocio de uniformes."


def render():
    st.header("🤖 Agente IA")
    st.caption("Asistente inteligente con acceso a tus datos · Powered by GROQ")

    if "ai_hist" not in st.session_state:
        st.session_state.ai_hist = []

    col_chat, col_cfg = st.columns([3,1])

    with col_cfg:
        st.subheader("⚙️ Config")
        saved_key = get_config("groq_api_key","")
        api_key   = st.text_input("GROQ API Key", value=saved_key, type="password", placeholder="gsk_...")
        model     = st.selectbox("Modelo", MODELOS)
        if st.button("💾 Guardar key", use_container_width=True):
            set_config("groq_api_key", api_key.strip())
            st.success("✅ Guardada"); st.rerun()

        key_activa = api_key.strip()
        if key_activa:
            st.success("🟢 IA activa")
        else:
            st.warning("🔴 Modo demo")
            st.caption("Obtén tu key gratis en console.groq.com")

        st.divider()
        st.subheader("💡 Preguntas rápidas")
        for s in SUGERENCIAS:
            label = s[:48]+"…" if len(s)>48 else s
            if st.button(label, use_container_width=True, key=f"sug_{s[:15]}"):
                st.session_state["_ai_prompt"] = s
                st.rerun()

        st.divider()
        st.subheader("📊 Snapshot")
        v   = q("SELECT COALESCE(SUM(total),0) as t,COUNT(*) as n FROM ventas WHERE estado='Completada'")[0]
        apt = q("SELECT COUNT(*) as n FROM apartados WHERE estado='Apartado'")[0]
        low = q("SELECT COUNT(*) as n FROM inventario WHERE cantidad<=min_stock")[0]
        st.metric("Ventas totales", f"${float(v['t']):,.2f}")
        st.metric("Transacciones",  v['n'])
        st.metric("Apartados",      apt['n'])
        st.metric("Stock bajo",     low['n'])
        if st.button("🗑️ Limpiar chat", use_container_width=True):
            st.session_state.ai_hist = []; st.rerun()

    with col_chat:
        if not st.session_state.ai_hist:
            st.info("👋 Hola, soy tu asistente. Tengo acceso en tiempo real a ventas, inventario, apartados y clientes. ¿En qué te ayudo?")

        for msg in st.session_state.ai_hist:
            av = "🤖" if msg["role"]=="assistant" else "👤"
            with st.chat_message(msg["role"], avatar=av):
                st.markdown(msg["content"])

        prompt_rapido = st.session_state.pop("_ai_prompt", None)
        user_input    = st.chat_input("Escribe tu pregunta...") or prompt_rapido

        if user_input:
            st.session_state.ai_hist.append({"role":"user","content":user_input})
            with st.chat_message("user", avatar="👤"):
                st.markdown(user_input)

            key_use = get_config("groq_api_key","").strip()
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Analizando datos..."):
                    if not key_use:
                        reply = _demo(user_input)
                    else:
                        ctx = _contexto()
                        sys_msg = ("Eres un asistente experto en gestión de negocios de venta de uniformes escolares, "
                                   "deportivos y empresariales. Respondes en español, de forma clara, práctica y con emojis. "
                                   "Siempre basas tus análisis en los datos reales proporcionados.\n\n" + ctx)
                        msgs = [{"role":"system","content":sys_msg}]
                        msgs += [{"role":m["role"],"content":m["content"]} for m in st.session_state.ai_hist[-10:]]
                        try:
                            reply = _llamar_groq(key_use, model, msgs)
                        except RuntimeError as e:
                            reply = f"❌ Error GROQ: {e}\n\nVerifica que tu API Key sea válida en console.groq.com"
                st.markdown(reply)
            st.session_state.ai_hist.append({"role":"assistant","content":reply})

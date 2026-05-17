import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import q, run, get_config

def render():
    st.header("💼 Apartados")
    st.caption("Gestión de ventas en abonos y apartados de mercancía")

    # KPIs
    activos  = q("SELECT COUNT(*) as n, COALESCE(SUM(saldo),0) as s FROM apartados WHERE estado='Apartado'")[0]
    captado  = q("SELECT COALESCE(SUM(abonado),0) as t FROM apartados WHERE estado='Apartado'")[0]
    vencidos = _vencidos()

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("💼 Apartados activos",   activos['n'])
    c2.metric("💵 Saldo por cobrar",    f"${float(activos['s']):,.2f}")
    c3.metric("💰 Anticipo captado",    f"${float(captado['t']):,.2f}")
    c4.metric("⚠️ Vencidos / por vencer", len(vencidos),
              delta_color="inverse", delta=f"-{len(vencidos)}" if vencidos else "0")

    st.divider()

    tab_activos, tab_vencer, tab_hist = st.tabs([
        "🟢 Activos", "⚠️ Por Vencer / Vencidos", "📋 Historial"
    ])

    with tab_activos:
        _tab_activos()
    with tab_vencer:
        _tab_vencer()
    with tab_hist:
        _tab_historial()


def _vencidos():
    dias = int(get_config("apartado_dias_alerta","7"))
    limite = (datetime.now() + timedelta(days=dias)).isoformat()
    return q("SELECT * FROM apartados WHERE estado='Apartado' AND fecha_limite IS NOT NULL AND fecha_limite <= ?",
             (limite,))


def _tab_activos():
    rows = q("""
        SELECT a.*, c.nombre as cliente_nombre
        FROM apartados a LEFT JOIN clientes c ON c.id=a.cliente_id
        WHERE a.estado='Apartado' ORDER BY a.fecha_apartado DESC
    """)
    if not rows:
        st.info("No hay apartados activos 🎉")
        return
    for a in rows:
        _card_apartado(a, tab_ctx="activos")


def _tab_vencer():
    dias = int(get_config("apartado_dias_alerta","7"))
    st.caption(f"Apartados que vencen en los próximos {dias} días o ya vencieron")

    hoy    = datetime.now()
    limite = (hoy + timedelta(days=dias)).isoformat()
    rows   = q("""
        SELECT a.*, c.nombre as cliente_nombre
        FROM apartados a LEFT JOIN clientes c ON c.id=a.cliente_id
        WHERE a.estado='Apartado' AND a.fecha_limite IS NOT NULL AND a.fecha_limite <= ?
        ORDER BY a.fecha_limite ASC
    """, (limite,))

    if not rows:
        st.success(f"✅ Sin apartados por vencer en los próximos {dias} días")
    else:
        for a in rows:
            fl = a['fecha_limite'][:10] if a['fecha_limite'] else "—"
            vencido = a['fecha_limite'] and a['fecha_limite'][:10] < hoy.strftime('%Y-%m-%d')
            label = "🔴 VENCIDO" if vencido else "🟡 Por vencer"
            st.markdown(f"**{label}** · Folio {a['folio']} · Vence: {fl}")
            _card_apartado(a, collapsed=False, tab_ctx="vencer")

    st.divider()
    st.subheader("📊 Análisis de antigüedad")
    todos = q("""
        SELECT a.folio, a.fecha_apartado, a.fecha_limite, a.saldo, a.total_venta,
               c.nombre as cliente
        FROM apartados a LEFT JOIN clientes c ON c.id=a.cliente_id
        WHERE a.estado='Apartado' ORDER BY a.fecha_apartado ASC
    """)
    if todos:
        df = pd.DataFrame(todos)
        df['Días activo'] = df['fecha_apartado'].apply(
            lambda x: (datetime.now() - datetime.fromisoformat(str(x)[:19])).days)
        df['Vence'] = df['fecha_limite'].apply(lambda x: str(x)[:10] if x else "Sin límite")
        df['Saldo'] = df['saldo'].apply(lambda x: f"${float(x):,.2f}")
        df['% Pagado'] = df.apply(
            lambda r: f"{(1 - float(r['saldo'])/float(r['total_venta']))*100:.0f}%" if float(r['total_venta']) else "0%",
            axis=1)
        st.dataframe(
            df[['folio','cliente','Días activo','Vence','Saldo','% Pagado']].rename(
                columns={'folio':'Folio','cliente':'Cliente'}),
            use_container_width=True, hide_index=True
        )
        if int(get_config("apartado_dias_alerta","7")) != 7:
            pass
        nuevo_dias = st.number_input("Días de alerta (configurable)", min_value=1,
                                     value=int(get_config("apartado_dias_alerta","7")))
        if st.button("Guardar configuración de alerta"):
            from database import set_config
            set_config("apartado_dias_alerta", str(nuevo_dias))
            st.success("✅ Guardado"); st.rerun()


def _tab_historial():
    rows = q("""
        SELECT a.*, c.nombre as cliente_nombre
        FROM apartados a LEFT JOIN clientes c ON c.id=a.cliente_id
        WHERE a.estado IN ('Liquidado','Cancelado')
        ORDER BY a.fecha_apartado DESC LIMIT 100
    """)
    if not rows:
        st.info("Sin historial aún")
        return
    liq  = [r for r in rows if r['estado']=='Liquidado']
    canc = [r for r in rows if r['estado']=='Cancelado']
    c1,c2 = st.columns(2)
    c1.metric("✅ Liquidados",  len(liq))
    c2.metric("❌ Cancelados", len(canc))
    for a in rows:
        ico = "✅" if a['estado']=='Liquidado' else "❌"
        with st.expander(f"{ico} **{a['folio']}** · {a['cliente_nombre'] or 'Sin cliente'} · ${float(a['total_venta']):,.2f}"):
            st.markdown(f"**Estado:** {a['estado']}  \n**Fecha:** {str(a['fecha_apartado'])[:10]}")
            _detalle_items(a['id'])


def _card_apartado(a, collapsed=True, tab_ctx=""):
    pct = int((float(a['abonado']) / float(a['total_venta'])) * 100) if float(a['total_venta']) else 0
    fl  = str(a['fecha_limite'])[:10] if a['fecha_limite'] else "Sin límite"
    with st.expander(
        f"**{a['folio']}** · {a['cliente_nombre'] or 'Sin cliente'} · "
        f"Total: ${float(a['total_venta']):,.2f} · Saldo: **${float(a['saldo']):,.2f}** · Vence: {fl}",
        expanded=not collapsed
    ):
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Total venta",  f"${float(a['total_venta']):,.2f}")
        m2.metric("Pagado",       f"${float(a['abonado']):,.2f}")
        m3.metric("Saldo",        f"${float(a['saldo']):,.2f}")
        m4.metric("% Cubierto",   f"{pct}%")
        st.progress(pct, text=f"{pct}% pagado")
        if a['notas']:
            st.caption(f"📝 {a['notas']}")

        tab_p, tab_ab, tab_acc = st.tabs(["🏷️ Productos", "💵 Abonos", "⚡ Acciones"])

        with tab_p:
            _detalle_items(a['id'])

        with tab_ab:
            _detalle_abonos(a['id'])
            st.divider()
            # Formulario de abono
            with st.form(f"abono_{a['id']}_{tab_ctx}"):
                st.markdown("**Registrar nuevo abono**")
                ab1, ab2 = st.columns(2)
                monto_ab = ab1.number_input("Monto del abono", min_value=0.01,
                                            max_value=float(a['saldo']), step=10.0, format="%.2f")
                metodo_ab = ab2.selectbox("Método",
                                          ["Efectivo","Tarjeta de Débito","Tarjeta de Crédito","Transferencia"])
                notas_ab = st.text_input("Notas del abono")
                if st.form_submit_button("💵 Registrar abono", type="primary", use_container_width=True, key=None):
                    _registrar_abono(a['id'], monto_ab, metodo_ab, notas_ab)

        with tab_acc:
            st.markdown("**Acciones sobre este apartado**")
            col_liq, col_can = st.columns(2)
            if col_liq.button("✅ Liquidar (cobrar saldo y entregar)",
                              key=f"liq_{a['id']}_{tab_ctx}", use_container_width=True, type="primary"):
                _liquidar(a)
            st.caption("Al liquidar se descuenta el inventario y el apartado queda cerrado.")
            st.divider()
            conf_cancel = st.checkbox(f"Confirmar cancelación del apartado {a['folio']}", key=f"chk_can_{a['id']}_{tab_ctx}")
            if conf_cancel:
                if col_can.button("❌ Cancelar apartado", key=f"can_{a['id']}_{tab_ctx}", use_container_width=True):
                    run("UPDATE apartados SET estado='Cancelado' WHERE id=?", (a['id'],))
                    st.warning("Apartado cancelado"); st.rerun()


def _detalle_items(apartado_id):
    items = q("""
        SELECT ai.cantidad, ai.precio_unitario, ai.subtotal, p.nombre, p.emoji
        FROM apartado_items ai JOIN productos p ON p.id=ai.producto_id
        WHERE ai.apartado_id=?
    """, (apartado_id,))
    if items:
        df = pd.DataFrame([{
            'Producto': f"{i['emoji']} {i['nombre']}",
            'Talla': i.get('talla','—'),
            'Cant.': i['cantidad'],
            'Precio': f"${float(i['precio_unitario']):,.2f}",
            'Subtotal': f"${float(i['subtotal']):,.2f}",
        } for i in items])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("Sin productos registrados")


def _detalle_abonos(apartado_id):
    abonos = q("SELECT * FROM apartado_abonos WHERE apartado_id=? ORDER BY fecha DESC", (apartado_id,))
    if abonos:
        df = pd.DataFrame([{
            'Fecha': str(ab['fecha'])[:16],
            'Monto': f"${float(ab['monto']):,.2f}",
            'Método': ab['metodo_pago'],
            'Notas': ab['notas'] or '',
        } for ab in abonos])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("Sin abonos registrados")


def _registrar_abono(apartado_id, monto, metodo, notas):
    run("INSERT INTO apartado_abonos(apartado_id,fecha,monto,metodo_pago,notas) VALUES(?,?,?,?,?)",
        (apartado_id, datetime.now().isoformat(), monto, metodo, notas))
    apt = q("SELECT abonado, saldo, total_venta FROM apartados WHERE id=?", (apartado_id,))[0]
    nuevo_abonado = float(apt['abonado']) + monto
    nuevo_saldo   = round(float(apt['total_venta']) - nuevo_abonado, 2)
    nuevo_estado  = 'Liquidado' if nuevo_saldo <= 0 else 'Apartado'
    run("UPDATE apartados SET abonado=?, saldo=?, estado=? WHERE id=?",
        (nuevo_abonado, max(0, nuevo_saldo), nuevo_estado, apartado_id))
    if nuevo_estado == 'Liquidado':
        # Descontar inventario al liquidar
        items = q("SELECT producto_id, cantidad FROM apartado_items WHERE apartado_id=?", (apartado_id,))
        for item in items:
            inv = q("SELECT id,cantidad FROM inventario WHERE producto_id=? LIMIT 1", (item['producto_id'],))
            if inv:
                run("UPDATE inventario SET cantidad=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (max(0, inv[0]['cantidad']-item['cantidad']), inv[0]['id']))
        st.success("✅ Apartado liquidado e inventario descontado")
    else:
        st.success(f"✅ Abono de ${monto:,.2f} registrado. Saldo restante: ${max(0,nuevo_saldo):,.2f}")
    st.rerun()


def _liquidar(a):
    saldo = float(a['saldo'])
    if saldo > 0:
        run("INSERT INTO apartado_abonos(apartado_id,fecha,monto,metodo_pago,notas) VALUES(?,?,?,?,?)",
            (a['id'], datetime.now().isoformat(), saldo, 'Efectivo', 'Liquidación final'))
    run("UPDATE apartados SET abonado=total_venta, saldo=0, estado='Liquidado' WHERE id=?", (a['id'],))
    items = q("SELECT producto_id, cantidad FROM apartado_items WHERE apartado_id=?", (a['id'],))
    for item in items:
        inv = q("SELECT id,cantidad FROM inventario WHERE producto_id=? LIMIT 1", (item['producto_id'],))
        if inv:
            run("UPDATE inventario SET cantidad=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (max(0, inv[0]['cantidad']-item['cantidad']), inv[0]['id']))
    st.success("✅ Apartado liquidado. Inventario descontado."); st.rerun()

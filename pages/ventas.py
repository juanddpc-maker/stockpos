import streamlit as st
import pandas as pd
from database import q, run

def render():
    st.markdown('<p class="sp-title">💳 <span class="sp-accent">Ventas</span></p>', unsafe_allow_html=True)
    st.markdown('<p class="sp-subtitle">Historial completo de transacciones</p>', unsafe_allow_html=True)

    # Filters
    fc1, fc2, fc3, fc4 = st.columns(4)
    search = fc1.text_input("🔍 Buscar folio/cliente", label_visibility="collapsed", placeholder="Folio o cliente...")
    estado_f = fc2.selectbox("Estado", ["Todos", "Completada", "Cancelada"], label_visibility="collapsed")
    metodo_f = fc3.selectbox("Método pago", ["Todos", "Efectivo", "Tarjeta", "Transferencia"], label_visibility="collapsed")
    orden_f = fc4.selectbox("Ordenar", ["Más reciente", "Más antigua", "Mayor monto", "Menor monto"], label_visibility="collapsed")

    ventas = q("""
        SELECT v.*, c.nombre as cliente_nombre
        FROM ventas v LEFT JOIN clientes c ON c.id=v.cliente_id
        ORDER BY v.fecha DESC
    """)

    # Apply filters
    if search:
        s = search.lower()
        ventas = [v for v in ventas if s in v['folio'].lower() or (v['cliente_nombre'] and s in v['cliente_nombre'].lower())]
    if estado_f != "Todos":
        ventas = [v for v in ventas if v['estado'] == estado_f]
    if metodo_f != "Todos":
        ventas = [v for v in ventas if v['metodo_pago'] == metodo_f]
    if orden_f == "Más antigua":
        ventas = sorted(ventas, key=lambda x: x['fecha'])
    elif orden_f == "Mayor monto":
        ventas = sorted(ventas, key=lambda x: x['total'], reverse=True)
    elif orden_f == "Menor monto":
        ventas = sorted(ventas, key=lambda x: x['total'])

    # Summary
    total_sum = sum(v['total'] for v in ventas if v['estado'] == 'Completada')
    m1, m2, m3 = st.columns(3)
    m1.metric("Total mostrado", f"${total_sum:,.2f}")
    m2.metric("Transacciones", len(ventas))
    m3.metric("Ticket promedio", f"${total_sum/len(ventas):,.2f}" if ventas else "$0")

    st.markdown("---")

    if not ventas:
        st.info("No hay ventas con los filtros aplicados")
        return

    for v in ventas:
        cliente = v['cliente_nombre'] or 'Público General'
        estado_icon = "✅" if v['estado'] == 'Completada' else "❌"
        with st.expander(f"{estado_icon} **{v['folio']}** · {cliente} · **${v['total']:,.2f}** · {v['fecha'][:16]}"):
            vc1, vc2, vc3, vc4 = st.columns(4)
            vc1.markdown(f"**Cliente:** {cliente}")
            vc2.markdown(f"**Método:** {v['metodo_pago']}")
            vc3.markdown(f"**Estado:** {v['estado']}")
            vc4.markdown(f"**Fecha:** {v['fecha'][:16]}")

            # Items
            items = q("""
                SELECT vi.*, p.nombre, p.emoji FROM venta_items vi
                JOIN productos p ON p.id=vi.producto_id WHERE vi.venta_id=?
            """, (v['id'],))

            if items:
                st.markdown("**Productos:**")
                df_items = pd.DataFrame([{
                    'Producto': f"{i['emoji']} {i['nombre']}",
                    'Cantidad': i['cantidad'],
                    'Precio Unit.': f"${i['precio_unitario']:,.2f}",
                    'Subtotal': f"${i['subtotal']:,.2f}"
                } for i in items])
                st.dataframe(df_items, use_container_width=True, hide_index=True)

            st.markdown(f"""
            <div style="text-align:right;background:#1a2744;border-radius:8px;padding:10px;margin-top:8px">
                <span style="color:#8892a4;margin-right:20px">Subtotal: ${v['subtotal']:,.2f}</span>
                <span style="color:#8892a4;margin-right:20px">IVA: ${v['impuesto']:,.2f}</span>
                <span style="color:#f5a623;font-weight:700;font-size:18px">Total: ${v['total']:,.2f}</span>
            </div>""", unsafe_allow_html=True)

            if v['estado'] == 'Completada':
                if st.button(f"❌ Cancelar Venta", key=f"cancel_{v['id']}"):
                    run("UPDATE ventas SET estado='Cancelada' WHERE id=?", (v['id'],))
                    st.warning("Venta cancelada")
                    st.rerun()

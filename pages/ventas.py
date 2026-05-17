import streamlit as st
import pandas as pd
from database import q, run

def render():
    st.header("🧾 Ventas")

    tab_hist, tab_detalle = st.tabs(["📋 Historial", "🔍 Buscar / Filtrar"])

    ventas = q("""
        SELECT v.*, COALESCE(c.nombre,'Público General') as cliente_nombre
        FROM ventas v LEFT JOIN clientes c ON c.id=v.cliente_id
        ORDER BY v.fecha DESC
    """)

    with tab_hist:
        # Resumen rápido
        total_sum = sum(float(v['total']) for v in ventas if v['estado']=='Completada')
        m1,m2,m3 = st.columns(3)
        m1.metric("Total en historial", f"${total_sum:,.2f}")
        m2.metric("Transacciones",      len(ventas))
        m3.metric("Promedio",           f"${total_sum/len(ventas):,.2f}" if ventas else "$0")
        st.divider()

        for v in ventas[:50]:  # mostramos máx 50
            ico  = "✅" if v['estado']=='Completada' else "❌"
            with st.expander(f"{ico} **{v['folio']}** · {v['cliente_nombre']} · **${float(v['total']):,.2f}** · {str(v['fecha'])[:16]}"):
                vc1,vc2,vc3,vc4 = st.columns(4)
                vc1.markdown(f"**Cliente:** {v['cliente_nombre']}")
                vc2.markdown(f"**Pago:** {v['metodo_pago']}")
                vc3.markdown(f"**Estado:** {v['estado']}")
                vc4.markdown(f"**Fecha:** {str(v['fecha'])[:16]}")

                items = q("""
                    SELECT vi.cantidad, vi.precio_unitario, vi.subtotal, p.nombre, p.emoji
                    FROM venta_items vi JOIN productos p ON p.id=vi.producto_id WHERE vi.venta_id=?
                """, (v['id'],))
                if items:
                    df = pd.DataFrame([{
                        'Producto': f"{i['emoji']} {i['nombre']}",
                        'Cant.': i['cantidad'],
                        'Precio': f"${float(i['precio_unitario']):,.2f}",
                        'Subtotal': f"${float(i['subtotal']):,.2f}",
                    } for i in items])
                    st.dataframe(df, use_container_width=True, hide_index=True)

                st.markdown(f"**Subtotal:** ${float(v['subtotal']):,.2f} · "
                            f"**IVA:** ${float(v['impuesto']):,.2f} · "
                            f"**Total: ${float(v['total']):,.2f}**")
                if v['notas']:
                    st.caption(f"📝 {v['notas']}")

                if v['estado'] == 'Completada':
                    if st.button("❌ Cancelar venta", key=f"cancel_{v['id']}"):
                        run("UPDATE ventas SET estado='Cancelada' WHERE id=?", (v['id'],))
                        st.warning("Venta cancelada")
                        st.rerun()

    with tab_detalle:
        st.subheader("Filtros avanzados")
        fc1,fc2,fc3 = st.columns(3)
        buscar  = fc1.text_input("Folio o cliente", placeholder="Buscar...")
        estado_f= fc2.selectbox("Estado",    ["Todos","Completada","Cancelada"])
        metodo_f= fc3.selectbox("Método",    ["Todos","Efectivo","Tarjeta de Débito","Tarjeta de Crédito","Transferencia"])

        fil = ventas
        if buscar:
            s = buscar.lower()
            fil = [v for v in fil if s in v['folio'].lower() or s in v['cliente_nombre'].lower()]
        if estado_f != "Todos":  fil = [v for v in fil if v['estado']==estado_f]
        if metodo_f != "Todos":  fil = [v for v in fil if v['metodo_pago']==metodo_f]

        if fil:
            df_fil = pd.DataFrame([{
                'Folio': v['folio'],
                'Fecha': str(v['fecha'])[:16],
                'Cliente': v['cliente_nombre'],
                'Total': f"${float(v['total']):,.2f}",
                'Pago': v['metodo_pago'],
                'Estado': v['estado'],
            } for v in fil])
            st.dataframe(df_fil, use_container_width=True, hide_index=True)
            total_f = sum(float(v['total']) for v in fil if v['estado']=='Completada')
            st.caption(f"Total filtrado: **${total_f:,.2f}** en {len(fil)} transacción(es)")
        else:
            st.info("Sin resultados")

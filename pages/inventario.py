import streamlit as st
import pandas as pd
from database import q, run

def render():
    st.markdown('<p class="sp-title">🗄️ <span class="sp-accent">Inventario</span></p>', unsafe_allow_html=True)
    st.markdown('<p class="sp-subtitle">Control de stock por producto y localidad</p>', unsafe_allow_html=True)

    tab_list, tab_add, tab_bulk = st.tabs(["📋 Stock Actual", "➕ Agregar Stock", "📝 Ajuste Masivo"])

    inv = q("""
        SELECT i.*, p.nombre, p.emoji, p.precio, c.nombre as categoria
        FROM inventario i
        JOIN productos p ON p.id=i.producto_id
        LEFT JOIN categorias c ON c.id=p.categoria_id
        ORDER BY p.nombre
    """)

    with tab_list:
        # Filter
        sf1, sf2 = st.columns(2)
        search = sf1.text_input("🔍 Buscar", placeholder="Producto o localidad...", label_visibility="collapsed")
        status_filter = sf2.selectbox("Estado", ["Todos", "Sin Stock", "Stock Bajo", "Normal"], label_visibility="collapsed")

        filtered = inv
        if search:
            s = search.lower()
            filtered = [r for r in filtered if s in r['nombre'].lower() or s in r['localidad'].lower()]
        if status_filter == "Sin Stock":
            filtered = [r for r in filtered if r['cantidad'] == 0]
        elif status_filter == "Stock Bajo":
            filtered = [r for r in filtered if 0 < r['cantidad'] <= r['min_stock']]
        elif status_filter == "Normal":
            filtered = [r for r in filtered if r['cantidad'] > r['min_stock']]

        for row in filtered:
            status = "❌ Sin Stock" if row['cantidad'] == 0 else ("⚠️ Stock Bajo" if row['cantidad'] <= row['min_stock'] else "✅ Normal")
            color = "#e94560" if row['cantidad'] == 0 else ("#f5a623" if row['cantidad'] <= row['min_stock'] else "#00c896")
            pct = min(100, (row['cantidad'] / max(row['max_stock'], 1)) * 100)

            with st.expander(f"{row['emoji']} **{row['nombre']}** | {row['localidad']} | Stock: **{row['cantidad']}** | {status}"):
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("Cantidad Actual", row['cantidad'])
                mc2.metric("Stock Mínimo", row['min_stock'])
                mc3.metric("Stock Máximo", row['max_stock'])
                mc4.metric("Valor", f"${row['precio'] * row['cantidad']:,.2f}")

                st.markdown(f"""
                <div style="background:#2d3f5c;border-radius:4px;height:8px;margin:8px 0">
                    <div style="background:{color};height:8px;border-radius:4px;width:{pct:.0f}%"></div>
                </div>""", unsafe_allow_html=True)

                with st.form(f"inv_edit_{row['id']}"):
                    fc1, fc2, fc3 = st.columns(3)
                    tipo = fc1.selectbox("Tipo de Ajuste", ["Establecer", "Agregar", "Restar"])
                    nueva_cant = fc2.number_input("Cantidad", min_value=0, value=row['cantidad'])
                    nueva_loc = fc3.text_input("Localidad", value=row['localidad'])
                    fm1, fm2 = st.columns(2)
                    nuevo_min = fm1.number_input("Stock Mínimo", min_value=0, value=row['min_stock'])
                    nuevo_max = fm2.number_input("Stock Máximo", min_value=1, value=row['max_stock'])

                    if st.form_submit_button("💾 Actualizar", type="primary"):
                        actual = row['cantidad']
                        if tipo == "Establecer":
                            final = nueva_cant
                        elif tipo == "Agregar":
                            final = actual + nueva_cant
                        else:
                            final = max(0, actual - nueva_cant)
                        run("UPDATE inventario SET cantidad=?, localidad=?, min_stock=?, max_stock=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                            (final, nueva_loc, nuevo_min, nuevo_max, row['id']))
                        st.success(f"Stock actualizado: {actual} → {final}")
                        st.rerun()

    with tab_add:
        st.markdown("#### ➕ Agregar Registro de Stock")
        prods = q("SELECT * FROM productos ORDER BY nombre")
        with st.form("add_stock"):
            prod_opts = {f"{p['emoji']} {p['nombre']}": p['id'] for p in prods}
            prod_sel = st.selectbox("Producto *", list(prod_opts.keys()))
            c1, c2 = st.columns(2)
            localidad = c1.text_input("Localidad *", value="Almacén Central")
            cantidad = c2.number_input("Cantidad", min_value=0)
            c3, c4 = st.columns(2)
            min_s = c3.number_input("Stock Mínimo", min_value=0, value=5)
            max_s = c4.number_input("Stock Máximo", min_value=1, value=100)
            if st.form_submit_button("💾 Agregar", type="primary", use_container_width=True):
                pid = prod_opts[prod_sel]
                existing = q("SELECT id FROM inventario WHERE producto_id=? AND localidad=?", (pid, localidad))
                if existing:
                    run("UPDATE inventario SET cantidad=cantidad+?, min_stock=?, max_stock=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (cantidad, min_s, max_s, existing[0]['id']))
                    st.success("Stock actualizado")
                else:
                    run("INSERT INTO inventario (producto_id, localidad, cantidad, min_stock, max_stock) VALUES (?,?,?,?,?)",
                        (pid, localidad, cantidad, min_s, max_s))
                    st.success("Stock agregado")
                st.rerun()

    with tab_bulk:
        st.markdown("#### 📝 Ajuste Masivo de Inventario")
        st.info("Modifica el stock de todos los productos directamente en la tabla.")

        df = pd.DataFrame([{
            'ID': r['id'], 'Producto': f"{r['emoji']} {r['nombre']}",
            'Localidad': r['localidad'], 'Cantidad': r['cantidad'],
            'Mín Stock': r['min_stock'], 'Máx Stock': r['max_stock'],
        } for r in inv])

        edited = st.data_editor(
            df, use_container_width=True, hide_index=True,
            disabled=['ID', 'Producto'],
            column_config={
                'Cantidad': st.column_config.NumberColumn(min_value=0),
                'Mín Stock': st.column_config.NumberColumn(min_value=0),
                'Máx Stock': st.column_config.NumberColumn(min_value=1),
            }
        )

        if st.button("💾 Guardar Ajuste Masivo", type="primary"):
            for _, row in edited.iterrows():
                run("UPDATE inventario SET cantidad=?, min_stock=?, max_stock=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (int(row['Cantidad']), int(row['Mín Stock']), int(row['Máx Stock']), int(row['ID'])))
            st.success("✅ Inventario actualizado correctamente")
            st.rerun()

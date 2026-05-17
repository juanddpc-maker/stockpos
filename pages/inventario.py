import streamlit as st
import pandas as pd
from database import q, run

def render():
    st.header("🗄️ Inventario")

    tab_ver, tab_agregar, tab_masivo = st.tabs(["📋 Stock Actual", "➕ Agregar / Ajustar", "📝 Ajuste Masivo"])

    inv = q("""
        SELECT i.*, p.nombre, p.emoji, p.precio, c.nombre as categoria
        FROM inventario i JOIN productos p ON p.id=i.producto_id
        LEFT JOIN categorias c ON c.id=p.categoria_id ORDER BY p.nombre
    """)

    with tab_ver:
        # Filtro de estado
        fc1, fc2 = st.columns([3,1])
        buscar = fc1.text_input("🔍 Buscar", placeholder="Producto o localidad...", label_visibility="collapsed")
        estado_f = fc2.selectbox("Estado", ["Todos","Sin Stock","Stock Bajo","Normal"], label_visibility="collapsed")

        fil = inv
        if buscar:
            s = buscar.lower()
            fil = [r for r in fil if s in r['nombre'].lower() or s in r['localidad'].lower()]
        if estado_f == "Sin Stock":   fil = [r for r in fil if r['cantidad']==0]
        elif estado_f == "Stock Bajo":fil = [r for r in fil if 0<r['cantidad']<=r['min_stock']]
        elif estado_f == "Normal":    fil = [r for r in fil if r['cantidad']>r['min_stock']]

        st.caption(f"{len(fil)} registro(s)")

        for row in fil:
            pct    = min(100, (row['cantidad']/max(row['max_stock'],1))*100)
            status = "❌ Sin Stock" if row['cantidad']==0 else ("⚠️ Stock Bajo" if row['cantidad']<=row['min_stock'] else "✅ Normal")
            with st.expander(f"{row['emoji']} **{row['nombre']}** | {row['localidad']} | **{row['cantidad']} uds** | {status}"):
                m1,m2,m3,m4 = st.columns(4)
                m1.metric("Cantidad",    row['cantidad'])
                m2.metric("Mínimo",      row['min_stock'])
                m3.metric("Máximo",      row['max_stock'])
                m4.metric("Valor stock", f"${float(row['precio'])*row['cantidad']:,.2f}")
                st.progress(int(pct), text=f"{pct:.0f}% del máximo")
                _form_ajuste(row)

    with tab_agregar:
        st.subheader("Agregar o ajustar stock")
        prods = q("SELECT * FROM productos ORDER BY nombre")
        with st.form("form_add_stock"):
            prod_opts = {f"{p['emoji']} {p['nombre']}": p['id'] for p in prods}
            prod_sel  = st.selectbox("Producto *", list(prod_opts.keys()))

            c1,c2 = st.columns(2)
            localidad = c1.text_input("Localidad", value="Tienda Principal")
            tipo      = c2.selectbox("Tipo de ajuste", ["Establecer cantidad","Agregar al stock","Restar del stock"])

            c3,c4,c5 = st.columns(3)
            cantidad  = c3.number_input("Cantidad", min_value=0)
            min_s     = c4.number_input("Stock mínimo", min_value=0, value=5)
            max_s     = c5.number_input("Stock máximo", min_value=1, value=100)

            if st.form_submit_button("💾 Guardar", type="primary", use_container_width=True):
                pid = prod_opts[prod_sel]
                existing = q("SELECT id,cantidad FROM inventario WHERE producto_id=? AND localidad=?", (pid,localidad))
                if existing:
                    curr = existing[0]['cantidad']
                    nueva = cantidad if tipo.startswith("Establecer") else (curr+cantidad if "Agregar" in tipo else max(0,curr-cantidad))
                    run("UPDATE inventario SET cantidad=?,min_stock=?,max_stock=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (nueva, min_s, max_s, existing[0]['id']))
                    st.success(f"Stock actualizado: {curr} → {nueva} unidades")
                else:
                    run("INSERT INTO inventario(producto_id,localidad,cantidad,min_stock,max_stock) VALUES(?,?,?,?,?)",
                        (pid, localidad, cantidad, min_s, max_s))
                    st.success(f"Registro de stock creado: {cantidad} unidades en {localidad}")
                st.rerun()

    with tab_masivo:
        st.subheader("Ajuste masivo de inventario")
        st.info("Edita directamente la tabla. Haz clic en **Guardar todo** cuando termines.")
        df = pd.DataFrame([{
            'ID': r['id'], 'Producto': f"{r['emoji']} {r['nombre']}",
            'Localidad': r['localidad'], 'Cantidad': r['cantidad'],
            'Mín': r['min_stock'], 'Máx': r['max_stock'],
        } for r in inv])
        edited = st.data_editor(
            df, use_container_width=True, hide_index=True,
            disabled=['ID','Producto'],
            column_config={
                'Cantidad': st.column_config.NumberColumn(min_value=0, step=1),
                'Mín':      st.column_config.NumberColumn(min_value=0, step=1),
                'Máx':      st.column_config.NumberColumn(min_value=1, step=1),
            }
        )
        if st.button("💾 Guardar todo el ajuste", type="primary"):
            n = 0
            for _, row in edited.iterrows():
                run("UPDATE inventario SET cantidad=?,min_stock=?,max_stock=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (int(row['Cantidad']), int(row['Mín']), int(row['Máx']), int(row['ID'])))
                n += 1
            st.success(f"✅ {n} registros actualizados")
            st.rerun()


def _form_ajuste(row):
    with st.form(f"adj_{row['id']}"):
        st.markdown("**Ajustar stock**")
        c1,c2,c3 = st.columns(3)
        tipo     = c1.selectbox("Tipo", ["Establecer","Agregar","Restar"])
        cantidad = c2.number_input("Cantidad", min_value=0, value=row['cantidad'])
        localidad= c3.text_input("Localidad", value=row['localidad'])
        c4,c5    = st.columns(2)
        min_s    = c4.number_input("Mínimo", min_value=0, value=row['min_stock'])
        max_s    = c5.number_input("Máximo", min_value=1, value=row['max_stock'])
        if st.form_submit_button("💾 Actualizar", type="primary"):
            curr = row['cantidad']
            nueva = cantidad if tipo=="Establecer" else (curr+cantidad if tipo=="Agregar" else max(0,curr-cantidad))
            run("UPDATE inventario SET cantidad=?,localidad=?,min_stock=?,max_stock=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (nueva, localidad, min_s, max_s, row['id']))
            st.success(f"Stock: {curr} → {nueva}")
            st.rerun()

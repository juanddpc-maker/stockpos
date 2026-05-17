import streamlit as st
import pandas as pd
from database import q, run, raw_query, raw_exec, engine_info

TABLAS = ["categorias","productos","inventario","clientes","ventas","venta_items","config"]

# Columnas editables por tabla (excluye PKs y timestamps auto)
EDITABLES = {
    "categorias":  ["nombre","emoji","descripcion"],
    "productos":   ["nombre","precio","categoria_id","emoji","codigo_barras","descripcion"],
    "inventario":  ["producto_id","localidad","cantidad","min_stock","max_stock"],
    "clientes":    ["nombre","telefono","email","rfc","direccion","notas"],
    "ventas":      ["folio","fecha","cliente_id","subtotal","impuesto","total","metodo_pago","estado","notas"],
    "venta_items": ["venta_id","producto_id","cantidad","precio_unitario","subtotal"],
    "config":      ["valor"],  # PK = clave
}

PK = {t: "clave" if t=="config" else "id" for t in TABLAS}

PLANTILLAS = [
    ("Todos los productos",     "SELECT * FROM productos ORDER BY nombre"),
    ("Inventario con nombres",  "SELECT p.nombre, i.localidad, i.cantidad, i.min_stock FROM inventario i JOIN productos p ON p.id=i.producto_id ORDER BY p.nombre"),
    ("Stock bajo o agotado",    "SELECT p.nombre, i.cantidad, i.min_stock, i.localidad FROM inventario i JOIN productos p ON p.id=i.producto_id WHERE i.cantidad <= i.min_stock"),
    ("Top productos vendidos",  "SELECT p.nombre, SUM(vi.cantidad) as vendidos, SUM(vi.subtotal) as ingresos FROM venta_items vi JOIN productos p ON p.id=vi.producto_id GROUP BY p.id ORDER BY vendidos DESC"),
    ("Ventas por día",          "SELECT DATE(fecha) as dia, COUNT(*) as n, SUM(total) as total FROM ventas WHERE estado='Completada' GROUP BY dia ORDER BY dia DESC"),
    ("Clientes con compras",    "SELECT c.nombre, COUNT(v.id) as compras, COALESCE(SUM(v.total),0) as total FROM clientes c LEFT JOIN ventas v ON v.cliente_id=c.id AND v.estado='Completada' GROUP BY c.id ORDER BY total DESC"),
]


def render():
    st.header("🛢️ Gestor de Base de Datos")

    # Banner motor
    info = engine_info()
    col_inf1, col_inf2 = st.columns([3,1])
    col_inf1.info(f"{info['icono']} **Motor:** {info['motor']}  |  `{info['url']}`")
    col_inf2.success("🟢 Producción" if info['prod'] else "🔵 Desarrollo")

    tab_exp, tab_editar, tab_insertar, tab_borrar, tab_sql, tab_csv = st.tabs([
        "📋 Explorar", "✏️ Editar filas", "➕ Insertar", "🗑️ Eliminar", "💻 SQL", "⬇️ Exportar CSV"
    ])

    # ── EXPLORAR ─────────────────────────────────────────────────────────────
    with tab_exp:
        st.subheader("Explorar tablas")
        tc1, tc2 = st.columns([1,3])
        with tc1:
            tabla = st.radio("Tabla", TABLAS)
        with tc2:
            total = q(f"SELECT COUNT(*) as n FROM {tabla}")[0]['n']
            lim   = st.number_input("Límite de filas", min_value=10, max_value=500, value=50, step=10)
            st.caption(f"Total en tabla: **{total}** filas · mostrando máx {lim}")
            rows = q(f"SELECT * FROM {tabla} ORDER BY 1 DESC LIMIT {lim}")
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("Tabla vacía")

    # ── EDITAR ────────────────────────────────────────────────────────────────
    with tab_editar:
        st.subheader("Editar una fila existente")
        st.caption("Selecciona la tabla y el ID del registro que quieres modificar.")

        ec1, ec2 = st.columns(2)
        tabla_e = ec1.selectbox("Tabla", TABLAS, key="ed_tabla")
        pk_col  = PK[tabla_e]

        # Obtener IDs disponibles
        ids_rows = q(f"SELECT {pk_col} FROM {tabla_e} ORDER BY 1 DESC LIMIT 200")
        ids_list = [str(r[pk_col]) for r in ids_rows]

        if not ids_list:
            st.info("Tabla vacía, nada que editar.")
        else:
            pk_val = ec2.selectbox(f"Valor de {pk_col}", ids_list, key="ed_pkval")

            # Cargar fila actual
            fila = q(f"SELECT * FROM {tabla_e} WHERE {pk_col}=?", (pk_val,))
            if not fila:
                st.warning("Registro no encontrado")
            else:
                fila = fila[0]
                cols_edit = EDITABLES.get(tabla_e, [c for c in fila.keys() if c not in (pk_col,"created_at","updated_at")])

                st.markdown(f"**Editando `{tabla_e}` donde `{pk_col}={pk_val}`**")
                with st.form("form_editar_fila"):
                    nuevos = {}
                    # Pares de columnas
                    for i in range(0, len(cols_edit), 2):
                        col_a, col_b = st.columns(2)
                        c = cols_edit[i]
                        nuevos[c] = col_a.text_input(c, value=str(fila.get(c,"") or ""))
                        if i+1 < len(cols_edit):
                            c2 = cols_edit[i+1]
                            nuevos[c2] = col_b.text_input(c2, value=str(fila.get(c2,"") or ""))

                    if st.form_submit_button("💾 Guardar cambios", type="primary", use_container_width=True):
                        sets = ", ".join([f"{c}=?" for c in nuevos])
                        vals = list(nuevos.values()) + [pk_val]
                        try:
                            run(f"UPDATE {tabla_e} SET {sets} WHERE {pk_col}=?", tuple(vals))
                            st.success(f"✅ Fila `{pk_col}={pk_val}` actualizada correctamente")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error: {e}")

    # ── INSERTAR ──────────────────────────────────────────────────────────────
    with tab_insertar:
        st.subheader("Insertar nueva fila")
        tabla_i = st.selectbox("Tabla", TABLAS, key="ins_tabla")
        cols_i  = EDITABLES.get(tabla_i, [])

        if not cols_i:
            st.info("No hay columnas configuradas para esta tabla.")
        else:
            with st.form("form_insertar_fila", clear_on_submit=True):
                vals_i = {}
                for i in range(0, len(cols_i), 2):
                    ca, cb = st.columns(2)
                    vals_i[cols_i[i]] = ca.text_input(cols_i[i])
                    if i+1 < len(cols_i):
                        vals_i[cols_i[i+1]] = cb.text_input(cols_i[i+1])

                if st.form_submit_button("➕ Insertar fila", type="primary", use_container_width=True):
                    col_str = ", ".join(vals_i.keys())
                    ph_str  = ", ".join(["?"]*len(vals_i))
                    try:
                        new_id = run(f"INSERT INTO {tabla_i} ({col_str}) VALUES ({ph_str})",
                                     tuple(vals_i.values()))
                        st.success(f"✅ Fila insertada correctamente (id={new_id})")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

    # ── ELIMINAR ──────────────────────────────────────────────────────────────
    with tab_borrar:
        st.subheader("Eliminar una fila")
        st.warning("⚠️ Esta operación es irreversible. Verifica el registro antes de eliminar.")

        bc1, bc2 = st.columns(2)
        tabla_b = bc1.selectbox("Tabla", TABLAS, key="del_tabla")
        pk_b    = PK[tabla_b]
        ids_b   = q(f"SELECT {pk_b} FROM {tabla_b} ORDER BY 1 DESC LIMIT 200")
        ids_b_list = [str(r[pk_b]) for r in ids_b]

        if not ids_b_list:
            st.info("Tabla vacía.")
        else:
            pk_bval = bc2.selectbox(f"Valor de {pk_b}", ids_b_list, key="del_pkval")

            # Previsualizar
            prev = q(f"SELECT * FROM {tabla_b} WHERE {pk_b}=?", (pk_bval,))
            if prev:
                st.markdown("**Vista previa del registro a eliminar:**")
                st.dataframe(pd.DataFrame(prev), use_container_width=True, hide_index=True)

            confirmar = st.checkbox(f"Confirmo que quiero eliminar `{tabla_b}` donde `{pk_b}={pk_bval}`")
            if confirmar:
                if st.button("🗑️ Eliminar ahora", type="primary"):
                    try:
                        run(f"DELETE FROM {tabla_b} WHERE {pk_b}=?", (pk_bval,))
                        st.success(f"✅ Registro `{pk_b}={pk_bval}` eliminado")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e}\n\nEs posible que haya registros relacionados en otras tablas.")

    # ── SQL ───────────────────────────────────────────────────────────────────
    with tab_sql:
        st.subheader("Consola SQL")
        st.warning("⚠️ El SQL se ejecuta directamente sobre la base de datos.")

        # Plantillas
        st.markdown("**Plantillas rápidas:**")
        p_cols = st.columns(3)
        for i, (label, sql_t) in enumerate(PLANTILLAS):
            if p_cols[i%3].button(label, key=f"plt_{i}", use_container_width=True):
                st.session_state["sql_console"] = sql_t

        sql_txt = st.text_area("SQL", value=st.session_state.get("sql_console","SELECT * FROM productos LIMIT 20"),
                               height=130, key="sql_area")

        run_col, clear_col = st.columns([1,5])
        ejecutar = run_col.button("▶ Ejecutar", type="primary")

        if ejecutar and sql_txt.strip():
            sql_up = sql_txt.strip().upper()
            if sql_up.startswith("SELECT"):
                cols, rows, err = raw_query(sql_txt.strip())
                if err:
                    st.error(f"❌ {err}")
                elif cols:
                    st.success(f"✅ {len(rows)} fila(s)")
                    st.dataframe(pd.DataFrame(rows, columns=cols), use_container_width=True)
                else:
                    st.info("Sin resultados")
            else:
                affected, err = raw_exec(sql_txt.strip())
                if err:
                    st.error(f"❌ {err}")
                else:
                    st.success(f"✅ Ejecutado · {affected} fila(s) afectada(s)")

    # ── EXPORTAR ──────────────────────────────────────────────────────────────
    with tab_csv:
        st.subheader("Exportar tablas a CSV")
        for t in TABLAS:
            rows = q(f"SELECT * FROM {t}")
            total_r = len(rows)
            rc1, rc2 = st.columns([3,1])
            rc1.markdown(f"**{t}** · {total_r} fila(s)")
            if rows:
                csv = pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
                rc2.download_button(f"⬇️ {t}.csv", csv, f"{t}.csv", "text/csv",
                                    key=f"dl_{t}", use_container_width=True)
            else:
                rc2.button(f"⬇️ vacía", disabled=True, key=f"dl_{t}", use_container_width=True)

import streamlit as st
import pandas as pd
from database import q, run, raw_query, raw_exec, engine_info

TABLAS = ["categorias","productos","inventario","clientes","ventas","venta_items",
          "apartados","apartado_items","apartado_abonos","config"]

EDITABLES = {
    "categorias":        ["nombre","emoji","descripcion"],
    "productos":         ["nombre","precio","categoria_id","emoji","codigo_barras","descripcion"],
    "inventario":        ["producto_id","talla","localidad","cantidad","min_stock","max_stock"],
    "clientes":          ["nombre","telefono","email","rfc","direccion","notas"],
    "ventas":            ["folio","fecha","cliente_id","subtotal","impuesto","total","metodo_pago","estado","notas"],
    "venta_items":       ["venta_id","producto_id","talla","cantidad","precio_unitario","subtotal"],
    "apartados":         ["folio","fecha_apartado","fecha_limite","cliente_id","total_venta","anticipo","abonado","saldo","estado","notas"],
    "apartado_items":    ["apartado_id","producto_id","talla","cantidad","precio_unitario","subtotal"],
    "apartado_abonos":   ["apartado_id","fecha","monto","metodo_pago","notas"],
    "config":            ["valor"],
}

# Emojis disponibles por tabla para dropdown en edición
EMOJIS_UNIFORMES = ["👕","👖","👗","👚","👔","🧥","🦺","🩱","🩲","🩳","🎽",
                    "👞","👟","🥾","🧦","🧢","🪢","🎒","📦","⭐","🗂️","🔧"]

PK = {t: "clave" if t=="config" else "id" for t in TABLAS}

SQL_PROHIBIDO = ["DROP TABLE","DROP DATABASE","DROP SCHEMA","TRUNCATE","ALTER TABLE","DROP INDEX"]

PLANTILLAS = [
    ("Todos los productos",     "SELECT * FROM productos ORDER BY nombre"),
    ("Inventario completo",     "SELECT p.nombre, i.localidad, i.cantidad, i.min_stock, i.max_stock FROM inventario i JOIN productos p ON p.id=i.producto_id ORDER BY p.nombre"),
    ("Stock bajo o agotado",    "SELECT p.nombre, i.cantidad, i.min_stock FROM inventario i JOIN productos p ON p.id=i.producto_id WHERE i.cantidad <= i.min_stock"),
    ("Top productos vendidos",  "SELECT p.nombre, SUM(vi.cantidad) as vendidos, SUM(vi.subtotal) as ingresos FROM venta_items vi JOIN productos p ON p.id=vi.producto_id GROUP BY p.id ORDER BY vendidos DESC"),
    ("Ventas por día",          "SELECT DATE(fecha) as dia, COUNT(*) as n, SUM(total) as total FROM ventas WHERE estado='Completada' GROUP BY dia ORDER BY dia DESC"),
    ("Apartados activos",       "SELECT a.folio, c.nombre as cliente, a.total_venta, a.saldo, a.fecha_limite FROM apartados a LEFT JOIN clientes c ON c.id=a.cliente_id WHERE a.estado='Apartado' ORDER BY a.fecha_limite"),
]


def render():
    st.header("🛢️ Gestor de Base de Datos")
    info = engine_info()
    c1, c2 = st.columns([3,1])
    c1.info(f"{info['icono']} **Motor:** {info['motor']}  |  `{info['url']}`")
    c2.success("🟢 Producción" if info['prod'] else "🔵 Desarrollo")

    tab_exp, tab_edit, tab_ins, tab_del, tab_sql, tab_csv, tab_purge = st.tabs([
        "📋 Explorar", "✏️ Editar", "➕ Insertar", "🗑️ Eliminar", "💻 SQL", "⬇️ CSV", "🧹 Depurar Tablas"
    ])

    # ── EXPLORAR ─────────────────────────────────────────────────────────────
    with tab_exp:
        st.subheader("Explorar tabla")
        tc1, tc2 = st.columns([1,4])
        tabla = tc1.radio("Tabla", TABLAS)
        with tc2:
            total = q(f"SELECT COUNT(*) as n FROM {tabla}")[0]['n']
            lim   = st.number_input("Límite", min_value=10, max_value=500, value=50, step=10, key="lim_exp")
            st.caption(f"**{tabla}** · {total} filas totales · mostrando {lim}")
            rows  = q(f"SELECT * FROM {tabla} ORDER BY 1 DESC LIMIT {lim}")
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("Tabla vacía")

    # ── EDITAR ────────────────────────────────────────────────────────────────
    with tab_edit:
        st.subheader("Editar fila existente")
        ec1, ec2 = st.columns(2)
        tabla_e = ec1.selectbox("Tabla", TABLAS, key="ed_tabla")
        pk_col  = PK[tabla_e]
        ids_r   = q(f"SELECT {pk_col} FROM {tabla_e} ORDER BY 1 DESC LIMIT 300")
        ids_l   = [str(r[pk_col]) for r in ids_r]
        if not ids_l:
            st.info("Tabla vacía"); 
        else:
            pk_val = ec2.selectbox(f"{pk_col}", ids_l, key="ed_pkval")
            fila   = q(f"SELECT * FROM {tabla_e} WHERE {pk_col}=?", (pk_val,))
            if fila:
                fila = fila[0]
                cols_e = EDITABLES.get(tabla_e, [])
                st.markdown(f"Editando **{tabla_e}** · `{pk_col}={pk_val}`")
                with st.form("form_editar"):
                    nuevos = {}
                    for i in range(0, len(cols_e), 2):
                        ca, cb = st.columns(2)
                        col_a = cols_e[i]
                        val_a = str(fila.get(col_a,"") or "")
                        # Usar dropdown para emojis
                        if col_a == "emoji":
                            idx = EMOJIS_UNIFORMES.index(val_a) if val_a in EMOJIS_UNIFORMES else 0
                            nuevos[col_a] = ca.selectbox(col_a, EMOJIS_UNIFORMES, index=idx, key=f"em_{col_a}")
                        else:
                            nuevos[col_a] = ca.text_input(col_a, value=val_a, key=f"ed_{col_a}")
                        if i+1 < len(cols_e):
                            col_b = cols_e[i+1]
                            val_b = str(fila.get(col_b,"") or "")
                            if col_b == "emoji":
                                idx2 = EMOJIS_UNIFORMES.index(val_b) if val_b in EMOJIS_UNIFORMES else 0
                                nuevos[col_b] = cb.selectbox(col_b, EMOJIS_UNIFORMES, index=idx2, key=f"em_{col_b}")
                            else:
                                nuevos[col_b] = cb.text_input(col_b, value=val_b, key=f"ed_{col_b}")
                    if st.form_submit_button("💾 Guardar cambios", type="primary", use_container_width=True):
                        sets = ", ".join([f"{c}=?" for c in nuevos])
                        vals = list(nuevos.values()) + [pk_val]
                        try:
                            run(f"UPDATE {tabla_e} SET {sets} WHERE {pk_col}=?", tuple(vals))
                            st.success(f"✅ Fila actualizada correctamente"); st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")

    # ── INSERTAR ──────────────────────────────────────────────────────────────
    with tab_ins:
        st.subheader("Insertar nueva fila")
        tabla_i = st.selectbox("Tabla", TABLAS, key="ins_tabla")
        cols_i  = EDITABLES.get(tabla_i, [])
        with st.form("form_insertar", clear_on_submit=True):
            vals_i = {}
            for i in range(0, len(cols_i), 2):
                ca, cb = st.columns(2)
                col_a = cols_i[i]
                if col_a == "emoji":
                    vals_i[col_a] = ca.selectbox(col_a, EMOJIS_UNIFORMES, key=f"ins_em_{col_a}")
                else:
                    vals_i[col_a] = ca.text_input(col_a, key=f"ins_{col_a}")
                if i+1 < len(cols_i):
                    col_b = cols_i[i+1]
                    if col_b == "emoji":
                        vals_i[col_b] = cb.selectbox(col_b, EMOJIS_UNIFORMES, key=f"ins_em_{col_b}")
                    else:
                        vals_i[col_b] = cb.text_input(col_b, key=f"ins_{col_b}")
            if st.form_submit_button("➕ Insertar fila", type="primary", use_container_width=True):
                col_str = ", ".join(vals_i.keys())
                ph_str  = ", ".join(["?"]*len(vals_i))
                try:
                    new_id = run(f"INSERT INTO {tabla_i} ({col_str}) VALUES ({ph_str})", tuple(vals_i.values()))
                    st.success(f"✅ Fila insertada (id={new_id})"); st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")

    # ── ELIMINAR ──────────────────────────────────────────────────────────────
    with tab_del:
        st.subheader("Eliminar fila")
        st.warning("⚠️ Esta operación es irreversible.")
        bc1, bc2 = st.columns(2)
        tabla_b = bc1.selectbox("Tabla", TABLAS, key="del_tabla")
        pk_b    = PK[tabla_b]
        ids_b   = q(f"SELECT {pk_b} FROM {tabla_b} ORDER BY 1 DESC LIMIT 300")
        ids_bl  = [str(r[pk_b]) for r in ids_b]
        if not ids_bl:
            st.info("Tabla vacía")
        else:
            pk_bval = bc2.selectbox(pk_b, ids_bl, key="del_pkval")
            prev    = q(f"SELECT * FROM {tabla_b} WHERE {pk_b}=?", (pk_bval,))
            if prev:
                st.markdown("**Registro a eliminar:**")
                st.dataframe(pd.DataFrame(prev), use_container_width=True, hide_index=True)
            confirmar = st.checkbox(f"Confirmo eliminar `{tabla_b}` · `{pk_b}={pk_bval}`")
            if confirmar:
                if st.button("🗑️ Eliminar ahora", type="primary"):
                    try:
                        run(f"DELETE FROM {tabla_b} WHERE {pk_b}=?", (pk_bval,))
                        st.success("✅ Eliminado"); st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e} — puede haber registros relacionados en otras tablas.")

    # ── SQL ───────────────────────────────────────────────────────────────────
    with tab_sql:
        st.subheader("Consola SQL")
        st.info("ℹ️ Solo se permiten SELECT. Para modificar datos usa las pestañas Editar / Insertar / Eliminar.")

        st.markdown("**Plantillas:**")
        pcols = st.columns(3)
        for i, (label, sql_t) in enumerate(PLANTILLAS):
            if pcols[i%3].button(label, key=f"plt_{i}", use_container_width=True):
                st.session_state["sql_console"] = sql_t

        sql_txt = st.text_area("SQL (solo SELECT)", height=120,
                               value=st.session_state.get("sql_console","SELECT * FROM productos LIMIT 20"),
                               key="sql_area")

        if st.button("▶ Ejecutar SELECT", type="primary"):
            sql_clean = sql_txt.strip().upper()
            # Seguridad: solo SELECT
            bloqueado = any(cmd in sql_clean for cmd in SQL_PROHIBIDO)
            if bloqueado:
                st.error("🚫 Operación no permitida. La consola SQL solo acepta SELECT.")
            elif not sql_clean.startswith("SELECT"):
                st.error("🚫 Solo se permiten consultas SELECT en esta consola. Usa las otras pestañas para modificar datos.")
            else:
                cols, rows, err = raw_query(sql_txt.strip())
                if err:
                    st.error(f"❌ {err}")
                elif cols:
                    st.success(f"✅ {len(rows)} fila(s)")
                    st.dataframe(pd.DataFrame(rows, columns=cols), use_container_width=True)
                else:
                    st.info("Sin resultados")

    # ── CSV ───────────────────────────────────────────────────────────────────
    with tab_csv:
        st.subheader("Exportar tablas a CSV")
        for t in TABLAS:
            rows  = q(f"SELECT * FROM {t}")
            rc1, rc2 = st.columns([3,1])
            rc1.markdown(f"**{t}** · {len(rows)} filas")
            if rows:
                csv = pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
                rc2.download_button(f"⬇️ CSV", csv, f"{t}.csv", "text/csv",
                                    key=f"dl_{t}", use_container_width=True)
            else:
                rc2.caption("vacía")

    # ── DEPURAR TABLAS ────────────────────────────────────────────────────────
    with tab_purge:
        st.subheader("🧹 Depurar Tablas")
        st.error(
            "⚠️ **ZONA DE PELIGRO** — Estas operaciones eliminan datos permanentemente y no se pueden deshacer. "
            "Se recomienda exportar un CSV antes de proceder."
        )

        # Tabla seleccionable con info de filas y descripción de riesgo
        TABLA_DESCRIPCIONES = {
            "categorias":       ("🗂️", "Categorías de productos",                  "alto",   "Elimina todas las categorías. Los productos quedarán sin categoría."),
            "productos":        ("👔", "Catálogo completo de productos",            "alto",   "Elimina todos los productos, su inventario y aparecerán como NULL en ventas."),
            "inventario":       ("🗄️", "Todo el stock registrado",                  "alto",   "Elimina todos los registros de stock. Los productos quedan con inventario en cero."),
            "clientes":         ("👥", "Base de clientes",                           "medio",  "Elimina todos los clientes. Las ventas quedan como Público General."),
            "ventas":           ("🧾", "Historial completo de ventas",              "alto",   "Elimina todo el historial de ventas y sus líneas de detalle."),
            "venta_items":      ("📋", "Líneas de detalle de ventas",               "medio",  "Elimina el detalle de productos por venta. Las ventas quedan sin desglose."),
            "apartados":        ("💼", "Todos los apartados (activos e historial)",  "alto",   "Elimina apartados, sus items y abonos."),
            "apartado_items":   ("📦", "Productos de apartados",                    "medio",  "Elimina el detalle de productos por apartado."),
            "apartado_abonos":  ("💵", "Historial de abonos",                       "medio",  "Elimina todos los abonos registrados."),
            "config":           ("⚙️", "Configuración del sistema",                 "critico","Elimina nombre de app, IVA, API keys y toda la config. La app vuelve a valores por defecto."),
            "tallas_catalogo":  ("📏", "Catálogo de tallas",                        "medio",  "Elimina el catálogo de tallas. Los productos conservan su tipo_talla pero sin referencia."),
        }

        RIESGO_COLOR = {"medio": "🟡", "alto": "🔴", "critico": "⛔"}

        st.markdown("---")
        st.markdown("### Selecciona la tabla a depurar")

        for tabla, (emoji, desc, riesgo, advertencia) in TABLA_DESCRIPCIONES.items():
            total = q(f"SELECT COUNT(*) as n FROM {tabla}")[0]['n']
            if total == 0:
                with st.expander(f"{emoji} **{tabla}** · 0 filas · ✅ Ya está vacía"):
                    st.caption("Esta tabla no tiene datos.")
                continue

            riesgo_icon = RIESGO_COLOR[riesgo]
            with st.expander(f"{emoji} **{tabla}** · {total} fila(s) · {riesgo_icon} Riesgo {riesgo.upper()}"):
                st.markdown(f"**{desc}**")
                st.warning(f"⚠️ {advertencia}")

                col_info, col_preview = st.columns([1,2])
                col_info.metric("Filas a eliminar", total)

                # Preview (primeras 3 filas)
                preview = q(f"SELECT * FROM {tabla} LIMIT 3")
                if preview:
                    col_preview.caption("Vista previa (primeras 3 filas):")
                    col_preview.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True)

                st.markdown(f"**Para confirmar escribe:** `{tabla}`")
                confirm_key = f"confirm_purge_{tabla}"
                st.text_input(
                    f"Confirmación",
                    placeholder=f"Escribe: {tabla}",
                    key=confirm_key,
                    label_visibility="collapsed"
                )

                btn_col, _ = st.columns([1,3])
                if btn_col.button(f"🧹 Depurar tabla `{tabla}`", key=f"btn_purge_{tabla}",
                                  type="primary", use_container_width=True):
                    typed = st.session_state.get(confirm_key, "").strip()
                    if typed != tabla:
                        st.error(f"❌ Escribiste **'{typed}'** pero se necesita exactamente: **{tabla}**")
                    else:
                        # Cascada de borrado según dependencias
                        try:
                            if tabla == "productos":
                                run("DELETE FROM apartado_items")
                                run("DELETE FROM venta_items")
                                run("DELETE FROM inventario")
                                run("DELETE FROM productos")
                            elif tabla == "ventas":
                                run("DELETE FROM venta_items")
                                run("DELETE FROM ventas")
                            elif tabla == "apartados":
                                run("DELETE FROM apartado_abonos")
                                run("DELETE FROM apartado_items")
                                run("DELETE FROM apartados")
                            elif tabla == "categorias":
                                run("UPDATE productos SET categoria_id=NULL")
                                run("DELETE FROM categorias")
                            elif tabla == "clientes":
                                run("UPDATE ventas SET cliente_id=NULL")
                                run("UPDATE apartados SET cliente_id=NULL")
                                run("DELETE FROM clientes")
                            else:
                                run(f"DELETE FROM {tabla}")
                            st.success(f"✅ Tabla **{tabla}** depurada correctamente. {total} fila(s) eliminada(s).")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al depurar: {e}")

        st.markdown("---")
        st.markdown("### 💣 Depurar TODO (Reset completo)")
        st.error("Esto elimina **absolutamente todos los datos** de todas las tablas. "
                 "La app volverá a su estado inicial con datos de muestra al reiniciar.")

        st.text_input(
            "Escribe RESET COMPLETO para confirmar",
            placeholder="RESET COMPLETO",
            key="confirm_reset_all",
            label_visibility="collapsed"
        )
        if st.button("💣 Reset completo de la base de datos", type="primary"):
            typed_all = st.session_state.get("confirm_reset_all", "").strip()
            if typed_all != "RESET COMPLETO":
                st.error(f"❌ Escribiste **'{typed_all}'** pero se necesita exactamente: **RESET COMPLETO**")
            else:
                try:
                    orden = ["apartado_abonos","apartado_items","apartados",
                             "venta_items","ventas","inventario",
                             "productos","categorias","clientes",
                             "tallas_catalogo","config"]
                    for t in orden:
                        run(f"DELETE FROM {t}")
                    st.success("✅ Reset completo realizado. Reinicia la app para cargar los datos de muestra.")
                    st.info("💡 Para recargar los datos de muestra, reinicia la app o haz un nuevo deploy.")
                except Exception as e:
                    st.error(f"❌ Error: {e}")

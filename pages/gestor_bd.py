import streamlit as st
import pandas as pd
from database import q, run, raw_query, engine_info

TABLAS = ["categorias", "productos", "inventario", "clientes", "ventas", "venta_items", "config"]

SCHEMAS = {
    "categorias":   "id, nombre, emoji, descripcion, created_at",
    "productos":    "id, nombre, precio, categoria_id, emoji, codigo_barras, descripcion, created_at",
    "inventario":   "id, producto_id, localidad, cantidad, min_stock, max_stock, updated_at",
    "clientes":     "id, nombre, telefono, email, rfc, direccion, notas, created_at",
    "ventas":       "id, folio, fecha, cliente_id, subtotal, impuesto, total, metodo_pago, estado, notas",
    "venta_items":  "id, venta_id, producto_id, cantidad, precio_unitario, subtotal",
    "config":       "clave, valor",
}


def render():
    st.markdown('<p class="sp-title">🛢️ Gestor de <span class="sp-accent">Base de Datos</span></p>', unsafe_allow_html=True)

    # Motor info banner
    info = engine_info()
    st.markdown(f"""
    <div style="background:#1a2744;border:1px solid #2d3f5c;border-radius:10px;
         padding:12px 18px;margin-bottom:16px;display:flex;align-items:center;gap:12px">
        <span style="font-size:24px">{info['icono']}</span>
        <div>
            <div style="font-weight:700">{info['motor']}</div>
            <div style="font-size:12px;color:#8892a4;font-family:monospace">{info['url']}</div>
        </div>
        <div style="margin-left:auto">
            <span style="background:{'rgba(0,200,150,0.15)' if info['motor']=='PostgreSQL' else 'rgba(74,158,255,0.15)'};
                  color:{'#00c896' if info['motor']=='PostgreSQL' else '#4a9eff'};
                  border-radius:20px;padding:3px 12px;font-size:12px;font-weight:700">
                {'🟢 Producción' if info['motor']=='PostgreSQL' else '🔵 Desarrollo'}
            </span>
        </div>
    </div>""", unsafe_allow_html=True)
    st.markdown('<p class="sp-subtitle">Administración directa de tablas y consola SQL</p>', unsafe_allow_html=True)

    tab_browser, tab_sql, tab_export = st.tabs(["📋 Explorador de Tablas", "💻 Consola SQL", "⬇️ Exportar"])

    # ── TAB: Explorador ───────────────────────────────────────────────────────
    with tab_browser:
        tc1, tc2 = st.columns([1, 3])

        with tc1:
            tabla = st.radio("Tabla", TABLAS, label_visibility="collapsed")

        with tc2:
            # Header
            hc1, hc2 = st.columns([3, 1])
            hc1.markdown(f"#### 🗄️ `{tabla}`")
            hc1.markdown(f"<code style='font-size:11px;color:#8892a4'>{SCHEMAS.get(tabla,'')}</code>",
                         unsafe_allow_html=True)

            # Stats
            count = q(f"SELECT COUNT(*) as n FROM {tabla}")[0]['n']
            hc2.metric("Filas", count)

            # Data
            rows = q(f"SELECT * FROM {tabla} ORDER BY 1 DESC LIMIT 200")
            if rows:
                df = pd.DataFrame(rows)
                edited = st.data_editor(
                    df, use_container_width=True, hide_index=True, num_rows="dynamic",
                    key=f"editor_{tabla}"
                )

                bc1, bc2, bc3 = st.columns(3)
                if bc1.button("💾 Guardar cambios", type="primary", use_container_width=True):
                    # Simple upsert: recorre filas editadas y hace UPDATE por id/clave
                    pk = "clave" if tabla == "config" else "id"
                    saved = 0
                    for _, row in edited.iterrows():
                        cols = [c for c in df.columns if c != pk]
                        sets = ", ".join([f"{c}=?" for c in cols])
                        vals = [row[c] for c in cols] + [row[pk]]
                        try:
                            run(f"UPDATE {tabla} SET {sets} WHERE {pk}=?", tuple(vals))
                            saved += 1
                        except Exception:
                            pass
                    st.success(f"✅ {saved} filas actualizadas")
                    st.rerun()

                if bc3.button("🔄 Recargar", use_container_width=True):
                    st.rerun()
            else:
                st.info("Tabla vacía")

            # Insert form
            with st.expander("➕ Insertar nueva fila"):
                cols_names = [c for c in SCHEMAS.get(tabla, "").split(", ")
                              if c not in ("id", "created_at", "updated_at")]
                with st.form(f"insert_{tabla}"):
                    vals_form = {}
                    for col in cols_names:
                        vals_form[col] = st.text_input(col)
                    if st.form_submit_button("Insertar", type="primary"):
                        placeholders = ", ".join(["?"] * len(cols_names))
                        col_str = ", ".join(cols_names)
                        try:
                            run(f"INSERT INTO {tabla} ({col_str}) VALUES ({placeholders})",
                                tuple(vals_form[c] for c in cols_names))
                            st.success("Fila insertada")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

    # ── TAB: SQL Console ──────────────────────────────────────────────────────
    with tab_sql:
        st.markdown("#### 💻 Consola SQL Libre")
        st.warning("⚠️ Cualquier SQL ejecutado aquí afecta la base de datos directamente.")

        # Quick templates
        st.markdown("**Plantillas:**")
        tc1, tc2, tc3, tc4 = st.columns(4)
        templates = {
            tc1: "SELECT * FROM productos LIMIT 10",
            tc2: "SELECT p.nombre, SUM(vi.cantidad) as vendidos FROM venta_items vi JOIN productos p ON p.id=vi.producto_id GROUP BY p.id ORDER BY vendidos DESC",
            tc3: "SELECT * FROM inventario WHERE cantidad <= min_stock",
            tc4: "SELECT DATE(fecha) as dia, SUM(total) as total FROM ventas WHERE estado='Completada' GROUP BY dia ORDER BY dia DESC",
        }
        labels = ["Productos", "Top vendidos", "Stock bajo", "Ventas por día"]
        for (col, sql), label in zip(templates.items(), labels):
            if col.button(label, use_container_width=True, key=f"tpl_{label}"):
                st.session_state["sql_input"] = sql

        sql_text = st.text_area(
            "SQL",
            value=st.session_state.get("sql_input", "SELECT * FROM productos LIMIT 20"),
            height=120, label_visibility="collapsed",
            key="sql_textarea"
        )

        rc1, rc2 = st.columns([1, 5])
        run_btn = rc1.button("▶ Ejecutar", type="primary")
        rc2.markdown("")

        if run_btn and sql_text.strip():
            cols, rows, err = raw_query(sql_text.strip())
            if err:
                st.error(f"❌ Error: {err}")
            elif cols:
                st.success(f"✅ {len(rows)} fila(s) retornadas")
                st.dataframe(pd.DataFrame(rows, columns=cols), use_container_width=True)
            else:
                st.success("✅ Ejecutado correctamente (sin resultados que mostrar)")

    # ── TAB: Export ───────────────────────────────────────────────────────────
    with tab_export:
        st.markdown("#### ⬇️ Exportar Tablas a CSV")
        for t in TABLAS:
            rows = q(f"SELECT * FROM {t}")
            if rows:
                df = pd.DataFrame(rows)
                csv = df.to_csv(index=False).encode("utf-8")
                col1, col2 = st.columns([3, 1])
                col1.markdown(f"**{t}** · {len(rows)} filas")
                col2.download_button(
                    f"⬇️ {t}.csv", csv, f"{t}.csv", "text/csv",
                    key=f"dl_{t}", use_container_width=True
                )

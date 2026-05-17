import streamlit as st
import pandas as pd
from database import q, run, TALLAS

def render():
    st.header("🗄️ Inventario")
    tab_ver, tab_agregar, tab_masivo = st.tabs(["📋 Stock por Talla","➕ Agregar / Ajustar","📝 Ajuste Masivo"])

    with tab_ver:      _tab_ver()
    with tab_agregar:  _tab_agregar()
    with tab_masivo:   _tab_masivo()


def _tab_ver():
    # ── Filtros ───────────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns([2, 2, 1, 1])

    # Categoría
    cats    = q("SELECT id, nombre, emoji FROM categorias ORDER BY nombre")
    cat_opts= {"Todas las categorías": None} | {f"{c['emoji']} {c['nombre']}": c['id'] for c in cats}
    cat_sel = fc1.selectbox("Categoría", list(cat_opts.keys()),
                            label_visibility="collapsed",
                            key="inv_cat_fil",
                            placeholder="Categoría...")
    cat_id  = cat_opts[cat_sel]

    # Búsqueda texto
    buscar  = fc2.text_input("Buscar", placeholder="Producto o localidad...",
                             label_visibility="collapsed", key="inv_buscar")

    # Talla
    tallas_disp = q("SELECT DISTINCT talla FROM inventario ORDER BY talla")
    talla_opts  = ["Todas las tallas"] + [r['talla'] for r in tallas_disp]
    talla_sel   = fc3.selectbox("Talla", talla_opts,
                                label_visibility="collapsed", key="inv_talla_fil")
    talla_fil   = None if talla_sel == "Todas las tallas" else talla_sel

    # Estado
    estado_f = fc4.selectbox("Estado", ["Todos","Sin Stock","Stock Bajo","Normal"],
                             label_visibility="collapsed", key="inv_estado_fil")

    # ── Query con filtros ─────────────────────────────────────────────────────
    where_parts = ["1=1"]
    if cat_id:    where_parts.append(f"p.categoria_id={cat_id}")
    if talla_fil: where_parts.append(f"i.talla='{talla_fil}'")
    where = " AND ".join(where_parts)

    inv = q(f"""
        SELECT i.id, i.talla, i.localidad, i.cantidad, i.min_stock, i.max_stock,
               p.id as prod_id, p.nombre, p.emoji, p.precio, p.tipo_talla,
               c.id as cat_id, c.nombre as categoria, c.emoji as cat_emoji
        FROM inventario i
        JOIN productos p ON p.id=i.producto_id
        LEFT JOIN categorias c ON c.id=p.categoria_id
        WHERE {where}
        ORDER BY c.nombre, p.nombre, i.talla
    """)

    # Filtros post-query
    if buscar:
        s = buscar.lower()
        inv = [r for r in inv if s in r['nombre'].lower() or s in r['localidad'].lower()]
    if estado_f == "Sin Stock":    inv = [r for r in inv if r['cantidad'] == 0]
    elif estado_f == "Stock Bajo": inv = [r for r in inv if 0 < r['cantidad'] <= r['min_stock']]
    elif estado_f == "Normal":     inv = [r for r in inv if r['cantidad'] > r['min_stock']]

    # ── Badge filtros activos ─────────────────────────────────────────────────
    activos = [f for f in [
        cat_sel if cat_id else None,
        f'"{buscar}"' if buscar else None,
        f"Talla: {talla_fil}" if talla_fil else None,
        estado_f if estado_f != "Todos" else None,
    ] if f]
    if activos:
        st.info(f"🔍 {' · '.join(activos)}")

    # Agrupar por producto para contar
    prods_seen = {}
    for r in inv:
        key = r['prod_id']
        if key not in prods_seen:
            prods_seen[key] = {'info': r, 'tallas': [], 'total': 0}
        prods_seen[key]['tallas'].append(r)
        prods_seen[key]['total'] += r['cantidad']

    st.caption(f"{len(prods_seen)} producto(s) · {len(inv)} registro(s) de talla")

    if not prods_seen:
        st.info("Sin productos con los filtros seleccionados.")
        return

    # ── Listar productos agrupados por categoría ──────────────────────────────
    # Agrupar por categoría para mostrar sección por sección
    por_cat = {}
    for pid, data in prods_seen.items():
        cat_nombre = data['info']['categoria'] or 'Sin categoría'
        cat_emoji  = data['info']['cat_emoji']  or '📦'
        cat_key    = f"{cat_emoji} {cat_nombre}"
        if cat_key not in por_cat:
            por_cat[cat_key] = []
        por_cat[cat_key].append(data)

    for cat_label, productos in por_cat.items():
        st.markdown(f"#### {cat_label}")
        total_cat = sum(p['total'] for p in productos)
        st.caption(f"{len(productos)} producto(s) · {total_cat} unidades en total")

        for data in productos:
            info   = data['info']
            tallas = data['tallas']
            total  = data['total']

            any_zero = any(t['cantidad'] == 0 for t in tallas)
            any_low  = any(0 < t['cantidad'] <= t['min_stock'] for t in tallas)
            status   = "❌" if any_zero else ("⚠️" if any_low else "✅")

            with st.expander(
                f"{info['emoji']} **{info['nombre']}** "
                f"· Stock total: **{total}** {status}"
            ):
                # Métricas por talla en fila
                if len(tallas) > 1:
                    cols = st.columns(min(len(tallas), 8))
                    for i, t in enumerate(tallas):
                        color = "🔴" if t['cantidad']==0 else ("🟡" if t['cantidad']<=t['min_stock'] else "🟢")
                        cols[i % 8].metric(f"Talla {t['talla']}", f"{color} {t['cantidad']}")
                else:
                    t = tallas[0]
                    color = "🔴" if t['cantidad']==0 else ("🟡" if t['cantidad']<=t['min_stock'] else "🟢")
                    st.metric(f"Talla {t['talla']} · {t['localidad']}", f"{color} {t['cantidad']}")

                st.divider()

                # Formulario de ajuste por talla
                for t in tallas:
                    with st.form(f"inv_form_{t['id']}"):
                        st.markdown(f"**Talla {t['talla']}** · 📍 {t['localidad']}")
                        fa, fb, fc, fd = st.columns(4)
                        tipo   = fa.selectbox("Ajuste",["Establecer","Agregar","Restar"],
                                              key=f"tipo_{t['id']}")
                        cant   = fb.number_input("Cantidad", min_value=0, value=t['cantidad'],
                                                  key=f"cant_{t['id']}")
                        mn     = fc.number_input("Mínimo",   min_value=0, value=t['min_stock'],
                                                  key=f"mn_{t['id']}")
                        mx     = fd.number_input("Máximo",   min_value=1, value=t['max_stock'],
                                                  key=f"mx_{t['id']}")
                        if st.form_submit_button(f"💾 Guardar talla {t['talla']}",
                                                  use_container_width=True):
                            curr  = t['cantidad']
                            nueva = (cant if tipo=="Establecer"
                                     else curr+cant if tipo=="Agregar"
                                     else max(0, curr-cant))
                            run("UPDATE inventario SET cantidad=?,min_stock=?,max_stock=?,"
                                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                                (nueva, mn, mx, t['id']))
                            st.success(f"✅ Talla {t['talla']}: {curr} → {nueva}")
                            st.rerun()

        st.divider()


def _tab_agregar():
    st.subheader("Agregar / Ajustar stock")
    prods = q("""
        SELECT p.id, p.nombre, p.emoji, p.tipo_talla, c.nombre as cat, c.emoji as cat_emoji
        FROM productos p LEFT JOIN categorias c ON c.id=p.categoria_id
        ORDER BY c.nombre, p.nombre
    """)
    with st.form("add_stock"):
        # Mostrar productos con categoría en el label
        prod_opts = {f"{p['cat_emoji'] or '📦'} {p['cat'] or 'Sin cat.'} › {p['emoji']} {p['nombre']}": p
                     for p in prods}
        prod_sel  = st.selectbox("Producto *", list(prod_opts.keys()))
        prod      = prod_opts[prod_sel]
        tallas    = TALLAS.get(prod['tipo_talla'], ["Única"])

        c1, c2, c3 = st.columns(3)
        talla_sel = c1.selectbox("Talla *", tallas)
        localidad = c2.text_input("Localidad", value="Tienda Principal")
        tipo      = c3.selectbox("Tipo de ajuste",
                                  ["Establecer cantidad","Agregar al stock","Restar del stock"])

        c4, c5, c6 = st.columns(3)
        cantidad  = c4.number_input("Cantidad",   min_value=0)
        min_s     = c5.number_input("Stock mínimo", min_value=0, value=2)
        max_s     = c6.number_input("Stock máximo", min_value=1, value=100)

        if st.form_submit_button("💾 Guardar", type="primary", use_container_width=True):
            pid = prod['id']
            ex  = q("SELECT id,cantidad FROM inventario WHERE producto_id=? AND talla=? AND localidad=?",
                    (pid, talla_sel, localidad))
            if ex:
                curr  = ex[0]['cantidad']
                nueva = (cantidad if "Establecer" in tipo
                         else curr+cantidad if "Agregar" in tipo
                         else max(0, curr-cantidad))
                run("UPDATE inventario SET cantidad=?,min_stock=?,max_stock=?,"
                    "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (nueva, min_s, max_s, ex[0]['id']))
                st.success(f"✅ {prod['nombre']} · Talla {talla_sel}: {curr} → {nueva} uds")
            else:
                run("INSERT INTO inventario(producto_id,talla,localidad,cantidad,min_stock,max_stock)"
                    " VALUES(?,?,?,?,?,?)",
                    (pid, talla_sel, localidad, cantidad, min_s, max_s))
                st.success(f"✅ Registro creado: {prod['nombre']} · {talla_sel} · {cantidad} uds en {localidad}")
            st.rerun()


def _tab_masivo():
    st.subheader("Ajuste masivo de inventario")
    st.info("Edita directamente la tabla. Haz clic en **Guardar todo** al terminar.")

    inv = q("""
        SELECT i.id,
               c.nombre as Categoría,
               p.nombre as Producto,
               i.talla as Talla,
               i.localidad as Localidad,
               i.cantidad as Cantidad,
               i.min_stock as Min,
               i.max_stock as Max
        FROM inventario i
        JOIN productos p ON p.id=i.producto_id
        LEFT JOIN categorias c ON c.id=p.categoria_id
        ORDER BY c.nombre, p.nombre, i.talla
    """)

    df = pd.DataFrame(inv)
    edited = st.data_editor(
        df, use_container_width=True, hide_index=True,
        disabled=['id','Categoría','Producto','Talla','Localidad'],
        column_config={
            'Cantidad': st.column_config.NumberColumn(min_value=0, step=1),
            'Min':      st.column_config.NumberColumn(min_value=0, step=1),
            'Max':      st.column_config.NumberColumn(min_value=1, step=1),
        }
    )
    if st.button("💾 Guardar todo el ajuste", type="primary"):
        n = 0
        for _, row in edited.iterrows():
            run("UPDATE inventario SET cantidad=?,min_stock=?,max_stock=?,"
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (int(row['Cantidad']), int(row['Min']), int(row['Max']), int(row['id'])))
            n += 1
        st.success(f"✅ {n} registros actualizados")
        st.rerun()

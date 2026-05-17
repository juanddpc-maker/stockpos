import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database import q

def render():
    st.header("📦 Dashboard de Inventario")

    # ── Filtros ───────────────────────────────────────────────────────────────
    with st.expander("🔍 Filtros", expanded=True):
        fc1, fc2, fc3, fc4 = st.columns(4)

        # Categorías
        cats = q("SELECT id, nombre, emoji FROM categorias ORDER BY nombre")
        cat_opts = {"Todas las categorías": None} | {f"{c['emoji']} {c['nombre']}": c['id'] for c in cats}
        cat_sel = fc1.selectbox("Categoría", list(cat_opts.keys()), key="inv_dash_cat")
        cat_id  = cat_opts[cat_sel]

        # Productos (filtrado por categoría si aplica)
        f_cat_prod = f"WHERE p.categoria_id={cat_id}" if cat_id else ""
        prods_list = q(f"SELECT id, nombre, emoji FROM productos p {f_cat_prod} ORDER BY nombre")
        prod_opts  = {"Todos los productos": None} | {f"{p['emoji']} {p['nombre']}": p['id'] for p in prods_list}
        prod_sel   = fc2.selectbox("Producto", list(prod_opts.keys()), key="inv_dash_prod")
        prod_id    = prod_opts[prod_sel]

        # Tallas
        tallas_disp = q("SELECT DISTINCT talla FROM inventario ORDER BY talla")
        talla_opts  = ["Todas las tallas"] + [r['talla'] for r in tallas_disp]
        talla_sel   = fc3.selectbox("Talla", talla_opts, key="inv_dash_talla")
        talla_fil   = None if talla_sel == "Todas las tallas" else talla_sel

        # Estado de stock
        estado_sel = fc4.selectbox("Estado", ["Todos","Sin Stock","Stock Bajo","Normal"], key="inv_dash_estado")

    # ── Construir query con filtros ───────────────────────────────────────────
    where_parts = ["1=1"]
    if cat_id:    where_parts.append(f"p.categoria_id={cat_id}")
    if prod_id:   where_parts.append(f"p.id={prod_id}")
    if talla_fil: where_parts.append(f"i.talla='{talla_fil}'")
    where = " AND ".join(where_parts)

    inv_raw = q(f"""
        SELECT i.id, i.talla, i.localidad, i.cantidad, i.min_stock, i.max_stock,
               p.id as prod_id, p.nombre, p.emoji, p.precio, p.tipo_talla,
               c.nombre as categoria, c.emoji as cat_emoji
        FROM inventario i
        JOIN productos p ON p.id=i.producto_id
        LEFT JOIN categorias c ON c.id=p.categoria_id
        WHERE {where}
        ORDER BY p.nombre, i.talla
    """)

    # Filtro de estado (post-query)
    if estado_sel == "Sin Stock":    inv_raw = [r for r in inv_raw if r['cantidad'] == 0]
    elif estado_sel == "Stock Bajo": inv_raw = [r for r in inv_raw if 0 < r['cantidad'] <= r['min_stock']]
    elif estado_sel == "Normal":     inv_raw = [r for r in inv_raw if r['cantidad'] > r['min_stock']]

    # Agrupar por producto para KPIs
    prods_agg = {}
    for r in inv_raw:
        pid = r['prod_id']
        if pid not in prods_agg:
            prods_agg[pid] = {**r, 'cantidad_total': 0}
        prods_agg[pid]['cantidad_total'] += r['cantidad']
    prods_agg = list(prods_agg.values())

    total_prods  = len(prods_agg)
    low_stock    = [r for r in prods_agg if 0 < r['cantidad_total'] <= r['min_stock']]
    no_stock     = [r for r in prods_agg if r['cantidad_total'] == 0]
    inv_value    = sum(float(r['precio']) * r['cantidad_total'] for r in prods_agg)
    total_uds    = sum(r['cantidad_total'] for r in prods_agg)

    # Badge de filtros activos
    filtros_activos = [f for f in [
        cat_sel if cat_id else None,
        f"Producto: {prods_list[list(prod_opts.values()).index(prod_id)-1]['nombre']}" if prod_id else None,
        f"Talla: {talla_fil}" if talla_fil else None,
        estado_sel if estado_sel != "Todos" else None,
    ] if f]
    if filtros_activos:
        st.info(f"🔍 Filtros activos: {' · '.join(filtros_activos)}")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📦 Productos",           total_prods)
    c2.metric("📊 Total Unidades",       total_uds)
    c3.metric("⚠️ Stock Bajo",          len(low_stock),
              delta=f"-{len(low_stock)}" if low_stock else "OK", delta_color="inverse")
    c4.metric("❌ Sin Stock",            len(no_stock),
              delta=f"-{len(no_stock)}" if no_stock else "OK",  delta_color="inverse")
    c5.metric("💎 Valor",               f"${inv_value:,.2f}")

    if not inv_raw:
        st.warning("Sin registros con los filtros seleccionados.")
        return

    st.divider()

    # ── Gráfica de barras ─────────────────────────────────────────────────────
    col_bar, col_pie = st.columns([3, 2])

    with col_bar:
        # Si hay filtro de talla específica → mostrar por producto+talla
        # Si no → mostrar total por producto
        if talla_fil or prod_id:
            # Detalle por producto + talla
            labels = [f"{r['emoji']} {r['nombre']} · {r['talla']}" for r in inv_raw]
            values = [r['cantidad'] for r in inv_raw]
            colors = ['#fc8181' if v==0 else ('#f6ad55' if v<=r['min_stock'] else '#68d391')
                      for v,r in zip(values, inv_raw)]
            title  = "Stock por producto / talla"
        else:
            # Agrupado por producto
            labels = [f"{r['emoji']} {r['nombre']}" for r in prods_agg]
            values = [r['cantidad_total'] for r in prods_agg]
            colors = ['#fc8181' if v==0 else ('#f6ad55' if v<=r['min_stock'] else '#68d391')
                      for v,r in zip(values, prods_agg)]
            title  = "Stock total por producto (todas las tallas)"

        st.subheader(title)
        sorted_pairs = sorted(zip(values, labels, colors), key=lambda x: x[0])
        sv, sl, sc = zip(*sorted_pairs) if sorted_pairs else ([], [], [])
        fig = go.Figure(go.Bar(
            x=list(sv), y=list(sl), orientation='h',
            marker_color=list(sc),
            text=list(sv), textposition='outside',
            hovertemplate="<b>%{y}</b><br>%{x} uds<extra></extra>",
        ))
        fig.update_layout(
            margin=dict(l=0,r=50,t=10,b=0),
            height=max(300, len(labels)*30),
            xaxis_title="Unidades"
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

    with col_pie:
        st.subheader("Distribución")
        if cat_id or prod_id:
            # Por talla cuando hay filtro de cat/producto
            talla_agg = {}
            for r in inv_raw:
                t = r['talla']
                talla_agg[t] = talla_agg.get(t, 0) + r['cantidad']
            if talla_agg:
                fig2 = go.Figure(go.Pie(
                    labels=list(talla_agg.keys()),
                    values=list(talla_agg.values()),
                    hole=0.4, textinfo="label+percent",
                    hovertemplate="<b>Talla %{label}</b><br>%{value} uds<extra></extra>",
                ))
                fig2.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=280, showlegend=False)
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False})
        else:
            # Por categoría (sin filtros)
            cat_agg = {}
            for r in inv_raw:
                label = f"{r['cat_emoji']} {r['categoria']}" if r['categoria'] else "Sin categoría"
                cat_agg[label] = cat_agg.get(label, 0) + r['cantidad']
            if cat_agg:
                fig2 = go.Figure(go.Pie(
                    labels=list(cat_agg.keys()),
                    values=list(cat_agg.values()),
                    hole=0.4, textinfo="label+percent",
                    hovertemplate="<b>%{label}</b><br>%{value} uds<extra></extra>",
                ))
                fig2.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=280, showlegend=False)
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False})

    # ── Alertas ───────────────────────────────────────────────────────────────
    alertas = [r for r in inv_raw if r['cantidad'] <= r['min_stock']]
    if alertas:
        st.divider()
        st.subheader(f"🚨 Alertas ({len(alertas)} registro(s))")
        cols = st.columns(min(len(alertas), 3))
        for i, a in enumerate(alertas):
            with cols[i % 3]:
                if a['cantidad'] == 0:
                    st.error(f"**{a['emoji']} {a['nombre']}**  \nTalla {a['talla']} · Sin stock", icon="❌")
                else:
                    st.warning(f"**{a['emoji']} {a['nombre']}**  \nTalla {a['talla']} · {a['cantidad']} uds (mín {a['min_stock']})", icon="⚠️")

    # ── Tallas (solo si no hay filtro de talla específica) ────────────────────
    if not talla_fil:
        tallas_stats = {}
        for r in inv_raw:
            if r['talla'] == 'Única': continue
            t = r['talla']
            if t not in tallas_stats:
                tallas_stats[t] = {'total':0,'agotados':0,'bajos':0}
            tallas_stats[t]['total']    += r['cantidad']
            tallas_stats[t]['agotados'] += 1 if r['cantidad']==0 else 0
            tallas_stats[t]['bajos']    += 1 if 0 < r['cantidad'] <= r['min_stock'] else 0

        if tallas_stats:
            st.divider()
            st.subheader("📏 Stock por Talla")
            tcols = st.columns(min(len(tallas_stats), 8))
            for i, (talla, stats) in enumerate(tallas_stats.items()):
                icon  = "🔴" if stats['agotados']>0 else ("🟡" if stats['bajos']>0 else "🟢")
                delta = f"{stats['agotados']} agot. / {stats['bajos']} bajo" \
                        if (stats['agotados']+stats['bajos'])>0 else "✅ OK"
                tcols[i%8].metric(
                    f"Talla {talla}", f"{icon} {stats['total']}",
                    delta=delta,
                    delta_color="inverse" if (stats['agotados']+stats['bajos'])>0 else "normal"
                )

    # ── Tabla completa ────────────────────────────────────────────────────────
    st.divider()
    st.subheader(f"📋 Detalle ({len(inv_raw)} registro(s))")

    df = pd.DataFrame([{
        'Producto':    f"{r['emoji']} {r['nombre']}",
        'Categoría':   r['categoria'] or '—',
        'Talla':       r['talla'],
        'Localidad':   r['localidad'],
        'Cantidad':    r['cantidad'],
        'Mín':         r['min_stock'],
        'Máx':         r['max_stock'],
        'Precio':      f"${float(r['precio']):,.2f}",
        'Valor Stock': f"${float(r['precio'])*r['cantidad']:,.2f}",
        'Estado':      ('❌ Sin Stock'  if r['cantidad']==0 else
                        '⚠️ Stock Bajo' if r['cantidad']<=r['min_stock'] else
                        '✅ Normal'),
    } for r in inv_raw])

    st.dataframe(df, use_container_width=True, hide_index=True,
                 column_config={
                     'Cantidad':    st.column_config.NumberColumn(),
                     'Mín':        st.column_config.NumberColumn(),
                     'Máx':        st.column_config.NumberColumn(),
                 })

    # Botón exportar CSV con filtros aplicados
    csv = df.to_csv(index=False).encode("utf-8")
    nombre_archivo = f"inventario{'_'+cat_sel.split(' ',1)[-1] if cat_id else ''}{'_talla'+talla_fil if talla_fil else ''}.csv"
    st.download_button("⬇️ Exportar CSV con filtros actuales", csv,
                       nombre_archivo, "text/csv", use_container_width=False)

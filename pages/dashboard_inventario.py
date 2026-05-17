import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database import q

def render():
    st.header("📦 Dashboard de Inventario")

    # Agrupar por producto (suma de todas las tallas)
    inv_prods = q("""
        SELECT p.id, p.nombre, p.emoji, p.precio, p.tipo_talla,
               c.nombre as categoria,
               COALESCE(SUM(i.cantidad),0) as cantidad,
               MIN(i.min_stock) as min_stock
        FROM productos p
        LEFT JOIN inventario i ON i.producto_id=p.id
        LEFT JOIN categorias c ON c.id=p.categoria_id
        GROUP BY p.id ORDER BY p.nombre
    """)

    total_prods = len(inv_prods)
    low_stock   = [r for r in inv_prods if 0 < r['cantidad'] <= r['min_stock']]
    no_stock    = [r for r in inv_prods if r['cantidad'] == 0]
    inv_value   = sum(float(r['precio']) * r['cantidad'] for r in inv_prods)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("📦 Productos",          total_prods)
    c2.metric("⚠️ Stock Bajo",         len(low_stock), delta=f"-{len(low_stock)}", delta_color="inverse")
    c3.metric("❌ Sin Stock",           len(no_stock),  delta=f"-{len(no_stock)}",  delta_color="inverse")
    c4.metric("💎 Valor del Inventario", f"${inv_value:,.2f}")

    st.divider()

    col1, col2 = st.columns([3,2])

    with col1:
        st.subheader("Stock por producto (total todas las tallas)")
        if inv_prods:
            df = pd.DataFrame(inv_prods)
            df['label'] = df['emoji'] + " " + df['nombre']
            df['color'] = df.apply(lambda r:
                '#fc8181' if r['cantidad']==0 else
                ('#f6ad55' if r['cantidad']<=r['min_stock'] else '#68d391'), axis=1)
            df_s = df.sort_values('cantidad', ascending=True)
            fig = go.Figure(go.Bar(
                x=df_s['cantidad'], y=df_s['label'],
                orientation='h', marker_color=df_s['color'],
                text=df_s['cantidad'], textposition='outside',
                hovertemplate="<b>%{y}</b><br>Stock total: %{x}<extra></extra>",
            ))
            fig.update_layout(margin=dict(l=0,r=40,t=10,b=0),
                              height=max(300, len(inv_prods)*30),
                              xaxis_title="Unidades")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

    with col2:
        st.subheader("🚨 Alertas")
        alertas = [r for r in inv_prods if r['cantidad'] <= r['min_stock']]
        if alertas:
            for a in alertas:
                st.markdown(f"**{a['emoji']} {a['nombre']}**  \nStock: **{a['cantidad']}** / Mín: {a['min_stock']}")
                if a['cantidad'] == 0:
                    st.error("Sin stock", icon="❌")
                else:
                    st.warning("Stock bajo", icon="⚠️")
        else:
            st.success("✅ Todo el inventario está en orden")

        st.subheader("Por categoría")
        cat_stock = q("""
            SELECT c.nombre, c.emoji, SUM(i.cantidad) as total
            FROM inventario i JOIN productos p ON p.id=i.producto_id
            JOIN categorias c ON c.id=p.categoria_id
            GROUP BY c.id HAVING total > 0
        """)
        if cat_stock:
            fig2 = go.Figure(go.Pie(
                labels=[f"{r['emoji']} {r['nombre']}" for r in cat_stock],
                values=[r['total'] for r in cat_stock],
                hole=0.4, textinfo="percent+label",
            ))
            fig2.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=220, showlegend=False)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False})

    # ── Stock por talla ───────────────────────────────────────────────────────
    tallas_stats = q("""
        SELECT i.talla,
               SUM(i.cantidad) as total,
               SUM(CASE WHEN i.cantidad=0 THEN 1 ELSE 0 END) as agotados,
               SUM(CASE WHEN i.cantidad>0 AND i.cantidad<=i.min_stock THEN 1 ELSE 0 END) as bajos
        FROM inventario i
        WHERE i.talla != 'Única'
        GROUP BY i.talla ORDER BY i.talla
    """)
    if tallas_stats:
        st.divider()
        st.subheader("📏 Stock por Talla")
        tcols = st.columns(min(len(tallas_stats), 8))
        for i, t in enumerate(tallas_stats):
            icon = "🔴" if t['agotados']>0 else ("🟡" if t['bajos']>0 else "🟢")
            delta_txt = f"{t['agotados']} agot. / {t['bajos']} bajo" if (t['agotados']+t['bajos'])>0 else "OK"
            tcols[i%8].metric(
                f"Talla {t['talla']}",
                f"{icon} {t['total']}",
                delta=delta_txt,
                delta_color="inverse" if (t['agotados']+t['bajos'])>0 else "normal"
            )

    # ── Tabla completa con tallas ─────────────────────────────────────────────
    st.divider()
    st.subheader("Inventario completo por talla")

    inv_full = q("""
        SELECT p.emoji||' '||p.nombre  AS Producto,
               c.nombre                AS Categoría,
               i.talla                 AS Talla,
               i.localidad             AS Localidad,
               i.cantidad              AS Cantidad,
               i.min_stock             AS Mín,
               i.max_stock             AS Máx,
               p.precio                AS _precio,
               CASE WHEN i.cantidad=0           THEN '❌ Sin Stock'
                    WHEN i.cantidad<=i.min_stock THEN '⚠️ Stock Bajo'
                    ELSE '✅ Normal' END         AS Estado
        FROM inventario i
        JOIN productos p ON p.id=i.producto_id
        LEFT JOIN categorias c ON c.id=p.categoria_id
        ORDER BY p.nombre, i.talla
    """)

    if inv_full:
        df2 = pd.DataFrame(inv_full)
        df2['Precio']      = df2['_precio'].apply(lambda x: f"${float(x):,.2f}")
        df2['Valor Stock'] = (df2['_precio'].astype(float) * df2['Cantidad']).apply(lambda x: f"${x:,.2f}")
        df2 = df2.drop(columns=['_precio'])
        st.dataframe(df2, use_container_width=True, hide_index=True)
    else:
        st.info("Sin registros de inventario")

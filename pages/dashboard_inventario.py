import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database import q

def render():
    st.header("📦 Dashboard de Inventario")

    inv = q("""
        SELECT i.*, p.nombre, p.emoji, p.precio, c.nombre as categoria
        FROM inventario i
        JOIN productos p ON p.id=i.producto_id
        LEFT JOIN categorias c ON c.id=p.categoria_id
    """)

    total_prods  = q("SELECT COUNT(*) as n FROM productos")[0]['n']
    low_stock    = [r for r in inv if 0 < r['cantidad'] <= r['min_stock']]
    no_stock     = [r for r in inv if r['cantidad'] == 0]
    inv_value    = sum(float(r['precio']) * r['cantidad'] for r in inv)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Productos en Catálogo", total_prods)
    c2.metric("⚠️ Stock Bajo",  len(low_stock), delta=f"-{len(low_stock)}", delta_color="inverse")
    c3.metric("❌ Sin Stock",   len(no_stock),  delta=f"-{len(no_stock)}",  delta_color="inverse")
    c4.metric("💎 Valor Total del Inventario", f"${inv_value:,.2f}")

    st.divider()

    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("Cantidad en stock por producto")
        if inv:
            df = pd.DataFrame(inv)
            df['label']  = df['emoji'] + " " + df['nombre']
            df['color']  = df.apply(lambda r:
                '#fc8181' if r['cantidad']==0 else
                ('#f6ad55' if r['cantidad']<=r['min_stock'] else '#68d391'), axis=1)
            df_sorted = df.sort_values('cantidad', ascending=True)
            fig = go.Figure(go.Bar(
                x=df_sorted['cantidad'], y=df_sorted['label'],
                orientation='h', marker_color=df_sorted['color'],
                text=df_sorted['cantidad'], textposition='outside',
                hovertemplate="<b>%{y}</b><br>Stock: %{x}<extra></extra>",
            ))
            fig.update_layout(margin=dict(l=0,r=40,t=10,b=0),
                              height=max(300, len(inv)*28),
                              xaxis_title="Unidades")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

    with col2:
        st.subheader("🚨 Alertas")
        alertas = [r for r in inv if r['cantidad'] <= r['min_stock']]
        if alertas:
            for a in alertas:
                tipo = "error" if a['cantidad']==0 else "warning"
                st.markdown(
                    f"**{a['emoji']} {a['nombre']}**  \n"
                    f"📍 {a['localidad']} · Stock: **{a['cantidad']}** / Mín: {a['min_stock']}"
                )
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
            JOIN categorias c ON c.id=p.categoria_id GROUP BY c.id
        """)
        if cat_stock:
            fig2 = go.Figure(go.Pie(
                labels=[f"{r['emoji']} {r['nombre']}" for r in cat_stock],
                values=[r['total'] for r in cat_stock],
                hole=0.4, textinfo="percent+label",
            ))
            fig2.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=220, showlegend=False)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False})

    st.divider()
    st.subheader("Inventario completo")
    if inv:
        df_full = pd.DataFrame(inv)
        df_full['Producto']    = df_full['emoji'] + " " + df_full['nombre']
        df_full['Precio']      = df_full['precio'].apply(lambda x: f"${float(x):,.2f}")
        df_full['Valor Stock'] = (df_full['precio'].astype(float) * df_full['cantidad']).apply(lambda x: f"${x:,.2f}")
        df_full['Estado']      = df_full.apply(lambda r:
            '❌ Sin Stock' if r['cantidad']==0 else
            ('⚠️ Stock Bajo' if r['cantidad']<=r['min_stock'] else '✅ Normal'), axis=1)
        st.dataframe(
            df_full[['Producto','categoria','localidad','cantidad','min_stock','max_stock','Precio','Valor Stock','Estado']]
            .rename(columns={'categoria':'Categoría','localidad':'Localidad',
                             'cantidad':'Cantidad','min_stock':'Mín','max_stock':'Máx'}),
            use_container_width=True, hide_index=True
        )

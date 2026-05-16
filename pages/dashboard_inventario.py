import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import q

def render():
    st.markdown('<p class="sp-title">📦 Dashboard de <span class="sp-accent">Inventario</span></p>', unsafe_allow_html=True)
    st.markdown('<p class="sp-subtitle">Estado actual del stock</p>', unsafe_allow_html=True)

    inv = q("""
        SELECT i.*, p.nombre, p.emoji, p.precio, c.nombre as categoria
        FROM inventario i
        JOIN productos p ON p.id=i.producto_id
        LEFT JOIN categorias c ON c.id=p.categoria_id
    """)

    total_prods = q("SELECT COUNT(*) as c FROM productos")[0]['c']
    low_stock = [r for r in inv if 0 < r['cantidad'] <= r['min_stock']]
    no_stock = [r for r in inv if r['cantidad'] == 0]
    inv_value = sum(r['precio'] * r['cantidad'] for r in inv)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Total Productos", total_prods)
    c2.metric("⚠️ Stock Bajo", len(low_stock), delta=f"-{len(low_stock)} necesitan atención", delta_color="inverse")
    c3.metric("❌ Sin Stock", len(no_stock), delta=f"-{len(no_stock)} agotados", delta_color="inverse")
    c4.metric("💎 Valor del Inventario", f"${inv_value:,.2f}")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📊 Niveles de Stock por Producto")
        df_inv = pd.DataFrame(inv)
        if not df_inv.empty:
            df_inv['label'] = df_inv['emoji'] + ' ' + df_inv['nombre']
            df_inv['pct'] = (df_inv['cantidad'] / df_inv['max_stock'].clip(lower=1) * 100).clip(upper=100)
            df_inv['color'] = df_inv.apply(
                lambda r: '#e94560' if r['cantidad'] == 0 else ('#f5a623' if r['cantidad'] <= r['min_stock'] else '#00c896'), axis=1
            )
            fig = go.Figure(go.Bar(
                x=df_inv['cantidad'], y=df_inv['label'],
                orientation='h',
                marker_color=df_inv['color'],
                text=df_inv['cantidad'],
                textposition='outside',
                hovertemplate="<b>%{y}</b><br>Stock: %{x}<extra></extra>",
            ))
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font_color='#e8eaf6', margin=dict(l=0, r=40, t=10, b=0),
                height=420, xaxis=dict(gridcolor='#2d3f5c'), yaxis=dict(gridcolor='#2d3f5c'),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col2:
        st.markdown("#### 🚨 Alertas de Inventario")
        alertas = [r for r in inv if r['cantidad'] <= r['min_stock']]
        if alertas:
            for a in alertas:
                color = "#e94560" if a['cantidad'] == 0 else "#f5a623"
                icon = "❌" if a['cantidad'] == 0 else "⚠️"
                status = "SIN STOCK" if a['cantidad'] == 0 else "STOCK BAJO"
                st.markdown(f"""
                <div style="background:#1a2744;border:1px solid {color};border-left:4px solid {color};
                     border-radius:8px;padding:12px;margin-bottom:8px">
                    <div style="font-weight:700;font-size:14px">{a['emoji']} {a['nombre']}</div>
                    <div style="font-size:12px;color:#8892a4">{a['localidad']}</div>
                    <div style="display:flex;gap:16px;margin-top:4px;font-size:13px">
                        <span>{icon} <b style="color:{color}">{status}</b></span>
                        <span>Stock actual: <b>{a['cantidad']}</b></span>
                        <span>Mínimo: <b>{a['min_stock']}</b></span>
                    </div>
                </div>""", unsafe_allow_html=True)
        else:
            st.success("✅ Todo el inventario está en orden")

        st.markdown("#### 🥧 Distribución por Categoría")
        cat_stock = q("""
            SELECT c.nombre, c.emoji, SUM(i.cantidad) as total
            FROM inventario i JOIN productos p ON p.id=i.producto_id
            JOIN categorias c ON c.id=p.categoria_id
            GROUP BY c.id
        """)
        if cat_stock:
            df_cat = pd.DataFrame(cat_stock)
            fig2 = go.Figure(go.Pie(
                labels=[f"{r['emoji']} {r['nombre']}" for _, r in df_cat.iterrows()],
                values=df_cat['total'],
                hole=0.5,
                marker_colors=['#e94560', '#f5a623', '#00c896', '#4a9eff', '#a855f7'],
                textinfo='percent+label',
            ))
            fig2.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font_color='#e8eaf6', margin=dict(l=0, r=0, t=10, b=0),
                height=220, showlegend=False,
            )
            st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})

    st.markdown("---")
    st.markdown("#### 📋 Inventario Completo por Localidad")

    df_full = pd.DataFrame(inv)
    if not df_full.empty:
        df_full['Producto'] = df_full['emoji'] + ' ' + df_full['nombre']
        df_full['Valor Stock'] = (df_full['precio'] * df_full['cantidad']).apply(lambda x: f"${x:,.2f}")
        df_full['precio'] = df_full['precio'].apply(lambda x: f"${x:,.2f}")
        df_full['Estado'] = df_full.apply(
            lambda r: '❌ Sin Stock' if r['cantidad'] == 0 else ('⚠️ Stock Bajo' if r['cantidad'] <= r['min_stock'] else '✅ Normal'), axis=1
        )
        st.dataframe(
            df_full[['Producto', 'categoria', 'localidad', 'cantidad', 'min_stock', 'max_stock', 'precio', 'Valor Stock', 'Estado']].rename(columns={
                'categoria': 'Categoría', 'localidad': 'Localidad', 'cantidad': 'Cantidad',
                'min_stock': 'Mín', 'max_stock': 'Máx', 'precio': 'Precio'
            }),
            use_container_width=True, hide_index=True
        )

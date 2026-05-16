import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from database import q, get_config

COLORS = dict(
    accent="#e94560", accent2="#f5a623", success="#00c896",
    info="#4a9eff", bg="#1a2744", border="#2d3f5c",
    warning="#f5a623", text_muted="#8892a4"
)

def render():
    st.markdown('<p class="sp-title">📊 Dashboard de <span class="sp-accent">Ventas</span></p>', unsafe_allow_html=True)
    st.markdown('<p class="sp-subtitle">Resumen general del negocio</p>', unsafe_allow_html=True)

    # ── Metrics ──────────────────────────────────────────────────────────────
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    ventas_hoy = q("SELECT SUM(total) as t, COUNT(*) as c FROM ventas WHERE DATE(fecha)=? AND estado='Completada'", (str(today),))
    ventas_ayer = q("SELECT SUM(total) as t, COUNT(*) as c FROM ventas WHERE DATE(fecha)=? AND estado='Completada'", (str(yesterday),))

    total_hoy = ventas_hoy[0]['t'] or 0
    trans_hoy = ventas_hoy[0]['c'] or 0
    total_ayer = ventas_ayer[0]['t'] or 0
    trans_ayer = ventas_ayer[0]['c'] or 0

    ticket_hoy = total_hoy / trans_hoy if trans_hoy else 0
    ticket_ayer = total_ayer / trans_ayer if trans_ayer else 0

    total_clientes = q("SELECT COUNT(*) as c FROM clientes")[0]['c']

    delta_ventas = f"{((total_hoy - total_ayer) / total_ayer * 100):.1f}%" if total_ayer else "N/A"
    delta_trans = f"{trans_hoy - trans_ayer:+d}" if trans_ayer else "N/A"
    delta_ticket = f"{((ticket_hoy - ticket_ayer) / ticket_ayer * 100):.1f}%" if ticket_ayer else "N/A"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Ventas Hoy", f"${total_hoy:,.2f}", delta_ventas)
    c2.metric("🧾 Transacciones", trans_hoy, delta_trans)
    c3.metric("📊 Ticket Promedio", f"${ticket_hoy:,.2f}", delta_ticket)
    c4.metric("👥 Clientes Activos", total_clientes)

    st.markdown("---")

    # ── Charts row ────────────────────────────────────────────────────────────
    col_bar, col_donut = st.columns([2, 1])

    with col_bar:
        st.markdown("#### 📈 Ventas últimos 7 días")
        labels, vals = [], []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            row = q("SELECT COALESCE(SUM(total),0) as t FROM ventas WHERE DATE(fecha)=? AND estado='Completada'", (str(d),))
            labels.append(d.strftime("%a %d"))
            vals.append(row[0]['t'])

        fig = go.Figure(go.Bar(
            x=labels, y=vals,
            marker_color=[COLORS['accent'] if i == 6 else COLORS['info'] for i in range(7)],
            hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
        ))
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font_color='#e8eaf6', margin=dict(l=0, r=0, t=10, b=0),
            height=280, showlegend=False,
            xaxis=dict(gridcolor='#2d3f5c'), yaxis=dict(gridcolor='#2d3f5c'),
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col_donut:
        st.markdown("#### 🥧 Por Categoría")
        cat_data = q("""
            SELECT c.nombre, c.emoji, COALESCE(SUM(vi.subtotal),0) as total
            FROM categorias c
            LEFT JOIN productos p ON p.categoria_id = c.id
            LEFT JOIN venta_items vi ON vi.producto_id = p.id
            LEFT JOIN ventas v ON v.id = vi.venta_id AND v.estado='Completada'
            GROUP BY c.id ORDER BY total DESC
        """)
        df_cat = pd.DataFrame(cat_data)
        if not df_cat.empty and df_cat['total'].sum() > 0:
            fig2 = go.Figure(go.Pie(
                labels=[f"{r['emoji']} {r['nombre']}" for _, r in df_cat.iterrows()],
                values=df_cat['total'],
                hole=0.55,
                marker_colors=[COLORS['accent'], COLORS['accent2'], COLORS['success'], COLORS['info'], '#a855f7'],
                textinfo='percent',
                hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<extra></extra>",
            ))
            fig2.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font_color='#e8eaf6', margin=dict(l=0, r=0, t=10, b=0),
                height=280, showlegend=True,
                legend=dict(font=dict(size=11), bgcolor='rgba(0,0,0,0)'),
            )
            st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Sin datos de ventas aún")

    st.markdown("---")

    # ── Bottom row ────────────────────────────────────────────────────────────
    col_last, col_top = st.columns(2)

    with col_last:
        st.markdown("#### 🕐 Últimas Ventas")
        last = q("""
            SELECT v.folio, c.nombre as cliente, v.total, v.metodo_pago, v.fecha, v.estado
            FROM ventas v LEFT JOIN clientes c ON c.id=v.cliente_id
            ORDER BY v.fecha DESC LIMIT 8
        """)
        if last:
            df = pd.DataFrame(last)
            df['fecha'] = pd.to_datetime(df['fecha']).dt.strftime('%d/%m %H:%M')
            df['total'] = df['total'].apply(lambda x: f"${x:,.2f}")
            df['cliente'] = df['cliente'].fillna('Público General')
            st.dataframe(df[['folio', 'cliente', 'total', 'metodo_pago', 'fecha']].rename(columns={
                'folio': 'Folio', 'cliente': 'Cliente', 'total': 'Total',
                'metodo_pago': 'Pago', 'fecha': 'Fecha'
            }), use_container_width=True, hide_index=True)
        else:
            st.info("Sin ventas registradas")

    with col_top:
        st.markdown("#### 🏆 Top Productos Vendidos")
        top = q("""
            SELECT p.emoji, p.nombre, SUM(vi.cantidad) as unidades, SUM(vi.subtotal) as ingresos
            FROM venta_items vi JOIN productos p ON p.id=vi.producto_id
            JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
            GROUP BY p.id ORDER BY unidades DESC LIMIT 8
        """)
        if top:
            df_top = pd.DataFrame(top)
            df_top['Producto'] = df_top['emoji'] + ' ' + df_top['nombre']
            df_top['ingresos'] = df_top['ingresos'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(df_top[['Producto', 'unidades', 'ingresos']].rename(columns={
                'unidades': 'Unidades', 'ingresos': 'Ingresos'
            }), use_container_width=True, hide_index=True)
        else:
            st.info("Sin ventas registradas")

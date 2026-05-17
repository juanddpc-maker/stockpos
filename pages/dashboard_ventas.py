import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from database import q

def render():
    st.header("📊 Dashboard de Ventas")
    today = datetime.now().date()
    ayer  = today - timedelta(days=1)
    sem   = today - timedelta(days=7)

    def kpi(fecha_desde, fecha_hasta=None):
        cond = f"DATE(fecha)='{fecha_desde}'" if fecha_hasta is None else f"DATE(fecha)>='{fecha_desde}'"
        r = q(f"SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas WHERE estado='Completada' AND {cond}")
        return float(r[0]['t']), int(r[0]['n'])

    t_hoy,  n_hoy  = kpi(today)
    t_ayer, n_ayer = kpi(ayer)
    t_sem,  n_sem  = kpi(sem)

    ticket_hoy  = t_hoy  / n_hoy  if n_hoy  else 0
    ticket_ayer = t_ayer / n_ayer if n_ayer else 0

    n_clientes = q("SELECT COUNT(*) as n FROM clientes")[0]['n']

    # ── KPIs ──────────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Ventas Hoy",        f"${t_hoy:,.2f}",
              f"{((t_hoy-t_ayer)/t_ayer*100):+.1f}% vs ayer" if t_ayer else "Sin dato ayer")
    c2.metric("🧾 Transacciones Hoy", n_hoy,
              f"{n_hoy-n_ayer:+d} vs ayer")
    c3.metric("📊 Ticket Promedio",   f"${ticket_hoy:,.2f}",
              f"{((ticket_hoy-ticket_ayer)/ticket_ayer*100):+.1f}%" if ticket_ayer else "")
    c4.metric("👥 Clientes",          n_clientes)

    st.divider()

    # ── Gráficas ──────────────────────────────────────────────────────────────
    col_bar, col_pie = st.columns([3, 2])

    with col_bar:
        st.subheader("Ventas últimos 14 días")
        labels, vals = [], []
        for i in range(13, -1, -1):
            d = today - timedelta(days=i)
            r = q("SELECT COALESCE(SUM(total),0) as t FROM ventas WHERE estado='Completada' AND DATE(fecha)=?", (str(d),))
            labels.append(d.strftime("%d/%m"))
            vals.append(float(r[0]['t']))
        fig = go.Figure(go.Bar(
            x=labels, y=vals,
            marker_color=["#4299e1" if i < 13 else "#f6ad55" for i in range(14)],
            hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
        ))
        fig.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=260,
                          xaxis=dict(tickfont=dict(size=11)),
                          yaxis=dict(tickprefix="$"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

    with col_pie:
        st.subheader("Por categoría")
        cat_data = q("""
            SELECT c.nombre, c.emoji, COALESCE(SUM(vi.subtotal),0) as total
            FROM categorias c
            LEFT JOIN productos p ON p.categoria_id=c.id
            LEFT JOIN venta_items vi ON vi.producto_id=p.id
            LEFT JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
            GROUP BY c.id HAVING total > 0 ORDER BY total DESC
        """)
        if cat_data:
            fig2 = go.Figure(go.Pie(
                labels=[f"{r['emoji']} {r['nombre']}" for r in cat_data],
                values=[float(r['total']) for r in cat_data],
                hole=0.45, textinfo="percent+label",
                hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<extra></extra>",
            ))
            fig2.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=260,
                               showlegend=False)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False})
        else:
            st.info("Sin datos de ventas aún")

    st.divider()

    # ── Tablas ────────────────────────────────────────────────────────────────
    col_ul, col_top = st.columns(2)

    with col_ul:
        st.subheader("Últimas 10 ventas")
        rows = q("""
            SELECT v.folio, COALESCE(c.nombre,'Público General') as cliente,
                   v.total, v.metodo_pago, v.estado,
                   SUBSTR(v.fecha,1,16) as fecha
            FROM ventas v LEFT JOIN clientes c ON c.id=v.cliente_id
            ORDER BY v.fecha DESC LIMIT 10
        """)
        if rows:
            df = pd.DataFrame(rows)
            df['total'] = df['total'].apply(lambda x: f"${float(x):,.2f}")
            df.columns = ['Folio','Cliente','Total','Pago','Estado','Fecha']
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Sin ventas registradas")

    with col_top:
        st.subheader("Top 10 productos vendidos")
        top = q("""
            SELECT p.emoji, p.nombre, SUM(vi.cantidad) as und,
                   SUM(vi.subtotal) as ing
            FROM venta_items vi
            JOIN productos p ON p.id=vi.producto_id
            JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
            GROUP BY p.id ORDER BY und DESC LIMIT 10
        """)
        if top:
            df2 = pd.DataFrame(top)
            df2['Producto'] = df2['emoji'] + " " + df2['nombre']
            df2['ing'] = df2['ing'].apply(lambda x: f"${float(x):,.2f}")
            df2 = df2[['Producto','und','ing']].rename(columns={'und':'Unidades','ing':'Ingresos'})
            st.dataframe(df2, use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos")

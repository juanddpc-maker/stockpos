import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from database import q

def render():
    st.header("📊 Dashboard de Ventas")

    today = datetime.now().date()
    ayer  = today - timedelta(days=1)

    # ── Filtro de rango de fechas ─────────────────────────────────────────────
    with st.expander("📅 Rango de fechas", expanded=True):
        rc1, rc2, rc3 = st.columns([2, 2, 3])

        # Presets rápidos
        preset = rc3.selectbox(
            "Período rápido",
            ["Personalizado","Hoy","Ayer","Esta semana","Últimos 7 días",
             "Últimos 14 días","Este mes","Últimos 30 días","Últimos 90 días","Todo el historial"],
            index=5,  # default: Últimos 14 días
            label_visibility="collapsed",
        )

        # Calcular fechas según preset
        if preset == "Hoy":
            default_ini, default_fin = today, today
        elif preset == "Ayer":
            default_ini, default_fin = ayer, ayer
        elif preset == "Esta semana":
            default_ini = today - timedelta(days=today.weekday())
            default_fin = today
        elif preset == "Últimos 7 días":
            default_ini, default_fin = today - timedelta(days=6), today
        elif preset == "Últimos 14 días":
            default_ini, default_fin = today - timedelta(days=13), today
        elif preset == "Este mes":
            default_ini = today.replace(day=1)
            default_fin = today
        elif preset == "Últimos 30 días":
            default_ini, default_fin = today - timedelta(days=29), today
        elif preset == "Últimos 90 días":
            default_ini, default_fin = today - timedelta(days=89), today
        elif preset == "Todo el historial":
            primera = q("SELECT DATE(MIN(fecha)) as d FROM ventas WHERE estado='Completada'")
            default_ini = date.fromisoformat(primera[0]['d']) if primera and primera[0]['d'] else today - timedelta(days=30)
            default_fin = today
        else:  # Personalizado — mantiene lo que el usuario escriba
            default_ini = today - timedelta(days=13)
            default_fin = today

        fecha_ini = rc1.date_input("Desde", value=default_ini, max_value=today, key="dash_fecha_ini")
        fecha_fin = rc2.date_input("Hasta", value=default_fin, max_value=today, key="dash_fecha_fin")

        if fecha_ini > fecha_fin:
            st.error("⚠️ La fecha de inicio no puede ser mayor a la fecha final")
            return

    dias_rango = (fecha_fin - fecha_ini).days + 1
    st.caption(f"Mostrando {dias_rango} día(s): {fecha_ini.strftime('%d/%m/%Y')} → {fecha_fin.strftime('%d/%m/%Y')}")

    # ── KPIs del rango seleccionado ───────────────────────────────────────────
    def kpi_rng(d_ini, d_fin):
        r = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas "
              "WHERE estado='Completada' AND DATE(fecha)>=? AND DATE(fecha)<=?",
              (str(d_ini), str(d_fin)))
        return float(r[0]['t']), int(r[0]['n'])

    def kpi_day(d):
        r = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas "
              "WHERE estado='Completada' AND DATE(fecha)=?", (str(d),))
        return float(r[0]['t']), int(r[0]['n'])

    t_rng,  n_rng  = kpi_rng(fecha_ini, fecha_fin)
    t_hoy,  n_hoy  = kpi_day(today)
    t_ayer, n_ayer = kpi_day(ayer)

    # Período anterior para comparar
    delta = timedelta(days=dias_rango)
    t_prev, n_prev = kpi_rng(fecha_ini - delta, fecha_fin - delta)

    ticket_rng  = t_rng  / n_rng  if n_rng  else 0
    ticket_prev = t_prev / n_prev if n_prev else 0

    apt = q("SELECT COUNT(*) as n, COALESCE(SUM(saldo),0) as s FROM apartados WHERE estado='Apartado'")[0]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💰 Ventas (período)",
              f"${t_rng:,.2f}",
              f"{((t_rng-t_prev)/t_prev*100):+.1f}% vs período ant." if t_prev else "—")
    c2.metric("🧾 Transacciones",
              n_rng,
              f"{n_rng-n_prev:+d} vs período ant." if n_prev else "—")
    c3.metric("📊 Ticket Promedio",
              f"${ticket_rng:,.2f}",
              f"{((ticket_rng-ticket_prev)/ticket_prev*100):+.1f}%" if ticket_prev else "—")
    c4.metric("💼 Apartados activos", apt['n'])
    c5.metric("💵 Por cobrar",        f"${float(apt['s']):,.2f}")

    st.divider()

    # ── Gráfica de barras por día en el rango ─────────────────────────────────
    col_bar, col_pie = st.columns([3, 2])

    with col_bar:
        st.subheader(f"Ventas por día ({fecha_ini.strftime('%d/%m')} – {fecha_fin.strftime('%d/%m/%Y')})")
        labels, vals = [], []
        d = fecha_ini
        while d <= fecha_fin:
            r = q("SELECT COALESCE(SUM(total),0) as t FROM ventas "
                  "WHERE estado='Completada' AND DATE(fecha)=?", (str(d),))
            labels.append(d.strftime("%d/%m"))
            vals.append(float(r[0]['t']))
            d += timedelta(days=1)

        # Color: hoy en naranja, resto en azul
        colors = []
        d = fecha_ini
        while d <= fecha_fin:
            colors.append("#f6ad55" if d == today else "#4299e1")
            d += timedelta(days=1)

        fig = go.Figure(go.Bar(
            x=labels, y=vals,
            marker_color=colors,
            hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
        ))
        fig.update_layout(
            margin=dict(l=0, r=0, t=10, b=0), height=260,
            yaxis=dict(tickprefix="$"),
            xaxis=dict(tickangle=-45 if dias_rango > 20 else 0),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_pie:
        st.subheader("Por categoría")
        cat_data = q("""
            SELECT c.nombre, c.emoji, COALESCE(SUM(vi.subtotal),0) as total
            FROM categorias c
            LEFT JOIN productos p ON p.categoria_id=c.id
            LEFT JOIN venta_items vi ON vi.producto_id=p.id
            LEFT JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
                   AND DATE(v.fecha)>=? AND DATE(v.fecha)<=?
            GROUP BY c.id HAVING total>0 ORDER BY total DESC
        """, (str(fecha_ini), str(fecha_fin)))

        if cat_data:
            fig2 = go.Figure(go.Pie(
                labels=[f"{r['emoji']} {r['nombre']}" for r in cat_data],
                values=[float(r['total']) for r in cat_data],
                hole=0.45, textinfo="percent+label",
                hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<extra></extra>",
            ))
            fig2.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=260, showlegend=False)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Sin ventas en el período seleccionado")

    st.divider()

    # ── Tablas del período ────────────────────────────────────────────────────
    col_ul, col_top = st.columns(2)

    with col_ul:
        st.subheader(f"Ventas del período ({n_rng})")
        rows = q("""
            SELECT v.folio, COALESCE(c.nombre,'Público General') as cliente,
                   v.total, v.metodo_pago, v.estado, SUBSTR(v.fecha,1,16) as fecha
            FROM ventas v LEFT JOIN clientes c ON c.id=v.cliente_id
            WHERE v.estado='Completada'
              AND DATE(v.fecha)>=? AND DATE(v.fecha)<=?
            ORDER BY v.fecha DESC LIMIT 50
        """, (str(fecha_ini), str(fecha_fin)))

        if rows:
            df = pd.DataFrame(rows)
            df['total'] = df['total'].apply(lambda x: f"${float(x):,.2f}")
            df.columns = ['Folio','Cliente','Total','Pago','Estado','Fecha']
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Sin ventas en el período")

    with col_top:
        st.subheader("Top 10 productos del período")
        top = q("""
            SELECT p.emoji, p.nombre, SUM(vi.cantidad) as und, SUM(vi.subtotal) as ing
            FROM venta_items vi
            JOIN productos p ON p.id=vi.producto_id
            JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
                         AND DATE(v.fecha)>=? AND DATE(v.fecha)<=?
            GROUP BY p.id ORDER BY und DESC LIMIT 10
        """, (str(fecha_ini), str(fecha_fin)))

        if top:
            df2 = pd.DataFrame(top)
            df2['Producto'] = df2['emoji'] + " " + df2['nombre']
            df2['ing'] = df2['ing'].apply(lambda x: f"${float(x):,.2f}")
            st.dataframe(
                df2[['Producto','und','ing']].rename(columns={'und':'Unidades','ing':'Ingresos'}),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("Sin ventas en el período")

    # ── Resumen por método de pago ────────────────────────────────────────────
    st.divider()
    st.subheader("💳 Ventas por método de pago")
    metodos = q("""
        SELECT metodo_pago, COUNT(*) as n, SUM(total) as total
        FROM ventas
        WHERE estado='Completada' AND DATE(fecha)>=? AND DATE(fecha)<=?
        GROUP BY metodo_pago ORDER BY total DESC
    """, (str(fecha_ini), str(fecha_fin)))

    if metodos:
        mc = st.columns(len(metodos))
        for i, m in enumerate(metodos):
            mc[i].metric(m['metodo_pago'],
                         f"${float(m['total']):,.2f}",
                         f"{m['n']} transacción(es)")
    else:
        st.info("Sin datos en el período")

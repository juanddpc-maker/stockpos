import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from database import q


def _preset_fechas(preset, today):
    ayer = today - timedelta(days=1)
    if preset == "Hoy":             return today, today
    elif preset == "Ayer":          return ayer, ayer
    elif preset == "Esta semana":   return today - timedelta(days=today.weekday()), today
    elif preset == "Últimos 7 días":  return today - timedelta(days=6), today
    elif preset == "Últimos 14 días": return today - timedelta(days=13), today
    elif preset == "Este mes":      return today.replace(day=1), today
    elif preset == "Últimos 30 días": return today - timedelta(days=29), today
    elif preset == "Últimos 90 días": return today - timedelta(days=89), today
    elif preset == "Todo el historial":
        r = q("SELECT DATE(MIN(fecha)) as d FROM ventas WHERE estado='Completada'")
        r2= q("SELECT DATE(MIN(fecha)) as d FROM apartado_abonos")
        fechas = [x[0]['d'] for x in [r,r2] if x and x[0]['d']]
        d0 = min(fechas) if fechas else str(today - timedelta(days=30))
        return date.fromisoformat(d0), today
    return today - timedelta(days=13), today


def _ingresos_rng(d_ini, d_fin):
    """Suma ventas directas + abonos de apartados en el rango."""
    v = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas "
          "WHERE estado='Completada' AND DATE(fecha)>=? AND DATE(fecha)<=?",
          (str(d_ini), str(d_fin)))
    a = q("SELECT COALESCE(SUM(monto),0) as t, COUNT(*) as n FROM apartado_abonos "
          "WHERE DATE(fecha)>=? AND DATE(fecha)<=?",
          (str(d_ini), str(d_fin)))
    return float(v[0]['t']) + float(a[0]['t']), int(v[0]['n']) + int(a[0]['n'])


def _ingresos_dia(d):
    v = q("SELECT COALESCE(SUM(total),0) as t FROM ventas "
          "WHERE estado='Completada' AND DATE(fecha)=?", (str(d),))
    a = q("SELECT COALESCE(SUM(monto),0) as t FROM apartado_abonos "
          "WHERE DATE(fecha)=?", (str(d),))
    return float(v[0]['t']) + float(a[0]['t'])


def render():
    st.header("📊 Dashboard de Ventas")
    today = datetime.now().date()

    PRESETS = ["Últimos 14 días","Hoy","Ayer","Esta semana","Últimos 7 días",
               "Este mes","Últimos 30 días","Últimos 90 días","Todo el historial","Personalizado"]

    if "dash_preset" not in st.session_state:
        st.session_state.dash_preset = "Últimos 14 días"
    if "dash_ini" not in st.session_state:
        st.session_state.dash_ini, st.session_state.dash_fin = _preset_fechas("Últimos 14 días", today)

    with st.expander("📅 Filtro de período", expanded=True):
        col_preset, col_ini, col_fin = st.columns([3, 2, 2])
        preset_sel = col_preset.selectbox("Período", PRESETS,
                                          index=PRESETS.index(st.session_state.dash_preset),
                                          label_visibility="collapsed")
        if preset_sel != st.session_state.dash_preset:
            st.session_state.dash_preset = preset_sel
            if preset_sel != "Personalizado":
                st.session_state.dash_ini, st.session_state.dash_fin = _preset_fechas(preset_sel, today)
            st.rerun()

        nueva_ini = col_ini.date_input("Desde", value=st.session_state.dash_ini, max_value=today)
        nueva_fin = col_fin.date_input("Hasta", value=st.session_state.dash_fin, max_value=today)

        if nueva_ini != st.session_state.dash_ini or nueva_fin != st.session_state.dash_fin:
            st.session_state.dash_ini    = nueva_ini
            st.session_state.dash_fin    = nueva_fin
            st.session_state.dash_preset = "Personalizado"
            st.rerun()

    fecha_ini = st.session_state.dash_ini
    fecha_fin = st.session_state.dash_fin

    if fecha_ini > fecha_fin:
        st.error("⚠️ La fecha de inicio no puede ser mayor a la fecha final")
        return

    dias_rango = (fecha_fin - fecha_ini).days + 1
    st.caption(f"📅 **{st.session_state.dash_preset}** · "
               f"{fecha_ini.strftime('%d/%m/%Y')} → {fecha_fin.strftime('%d/%m/%Y')} "
               f"({dias_rango} día(s)) · Incluye ventas directas + abonos de apartados")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    t_rng, n_rng   = _ingresos_rng(fecha_ini, fecha_fin)
    delta           = timedelta(days=dias_rango)
    t_prev, n_prev  = _ingresos_rng(fecha_ini - delta, fecha_ini - timedelta(days=1))

    t_hoy  = _ingresos_dia(today)
    t_ayer = _ingresos_dia(today - timedelta(days=1))

    ticket_rng  = t_rng  / n_rng  if n_rng  else 0
    ticket_prev = t_prev / n_prev if n_prev else 0

    # Desglose para info
    v_rng = q("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM ventas "
              "WHERE estado='Completada' AND DATE(fecha)>=? AND DATE(fecha)<=?",
              (str(fecha_ini), str(fecha_fin)))
    a_rng = q("SELECT COALESCE(SUM(monto),0) as t, COUNT(*) as n FROM apartado_abonos "
              "WHERE DATE(fecha)>=? AND DATE(fecha)<=?",
              (str(fecha_ini), str(fecha_fin)))

    apt = q("SELECT COUNT(*) as n, COALESCE(SUM(saldo),0) as s FROM apartados WHERE estado='Apartado'")[0]

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("💰 Ingresos período",  f"${t_rng:,.2f}",
              f"{((t_rng-t_prev)/t_prev*100):+.1f}% vs ant." if t_prev else "—")
    c2.metric("🧾 Movimientos",       n_rng,
              f"{n_rng-n_prev:+d} vs ant." if n_prev else "—")
    c3.metric("📊 Ticket Promedio",   f"${ticket_rng:,.2f}",
              f"{((ticket_rng-ticket_prev)/ticket_prev*100):+.1f}%" if ticket_prev else "—")
    c4.metric("💼 Apartados activos", apt['n'])
    c5.metric("💵 Por cobrar",        f"${float(apt['s']):,.2f}")

    # Desglose ventas vs abonos
    col_d1, col_d2 = st.columns(2)
    col_d1.info(f"🧾 Ventas directas: **${float(v_rng[0]['t']):,.2f}** ({v_rng[0]['n']} transacciones)")
    col_d2.info(f"💼 Abonos/anticipos de apartados: **${float(a_rng[0]['t']):,.2f}** ({a_rng[0]['n']} movimientos)")

    st.divider()

    # ── Gráfica apilada: ventas + abonos por día ───────────────────────────────
    col_bar, col_pie = st.columns([3, 2])

    with col_bar:
        st.subheader(f"Ingresos por día · {fecha_ini.strftime('%d/%m')} – {fecha_fin.strftime('%d/%m/%Y')}")
        labels, vals_v, vals_a = [], [], []
        d = fecha_ini
        while d <= fecha_fin:
            r_v = q("SELECT COALESCE(SUM(total),0) as t FROM ventas "
                    "WHERE estado='Completada' AND DATE(fecha)=?", (str(d),))
            r_a = q("SELECT COALESCE(SUM(monto),0) as t FROM apartado_abonos "
                    "WHERE DATE(fecha)=?", (str(d),))
            labels.append(d.strftime("%d/%m"))
            vals_v.append(float(r_v[0]['t']))
            vals_a.append(float(r_a[0]['t']))
            d += timedelta(days=1)

        fig = go.Figure()
        fig.add_trace(go.Bar(name="Ventas directas", x=labels, y=vals_v,
                             marker_color="#4299e1",
                             hovertemplate="<b>%{x}</b><br>Ventas: $%{y:,.2f}<extra></extra>"))
        fig.add_trace(go.Bar(name="Abonos apartados", x=labels, y=vals_a,
                             marker_color="#f6ad55",
                             hovertemplate="<b>%{x}</b><br>Abonos: $%{y:,.2f}<extra></extra>"))
        fig.update_layout(
            barmode="stack",
            margin=dict(l=0, r=0, t=10, b=0), height=280,
            yaxis=dict(tickprefix="$"),
            xaxis=dict(tickangle=-45 if dias_rango > 20 else 0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
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
            fig2.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=280, showlegend=False)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Sin datos de ventas en el período")

    st.divider()

    # ── Movimientos del período (ventas + abonos mezclados) ────────────────────
    col_mov, col_top = st.columns(2)

    with col_mov:
        st.subheader(f"📋 Movimientos del período ({n_rng})")

        # Ventas directas
        ventas_rows = q("""
            SELECT v.folio as ref, 'Venta directa' as tipo,
                   COALESCE(c.nombre,'Público General') as cliente,
                   v.total as monto, v.metodo_pago, SUBSTR(v.fecha,1,16) as fecha
            FROM ventas v LEFT JOIN clientes c ON c.id=v.cliente_id
            WHERE v.estado='Completada'
              AND DATE(v.fecha)>=? AND DATE(v.fecha)<=?
        """, (str(fecha_ini), str(fecha_fin)))

        # Abonos de apartados
        abonos_rows = q("""
            SELECT a.folio as ref,
                   CASE ab.notas
                     WHEN 'Anticipo inicial' THEN 'Anticipo apartado'
                     ELSE 'Abono apartado'
                   END as tipo,
                   COALESCE(cl.nombre,'Sin cliente') as cliente,
                   ab.monto as monto, ab.metodo_pago, SUBSTR(ab.fecha,1,16) as fecha
            FROM apartado_abonos ab
            JOIN apartados a ON a.id=ab.apartado_id
            LEFT JOIN clientes cl ON cl.id=a.cliente_id
            WHERE DATE(ab.fecha)>=? AND DATE(ab.fecha)<=?
        """, (str(fecha_ini), str(fecha_fin)))

        todos = ventas_rows + abonos_rows
        todos.sort(key=lambda x: x['fecha'], reverse=True)

        if todos:
            df_mov = pd.DataFrame([{
                'Ref':     r['ref'],
                'Tipo':    r['tipo'],
                'Cliente': r['cliente'],
                'Monto':   f"${float(r['monto']):,.2f}",
                'Pago':    r['metodo_pago'],
                'Fecha':   r['fecha'],
            } for r in todos])
            st.dataframe(df_mov, use_container_width=True, hide_index=True)
        else:
            st.info("Sin movimientos en el período")

    with col_top:
        st.subheader("🏆 Top 10 productos del período")
        top = q("""
            SELECT p.emoji, p.nombre, c.nombre as categoria, c.emoji as cat_emoji,
                   SUM(vi.cantidad) as und, SUM(vi.subtotal) as ing
            FROM venta_items vi
            JOIN productos p ON p.id=vi.producto_id
            LEFT JOIN categorias c ON c.id=p.categoria_id
            JOIN ventas v ON v.id=vi.venta_id AND v.estado='Completada'
                         AND DATE(v.fecha)>=? AND DATE(v.fecha)<=?
            GROUP BY p.id ORDER BY und DESC LIMIT 10
        """, (str(fecha_ini), str(fecha_fin)))

        if top:
            df2 = pd.DataFrame(top)
            df2['Producto']  = df2['emoji']     + " " + df2['nombre']
            df2['Categoría'] = df2['cat_emoji'] + " " + df2['categoria'].fillna('—')
            df2['ing']       = df2['ing'].apply(lambda x: f"${float(x):,.2f}")
            st.dataframe(
                df2[['Producto','Categoría','und','ing']].rename(
                    columns={'und':'Unidades','ing':'Ingresos'}),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("Sin ventas en el período")

    # ── Por método de pago (ventas + abonos) ──────────────────────────────────
    st.divider()
    st.subheader("💳 Ingresos por método de pago")

    metodos_v = q("""
        SELECT metodo_pago, COUNT(*) as n, SUM(total) as total
        FROM ventas WHERE estado='Completada'
          AND DATE(fecha)>=? AND DATE(fecha)<=?
        GROUP BY metodo_pago
    """, (str(fecha_ini), str(fecha_fin)))

    metodos_a = q("""
        SELECT metodo_pago, COUNT(*) as n, SUM(monto) as total
        FROM apartado_abonos
        WHERE DATE(fecha)>=? AND DATE(fecha)<=?
        GROUP BY metodo_pago
    """, (str(fecha_ini), str(fecha_fin)))

    # Merge por método
    metodos_map = {}
    for r in metodos_v + metodos_a:
        k = r['metodo_pago']
        if k not in metodos_map:
            metodos_map[k] = {'n': 0, 'total': 0.0}
        metodos_map[k]['n']     += int(r['n'])
        metodos_map[k]['total'] += float(r['total'])

    metodos = sorted(metodos_map.items(), key=lambda x: x[1]['total'], reverse=True)
    if metodos:
        mc = st.columns(min(len(metodos), 5))
        for i, (metodo, vals) in enumerate(metodos):
            mc[i].metric(metodo, f"${vals['total']:,.2f}", f"{vals['n']} movimiento(s)")
    else:
        st.info("Sin datos en el período")

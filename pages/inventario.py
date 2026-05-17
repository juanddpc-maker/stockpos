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
    fc1,fc2,fc3 = st.columns([3,1,1])
    buscar   = fc1.text_input("🔍 Buscar", placeholder="Producto o localidad...", label_visibility="collapsed")
    estado_f = fc2.selectbox("Estado",["Todos","Sin Stock","Stock Bajo","Normal"], label_visibility="collapsed")
    talla_f  = fc3.text_input("Talla", placeholder="Ej: M, 10...", label_visibility="collapsed")

    inv = q("""
        SELECT i.id, i.talla, i.localidad, i.cantidad, i.min_stock, i.max_stock,
               p.id as prod_id, p.nombre, p.emoji, p.precio, p.tipo_talla,
               c.nombre as categoria
        FROM inventario i JOIN productos p ON p.id=i.producto_id
        LEFT JOIN categorias c ON c.id=p.categoria_id
        ORDER BY p.nombre, i.talla
    """)

    # Filters
    if buscar:
        s = buscar.lower()
        inv = [r for r in inv if s in r['nombre'].lower() or s in r['localidad'].lower()]
    if talla_f:
        inv = [r for r in inv if talla_f.upper() in r['talla'].upper()]
    if estado_f=="Sin Stock":   inv=[r for r in inv if r['cantidad']==0]
    elif estado_f=="Stock Bajo":inv=[r for r in inv if 0<r['cantidad']<=r['min_stock']]
    elif estado_f=="Normal":    inv=[r for r in inv if r['cantidad']>r['min_stock']]

    # Group by product
    prods_seen = {}
    for r in inv:
        if r['prod_id'] not in prods_seen:
            prods_seen[r['prod_id']] = {'info':r, 'tallas':[]}
        prods_seen[r['prod_id']]['tallas'].append(r)

    st.caption(f"{len(prods_seen)} producto(s) · {len(inv)} registro(s) de talla")

    for pid, data in prods_seen.items():
        info   = data['info']
        tallas = data['tallas']
        total  = sum(t['cantidad'] for t in tallas)
        any_low= any(t['cantidad']<=t['min_stock'] for t in tallas)
        any_zero=any(t['cantidad']==0 for t in tallas)
        status = "❌" if any_zero else ("⚠️" if any_low else "✅")

        with st.expander(f"{info['emoji']} **{info['nombre']}** · Stock total: **{total}** {status}"):
            # Tallas grid
            cols = st.columns(min(len(tallas), 6))
            for i,t in enumerate(tallas):
                color = "🔴" if t['cantidad']==0 else ("🟡" if t['cantidad']<=t['min_stock'] else "🟢")
                cols[i%6].metric(t['talla'], f"{color} {t['cantidad']}")

            st.divider()
            # Edit each talla
            for t in tallas:
                with st.form(f"inv_{t['id']}"):
                    st.markdown(f"**Talla {t['talla']}** · {t['localidad']}")
                    fc1,fc2,fc3,fc4 = st.columns(4)
                    tipo   = fc1.selectbox("Ajuste",["Establecer","Agregar","Restar"], key=f"tipo_{t['id']}")
                    cant   = fc2.number_input("Cantidad", min_value=0, value=t['cantidad'], key=f"cant_{t['id']}")
                    mn     = fc3.number_input("Mínimo",   min_value=0, value=t['min_stock'], key=f"mn_{t['id']}")
                    mx     = fc4.number_input("Máximo",   min_value=1, value=t['max_stock'], key=f"mx_{t['id']}")
                    if st.form_submit_button(f"💾 Guardar talla {t['talla']}", use_container_width=True):
                        curr = t['cantidad']
                        nueva = cant if tipo=="Establecer" else (curr+cant if tipo=="Agregar" else max(0,curr-cant))
                        run("UPDATE inventario SET cantidad=?,min_stock=?,max_stock=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                            (nueva, mn, mx, t['id']))
                        st.success(f"Talla {t['talla']}: {curr} → {nueva}"); st.rerun()


def _tab_agregar():
    st.subheader("Agregar / Ajustar stock")
    prods = q("SELECT id, nombre, emoji, tipo_talla FROM productos ORDER BY nombre")
    with st.form("add_stock"):
        prod_opts = {f"{p['emoji']} {p['nombre']}": p for p in prods}
        prod_sel  = st.selectbox("Producto *", list(prod_opts.keys()))
        prod      = prod_opts[prod_sel]
        tallas    = TALLAS.get(prod['tipo_talla'],["Única"])

        c1,c2,c3 = st.columns(3)
        talla_sel = c1.selectbox("Talla *", tallas)
        localidad = c2.text_input("Localidad", value="Tienda Principal")
        tipo      = c3.selectbox("Tipo", ["Establecer","Agregar","Restar"])

        c4,c5,c6 = st.columns(3)
        cantidad  = c4.number_input("Cantidad", min_value=0)
        min_s     = c5.number_input("Mínimo",   min_value=0, value=2)
        max_s     = c6.number_input("Máximo",   min_value=1, value=100)

        if st.form_submit_button("💾 Guardar", type="primary", use_container_width=True):
            pid = prod['id']
            ex  = q("SELECT id,cantidad FROM inventario WHERE producto_id=? AND talla=? AND localidad=?",
                    (pid, talla_sel, localidad))
            if ex:
                curr  = ex[0]['cantidad']
                nueva = cantidad if tipo=="Establecer" else (curr+cantidad if "Agregar" in tipo else max(0,curr-cantidad))
                run("UPDATE inventario SET cantidad=?,min_stock=?,max_stock=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (nueva, min_s, max_s, ex[0]['id']))
                st.success(f"Stock {talla_sel}: {curr} → {nueva}")
            else:
                run("INSERT INTO inventario(producto_id,talla,localidad,cantidad,min_stock,max_stock) VALUES(?,?,?,?,?,?)",
                    (pid, talla_sel, localidad, cantidad, min_s, max_s))
                st.success(f"Registro creado: {talla_sel} · {cantidad} uds")
            st.rerun()


def _tab_masivo():
    st.subheader("Ajuste masivo")
    st.info("Edita directamente. Haz clic en **Guardar todo** al terminar.")
    inv = q("""
        SELECT i.id, p.nombre as Producto, i.talla as Talla, i.localidad as Localidad,
               i.cantidad as Cantidad, i.min_stock as Min, i.max_stock as Max
        FROM inventario i JOIN productos p ON p.id=i.producto_id
        ORDER BY p.nombre, i.talla
    """)
    df = pd.DataFrame(inv)
    edited = st.data_editor(
        df, use_container_width=True, hide_index=True,
        disabled=['id','Producto','Talla','Localidad'],
        column_config={
            'Cantidad': st.column_config.NumberColumn(min_value=0, step=1),
            'Min':      st.column_config.NumberColumn(min_value=0, step=1),
            'Max':      st.column_config.NumberColumn(min_value=1, step=1),
        }
    )
    if st.button("💾 Guardar todo", type="primary"):
        for _,row in edited.iterrows():
            run("UPDATE inventario SET cantidad=?,min_stock=?,max_stock=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (int(row['Cantidad']), int(row['Min']), int(row['Max']), int(row['id'])))
        st.success(f"✅ {len(edited)} registros guardados"); st.rerun()

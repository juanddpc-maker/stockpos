import streamlit as st
from database import q, run, TALLAS, get_tallas_producto

EMOJIS = ["👕","👖","👗","👚","👔","🧥","🦺","🩱","🩲","🩳","🎽","👞","👟","🥾","🧦","🧢","🪢","🎒","📦","⭐"]
TIPO_TALLA_OPTS = {"Escolar por número (2-16)":"escolar_num","Ropa (XS-XXL)":"ropa","Única / Sin talla":"unico"}
TIPO_TALLA_LABELS = {v:k for k,v in TIPO_TALLA_OPTS.items()}

def render():
    st.header("👔 Productos")
    tab_lista, tab_nuevo = st.tabs(["📋 Lista","➕ Nuevo Producto"])
    cats = q("SELECT * FROM categorias ORDER BY nombre")
    with tab_nuevo: _form_nuevo(cats)
    with tab_lista: _lista(cats)


def _lista(cats):
    fc1,fc2 = st.columns([3,1])
    buscar  = fc1.text_input("🔍 Buscar", placeholder="Nombre...", label_visibility="collapsed")
    cat_opts= {"Todas":None}|{f"{c['emoji']} {c['nombre']}":c['id'] for c in cats}
    cat_sel = fc2.selectbox("Cat.", list(cat_opts.keys()), label_visibility="collapsed")
    cat_id  = cat_opts[cat_sel]

    f_n = f"AND LOWER(p.nombre) LIKE '%{buscar.lower()}%'" if buscar else ""
    f_c = f"AND p.categoria_id={cat_id}" if cat_id else ""

    prods = q(f"""
        SELECT p.id, p.nombre, p.precio, p.emoji, p.descripcion, p.codigo_barras,
               p.categoria_id, p.tipo_talla,
               c.nombre as cat_nombre, c.emoji as cat_emoji,
               COALESCE((SELECT SUM(cantidad) FROM inventario WHERE producto_id=p.id),0) AS stock
        FROM productos p LEFT JOIN categorias c ON c.id=p.categoria_id
        WHERE 1=1 {f_n} {f_c} ORDER BY p.nombre
    """)

    st.caption(f"{len(prods)} producto(s)")
    for p in prods:
        stock  = int(p['stock'])
        min_s  = q("SELECT COALESCE(MIN(min_stock),5) as m FROM inventario WHERE producto_id=?", (p['id'],))[0]['m']
        status = "❌ Sin stock" if stock==0 else ("⚠️ Stock bajo" if stock<=min_s else "✅ Normal")
        talla_label = TIPO_TALLA_LABELS.get(p['tipo_talla'],'—')
        with st.expander(f"{p['emoji']} **{p['nombre']}** · ${float(p['precio']):,.2f} · {status} · 📏 {talla_label}"):
            m1,m2,m3,m4 = st.columns(4)
            m1.metric("Precio", f"${float(p['precio']):,.2f}")
            m2.metric("Stock total", stock)
            m3.metric("Categoría", f"{p['cat_emoji'] or ''} {p['cat_nombre'] or '—'}")
            m4.metric("Tipo talla", talla_label)

            # Stock por talla
            if p['tipo_talla'] != 'unico':
                tallas_stock = q("SELECT talla, SUM(cantidad) as cant FROM inventario WHERE producto_id=? GROUP BY talla ORDER BY cant DESC", (p['id'],))
                if tallas_stock:
                    st.markdown("**Stock por talla:**")
                    cols = st.columns(len(tallas_stock))
                    for i,ts in enumerate(tallas_stock):
                        color = "🔴" if ts['cant']==0 else ("🟡" if ts['cant']<=3 else "🟢")
                        cols[i].metric(ts['talla'], f"{color} {ts['cant']}")

            st.divider()
            _form_editar(p, cats)


def _form_nuevo(cats):
    st.subheader("Nuevo producto")
    with st.form("form_nuevo", clear_on_submit=True):
        c1,c2 = st.columns(2)
        nombre = c1.text_input("Nombre *")
        precio = c2.number_input("Precio *", min_value=0.01, step=1.0, format="%.2f")
        c3,c4  = st.columns(2)
        cat_opts = {f"{c['emoji']} {c['nombre']}":c['id'] for c in cats}
        cat_sel  = c3.selectbox("Categoría *", list(cat_opts.keys()))
        emoji    = c4.selectbox("Ícono", EMOJIS)
        c5,c6    = st.columns(2)
        tipo_sel = c5.selectbox("Tipo de talla", list(TIPO_TALLA_OPTS.keys()))
        codigo   = c6.text_input("Código de barras")
        desc     = st.text_area("Descripción", height=70)

        tipo_talla = TIPO_TALLA_OPTS[tipo_sel]
        tallas     = TALLAS.get(tipo_talla, ["Única"])

        st.markdown(f"**Stock inicial** · Se crearán {len(tallas)} registro(s): {', '.join(tallas)}")
        s1,s2,s3 = st.columns(3)
        localidad  = s1.text_input("Localidad", value="Tienda Principal")
        cant_ini   = s2.number_input("Cantidad por talla", min_value=0, value=0)
        min_stock  = s3.number_input("Mínimo por talla", min_value=0, value=2)

        if st.form_submit_button("💾 Guardar producto", type="primary", use_container_width=True):
            if not nombre.strip(): st.error("Nombre requerido")
            elif precio<=0: st.error("Precio inválido")
            else:
                pid = run("INSERT INTO productos(nombre,precio,categoria_id,emoji,descripcion,codigo_barras,tipo_talla)"
                          " VALUES(?,?,?,?,?,?,?)",
                          (nombre.strip(), precio, cat_opts[cat_sel], emoji, desc, codigo, tipo_talla))
                for talla in tallas:
                    run("INSERT INTO inventario(producto_id,talla,localidad,cantidad,min_stock,max_stock)"
                        " VALUES(?,?,?,?,?,?)", (pid, talla, localidad, cant_ini, min_stock, 100))
                st.success(f"✅ **{nombre}** creado con {len(tallas)} talla(s)"); st.rerun()


def _form_editar(p, cats):
    cat_opts    = {f"{c['emoji']} {c['nombre']}":c['id'] for c in cats}
    cat_default = next((k for k,v in cat_opts.items() if v==p['categoria_id']), list(cat_opts.keys())[0])
    tipo_default= next((k for k,v in TIPO_TALLA_OPTS.items() if v==p['tipo_talla']), list(TIPO_TALLA_OPTS.keys())[0])

    with st.form(f"edit_{p['id']}"):
        c1,c2 = st.columns(2)
        nombre  = c1.text_input("Nombre", value=p['nombre'])
        precio  = c2.number_input("Precio", value=float(p['precio']), min_value=0.01, step=1.0, format="%.2f")
        c3,c4   = st.columns(2)
        cat_sel = c3.selectbox("Categoría", list(cat_opts.keys()), index=list(cat_opts.keys()).index(cat_default))
        emoji   = c4.selectbox("Ícono", EMOJIS, index=EMOJIS.index(p['emoji']) if p['emoji'] in EMOJIS else 0)
        c5,c6   = st.columns(2)
        tipo_sel= c5.selectbox("Tipo de talla", list(TIPO_TALLA_OPTS.keys()),
                               index=list(TIPO_TALLA_OPTS.keys()).index(tipo_default))
        codigo  = c6.text_input("Cód. barras", value=p['codigo_barras'] or "")
        desc    = st.text_area("Descripción", value=p['descripcion'] or "", height=60)

        cg,ce = st.columns(2)
        guardar  = cg.form_submit_button("💾 Guardar", type="primary", use_container_width=True)
        eliminar = ce.form_submit_button("🗑️ Eliminar", use_container_width=True)

        if guardar:
            nuevo_tipo = TIPO_TALLA_OPTS[tipo_sel]
            run("UPDATE productos SET nombre=?,precio=?,categoria_id=?,emoji=?,descripcion=?,codigo_barras=?,tipo_talla=? WHERE id=?",
                (nombre, precio, cat_opts[cat_sel], emoji, desc, codigo, nuevo_tipo, p['id']))
            # Si cambió tipo de talla, agregar tallas faltantes
            if nuevo_tipo != p['tipo_talla']:
                loc = q("SELECT localidad FROM inventario WHERE producto_id=? LIMIT 1",(p['id'],))
                localidad = loc[0]['localidad'] if loc else "Tienda Principal"
                for talla in TALLAS.get(nuevo_tipo,["Única"]):
                    exist = q("SELECT id FROM inventario WHERE producto_id=? AND talla=?",(p['id'],talla))
                    if not exist:
                        run("INSERT INTO inventario(producto_id,talla,localidad,cantidad,min_stock,max_stock) VALUES(?,?,?,0,2,100)",
                            (p['id'], talla, localidad))
            st.success("✅ Actualizado"); st.rerun()

        if eliminar:
            run("DELETE FROM apartado_items WHERE producto_id=?", (p['id'],))
            run("DELETE FROM venta_items WHERE producto_id=?",    (p['id'],))
            run("DELETE FROM inventario WHERE producto_id=?",     (p['id'],))
            run("DELETE FROM productos WHERE id=?",               (p['id'],))
            st.success("Eliminado"); st.rerun()

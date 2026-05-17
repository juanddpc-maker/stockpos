import streamlit as st
from database import q, run

EMOJIS_UNIFORMES = [
    "👕","👖","👗","👚","👔","🧥","🦺","🩱","🩲","🩳","🎽",
    "👞","👟","🥾","🧦","🧢","🪢","🎒","📦","⭐","🔧","🌿"
]

def render():
    st.header("👔 Productos")
    tab_lista, tab_nuevo = st.tabs(["📋 Lista de Productos", "➕ Nuevo Producto"])
    cats = q("SELECT * FROM categorias ORDER BY nombre")
    with tab_nuevo:
        _form_nuevo(cats)
    with tab_lista:
        _lista(cats)


def _lista(cats):
    fc1, fc2 = st.columns([3,1])
    buscar  = fc1.text_input("🔍 Buscar", placeholder="Nombre del producto...", label_visibility="collapsed")
    cat_opts = {"Todas": None} | {f"{c['emoji']} {c['nombre']}": c['id'] for c in cats}
    cat_sel  = fc2.selectbox("Categoría", list(cat_opts.keys()), label_visibility="collapsed")
    cat_id   = cat_opts[cat_sel]

    filtro_n = f"AND LOWER(p.nombre) LIKE '%{buscar.lower()}%'" if buscar else ""
    filtro_c = f"AND p.categoria_id={cat_id}" if cat_id else ""

    prods = q(f"""
        SELECT p.id, p.nombre, p.precio, p.emoji, p.descripcion, p.codigo_barras,
               p.categoria_id,
               c.nombre as cat_nombre, c.emoji as cat_emoji,
               COALESCE((SELECT SUM(cantidad) FROM inventario WHERE producto_id=p.id),0) AS stock,
               COALESCE((SELECT MIN(min_stock) FROM inventario WHERE producto_id=p.id),5) AS min_stock
        FROM productos p
        LEFT JOIN categorias c ON c.id=p.categoria_id
        WHERE 1=1 {filtro_n} {filtro_c}
        ORDER BY p.nombre
    """)

    st.caption(f"{len(prods)} producto(s) encontrado(s)")
    if not prods:
        st.info("No hay productos con los filtros seleccionados.")
        return

    for p in prods:
        stock   = int(p['stock'])
        min_s   = int(p['min_stock'])
        status  = "❌ Sin stock" if stock == 0 else ("⚠️ Stock bajo" if stock <= min_s else "✅ Normal")
        with st.expander(f"{p['emoji']} **{p['nombre']}** · ${float(p['precio']):,.2f} · {status} ({stock} uds)"):
            i1, i2, i3 = st.columns(3)
            i1.metric("Precio",       f"${float(p['precio']):,.2f}")
            i2.metric("Stock actual", stock)
            i3.metric("Categoría",    f"{p['cat_emoji'] or ''} {p['cat_nombre'] or '—'}")
            if p['descripcion']:
                st.caption(p['descripcion'])
            st.divider()
            _form_editar(p, cats)


def _form_nuevo(cats):
    st.subheader("Agregar nuevo producto")
    with st.form("form_nuevo_prod", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre del producto *")
        precio = c2.number_input("Precio de venta *", min_value=0.01, step=1.0, format="%.2f")
        c3, c4 = st.columns(2)
        cat_opts = {f"{c['emoji']} {c['nombre']}": c['id'] for c in cats}
        cat_sel  = c3.selectbox("Categoría *", list(cat_opts.keys()))
        emoji    = c4.selectbox("Ícono", EMOJIS_UNIFORMES)
        descripcion = st.text_area("Descripción", height=70, placeholder="Descripción opcional...")
        codigo      = st.text_input("Código de barras", placeholder="Opcional")
        st.markdown("**Stock inicial**")
        s1, s2, s3, s4 = st.columns(4)
        localidad = s1.text_input("Localidad",  value="Tienda Principal")
        cant_ini  = s2.number_input("Cantidad", min_value=0, value=0)
        min_stock = s3.number_input("Mínimo",   min_value=0, value=5)
        max_stock = s4.number_input("Máximo",   min_value=1, value=100)
        if st.form_submit_button("💾 Guardar producto", type="primary", use_container_width=True):
            if not nombre.strip():
                st.error("El nombre es requerido")
            elif precio <= 0:
                st.error("El precio debe ser mayor a 0")
            else:
                pid = run("INSERT INTO productos(nombre,precio,categoria_id,emoji,descripcion,codigo_barras)"
                          " VALUES(?,?,?,?,?,?)",
                          (nombre.strip(), precio, cat_opts[cat_sel], emoji, descripcion, codigo))
                run("INSERT INTO inventario(producto_id,localidad,cantidad,min_stock,max_stock)"
                    " VALUES(?,?,?,?,?)", (pid, localidad, cant_ini, min_stock, max_stock))
                st.success(f"✅ Producto **{nombre}** creado correctamente")
                st.rerun()


def _form_editar(p, cats):
    cat_opts    = {f"{c['emoji']} {c['nombre']}": c['id'] for c in cats}
    cat_default = next((k for k,v in cat_opts.items() if v == p['categoria_id']), list(cat_opts.keys())[0])
    emoji_idx   = EMOJIS_UNIFORMES.index(p['emoji']) if p['emoji'] in EMOJIS_UNIFORMES else 0

    with st.form(f"form_edit_{p['id']}"):
        st.markdown("**Editar producto**")
        c1, c2 = st.columns(2)
        nombre  = c1.text_input("Nombre",  value=p['nombre'])
        precio  = c2.number_input("Precio", value=float(p['precio']), min_value=0.01, step=1.0, format="%.2f")
        c3, c4  = st.columns(2)
        cat_sel = c3.selectbox("Categoría", list(cat_opts.keys()),
                               index=list(cat_opts.keys()).index(cat_default))
        emoji   = c4.selectbox("Ícono", EMOJIS_UNIFORMES, index=emoji_idx)
        descripcion = st.text_area("Descripción", value=p['descripcion'] or "", height=70)
        codigo      = st.text_input("Código de barras", value=p['codigo_barras'] or "")
        col_g, col_e = st.columns(2)
        guardar  = col_g.form_submit_button("💾 Guardar cambios", type="primary", use_container_width=True)
        eliminar = col_e.form_submit_button("🗑️ Eliminar producto", use_container_width=True)
        if guardar:
            run("UPDATE productos SET nombre=?,precio=?,categoria_id=?,emoji=?,descripcion=?,codigo_barras=? WHERE id=?",
                (nombre, precio, cat_opts[cat_sel], emoji, descripcion, codigo, p['id']))
            st.success("✅ Producto actualizado"); st.rerun()
        if eliminar:
            n_items = q("SELECT COUNT(*) as n FROM venta_items WHERE producto_id=?", (p['id'],))[0]['n']
            run("DELETE FROM apartado_items WHERE producto_id=?", (p['id'],))
            run("DELETE FROM venta_items WHERE producto_id=?", (p['id'],))
            run("DELETE FROM inventario WHERE producto_id=?", (p['id'],))
            run("DELETE FROM productos WHERE id=?", (p['id'],))
            msg = f"Producto eliminado" + (f" (estaba en {n_items} venta(s))" if n_items else "")
            st.success(msg); st.rerun()

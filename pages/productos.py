import streamlit as st
import pandas as pd
from database import q, run

EMOJIS = ["📦","💻","🖱️","⌨️","🎧","🖥️","👕","👖","🧥","🍎","💧","☕","🍿","💡","🪑","🔧","📏","📱","🎮","🏠","⚽","📚","🌿","💊","🧴"]

def render():
    st.markdown('<p class="sp-title">🏷️ <span class="sp-accent">Productos</span></p>', unsafe_allow_html=True)
    st.markdown('<p class="sp-subtitle">Catálogo de productos</p>', unsafe_allow_html=True)

    tab_list, tab_new = st.tabs(["📋 Listado", "➕ Nuevo Producto"])

    with tab_list:
        sf1, sf2 = st.columns([3, 1])
        search = sf1.text_input("🔍 Buscar producto", placeholder="Nombre...", label_visibility="collapsed")
        cats = q("SELECT * FROM categorias ORDER BY nombre")
        cat_opts = {"Todas": None} | {f"{c['emoji']} {c['nombre']}": c['id'] for c in cats}
        cat_sel = sf2.selectbox("Categoría", list(cat_opts.keys()), label_visibility="collapsed")
        cat_id = cat_opts[cat_sel]

        prods = q("""
            SELECT p.*, c.nombre as cat_nombre, c.emoji as cat_emoji,
                   COALESCE((SELECT SUM(cantidad) FROM inventario WHERE producto_id=p.id),0) as stock
            FROM productos p LEFT JOIN categorias c ON c.id=p.categoria_id
            WHERE (%s) AND (%s)
            ORDER BY p.nombre
        """ % (
            f"LOWER(p.nombre) LIKE '%{search.lower()}%'" if search else "1=1",
            f"p.categoria_id={cat_id}" if cat_id else "1=1"
        ))

        if not prods:
            st.info("No hay productos")
        else:
            for p in prods:
                stock = p['stock']
                status = "❌ Sin Stock" if stock == 0 else ("⚠️ Stock Bajo" if stock <= 5 else "✅ Normal")
                with st.expander(f"{p['emoji']} **{p['nombre']}** · ${p['precio']:,.2f} · {status}"):
                    ec1, ec2, ec3 = st.columns(3)
                    ec1.markdown(f"**Categoría:** {p['cat_emoji']} {p['cat_nombre']}")
                    ec2.markdown(f"**Precio:** ${p['precio']:,.2f}")
                    ec3.markdown(f"**Stock Total:** {stock}")

                    st.markdown("---")
                    _edit_form(p, cats)

    with tab_new:
        _new_form(cats)


def _new_form(cats):
    st.markdown("#### ➕ Agregar Nuevo Producto")
    with st.form("new_product"):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre *")
        precio = c2.number_input("Precio *", min_value=0.0, step=0.5, format="%.2f")

        c3, c4 = st.columns(2)
        cat_opts = {f"{c['emoji']} {c['nombre']}": c['id'] for c in cats}
        cat_sel = c3.selectbox("Categoría", list(cat_opts.keys()))
        emoji = c4.selectbox("Emoji", EMOJIS)

        descripcion = st.text_area("Descripción", height=80)
        codigo = st.text_input("Código de Barras")

        st.markdown("**Stock Inicial**")
        sc1, sc2, sc3, sc4 = st.columns(4)
        localidad = sc1.text_input("Localidad", value="Almacén Central")
        cant_ini = sc2.number_input("Cantidad", min_value=0, value=0)
        min_s = sc3.number_input("Mín. Stock", min_value=0, value=5)
        max_s = sc4.number_input("Máx. Stock", min_value=1, value=50)

        submitted = st.form_submit_button("💾 Guardar Producto", type="primary", use_container_width=True)
        if submitted:
            if not nombre or not precio:
                st.error("Nombre y precio son requeridos")
            else:
                pid = run(
                    "INSERT INTO productos (nombre, precio, categoria_id, emoji, descripcion, codigo_barras) VALUES (?,?,?,?,?,?)",
                    (nombre, precio, cat_opts[cat_sel], emoji, descripcion, codigo)
                )
                run(
                    "INSERT INTO inventario (producto_id, localidad, cantidad, min_stock, max_stock) VALUES (?,?,?,?,?)",
                    (pid, localidad, cant_ini, min_s, max_s)
                )
                st.success(f"✅ Producto **{nombre}** creado correctamente")
                st.rerun()


def _edit_form(p, cats):
    with st.form(f"edit_{p['id']}"):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre", value=p['nombre'])
        precio = c2.number_input("Precio", value=float(p['precio']), min_value=0.0, step=0.5, format="%.2f")

        c3, c4 = st.columns(2)
        cat_opts = {f"{c['emoji']} {c['nombre']}": c['id'] for c in cats}
        cat_default = next((k for k, v in cat_opts.items() if v == p['categoria_id']), list(cat_opts.keys())[0])
        cat_sel = c3.selectbox("Categoría", list(cat_opts.keys()), index=list(cat_opts.keys()).index(cat_default))
        emoji = c4.selectbox("Emoji", EMOJIS, index=EMOJIS.index(p['emoji']) if p['emoji'] in EMOJIS else 0)

        descripcion = st.text_area("Descripción", value=p['descripcion'] or "", height=60)

        sb1, sb2, sb3 = st.columns(3)
        save = sb1.form_submit_button("💾 Guardar", type="primary", use_container_width=True)
        delete = sb3.form_submit_button("🗑️ Eliminar", use_container_width=True)

        if save:
            run("UPDATE productos SET nombre=?, precio=?, categoria_id=?, emoji=?, descripcion=? WHERE id=?",
                (nombre, precio, cat_opts[cat_sel], emoji, descripcion, p['id']))
            st.success("Producto actualizado")
            st.rerun()

        if delete:
            run("DELETE FROM inventario WHERE producto_id=?", (p['id'],))
            run("DELETE FROM productos WHERE id=?", (p['id'],))
            st.warning("Producto eliminado")
            st.rerun()

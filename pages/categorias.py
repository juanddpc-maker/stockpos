import streamlit as st
from database import q, run

EMOJIS = ["🗂️","💻","👕","🍎","🏠","🔧","📦","🎮","📚","🌿","💊","🧴","⚽","🎵","🚗","✈️","🏥","🍕","☕","🎨"]

def render():
    st.markdown('<p class="sp-title">🗂️ <span class="sp-accent">Categorías</span></p>', unsafe_allow_html=True)
    st.markdown('<p class="sp-subtitle">Gestión de categorías de productos</p>', unsafe_allow_html=True)

    tab_list, tab_new = st.tabs(["📋 Categorías", "➕ Nueva Categoría"])

    cats = q("""
        SELECT c.*, COUNT(p.id) as n_productos
        FROM categorias c LEFT JOIN productos p ON p.categoria_id=c.id
        GROUP BY c.id ORDER BY c.nombre
    """)

    with tab_list:
        if not cats:
            st.info("No hay categorías registradas")
        else:
            # Summary cards
            cols = st.columns(min(len(cats), 5))
            for i, c in enumerate(cats):
                cols[i % 5].markdown(f"""
                <div style="background:#1a2744;border:1px solid #2d3f5c;border-radius:10px;
                     padding:16px;text-align:center;margin-bottom:12px">
                    <div style="font-size:32px">{c['emoji']}</div>
                    <div style="font-weight:700;font-size:14px;margin-top:6px">{c['nombre']}</div>
                    <div style="color:#8892a4;font-size:12px">{c['n_productos']} productos</div>
                </div>""", unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("#### ✏️ Editar Categorías")
            for c in cats:
                with st.expander(f"{c['emoji']} **{c['nombre']}** · {c['n_productos']} productos"):
                    if c['descripcion']:
                        st.caption(c['descripcion'])
                    with st.form(f"edit_cat_{c['id']}"):
                        ec1, ec2 = st.columns([3, 1])
                        nombre = ec1.text_input("Nombre", value=c['nombre'])
                        emoji  = ec2.selectbox("Emoji", EMOJIS,
                                               index=EMOJIS.index(c['emoji']) if c['emoji'] in EMOJIS else 0)
                        desc = st.text_input("Descripción", value=c['descripcion'] or "")

                        sb1, _, sb3 = st.columns([1, 2, 1])
                        save   = sb1.form_submit_button("💾 Guardar", type="primary")
                        delete = sb3.form_submit_button("🗑️ Eliminar")

                        if save:
                            run("UPDATE categorias SET nombre=?, emoji=?, descripcion=? WHERE id=?",
                                (nombre, emoji, desc, c['id']))
                            st.success("Categoría actualizada")
                            st.rerun()

                        if delete:
                            if c['n_productos'] > 0:
                                st.error(f"No se puede eliminar: tiene {c['n_productos']} productos asociados")
                            else:
                                run("DELETE FROM categorias WHERE id=?", (c['id'],))
                                st.warning("Categoría eliminada")
                                st.rerun()

    with tab_new:
        st.markdown("#### ➕ Nueva Categoría")
        with st.form("new_cat"):
            nc1, nc2 = st.columns([3, 1])
            nombre = nc1.text_input("Nombre *")
            emoji  = nc2.selectbox("Emoji", EMOJIS)
            desc   = st.text_input("Descripción")

            if st.form_submit_button("💾 Crear Categoría", type="primary", use_container_width=True):
                if not nombre.strip():
                    st.error("El nombre es requerido")
                elif q("SELECT id FROM categorias WHERE nombre=?", (nombre.strip(),)):
                    st.error("Ya existe una categoría con ese nombre")
                else:
                    run("INSERT INTO categorias (nombre, emoji, descripcion) VALUES (?,?,?)",
                        (nombre.strip(), emoji, desc))
                    st.success(f"✅ Categoría **{nombre}** creada")
                    st.rerun()

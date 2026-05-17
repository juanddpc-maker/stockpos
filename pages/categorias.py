import streamlit as st
from database import q, run

EMOJIS = ["🗂️","🎒","⚽","👔","👟","🧢","📦","🔧","🌿","💊","🎵","🍎","🏠","⭐","💎"]

def render():
    st.header("🗂️ Categorías")
    tab_lista, tab_nueva = st.tabs(["📋 Categorías", "➕ Nueva Categoría"])

    with tab_nueva:
        st.subheader("Crear nueva categoría")
        with st.form("form_nueva_cat", clear_on_submit=True):
            c1,c2 = st.columns([3,1])
            nombre = c1.text_input("Nombre de la categoría *")
            emoji  = c2.selectbox("Ícono", EMOJIS)
            desc   = st.text_input("Descripción", placeholder="Descripción corta...")
            if st.form_submit_button("💾 Crear categoría", type="primary", use_container_width=True):
                if not nombre.strip():
                    st.error("El nombre es requerido")
                elif q("SELECT id FROM categorias WHERE nombre=?", (nombre.strip(),)):
                    st.error("Ya existe una categoría con ese nombre")
                else:
                    run("INSERT INTO categorias(nombre,emoji,descripcion) VALUES(?,?,?)",
                        (nombre.strip(), emoji, desc))
                    st.success(f"✅ Categoría **{nombre}** creada"); st.rerun()

    with tab_lista:
        cats = q("""
            SELECT c.*, COUNT(p.id) as n_prod
            FROM categorias c LEFT JOIN productos p ON p.categoria_id=c.id
            GROUP BY c.id ORDER BY c.nombre
        """)
        # Tarjetas de resumen
        cols = st.columns(min(len(cats), 5)) if cats else []
        for i, c in enumerate(cats):
            cols[i%5].metric(f"{c['emoji']} {c['nombre']}", f"{c['n_prod']} producto(s)")

        st.divider()
        for c in cats:
            with st.expander(f"{c['emoji']} **{c['nombre']}** · {c['n_prod']} producto(s)"):
                if c['descripcion']:
                    st.caption(c['descripcion'])
                with st.form(f"edit_cat_{c['id']}"):
                    ec1,ec2 = st.columns([3,1])
                    nombre  = ec1.text_input("Nombre", value=c['nombre'])
                    emoji   = ec2.selectbox("Ícono", EMOJIS,
                                           index=EMOJIS.index(c['emoji']) if c['emoji'] in EMOJIS else 0)
                    desc    = st.text_input("Descripción", value=c['descripcion'] or "")
                    cg,ce   = st.columns(2)
                    guardar  = cg.form_submit_button("💾 Guardar", type="primary", use_container_width=True)
                    eliminar = ce.form_submit_button("🗑️ Eliminar", use_container_width=True)
                    if guardar:
                        run("UPDATE categorias SET nombre=?,emoji=?,descripcion=? WHERE id=?",
                            (nombre, emoji, desc, c['id']))
                        st.success("Categoría actualizada"); st.rerun()
                    if eliminar:
                        if c['n_prod'] > 0:
                            st.error(f"No se puede eliminar: tiene {c['n_prod']} producto(s) asociado(s)")
                        else:
                            run("DELETE FROM categorias WHERE id=?", (c['id'],))
                            st.success("Categoría eliminada"); st.rerun()

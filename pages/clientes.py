import streamlit as st
import pandas as pd
from database import q, run

def render():
    st.markdown('<p class="sp-title">👥 <span class="sp-accent">Clientes</span></p>', unsafe_allow_html=True)
    st.markdown('<p class="sp-subtitle">Base de datos de clientes</p>', unsafe_allow_html=True)

    tab_list, tab_new = st.tabs(["📋 Clientes", "➕ Nuevo Cliente"])

    with tab_list:
        search = st.text_input("🔍 Buscar cliente", placeholder="Nombre, email o RFC...", label_visibility="collapsed")
        clientes = q("SELECT * FROM clientes ORDER BY nombre")
        if search:
            s = search.lower()
            clientes = [c for c in clientes if s in c['nombre'].lower() or (c['email'] and s in c['email'].lower()) or (c['rfc'] and s in c['rfc'].lower())]

        if not clientes:
            st.info("No hay clientes registrados")
        else:
            for c in clientes:
                ventas = q("SELECT COUNT(*) as n, COALESCE(SUM(total),0) as t FROM ventas WHERE cliente_id=? AND estado='Completada'", (c['id'],))
                n_ventas = ventas[0]['n']
                total_gastado = ventas[0]['t']

                with st.expander(f"👤 **{c['nombre']}** · {c['telefono'] or '-'} · {n_ventas} compras · ${total_gastado:,.2f}"):
                    cc1, cc2 = st.columns(2)
                    cc1.markdown(f"📧 **Email:** {c['email'] or '-'}")
                    cc2.markdown(f"📋 **RFC:** {c['rfc'] or '-'}")
                    st.markdown(f"📍 **Dirección:** {c['direccion'] or '-'}")
                    if c['notas']:
                        st.markdown(f"📝 **Notas:** {c['notas']}")

                    st.metric("Total gastado", f"${total_gastado:,.2f}", f"{n_ventas} transacciones")

                    st.markdown("---")
                    with st.form(f"edit_cl_{c['id']}"):
                        ec1, ec2 = st.columns(2)
                        nombre = ec1.text_input("Nombre", value=c['nombre'])
                        telefono = ec2.text_input("Teléfono", value=c['telefono'] or "")
                        ec3, ec4 = st.columns(2)
                        email = ec3.text_input("Email", value=c['email'] or "")
                        rfc = ec4.text_input("RFC", value=c['rfc'] or "")
                        direccion = st.text_input("Dirección", value=c['direccion'] or "")
                        notas = st.text_area("Notas", value=c['notas'] or "", height=60)

                        sb1, sb2, sb3 = st.columns(3)
                        save = sb1.form_submit_button("💾 Guardar", type="primary")
                        delete = sb3.form_submit_button("🗑️ Eliminar")

                        if save:
                            run("UPDATE clientes SET nombre=?, telefono=?, email=?, rfc=?, direccion=?, notas=? WHERE id=?",
                                (nombre, telefono, email, rfc, direccion, notas, c['id']))
                            st.success("Cliente actualizado")
                            st.rerun()
                        if delete:
                            run("DELETE FROM clientes WHERE id=?", (c['id'],))
                            st.warning("Cliente eliminado")
                            st.rerun()

    with tab_new:
        st.markdown("#### ➕ Nuevo Cliente")
        with st.form("new_cliente"):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre *")
            telefono = c2.text_input("Teléfono")
            c3, c4 = st.columns(2)
            email = c3.text_input("Email")
            rfc = c4.text_input("RFC")
            direccion = st.text_input("Dirección")
            notas = st.text_area("Notas", height=80)

            if st.form_submit_button("💾 Guardar Cliente", type="primary", use_container_width=True):
                if not nombre:
                    st.error("El nombre es requerido")
                else:
                    run("INSERT INTO clientes (nombre, telefono, email, rfc, direccion, notas) VALUES (?,?,?,?,?,?)",
                        (nombre, telefono, email, rfc, direccion, notas))
                    st.success(f"✅ Cliente **{nombre}** creado")
                    st.rerun()

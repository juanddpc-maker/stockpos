import streamlit as st
from database import q, run

def render():
    st.header("👥 Clientes")
    tab_lista, tab_nuevo = st.tabs(["📋 Clientes", "➕ Nuevo Cliente"])

    with tab_nuevo:
        st.subheader("Registrar nuevo cliente")
        with st.form("form_nuevo_cl", clear_on_submit=True):
            c1,c2 = st.columns(2)
            nombre   = c1.text_input("Nombre completo *")
            telefono = c2.text_input("Teléfono")
            c3,c4    = st.columns(2)
            email    = c3.text_input("Email")
            rfc      = c4.text_input("RFC")
            direccion= st.text_input("Dirección")
            notas    = st.text_area("Notas", height=80, placeholder="Escuela, empresa, condiciones especiales...")
            if st.form_submit_button("💾 Guardar cliente", type="primary", use_container_width=True):
                if not nombre.strip():
                    st.error("El nombre es requerido")
                else:
                    run("INSERT INTO clientes(nombre,telefono,email,rfc,direccion,notas) VALUES(?,?,?,?,?,?)",
                        (nombre.strip(),telefono,email,rfc,direccion,notas))
                    st.success(f"✅ Cliente **{nombre}** registrado")
                    st.rerun()

    with tab_lista:
        buscar = st.text_input("🔍 Buscar cliente", placeholder="Nombre, RFC o email...", label_visibility="collapsed")
        clientes = q("SELECT * FROM clientes ORDER BY nombre")
        if buscar:
            s = buscar.lower()
            clientes = [c for c in clientes if s in c['nombre'].lower()
                        or (c['rfc'] and s in c['rfc'].lower())
                        or (c['email'] and s in c['email'].lower())]

        st.caption(f"{len(clientes)} cliente(s)")

        for c in clientes:
            compras = q("SELECT COUNT(*) as n, COALESCE(SUM(total),0) as t FROM ventas WHERE cliente_id=? AND estado='Completada'", (c['id'],))
            n_c = compras[0]['n']; tot_c = float(compras[0]['t'])
            with st.expander(f"👤 **{c['nombre']}** · {c['telefono'] or '—'} · {n_c} compra(s) · ${tot_c:,.2f}"):
                ci1,ci2 = st.columns(2)
                ci1.markdown(f"📧 **Email:** {c['email'] or '—'}")
                ci2.markdown(f"🪪 **RFC:** {c['rfc'] or '—'}")
                st.markdown(f"📍 **Dirección:** {c['direccion'] or '—'}")
                if c['notas']:
                    st.info(f"📝 {c['notas']}")
                cm1,cm2,cm3 = st.columns(3)
                cm1.metric("Compras", n_c)
                cm2.metric("Total gastado", f"${tot_c:,.2f}")
                cm3.metric("Ticket promedio", f"${tot_c/n_c:,.2f}" if n_c else "$0")
                st.divider()
                with st.form(f"edit_cl_{c['id']}"):
                    ec1,ec2 = st.columns(2)
                    nombre   = ec1.text_input("Nombre", value=c['nombre'])
                    telefono = ec2.text_input("Teléfono", value=c['telefono'] or "")
                    ec3,ec4  = st.columns(2)
                    email    = ec3.text_input("Email", value=c['email'] or "")
                    rfc      = ec4.text_input("RFC", value=c['rfc'] or "")
                    direccion= st.text_input("Dirección", value=c['direccion'] or "")
                    notas    = st.text_area("Notas", value=c['notas'] or "", height=70)
                    cg,ce    = st.columns(2)
                    guardar  = cg.form_submit_button("💾 Guardar", type="primary", use_container_width=True)
                    eliminar = ce.form_submit_button("🗑️ Eliminar", use_container_width=True)
                    if guardar:
                        run("UPDATE clientes SET nombre=?,telefono=?,email=?,rfc=?,direccion=?,notas=? WHERE id=?",
                            (nombre,telefono,email,rfc,direccion,notas,c['id']))
                        st.success("Cliente actualizado"); st.rerun()
                    if eliminar:
                        run("UPDATE ventas SET cliente_id=NULL WHERE cliente_id=?", (c['id'],))
                        run("DELETE FROM clientes WHERE id=?", (c['id'],))
                        st.success("Cliente eliminado"); st.rerun()

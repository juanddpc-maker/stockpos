import streamlit as st
from datetime import datetime
from database import q, run, next_folio

IVA = 0.16

def render():
    st.header("🛒 Punto de Venta")
    st.caption("Selecciona productos → ajusta cantidades → procesa la venta")

    if 'cart' not in st.session_state:
        st.session_state.cart = {}
    if 'pos_cliente' not in st.session_state:
        st.session_state.pos_cliente = None
    if 'venta_ok' not in st.session_state:
        st.session_state.venta_ok = None

    # ── Venta exitosa ────────────────────────────────────────────────────────
    if st.session_state.venta_ok:
        folio, total = st.session_state.venta_ok
        st.success(f"✅ ¡Venta **{folio}** registrada exitosamente!  Total cobrado: **${total:,.2f}**")
        if st.button("🔄 Nueva venta", type="primary"):
            st.session_state.venta_ok = None
            st.rerun()
        return

    col_prod, col_cart = st.columns([3, 2])

    # ── Panel de productos ────────────────────────────────────────────────────
    with col_prod:
        st.subheader("Productos disponibles")
        cats = q("SELECT * FROM categorias ORDER BY nombre")
        cat_opts = ["Todas las categorías"] + [f"{c['emoji']} {c['nombre']}" for c in cats]
        cat_map  = {f"{c['emoji']} {c['nombre']}": c['id'] for c in cats}

        fcol1, fcol2 = st.columns([2,1])
        buscar  = fcol1.text_input("🔍 Buscar producto", placeholder="Escribe nombre...", label_visibility="collapsed")
        cat_sel = fcol2.selectbox("Categoría", cat_opts, label_visibility="collapsed")

        cat_id = cat_map.get(cat_sel)
        filtro_cat  = f"AND p.categoria_id={cat_id}" if cat_id else ""
        filtro_nom  = f"AND LOWER(p.nombre) LIKE '%{buscar.lower()}%'" if buscar else ""

        prods = q(f"""
            SELECT p.*, COALESCE((SELECT SUM(cantidad) FROM inventario WHERE producto_id=p.id),0) as stock
            FROM productos p WHERE 1=1 {filtro_cat} {filtro_nom} ORDER BY p.nombre
        """)

        if not prods:
            st.info("No se encontraron productos")
        else:
            # Tabla interactiva de productos
            for p in prods:
                stock = int(p['stock'])
                en_cart = st.session_state.cart.get(p['id'], {}).get('qty', 0)
                with st.container():
                    pc1, pc2, pc3, pc4 = st.columns([4, 2, 2, 2])
                    pc1.markdown(f"**{p['emoji']} {p['nombre']}**  \n"
                                 f"{'🟢 Stock: '+str(stock) if stock > p['min_stock'] else ('🟡 Stock bajo: '+str(stock) if stock > 0 else '🔴 Sin stock')}")
                    pc2.markdown(f"**${float(p['precio']):,.2f}**")
                    if en_cart:
                        pc3.markdown(f"🛒 **{en_cart} en carrito**")
                    else:
                        pc3.markdown("")

                    if stock > 0:
                        if pc4.button("➕ Agregar", key=f"add_{p['id']}", use_container_width=True):
                            cart = st.session_state.cart
                            if p['id'] in cart:
                                if cart[p['id']]['qty'] < stock:
                                    cart[p['id']]['qty'] += 1
                                else:
                                    st.toast("⚠️ No hay más stock disponible")
                            else:
                                cart[p['id']] = {
                                    'nombre': p['nombre'], 'emoji': p['emoji'],
                                    'precio': float(p['precio']), 'qty': 1, 'stock': stock
                                }
                            st.rerun()
                    else:
                        pc4.button("Sin stock", key=f"add_{p['id']}", disabled=True, use_container_width=True)
                st.divider()

    # ── Panel del carrito ─────────────────────────────────────────────────────
    with col_cart:
        st.subheader("🛒 Carrito de Venta")

        # Cliente
        clientes = q("SELECT id, nombre, telefono FROM clientes ORDER BY nombre")
        cl_opts  = {"— Público General —": None}
        cl_opts.update({f"{c['nombre']} ({c['telefono'] or 'sin tel.'})": c['id'] for c in clientes})
        cl_sel = st.selectbox("👤 Cliente", list(cl_opts.keys()))
        st.session_state.pos_cliente = cl_opts[cl_sel]

        st.divider()

        cart = st.session_state.cart
        if not cart:
            st.info("El carrito está vacío.\nAgrega productos desde el panel izquierdo.")
        else:
            subtotal = 0.0
            for pid, item in list(cart.items()):
                lc1, lc2, lc3, lc4 = st.columns([4, 1, 1, 1])
                lc1.markdown(f"**{item['emoji']} {item['nombre']}**  \n${item['precio']:,.2f} c/u")
                if lc2.button("−", key=f"dec_{pid}", use_container_width=True):
                    if cart[pid]['qty'] > 1: cart[pid]['qty'] -= 1
                    else: del cart[pid]
                    st.rerun()
                lc3.markdown(f"<div style='text-align:center;padding-top:8px;font-weight:700'>{item['qty']}</div>",
                             unsafe_allow_html=True)
                if lc4.button("＋", key=f"inc_{pid}", use_container_width=True):
                    if cart[pid]['qty'] < item['stock']: cart[pid]['qty'] += 1
                    else: st.toast("No hay más stock")
                    st.rerun()
                line = item['precio'] * item['qty']
                subtotal += line
                st.caption(f"Subtotal línea: ${line:,.2f}")
                st.divider()

            iva   = round(subtotal * IVA, 2)
            total = subtotal + iva

            st.markdown(f"""
| Concepto | Monto |
|---|---|
| Subtotal | ${subtotal:,.2f} |
| IVA (16%) | ${iva:,.2f} |
| **TOTAL** | **${total:,.2f}** |
""")

            metodo = st.selectbox("💳 Método de pago",
                                  ["Efectivo","Tarjeta de Débito","Tarjeta de Crédito","Transferencia","Cheque"])
            notas_venta = st.text_input("📝 Notas (opcional)", placeholder="Referencia, pedido, etc.")

            col_clear, col_sale = st.columns(2)
            if col_clear.button("🗑️ Limpiar carrito", use_container_width=True):
                st.session_state.cart = {}
                st.rerun()
            if col_sale.button("✅ Procesar venta", type="primary", use_container_width=True):
                _procesar(cart, subtotal, iva, total, metodo, st.session_state.pos_cliente, notas_venta)


def _procesar(cart, subtotal, iva, total, metodo, cliente_id, notas):
    folio = next_folio()
    vid = run(
        "INSERT INTO ventas(folio,fecha,cliente_id,subtotal,impuesto,total,metodo_pago,estado,notas)"
        " VALUES(?,?,?,?,?,?,?,'Completada',?)",
        (folio, datetime.now().isoformat(), cliente_id, subtotal, iva, total, metodo, notas)
    )
    for pid, item in cart.items():
        run("INSERT INTO venta_items(venta_id,producto_id,cantidad,precio_unitario,subtotal) VALUES(?,?,?,?,?)",
            (vid, pid, item['qty'], item['precio'], item['precio']*item['qty']))
        inv = q("SELECT id, cantidad FROM inventario WHERE producto_id=? LIMIT 1", (pid,))
        if inv:
            run("UPDATE inventario SET cantidad=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (max(0, inv[0]['cantidad']-item['qty']), inv[0]['id']))
    st.session_state.cart = {}
    st.session_state.pos_cliente = None
    st.session_state.venta_ok = (folio, total)
    st.rerun()

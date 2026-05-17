import streamlit as st
from datetime import datetime, timedelta
from database import q, run, next_folio, next_apartado_folio

IVA = 0.16

def render():
    st.header("🛒 Punto de Venta")

    tab_venta, tab_apartar = st.tabs(["💰 Nueva Venta", "💼 Nuevo Apartado"])

    with tab_venta:
        _panel_venta()
    with tab_apartar:
        _panel_apartar()


# ══════════════════════════ VENTA NORMAL ══════════════════════════════════════

def _panel_venta():
    if 'cart' not in st.session_state:
        st.session_state.cart = {}
    if 'venta_ok' not in st.session_state:
        st.session_state.venta_ok = None

    if st.session_state.venta_ok:
        folio, total = st.session_state.venta_ok
        st.success(f"✅ ¡Venta **{folio}** registrada! Total: **${total:,.2f}**")
        if st.button("🔄 Nueva venta", type="primary", key="btn_nueva_venta"):
            st.session_state.venta_ok = None
            st.rerun()
        return

    col_prod, col_cart = st.columns([3, 2])

    with col_prod:
        st.subheader("Productos")
        prods = _get_prods("v")
        _render_prods(prods, "v")

    with col_cart:
        st.subheader("🛒 Carrito")
        cliente_id = _selector_cliente("v")
        st.divider()
        cart = st.session_state.cart
        if not cart:
            st.info("Agrega productos desde el panel izquierdo.")
        else:
            subtotal = _render_cart(cart, "v")
            iva   = round(subtotal * IVA, 2)
            total = subtotal + iva
            _totales(subtotal, iva, total)
            metodo = st.selectbox("💳 Pago",
                                  ["Efectivo","Tarjeta de Débito","Tarjeta de Crédito","Transferencia","Cheque"],
                                  key="metodo_v")
            notas  = st.text_input("📝 Notas", placeholder="Referencia, pedido...", key="notas_v")
            c1, c2 = st.columns(2)
            if c1.button("🗑️ Limpiar", use_container_width=True, key="limpiar_v"):
                st.session_state.cart = {}
                st.rerun()
            if c2.button("✅ Procesar venta", type="primary", use_container_width=True, key="procesar_v"):
                _procesar_venta(cart, subtotal, iva, total, metodo, cliente_id, notas)


# ══════════════════════════ APARTADO ══════════════════════════════════════════

def _panel_apartar():
    if 'cart_a' not in st.session_state:
        st.session_state.cart_a = {}
    if 'apartado_ok' not in st.session_state:
        st.session_state.apartado_ok = None

    if st.session_state.apartado_ok:
        folio, total, saldo = st.session_state.apartado_ok
        st.success(f"💼 Apartado **{folio}** registrado — Total: **${total:,.2f}** · Saldo: **${saldo:,.2f}**")
        if st.button("🔄 Nuevo apartado", type="primary", key="btn_nuevo_apartado"):
            st.session_state.apartado_ok = None
            st.rerun()
        return

    col_prod, col_cart = st.columns([3, 2])

    with col_prod:
        st.subheader("Productos a apartar")
        prods = _get_prods("a")
        _render_prods(prods, "a")

    with col_cart:
        st.subheader("💼 Detalle del Apartado")
        cliente_id = _selector_cliente("a")
        st.divider()
        cart = st.session_state.cart_a
        if not cart:
            st.info("Agrega productos desde el panel izquierdo.")
        else:
            subtotal = _render_cart(cart, "a")
            iva   = round(subtotal * IVA, 2)
            total = subtotal + iva
            _totales(subtotal, iva, total)

            st.markdown("**Datos del apartado**")
            ac1, ac2 = st.columns(2)
            anticipo = ac1.number_input(
                "💵 Anticipo recibido *",
                min_value=0.0, max_value=float(total),
                step=10.0, format="%.2f", key="anticipo_a"
            )
            dias = ac2.number_input("📅 Días para liquidar", min_value=1, value=15, key="dias_a")
            fecha_limite = datetime.now() + timedelta(days=int(dias))
            ac2.caption(f"Vence: {fecha_limite.strftime('%d/%m/%Y')}")

            saldo = round(total - anticipo, 2)
            st.metric("Saldo pendiente", f"${saldo:,.2f}",
                      delta=f"-${anticipo:,.2f} anticipo", delta_color="normal")

            metodo = st.selectbox("💳 Pago del anticipo",
                                  ["Efectivo","Tarjeta de Débito","Tarjeta de Crédito","Transferencia"],
                                  key="metodo_a")
            notas  = st.text_input("📝 Notas", placeholder="Nombre, referencia...", key="notas_a")

            c1, c2 = st.columns(2)
            if c1.button("🗑️ Limpiar", use_container_width=True, key="limpiar_a"):
                st.session_state.cart_a = {}
                st.rerun()
            if c2.button("💼 Registrar Apartado", type="primary", use_container_width=True, key="registrar_a"):
                if not cliente_id:
                    st.error("⚠️ Selecciona un cliente para el apartado")
                elif anticipo <= 0:
                    st.error("⚠️ El anticipo debe ser mayor a $0")
                else:
                    _procesar_apartado(cart, subtotal, iva, total, anticipo,
                                       saldo, fecha_limite, metodo, cliente_id, notas)


# ══════════════════════════ HELPERS ═══════════════════════════════════════════

def _get_prods(modo):
    """modo='v' para venta, 'a' para apartado — keys únicas por modo."""
    cats    = q("SELECT * FROM categorias ORDER BY nombre")
    cat_opts= ["Todas las categorías"] + [f"{c['emoji']} {c['nombre']}" for c in cats]
    cat_map = {f"{c['emoji']} {c['nombre']}": c['id'] for c in cats}

    fc1, fc2 = st.columns([2, 1])
    buscar  = fc1.text_input("🔍 Buscar", placeholder="Nombre...",
                             label_visibility="collapsed", key=f"buscar_{modo}")
    cat_sel = fc2.selectbox("Cat.", cat_opts,
                            label_visibility="collapsed", key=f"cat_{modo}")
    cat_id  = cat_map.get(cat_sel)

    f_cat = f"AND p.categoria_id={cat_id}" if cat_id else ""
    f_nom = f"AND LOWER(p.nombre) LIKE '%{buscar.lower()}%'" if buscar else ""

    return q(f"""
        SELECT p.id, p.nombre, p.precio, p.emoji,
               COALESCE((SELECT SUM(cantidad) FROM inventario WHERE producto_id=p.id), 0) AS stock,
               COALESCE((SELECT MIN(min_stock) FROM inventario WHERE producto_id=p.id), 5) AS min_stock
        FROM productos p
        WHERE 1=1 {f_cat} {f_nom}
        ORDER BY p.nombre
    """)


def _render_prods(prods, modo):
    cart_key = 'cart' if modo == 'v' else 'cart_a'
    if not prods:
        st.info("No se encontraron productos")
        return
    for p in prods:
        stock  = int(p['stock'])
        min_s  = int(p['min_stock'])
        en_cart = st.session_state[cart_key].get(p['id'], {}).get('qty', 0)

        if stock == 0:       lbl = "🔴 Sin stock"
        elif stock <= min_s: lbl = f"🟡 Stock bajo: {stock}"
        else:                lbl = f"🟢 Stock: {stock}"

        pc1, pc2, pc3, pc4 = st.columns([4, 2, 2, 2])
        pc1.markdown(f"**{p['emoji']} {p['nombre']}**  \n{lbl}")
        pc2.markdown(f"**${float(p['precio']):,.2f}**")
        pc3.markdown(f"🛒 **{en_cart}**" if en_cart else "")

        if stock > 0:
            if pc4.button("➕ Agregar", key=f"add_{modo}_{p['id']}", use_container_width=True):
                cart = st.session_state[cart_key]
                if p['id'] in cart:
                    if cart[p['id']]['qty'] < stock:
                        cart[p['id']]['qty'] += 1
                    else:
                        st.toast("⚠️ Sin más stock disponible")
                else:
                    cart[p['id']] = {
                        'nombre': p['nombre'], 'emoji': p['emoji'],
                        'precio': float(p['precio']), 'qty': 1, 'stock': stock
                    }
                st.rerun()
        else:
            pc4.button("Agotado", key=f"add_{modo}_{p['id']}", disabled=True, use_container_width=True)
        st.divider()


def _render_cart(cart, modo):
    subtotal = 0.0
    for pid, item in list(cart.items()):
        c1, c2, c3, c4 = st.columns([4, 1, 1, 1])
        c1.markdown(f"**{item['emoji']} {item['nombre']}**  \n${item['precio']:,.2f} c/u")
        if c2.button("−", key=f"dec_{modo}_{pid}", use_container_width=True):
            if cart[pid]['qty'] > 1:
                cart[pid]['qty'] -= 1
            else:
                del cart[pid]
            st.rerun()
        c3.markdown(
            f"<div style='text-align:center;padding-top:8px;font-weight:700'>"
            f"{item['qty']}</div>",
            unsafe_allow_html=True
        )
        if c4.button("＋", key=f"inc_{modo}_{pid}", use_container_width=True):
            if cart[pid]['qty'] < item['stock']:
                cart[pid]['qty'] += 1
            else:
                st.toast("Sin más stock")
            st.rerun()
        line = item['precio'] * item['qty']
        subtotal += line
        st.caption(f"Subtotal: ${line:,.2f}")
        st.divider()
    return subtotal


def _totales(subtotal, iva, total):
    st.markdown(f"""
| Concepto | Monto |
|---|---|
| Subtotal | ${subtotal:,.2f} |
| IVA 16% | ${iva:,.2f} |
| **TOTAL** | **${total:,.2f}** |
""")


def _selector_cliente(modo):
    clientes = q("SELECT id, nombre, telefono FROM clientes ORDER BY nombre")
    opts = {"— Público General —": None}
    opts.update({f"{c['nombre']} ({c['telefono'] or 'sin tel.'})": c['id'] for c in clientes})
    sel = st.selectbox("👤 Cliente", list(opts.keys()), key=f"cliente_{modo}")
    return opts[sel]


def _procesar_venta(cart, subtotal, iva, total, metodo, cliente_id, notas):
    folio = next_folio()
    vid   = run(
        "INSERT INTO ventas(folio,fecha,cliente_id,subtotal,impuesto,total,metodo_pago,estado,notas)"
        " VALUES(?,?,?,?,?,?,?,'Completada',?)",
        (folio, datetime.now().isoformat(), cliente_id, subtotal, iva, total, metodo, notas)
    )
    for pid, item in cart.items():
        run("INSERT INTO venta_items(venta_id,producto_id,cantidad,precio_unitario,subtotal)"
            " VALUES(?,?,?,?,?)",
            (vid, pid, item['qty'], item['precio'], item['precio'] * item['qty']))
        inv = q("SELECT id,cantidad FROM inventario WHERE producto_id=? LIMIT 1", (pid,))
        if inv:
            run("UPDATE inventario SET cantidad=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (max(0, inv[0]['cantidad'] - item['qty']), inv[0]['id']))
    st.session_state.cart     = {}
    st.session_state.venta_ok = (folio, total)
    st.rerun()


def _procesar_apartado(cart, subtotal, iva, total, anticipo, saldo,
                        fecha_limite, metodo, cliente_id, notas):
    folio = next_apartado_folio()
    aid   = run(
        "INSERT INTO apartados(folio,fecha_apartado,fecha_limite,cliente_id,"
        "total_venta,anticipo,abonado,saldo,estado,notas)"
        " VALUES(?,?,?,?,?,?,?,?,'Apartado',?)",
        (folio, datetime.now().isoformat(), fecha_limite.isoformat(),
         cliente_id, total, anticipo, anticipo, saldo, notas)
    )
    for pid, item in cart.items():
        run("INSERT INTO apartado_items(apartado_id,producto_id,cantidad,precio_unitario,subtotal)"
            " VALUES(?,?,?,?,?)",
            (aid, pid, item['qty'], item['precio'], item['precio'] * item['qty']))
    run("INSERT INTO apartado_abonos(apartado_id,fecha,monto,metodo_pago,notas)"
        " VALUES(?,?,?,?,?)",
        (aid, datetime.now().isoformat(), anticipo, metodo, "Anticipo inicial"))
    st.session_state.cart_a      = {}
    st.session_state.apartado_ok = (folio, total, saldo)
    st.rerun()

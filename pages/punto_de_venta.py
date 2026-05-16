import streamlit as st
import pandas as pd
from datetime import datetime
from database import q, run, next_folio, get_config

IVA = 0.16

def render():
    st.markdown('<p class="sp-title">🛒 Punto de <span class="sp-accent">Venta</span></p>', unsafe_allow_html=True)
    st.markdown('<p class="sp-subtitle">Nueva venta · El inventario se actualiza automáticamente</p>', unsafe_allow_html=True)

    # ── Session cart ─────────────────────────────────────────────────────────
    if 'cart' not in st.session_state:
        st.session_state.cart = {}   # {prod_id: {nombre, emoji, precio, qty}}
    if 'pos_cliente_id' not in st.session_state:
        st.session_state.pos_cliente_id = None
    if 'sale_done' not in st.session_state:
        st.session_state.sale_done = None

    # ── Sale success banner ───────────────────────────────────────────────────
    if st.session_state.sale_done:
        folio, total = st.session_state.sale_done
        st.success(f"✅ ¡Venta **{folio}** procesada exitosamente! Total: **${total:,.2f}**")
        if st.button("🔄 Nueva Venta"):
            st.session_state.sale_done = None
            st.rerun()
        return

    col_products, col_cart = st.columns([2, 1])

    # ── Products panel ────────────────────────────────────────────────────────
    with col_products:
        st.markdown("### 🏷️ Productos")

        sf1, sf2 = st.columns([2, 1])
        search = sf1.text_input("🔍 Buscar", placeholder="Nombre del producto...", label_visibility="collapsed")
        cats = q("SELECT * FROM categorias ORDER BY nombre")
        cat_opts = {"Todas": None} | {f"{c['emoji']} {c['nombre']}": c['id'] for c in cats}
        cat_sel = sf2.selectbox("Categoría", list(cat_opts.keys()), label_visibility="collapsed")
        cat_id = cat_opts[cat_sel]

        prods = q("""
            SELECT p.*, c.nombre as cat_nombre,
                   COALESCE((SELECT SUM(cantidad) FROM inventario WHERE producto_id=p.id),0) as stock
            FROM productos p LEFT JOIN categorias c ON c.id=p.categoria_id
            WHERE (%s) AND (%s)
            ORDER BY p.nombre
        """ % (
            f"LOWER(p.nombre) LIKE '%{search.lower()}%'" if search else "1=1",
            f"p.categoria_id={cat_id}" if cat_id else "1=1"
        ))

        if not prods:
            st.info("Sin productos encontrados")
        else:
            # Render in 3 columns
            cols = st.columns(3)
            for i, p in enumerate(prods):
                with cols[i % 3]:
                    stock = p['stock']
                    disabled = stock == 0
                    in_cart = st.session_state.cart.get(p['id'], {}).get('qty', 0)
                    border_color = "#e94560" if in_cart else ("#2d3f5c" if not disabled else "#1a2744")
                    stock_color = "#e94560" if stock == 0 else ("#f5a623" if stock <= 5 else "#00c896")

                    st.markdown(f"""
                    <div style="background:#1a2744;border:2px solid {border_color};border-radius:10px;
                         padding:14px;margin-bottom:10px;opacity:{'0.5' if disabled else '1'}">
                        <div style="font-size:32px;text-align:center;margin-bottom:6px">{p['emoji']}</div>
                        <div style="font-weight:600;font-size:13px;margin-bottom:4px">{p['nombre']}</div>
                        <div style="color:#f5a623;font-weight:700;font-size:16px">${p['precio']:,.2f}</div>
                        <div style="font-size:11px;color:{stock_color};margin-top:2px">
                            {'Sin stock' if stock == 0 else f'Stock: {stock}'}</div>
                        {f'<div style="font-size:11px;color:#e94560;margin-top:2px">En carrito: {in_cart}</div>' if in_cart else ''}
                    </div>""", unsafe_allow_html=True)

                    if not disabled:
                        if st.button(f"➕ Agregar", key=f"add_{p['id']}", use_container_width=True):
                            cart = st.session_state.cart
                            if p['id'] in cart:
                                if cart[p['id']]['qty'] < stock:
                                    cart[p['id']]['qty'] += 1
                                else:
                                    st.warning("Stock insuficiente")
                            else:
                                cart[p['id']] = {
                                    'nombre': p['nombre'], 'emoji': p['emoji'],
                                    'precio': p['precio'], 'qty': 1
                                }
                            st.rerun()
                    else:
                        st.button("Sin Stock", key=f"add_{p['id']}", disabled=True, use_container_width=True)

    # ── Cart panel ────────────────────────────────────────────────────────────
    with col_cart:
        st.markdown("### 🛒 Carrito")

        # Customer select
        clientes = q("SELECT id, nombre, telefono FROM clientes ORDER BY nombre")
        cl_opts = {"— Público General —": None} | {f"{c['nombre']} · {c['telefono']}": c['id'] for c in clientes}
        cl_sel = st.selectbox("👤 Cliente", list(cl_opts.keys()))
        st.session_state.pos_cliente_id = cl_opts[cl_sel]

        st.markdown("---")

        cart = st.session_state.cart
        if not cart:
            st.markdown('<div style="text-align:center;padding:30px;color:#8892a4">🛍️ Carrito vacío<br>Agrega productos</div>', unsafe_allow_html=True)
        else:
            subtotal = 0
            for pid, item in list(cart.items()):
                with st.container():
                    r1, r2, r3 = st.columns([3, 2, 1])
                    r1.markdown(f"**{item['emoji']} {item['nombre']}**  \n${item['precio']:,.2f} c/u")

                    qty_col1, qty_col2, qty_col3 = r2.columns(3)
                    if qty_col1.button("−", key=f"dec_{pid}"):
                        if cart[pid]['qty'] > 1:
                            cart[pid]['qty'] -= 1
                        else:
                            del cart[pid]
                        st.rerun()
                    qty_col2.markdown(f"<div style='text-align:center;font-weight:700;padding-top:6px'>{item['qty']}</div>", unsafe_allow_html=True)
                    if qty_col3.button("＋", key=f"inc_{pid}"):
                        cart[pid]['qty'] += 1
                        st.rerun()

                    if r3.button("✕", key=f"rm_{pid}"):
                        del cart[pid]
                        st.rerun()

                    line = item['precio'] * item['qty']
                    subtotal += line
                    st.markdown(f"<div style='text-align:right;color:#f5a623;font-size:13px'>= ${line:,.2f}</div>", unsafe_allow_html=True)
                    st.markdown('<hr style="border-color:#2d3f5c;margin:6px 0">', unsafe_allow_html=True)

            iva = subtotal * IVA
            total = subtotal + iva

            st.markdown(f"""
            <div style="background:#1a2744;border-radius:10px;padding:14px;margin-top:8px">
                <div style="display:flex;justify-content:space-between;margin-bottom:6px;font-size:13px;color:#8892a4">
                    <span>Subtotal</span><span>${subtotal:,.2f}</span>
                </div>
                <div style="display:flex;justify-content:space-between;margin-bottom:8px;font-size:13px;color:#8892a4">
                    <span>IVA 16%</span><span>${iva:,.2f}</span>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:20px;font-weight:800;color:#f5a623;
                     border-top:1px solid #2d3f5c;padding-top:8px">
                    <span>TOTAL</span><span>${total:,.2f}</span>
                </div>
            </div>""", unsafe_allow_html=True)

            metodo = st.selectbox("💳 Método de Pago", ["Efectivo", "Tarjeta", "Transferencia", "Cheque"])

            bc1, bc2 = st.columns(2)
            if bc1.button("🗑️ Limpiar", use_container_width=True):
                st.session_state.cart = {}
                st.rerun()

            if bc2.button("✅ Procesar Venta", type="primary", use_container_width=True):
                _process_sale(cart, subtotal, iva, total, metodo, st.session_state.pos_cliente_id)


def _process_sale(cart, subtotal, iva, total, metodo, cliente_id):
    folio = next_folio()
    fecha = datetime.now().isoformat()

    venta_id = run(
        "INSERT INTO ventas (folio, fecha, cliente_id, subtotal, impuesto, total, metodo_pago, estado) VALUES (?,?,?,?,?,?,?,'Completada')",
        (folio, fecha, cliente_id, subtotal, iva, total, metodo)
    )

    for pid, item in cart.items():
        run(
            "INSERT INTO venta_items (venta_id, producto_id, cantidad, precio_unitario, subtotal) VALUES (?,?,?,?,?)",
            (venta_id, pid, item['qty'], item['precio'], item['precio'] * item['qty'])
        )
        # Deduct inventory
        inv_row = q("SELECT id, cantidad FROM inventario WHERE producto_id=? LIMIT 1", (pid,))
        if inv_row:
            nueva = max(0, inv_row[0]['cantidad'] - item['qty'])
            run("UPDATE inventario SET cantidad=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (nueva, inv_row[0]['id']))

    st.session_state.cart = {}
    st.session_state.pos_cliente_id = None
    st.session_state.sale_done = (folio, total)
    st.rerun()

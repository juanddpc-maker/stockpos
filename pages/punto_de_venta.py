import streamlit as st
from datetime import datetime, timedelta
from database import q, run, next_folio, next_apartado_folio, get_config, get_tallas_producto

def get_iva():
    return float(get_config("iva_pct","16")) / 100

def render():
    st.header("🛒 Punto de Venta")
    tab_venta, tab_apartar = st.tabs(["💰 Nueva Venta","💼 Nuevo Apartado"])
    with tab_venta:    _panel("v")
    with tab_apartar:  _panel("a")


def _panel(modo):
    cart_key  = "cart" if modo=="v" else "cart_a"
    done_key  = "venta_ok" if modo=="v" else "apartado_ok"

    if cart_key  not in st.session_state: st.session_state[cart_key]  = {}
    if done_key  not in st.session_state: st.session_state[done_key]  = None

    # ── Success banner ────────────────────────────────────────────────────────
    if st.session_state[done_key]:
        if modo == "v":
            folio, total = st.session_state[done_key]
            st.success(f"✅ Venta **{folio}** registrada · Total: **${total:,.2f}**")
        else:
            folio, total, saldo = st.session_state[done_key]
            st.success(f"💼 Apartado **{folio}** registrado · Total: **${total:,.2f}** · Saldo: **${saldo:,.2f}**")
        if st.button("🔄 Nuevo", type="primary", key=f"btn_nuevo_{modo}"):
            st.session_state[done_key] = None
            st.rerun()
        return

    col_prod, col_cart = st.columns([3,2])

    # ── Productos ─────────────────────────────────────────────────────────────
    with col_prod:
        st.subheader("Productos")
        cats    = q("SELECT * FROM categorias ORDER BY nombre")
        cat_opts= ["Todas"] + [f"{c['emoji']} {c['nombre']}" for c in cats]
        cat_map = {f"{c['emoji']} {c['nombre']}": c['id'] for c in cats}
        fc1, fc2 = st.columns([2,1])
        buscar   = fc1.text_input("🔍 Buscar", label_visibility="collapsed",
                                   placeholder="Nombre...", key=f"buscar_{modo}")
        cat_sel  = fc2.selectbox("Cat.", cat_opts, label_visibility="collapsed", key=f"cat_{modo}")
        cat_id   = cat_map.get(cat_sel)
        f_cat = f"AND p.categoria_id={cat_id}" if cat_id else ""
        f_nom = f"AND LOWER(p.nombre) LIKE '%{buscar.lower()}%'" if buscar else ""

        prods = q(f"""
            SELECT p.id, p.nombre, p.precio, p.emoji, p.tipo_talla,
                   COALESCE((SELECT SUM(cantidad) FROM inventario WHERE producto_id=p.id),0) AS stock_total
            FROM productos p WHERE 1=1 {f_cat} {f_nom} ORDER BY p.nombre
        """)

        if not prods:
            st.info("Sin productos")
        else:
            for p in prods:
                tallas      = get_tallas_producto(p['id'])
                tiene_tallas = len(tallas) > 1 or tallas[0] != "Única"
                stock_total  = int(p['stock_total'])

                pc1, pc2, pc3 = st.columns([5,2,2])
                pc1.markdown(f"**{p['emoji']} {p['nombre']}**  \n"
                             f"{'🟢' if stock_total>5 else '🟡' if stock_total>0 else '🔴'} "
                             f"Stock total: {stock_total}")
                pc2.markdown(f"**${float(p['precio']):,.2f}**")

                if stock_total > 0:
                    if tiene_tallas:
                        # Mostrar stock por talla
                        stocks = q("SELECT talla, SUM(cantidad) as cant FROM inventario WHERE producto_id=? GROUP BY talla",
                                   (p['id'],))
                        stock_map = {r['talla']: int(r['cant']) for r in stocks}
                        tallas_disp = [t for t in tallas if stock_map.get(t,0) > 0]
                        if tallas_disp:
                            talla_sel = pc3.selectbox("Talla", tallas_disp,
                                                      key=f"talla_{modo}_{p['id']}")
                            cant_talla = stock_map.get(talla_sel, 0)
                            pc3.caption(f"Stock: {cant_talla}")
                            if st.button(f"➕ Agregar {talla_sel}", key=f"add_{modo}_{p['id']}",
                                         use_container_width=True):
                                _add_cart(st.session_state[cart_key], p, talla_sel, cant_talla)
                        else:
                            pc3.button("Sin stock", disabled=True, key=f"add_{modo}_{p['id']}", use_container_width=True)
                    else:
                        inv = q("SELECT cantidad FROM inventario WHERE producto_id=? AND talla='Única' LIMIT 1",(p['id'],))
                        cant = int(inv[0]['cantidad']) if inv else 0
                        if pc3.button("➕ Agregar", key=f"add_{modo}_{p['id']}", use_container_width=True):
                            _add_cart(st.session_state[cart_key], p, "Única", cant)
                else:
                    pc3.button("Agotado", disabled=True, key=f"add_{modo}_{p['id']}", use_container_width=True)
                st.divider()

    # ── Carrito ───────────────────────────────────────────────────────────────
    with col_cart:
        title = "🛒 Carrito" if modo=="v" else "💼 Detalle Apartado"
        st.subheader(title)
        cliente_id = _selector_cliente(modo)
        st.divider()

        cart = st.session_state[cart_key]
        if not cart:
            st.info("Agrega productos desde la izquierda.")
        else:
            subtotal = 0.0
            for key, item in list(cart.items()):
                c1,c2,c3,c4 = st.columns([4,1,1,1])
                talla_label = f" · **{item['talla']}**" if item['talla'] != "Única" else ""
                c1.markdown(f"**{item['emoji']} {item['nombre']}**{talla_label}  \n"
                            f"${item['precio']:,.2f} c/u")
                if c2.button("−", key=f"dec_{modo}_{key}", use_container_width=True):
                    if cart[key]['qty']>1: cart[key]['qty']-=1
                    else: del cart[key]
                    st.rerun()
                c3.markdown(f"<div style='text-align:center;padding-top:8px;font-weight:700'>"
                            f"{item['qty']}</div>", unsafe_allow_html=True)
                if c4.button("＋", key=f"inc_{modo}_{key}", use_container_width=True):
                    if cart[key]['qty'] < item['stock']: cart[key]['qty']+=1
                    else: st.toast("Sin más stock en esta talla")
                    st.rerun()
                line = item['precio']*item['qty']; subtotal+=line
                st.caption(f"${line:,.2f}"); st.divider()

            iva_pct = int(get_config("iva_pct","16"))
            iva   = round(subtotal * get_iva(), 2)
            total = subtotal + iva
            st.markdown(f"""| Concepto | Monto |\n|---|---|\n| Subtotal | ${subtotal:,.2f} |\n| IVA {iva_pct}% | ${iva:,.2f} |\n| **TOTAL** | **${total:,.2f}** |""")

            if modo == "v":
                metodo = st.selectbox("💳 Pago",["Efectivo","Tarjeta de Débito","Tarjeta de Crédito","Transferencia","Cheque"], key="metodo_v")
                notas  = st.text_input("📝 Notas", key="notas_v")
                c1,c2  = st.columns(2)
                if c1.button("🗑️ Limpiar", use_container_width=True, key="limpiar_v"):
                    st.session_state[cart_key]={}; st.rerun()
                if c2.button("✅ Procesar venta", type="primary", use_container_width=True, key="procesar_v"):
                    _procesar_venta(cart, subtotal, iva, total, metodo, cliente_id, notas)
            else:
                ac1,ac2 = st.columns(2)
                anticipo = ac1.number_input("💵 Anticipo *", min_value=0.0, max_value=float(total),
                                            step=10.0, format="%.2f", key="anticipo_a")
                dias = ac2.number_input("📅 Días para liquidar", min_value=1, value=15, key="dias_a")
                fecha_limite = datetime.now() + timedelta(days=int(dias))
                ac2.caption(f"Vence: {fecha_limite.strftime('%d/%m/%Y')}")
                saldo_apt = round(total-anticipo, 2)
                st.metric("Saldo pendiente", f"${saldo_apt:,.2f}")
                metodo = st.selectbox("💳 Pago anticipo",["Efectivo","Tarjeta de Débito","Tarjeta de Crédito","Transferencia"], key="metodo_a")
                notas  = st.text_input("📝 Notas", key="notas_a")
                c1,c2  = st.columns(2)
                if c1.button("🗑️ Limpiar", use_container_width=True, key="limpiar_a"):
                    st.session_state[cart_key]={}; st.rerun()
                if c2.button("💼 Registrar Apartado", type="primary", use_container_width=True, key="registrar_a"):
                    if not cliente_id: st.error("⚠️ Selecciona un cliente")
                    elif anticipo<=0:  st.error("⚠️ El anticipo debe ser mayor a $0")
                    else: _procesar_apartado(cart, subtotal, iva, total, anticipo,
                                             saldo_apt, fecha_limite, metodo, cliente_id, notas)


def _add_cart(cart, p, talla, stock):
    key = f"{p['id']}_{talla}"
    if key in cart:
        if cart[key]['qty'] < stock: cart[key]['qty']+=1
        else: st.toast("⚠️ Sin más stock en esta talla")
    else:
        cart[key] = {'prod_id':p['id'], 'nombre':p['nombre'], 'emoji':p['emoji'],
                     'precio':float(p['precio']), 'talla':talla, 'qty':1, 'stock':stock}
    st.rerun()


def _selector_cliente(modo):
    clientes = q("SELECT id,nombre,telefono FROM clientes ORDER BY nombre")
    opts = {"— Público General —": None}
    opts.update({f"{c['nombre']} ({c['telefono'] or 'sin tel.'})": c['id'] for c in clientes})
    sel = st.selectbox("👤 Cliente", list(opts.keys()), key=f"cliente_{modo}")
    return opts[sel]


def _procesar_venta(cart, subtotal, iva, total, metodo, cliente_id, notas):
    folio = next_folio()
    vid   = run("INSERT INTO ventas(folio,fecha,cliente_id,subtotal,impuesto,total,metodo_pago,estado,notas)"
                " VALUES(?,?,?,?,?,?,?,'Completada',?)",
                (folio, datetime.now().isoformat(), cliente_id, subtotal, iva, total, metodo, notas))
    for key, item in cart.items():
        run("INSERT INTO venta_items(venta_id,producto_id,talla,cantidad,precio_unitario,subtotal)"
            " VALUES(?,?,?,?,?,?)",
            (vid, item['prod_id'], item['talla'], item['qty'], item['precio'], item['precio']*item['qty']))
        inv = q("SELECT id,cantidad FROM inventario WHERE producto_id=? AND talla=? LIMIT 1",
                (item['prod_id'], item['talla']))
        if inv:
            run("UPDATE inventario SET cantidad=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (max(0, inv[0]['cantidad']-item['qty']), inv[0]['id']))
    st.session_state.cart = {}
    st.session_state.venta_ok = (folio, total)
    st.rerun()


def _procesar_apartado(cart, subtotal, iva, total, anticipo, saldo, fecha_limite, metodo, cliente_id, notas):
    folio = next_apartado_folio()
    aid = run("INSERT INTO apartados(folio,fecha_apartado,fecha_limite,cliente_id,"
              "total_venta,anticipo,abonado,saldo,estado,notas)"
              " VALUES(?,?,?,?,?,?,?,?,'Apartado',?)",
              (folio, datetime.now().isoformat(), fecha_limite.isoformat(),
               cliente_id, total, anticipo, anticipo, saldo, notas))
    for key, item in cart.items():
        run("INSERT INTO apartado_items(apartado_id,producto_id,talla,cantidad,precio_unitario,subtotal)"
            " VALUES(?,?,?,?,?,?)",
            (aid, item['prod_id'], item['talla'], item['qty'], item['precio'], item['precio']*item['qty']))
    run("INSERT INTO apartado_abonos(apartado_id,fecha,monto,metodo_pago,notas) VALUES(?,?,?,?,?)",
        (aid, datetime.now().isoformat(), anticipo, metodo, "Anticipo inicial"))
    st.session_state.cart_a = {}
    st.session_state.apartado_ok = (folio, total, saldo)
    st.rerun()

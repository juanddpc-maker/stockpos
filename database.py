"""
database.py — Sistema de Uniformes
SQLite (local/dev) ↔ PostgreSQL (producción)
Detección automática por variable DATABASE_URL
"""
import os, sqlite3, random
from contextlib import contextmanager
from datetime import datetime, timedelta

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_PG = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")
_SQLITE = os.path.join(os.path.dirname(__file__), "data", "stockpos.db")


def _adapt(sql):
    if USE_PG:
        sql = sql.replace("?", "%s")
        sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        sql = sql.replace("INSERT OR IGNORE", "INSERT")
        sql = sql.replace("INSERT OR REPLACE", "INSERT")
    return sql


def _sqlite():
    os.makedirs(os.path.dirname(_SQLITE), exist_ok=True)
    c = sqlite3.connect(_SQLITE, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def _pg():
    import psycopg2, psycopg2.extras
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


@contextmanager
def _ctx():
    if USE_PG:
        conn = _pg()
        try:
            yield conn; conn.commit()
        except:
            conn.rollback(); raise
        finally:
            conn.close()
    else:
        conn = _sqlite()
        try:
            yield conn; conn.commit()
        finally:
            conn.close()


_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS categorias(
  id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE,
  emoji TEXT DEFAULT '🗂️', descripcion TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS productos(
  id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
  precio REAL NOT NULL, categoria_id INTEGER, emoji TEXT DEFAULT '📦',
  codigo_barras TEXT, descripcion TEXT, tipo_talla TEXT DEFAULT 'unico',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(categoria_id) REFERENCES categorias(id));
CREATE TABLE IF NOT EXISTS tallas_catalogo(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tipo TEXT NOT NULL,
  talla TEXT NOT NULL,
  orden INTEGER DEFAULT 0,
  UNIQUE(tipo, talla));
CREATE TABLE IF NOT EXISTS inventario(
  id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER NOT NULL,
  talla TEXT NOT NULL DEFAULT 'Única',
  localidad TEXT NOT NULL DEFAULT 'Tienda Principal', cantidad INTEGER NOT NULL DEFAULT 0,
  min_stock INTEGER DEFAULT 5, max_stock INTEGER DEFAULT 100,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(producto_id) REFERENCES productos(id),
  UNIQUE(producto_id, talla, localidad));
CREATE TABLE IF NOT EXISTS clientes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
  telefono TEXT, email TEXT, rfc TEXT, direccion TEXT, notas TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS ventas(
  id INTEGER PRIMARY KEY AUTOINCREMENT, folio TEXT NOT NULL UNIQUE,
  fecha TEXT NOT NULL, cliente_id INTEGER, subtotal REAL NOT NULL DEFAULT 0,
  impuesto REAL NOT NULL DEFAULT 0, total REAL NOT NULL DEFAULT 0,
  metodo_pago TEXT DEFAULT 'Efectivo', estado TEXT DEFAULT 'Completada',
  notas TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(cliente_id) REFERENCES clientes(id));
CREATE TABLE IF NOT EXISTS venta_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT, venta_id INTEGER NOT NULL,
  producto_id INTEGER NOT NULL, talla TEXT DEFAULT 'Única', cantidad INTEGER NOT NULL,
  precio_unitario REAL NOT NULL, subtotal REAL NOT NULL,
  FOREIGN KEY(venta_id) REFERENCES ventas(id),
  FOREIGN KEY(producto_id) REFERENCES productos(id));
CREATE TABLE IF NOT EXISTS apartados(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  folio TEXT NOT NULL UNIQUE,
  fecha_apartado TEXT NOT NULL,
  fecha_limite TEXT,
  cliente_id INTEGER,
  total_venta REAL NOT NULL DEFAULT 0,
  anticipo REAL NOT NULL DEFAULT 0,
  abonado REAL NOT NULL DEFAULT 0,
  saldo REAL NOT NULL DEFAULT 0,
  estado TEXT DEFAULT 'Apartado',
  notas TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(cliente_id) REFERENCES clientes(id));
CREATE TABLE IF NOT EXISTS apartado_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  apartado_id INTEGER NOT NULL,
  producto_id INTEGER NOT NULL,
  cantidad INTEGER NOT NULL,
  precio_unitario REAL NOT NULL,
  subtotal REAL NOT NULL,
  FOREIGN KEY(apartado_id) REFERENCES apartados(id),
  FOREIGN KEY(producto_id) REFERENCES productos(id));
CREATE TABLE IF NOT EXISTS apartado_abonos(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  apartado_id INTEGER NOT NULL,
  fecha TEXT NOT NULL,
  monto REAL NOT NULL,
  metodo_pago TEXT DEFAULT 'Efectivo',
  notas TEXT,
  FOREIGN KEY(apartado_id) REFERENCES apartados(id));
CREATE TABLE IF NOT EXISTS config(clave TEXT PRIMARY KEY, valor TEXT);
"""

_DDL_PG = """
CREATE TABLE IF NOT EXISTS categorias(
  id SERIAL PRIMARY KEY, nombre TEXT NOT NULL UNIQUE,
  emoji TEXT DEFAULT '🗂️', descripcion TEXT, created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS productos(
  id SERIAL PRIMARY KEY, nombre TEXT NOT NULL, precio NUMERIC(12,2) NOT NULL,
  categoria_id INTEGER REFERENCES categorias(id), emoji TEXT DEFAULT '📦',
  codigo_barras TEXT, descripcion TEXT, tipo_talla TEXT DEFAULT 'unico', created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS tallas_catalogo(
  id SERIAL PRIMARY KEY, tipo TEXT NOT NULL, talla TEXT NOT NULL, orden INTEGER DEFAULT 0,
  UNIQUE(tipo, talla));
CREATE TABLE IF NOT EXISTS inventario(
  id SERIAL PRIMARY KEY, producto_id INTEGER NOT NULL REFERENCES productos(id),
  talla TEXT NOT NULL DEFAULT 'Única',
  localidad TEXT NOT NULL DEFAULT 'Tienda Principal', cantidad INTEGER NOT NULL DEFAULT 0,
  min_stock INTEGER DEFAULT 5, max_stock INTEGER DEFAULT 100, updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(producto_id, talla, localidad));
CREATE TABLE IF NOT EXISTS clientes(
  id SERIAL PRIMARY KEY, nombre TEXT NOT NULL, telefono TEXT, email TEXT,
  rfc TEXT, direccion TEXT, notas TEXT, created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS ventas(
  id SERIAL PRIMARY KEY, folio TEXT NOT NULL UNIQUE, fecha TIMESTAMPTZ NOT NULL,
  cliente_id INTEGER REFERENCES clientes(id), subtotal NUMERIC(12,2) NOT NULL DEFAULT 0,
  impuesto NUMERIC(12,2) NOT NULL DEFAULT 0, total NUMERIC(12,2) NOT NULL DEFAULT 0,
  metodo_pago TEXT DEFAULT 'Efectivo', estado TEXT DEFAULT 'Completada',
  notas TEXT, created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS venta_items(
  id SERIAL PRIMARY KEY, venta_id INTEGER NOT NULL REFERENCES ventas(id),
  producto_id INTEGER NOT NULL REFERENCES productos(id), talla TEXT DEFAULT 'Única', cantidad INTEGER NOT NULL,
  precio_unitario NUMERIC(12,2) NOT NULL, subtotal NUMERIC(12,2) NOT NULL);
CREATE TABLE IF NOT EXISTS apartados(
  id SERIAL PRIMARY KEY, folio TEXT NOT NULL UNIQUE,
  fecha_apartado TIMESTAMPTZ NOT NULL, fecha_limite TIMESTAMPTZ,
  cliente_id INTEGER REFERENCES clientes(id),
  total_venta NUMERIC(12,2) NOT NULL DEFAULT 0,
  anticipo NUMERIC(12,2) NOT NULL DEFAULT 0,
  abonado NUMERIC(12,2) NOT NULL DEFAULT 0,
  saldo NUMERIC(12,2) NOT NULL DEFAULT 0,
  estado TEXT DEFAULT 'Apartado', notas TEXT, created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS apartado_items(
  id SERIAL PRIMARY KEY, apartado_id INTEGER NOT NULL REFERENCES apartados(id),
  producto_id INTEGER NOT NULL REFERENCES productos(id),
  talla TEXT DEFAULT 'Única', cantidad INTEGER NOT NULL, precio_unitario NUMERIC(12,2) NOT NULL, subtotal NUMERIC(12,2) NOT NULL);
CREATE TABLE IF NOT EXISTS apartado_abonos(
  id SERIAL PRIMARY KEY, apartado_id INTEGER NOT NULL REFERENCES apartados(id),
  fecha TIMESTAMPTZ NOT NULL, monto NUMERIC(12,2) NOT NULL,
  metodo_pago TEXT DEFAULT 'Efectivo', notas TEXT);
CREATE TABLE IF NOT EXISTS config(clave TEXT PRIMARY KEY, valor TEXT);
"""


def init_db():
    with _ctx() as conn:
        cur = conn.cursor()
        if USE_PG:
            for s in _DDL_PG.split(";"):
                s = s.strip()
                if s: cur.execute(s)
            cur.execute("SELECT COUNT(*) as n FROM categorias")
            n = cur.fetchone()['n']
        else:
            conn.executescript(_DDL_SQLITE)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM categorias")
            n = cur.fetchone()[0]
        # Migration: add talla columns to existing DBs
        migrate_add_talla()
        if n == 0:
            _seed(conn, cur)


TALLAS = {
    "ropa":        ["XS","S","M","L","XL","XXL"],
    "escolar_num": ["2","4","6","8","10","12","14","16"],
    "unico":       ["Única"],
}

# Tipo de talla por categoría (índice 1-based según seed)
# 1=Escolares→escolar_num, 2=Deportivos→ropa, 3=Empresariales→ropa, 4=Calzado→unico, 5=Accesorios→unico
CAT_TALLA = {1:"escolar_num", 2:"ropa", 3:"ropa", 4:"unico", 5:"unico"}


def get_tallas(tipo_talla):
    return TALLAS.get(tipo_talla, ["Única"])


def _seed(conn, cur):
    ph = "%s" if USE_PG else "?"

    def ins(sql, rows):
        cur.executemany(sql.replace("?", ph), rows)

    # Tallas catálogo
    tallas_rows = []
    for tipo, tallas in TALLAS.items():
        for orden, talla in enumerate(tallas):
            tallas_rows.append((tipo, talla, orden))
    ins("INSERT OR IGNORE INTO tallas_catalogo(tipo,talla,orden) VALUES(?,?,?)", tallas_rows)

    ins("INSERT INTO categorias(nombre,emoji,descripcion) VALUES(?,?,?)", [
        ('Uniformes Escolares',    '🎒', 'Uniformes para nivel básico y medio'),
        ('Uniformes Deportivos',   '🎽', 'Pants, shorts y playeras deportivas'),
        ('Uniformes Empresariales','👔', 'Camisas, chalecos y pantalones de trabajo'),
        ('Calzado',                '👟', 'Zapatos y tenis escolares/deportivos'),
        ('Accesorios',             '🧢', 'Corbatas, cinturones, gorras y más'),
    ])
    ins("INSERT INTO productos(nombre,precio,categoria_id,emoji,tipo_talla) VALUES(?,?,?,?,?)", [
        ('Camisa Escolar Blanca',    185, 1, '👕', 'escolar_num'),
        ('Pantalón Escolar Azul',    220, 1, '👖', 'escolar_num'),
        ('Falda Escolar Cuadros',    195, 1, '👗', 'escolar_num'),
        ('Sudadera Escolar',         280, 1, '🧥', 'escolar_num'),
        ('Playera Polo Escolar',     165, 1, '👚', 'escolar_num'),
        ('Pants Deportivo Completo', 350, 2, '🩱', 'ropa'),
        ('Playera Deportiva',        150, 2, '🎽', 'ropa'),
        ('Short Deportivo',          120, 2, '🩲', 'ropa'),
        ('Camisa Empresarial',       320, 3, '👔', 'ropa'),
        ('Chaleco Empresarial',      280, 3, '🦺', 'ropa'),
        ('Pantalón de Trabajo',      350, 3, '👖', 'ropa'),
        ('Zapato Escolar Negro',     480, 4, '👞', 'unico'),
        ('Tenis Deportivo Blanco',   520, 4, '👟', 'unico'),
        ('Corbata Escolar',           85, 5, '👔', 'unico'),
        ('Cinturón Negro',           110, 5, '🪢', 'unico'),
        ('Gorra con Logo',           145, 5, '🧢', 'unico'),
        ('Calcetines Escolares',      45, 5, '🧦', 'unico'),
    ])
    # Inventario con tallas: (prod_id, tipo_talla, localidad, cant_por_talla, min, max)
    prod_inv = [
        (1,'escolar_num','Tienda Principal',8,2,20),
        (2,'escolar_num','Tienda Principal',6,2,15),
        (3,'escolar_num','Tienda Principal',5,2,15),
        (4,'escolar_num','Almacén',5,2,15),
        (5,'escolar_num','Tienda Principal',4,2,12),
        (6,'ropa','Almacén',3,1,10),
        (7,'ropa','Tienda Principal',8,2,20),
        (8,'ropa','Tienda Principal',7,2,18),
        (9,'ropa','Almacén',4,1,12),
        (10,'ropa','Almacén',3,1,8),
        (11,'ropa','Almacén',4,1,10),
        (12,'unico','Tienda Principal',4,5,30),
        (13,'unico','Tienda Principal',8,5,30),
        (14,'unico','Tienda Principal',35,5,60),
        (15,'unico','Almacén',25,5,50),
        (16,'unico','Almacén',3,2,20),
        (17,'unico','Tienda Principal',50,10,80),
    ]
    inv_rows = []
    for pid, tipo, loc, cant, mn, mx in prod_inv:
        for talla in TALLAS.get(tipo, ["Única"]):
            inv_rows.append((pid, talla, loc, cant, mn, mx))
    ins("INSERT INTO inventario(producto_id,talla,localidad,cantidad,min_stock,max_stock) VALUES(?,?,?,?,?,?)", inv_rows)
    ins("INSERT INTO clientes(nombre,telefono,email,rfc,direccion,notas) VALUES(?,?,?,?,?,?)", [
        ('Escuela Primaria Benito Juárez','664-100-0001','compras@juarez.edu.mx','ESB900101AA1','Av. Principal 100, TJ','Pedido anual en agosto'),
        ('Secundaria Lázaro Cárdenas',   '664-100-0002','admin@lazaro.edu.mx',  'SLC850615BB2','Blvd. Centro 200, TJ', 'Cliente frecuente'),
        ('Empresa Logística MX',         '664-100-0003','rh@logisticamx.com',   'ELM920320CC3','Zona Industrial 45, TJ','Uniformes ejecutivos'),
        ('Deportivo Municipal',          '664-100-0004','contacto@deportivo.mx','DMP880712DD4','Parque Central s/n, TJ','Equipos de fútbol'),
        ('Prepa Técnica No. 5',          '664-100-0005','prepa5@edu.mx',        'PTN950815EE5','Col. Libertad 78, TJ', ''),
    ])
    cfg = [('app_nombre','UniControl'),('app_subtitulo','Sistema de Uniformes'),
           ('empresa_nombre','Mi Empresa de Uniformes'),('empresa_rfc',''),
           ('empresa_direccion',''),('empresa_telefono',''),('empresa_email',''),
           ('iva_pct','16'),('moneda','MXN'),('groq_api_key',''),
           ('apartado_dias_alerta','7')]
    if USE_PG:
        for k,v in cfg:
            cur.execute("INSERT INTO config VALUES(%s,%s) ON CONFLICT DO NOTHING",(k,v))
    else:
        for k,v in cfg:
            cur.execute("INSERT OR IGNORE INTO config VALUES(?,?)",(k,v))

    precios = [185,220,195,280,165,350,150,120,320,280,350,480,520,85,110,145,45]
    now = datetime.now()
    for i in range(15):
        fecha  = now - timedelta(days=random.randint(0,13), hours=random.randint(0,8))
        folio  = f"V-{1001+i}"
        cli_id = random.randint(1,5)
        metodo = random.choice(['Efectivo','Tarjeta','Transferencia'])
        fv = fecha if USE_PG else fecha.isoformat()
        if USE_PG:
            cur.execute("INSERT INTO ventas(folio,fecha,cliente_id,subtotal,impuesto,total,metodo_pago,estado)"
                        " VALUES(%s,%s,%s,0,0,0,%s,'Completada') RETURNING id",(folio,fv,cli_id,metodo))
            vid = cur.fetchone()['id']
        else:
            cur.execute("INSERT INTO ventas(folio,fecha,cliente_id,subtotal,impuesto,total,metodo_pago,estado)"
                        " VALUES(?,?,?,0,0,0,?,'Completada')",(folio,fv,cli_id,metodo))
            vid = cur.lastrowid
        sub = 0
        for _ in range(random.randint(1,4)):
            pid=random.randint(1,17); qty=random.randint(1,6)
            p=precios[pid-1]; line=p*qty; sub+=line
            cur.execute(("INSERT INTO venta_items(venta_id,producto_id,cantidad,precio_unitario,subtotal)"
                         " VALUES(%s,%s,%s,%s,%s)" if USE_PG else
                         "INSERT INTO venta_items(venta_id,producto_id,cantidad,precio_unitario,subtotal)"
                         " VALUES(?,?,?,?,?)"),(vid,pid,qty,p,line))
        imp=round(sub*0.16,2)
        cur.execute(("UPDATE ventas SET subtotal=%s,impuesto=%s,total=%s WHERE id=%s" if USE_PG else
                     "UPDATE ventas SET subtotal=?,impuesto=?,total=? WHERE id=?"),(sub,imp,sub+imp,vid))


# ── Public API ────────────────────────────────────────────────────────────────

def get_tallas_producto(producto_id):
    """Retorna lista de tallas disponibles para un producto según su tipo_talla."""
    p = q("SELECT tipo_talla FROM productos WHERE id=?", (producto_id,))
    if not p: return ["Única"]
    return TALLAS.get(p[0].get("tipo_talla","unico"), ["Única"])


def migrate_add_talla():
    """Migración segura: agrega columna talla si no existe (para BDs existentes)."""
    try:
        with _ctx() as conn:
            cur = conn.cursor()
            if USE_PG:
                cur.execute("ALTER TABLE inventario ADD COLUMN IF NOT EXISTS talla TEXT DEFAULT 'Única'")
                cur.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS tipo_talla TEXT DEFAULT 'unico'")
                cur.execute("ALTER TABLE venta_items ADD COLUMN IF NOT EXISTS talla TEXT DEFAULT 'Única'")
                cur.execute("ALTER TABLE apartado_items ADD COLUMN IF NOT EXISTS talla TEXT DEFAULT 'Única'")
                cur.execute("CREATE TABLE IF NOT EXISTS tallas_catalogo(id SERIAL PRIMARY KEY, tipo TEXT NOT NULL, talla TEXT NOT NULL, orden INTEGER DEFAULT 0, UNIQUE(tipo,talla))")
            else:
                for ddl in [
                    "ALTER TABLE inventario ADD COLUMN talla TEXT DEFAULT 'Única'",
                    "ALTER TABLE productos ADD COLUMN tipo_talla TEXT DEFAULT 'unico'",
                    "ALTER TABLE venta_items ADD COLUMN talla TEXT DEFAULT 'Única'",
                    "ALTER TABLE apartado_items ADD COLUMN talla TEXT DEFAULT 'Única'",
                ]:
                    try: cur.execute(ddl)
                    except: pass
                cur.execute("CREATE TABLE IF NOT EXISTS tallas_catalogo(id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, talla TEXT NOT NULL, orden INTEGER DEFAULT 0, UNIQUE(tipo,talla))")
            # Seed tallas
            ph = "%s" if USE_PG else "?"
            for tipo, tallas in TALLAS.items():
                for orden, talla in enumerate(tallas):
                    try:
                        cur.execute(f"INSERT OR IGNORE INTO tallas_catalogo(tipo,talla,orden) VALUES({ph},{ph},{ph})", (tipo,talla,orden))
                    except: pass
    except Exception as e:
        pass  # ya existían las columnas

def q(sql, params=()):
    with _ctx() as conn:
        cur = conn.cursor()
        cur.execute(_adapt(sql), params)
        return [dict(r) for r in cur.fetchall()]


def run(sql, params=()):
    adapted = _adapt(sql)
    with _ctx() as conn:
        cur = conn.cursor()
        if USE_PG and adapted.strip().upper().startswith("INSERT"):
            cur.execute(adapted + " RETURNING id", params)
            row = cur.fetchone()
            return row['id'] if row else None
        cur.execute(adapted, params)
        return getattr(cur, 'lastrowid', None)


def raw_query(sql):
    try:
        with _ctx() as conn:
            cur = conn.cursor()
            cur.execute(_adapt(sql))
            if cur.description:
                cols = [d[0] for d in cur.description]
                rows = [list(r.values()) if isinstance(r,dict) else list(r) for r in cur.fetchall()]
                return cols, rows, None
            return [], [], None
    except Exception as e:
        return [], [], str(e)


def raw_exec(sql):
    try:
        with _ctx() as conn:
            cur = conn.cursor()
            cur.execute(_adapt(sql))
            return getattr(cur, 'rowcount', 0), None
    except Exception as e:
        return 0, str(e)


def get_config(k, default=""):
    r = q("SELECT valor FROM config WHERE clave=?", (k,))
    return r[0]['valor'] if r else default


def set_config(k, v):
    if USE_PG:
        with _ctx() as conn:
            conn.cursor().execute(
                "INSERT INTO config(clave,valor) VALUES(%s,%s) ON CONFLICT(clave) DO UPDATE SET valor=EXCLUDED.valor",
                (k,v))
    else:
        run("INSERT OR REPLACE INTO config(clave,valor) VALUES(?,?)",(k,v))


def next_folio(prefix="V"):
    r = q(f"SELECT folio FROM ventas WHERE folio LIKE '{prefix}-%' ORDER BY id DESC LIMIT 1")
    if not r: return f"{prefix}-1001"
    try: return f"{prefix}-{int(r[0]['folio'].split('-')[1])+1}"
    except: return f"{prefix}-1001"


def next_apartado_folio():
    r = q("SELECT folio FROM apartados ORDER BY id DESC LIMIT 1")
    if not r: return "A-1001"
    try: return f"A-{int(r[0]['folio'].split('-')[1])+1}"
    except: return "A-1001"


def engine_info():
    return {"motor":"PostgreSQL" if USE_PG else "SQLite",
            "url": DATABASE_URL if USE_PG else _SQLITE,
            "icono":"🐘" if USE_PG else "🗃️",
            "prod": USE_PG}

"""
database.py  —  StockPOS
Soporte dual: SQLite (local/dev) y PostgreSQL (producción)

Detección automática:
  - Si existe la variable de entorno DATABASE_URL  → PostgreSQL
  - Si no existe                                   → SQLite  (data/stockpos.db)

Para producción agrega en tu .env:
  DATABASE_URL=postgresql://user:password@host:5432/stockpos
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
import random

# ── Detección de motor ────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES  = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")

# Ruta SQLite (solo modo local)
_SQLITE_PATH = os.path.join(os.path.dirname(__file__), "data", "stockpos.db")


# ── Adaptadores ───────────────────────────────────────────────────────────────
def _adapt(sql: str) -> str:
    """Convierte sintaxis SQLite → PostgreSQL cuando sea necesario."""
    if USE_POSTGRES:
        sql = sql.replace("?", "%s")
        sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        sql = sql.replace("INSERT OR IGNORE", "INSERT")
        sql = sql.replace("INSERT OR REPLACE", "INSERT")
    return sql


# ── Conexiones ────────────────────────────────────────────────────────────────
def _get_sqlite_conn():
    os.makedirs(os.path.dirname(_SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(_SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _get_pg_conn():
    import psycopg2
    import psycopg2.extras
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


@contextmanager
def _conn_ctx():
    if USE_POSTGRES:
        conn = _get_pg_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = _get_sqlite_conn()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


# ── DDL por motor ─────────────────────────────────────────────────────────────
_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS categorias (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL UNIQUE,
    emoji       TEXT DEFAULT '🗂️',
    descripcion TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS productos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre        TEXT NOT NULL,
    precio        REAL NOT NULL,
    categoria_id  INTEGER,
    emoji         TEXT DEFAULT '📦',
    codigo_barras TEXT,
    descripcion   TEXT,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (categoria_id) REFERENCES categorias(id)
);
CREATE TABLE IF NOT EXISTS inventario (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_id INTEGER NOT NULL,
    localidad   TEXT NOT NULL DEFAULT 'Almacén Central',
    cantidad    INTEGER NOT NULL DEFAULT 0,
    min_stock   INTEGER DEFAULT 5,
    max_stock   INTEGER DEFAULT 100,
    updated_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (producto_id) REFERENCES productos(id)
);
CREATE TABLE IF NOT EXISTS clientes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre     TEXT NOT NULL,
    telefono   TEXT,
    email      TEXT,
    rfc        TEXT,
    direccion  TEXT,
    notas      TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ventas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    folio       TEXT NOT NULL UNIQUE,
    fecha       TEXT NOT NULL,
    cliente_id  INTEGER,
    subtotal    REAL NOT NULL DEFAULT 0,
    impuesto    REAL NOT NULL DEFAULT 0,
    total       REAL NOT NULL DEFAULT 0,
    metodo_pago TEXT DEFAULT 'Efectivo',
    estado      TEXT DEFAULT 'Completada',
    notas       TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);
CREATE TABLE IF NOT EXISTS venta_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id        INTEGER NOT NULL,
    producto_id     INTEGER NOT NULL,
    cantidad        INTEGER NOT NULL,
    precio_unitario REAL NOT NULL,
    subtotal        REAL NOT NULL,
    FOREIGN KEY (venta_id)    REFERENCES ventas(id),
    FOREIGN KEY (producto_id) REFERENCES productos(id)
);
CREATE TABLE IF NOT EXISTS config (
    clave TEXT PRIMARY KEY,
    valor TEXT
);
"""

_DDL_POSTGRES = """
CREATE TABLE IF NOT EXISTS categorias (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT NOT NULL UNIQUE,
    emoji       TEXT DEFAULT '🗂️',
    descripcion TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS productos (
    id            SERIAL PRIMARY KEY,
    nombre        TEXT NOT NULL,
    precio        NUMERIC(12,2) NOT NULL,
    categoria_id  INTEGER REFERENCES categorias(id),
    emoji         TEXT DEFAULT '📦',
    codigo_barras TEXT,
    descripcion   TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS inventario (
    id          SERIAL PRIMARY KEY,
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    localidad   TEXT NOT NULL DEFAULT 'Almacén Central',
    cantidad    INTEGER NOT NULL DEFAULT 0,
    min_stock   INTEGER DEFAULT 5,
    max_stock   INTEGER DEFAULT 100,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS clientes (
    id         SERIAL PRIMARY KEY,
    nombre     TEXT NOT NULL,
    telefono   TEXT,
    email      TEXT,
    rfc        TEXT,
    direccion  TEXT,
    notas      TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS ventas (
    id          SERIAL PRIMARY KEY,
    folio       TEXT NOT NULL UNIQUE,
    fecha       TIMESTAMPTZ NOT NULL,
    cliente_id  INTEGER REFERENCES clientes(id),
    subtotal    NUMERIC(12,2) NOT NULL DEFAULT 0,
    impuesto    NUMERIC(12,2) NOT NULL DEFAULT 0,
    total       NUMERIC(12,2) NOT NULL DEFAULT 0,
    metodo_pago TEXT DEFAULT 'Efectivo',
    estado      TEXT DEFAULT 'Completada',
    notas       TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS venta_items (
    id              SERIAL PRIMARY KEY,
    venta_id        INTEGER NOT NULL REFERENCES ventas(id),
    producto_id     INTEGER NOT NULL REFERENCES productos(id),
    cantidad        INTEGER NOT NULL,
    precio_unitario NUMERIC(12,2) NOT NULL,
    subtotal        NUMERIC(12,2) NOT NULL
);
CREATE TABLE IF NOT EXISTS config (
    clave TEXT PRIMARY KEY,
    valor TEXT
);
"""


# ── init_db ───────────────────────────────────────────────────────────────────
def init_db():
    """Crea tablas y datos de muestra si la base está vacía."""
    with _conn_ctx() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            for stmt in _DDL_POSTGRES.split(";"):
                s = stmt.strip()
                if s:
                    cur.execute(s)
            cur.execute("SELECT COUNT(*) as n FROM categorias")
            row = cur.fetchone()
            n = row['n']
        else:
            conn.executescript(_DDL_SQLITE)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM categorias")
            n = cur.fetchone()[0]

        if n == 0:
            _seed_data(conn, cur)


def _seed_data(conn, cur):
    ph = "%s" if USE_POSTGRES else "?"

    def ins(sql, rows):
        cur.executemany(sql.replace("?", ph), rows)

    ins("INSERT INTO categorias (nombre, emoji, descripcion) VALUES (?,?,?)", [
        ('Electrónicos', '💻', 'Gadgets y tecnología'),
        ('Ropa',         '👕', 'Prendas y accesorios'),
        ('Alimentos',    '🍎', 'Comida y bebidas'),
        ('Hogar',        '🏠', 'Artículos para el hogar'),
        ('Herramientas', '🔧', 'Ferretería y herramientas'),
    ])
    ins("INSERT INTO productos (nombre, precio, categoria_id, emoji) VALUES (?,?,?,?)", [
        ('Laptop Pro 15"',    18999, 1, '💻'), ('Mouse Inalámbrico',  299, 1, '🖱️'),
        ('Teclado Mecánico',    899, 1, '⌨️'), ('Audífonos Bluetooth',799, 1, '🎧'),
        ('Monitor 24"',        4500, 1, '🖥️'), ('Playera Básica',     199, 2, '👕'),
        ('Pantalón Slim',       499, 2, '👖'), ('Chamarra Denim',      850, 2, '🧥'),
        ('Agua Mineral 1.5L',    25, 3, '💧'), ('Café Gourmet 500g',  120, 3, '☕'),
        ('Snack Mix',            45, 3, '🍿'), ('Lámpara LED',        350, 4, '💡'),
        ('Silla Ergonómica',   3500, 4, '🪑'), ('Desarmador Set',     180, 5, '🔧'),
        ('Cinta Métrica',        75, 5, '📏'),
    ])
    ins("INSERT INTO inventario (producto_id, localidad, cantidad, min_stock, max_stock) VALUES (?,?,?,?,?)", [
        (1,'Almacén Central',15,5,50),(2,'Almacén Central',48,10,100),(3,'Almacén Central',22,8,60),
        (4,'Tienda Principal',7,10,50),(5,'Almacén Central',3,5,20),(6,'Tienda Principal',3,10,80),
        (7,'Tienda Principal',20,5,50),(8,'Tienda Principal',12,5,40),(9,'Almacén Central',0,50,200),
        (10,'Tienda Principal',35,20,100),(11,'Tienda Principal',60,30,150),(12,'Almacén Central',18,5,40),
        (13,'Almacén Central',4,3,20),(14,'Almacén Central',25,10,60),(15,'Almacén Central',40,15,80),
    ])
    ins("INSERT INTO clientes (nombre, telefono, email, rfc, direccion, notas) VALUES (?,?,?,?,?,?)", [
        ('María García','664-555-0101','maria@email.com','GARM900101A1','Av. Revolución 123, TJ',''),
        ('Juan Pérez','664-555-0202','juan@email.com','PEJJ850615B2','Blvd. Agua Caliente 45, TJ',''),
        ('Ana Torres','664-555-0303','ana@email.com','TOAA920320C3','Calle 5 de Mayo 78, TJ',''),
        ('Carlos López','664-555-0404','carlos@email.com','LOCL880712D4','Zona Río, TJ','Cliente frecuente'),
        ('Sofía Martínez','664-555-0505','sofia@email.com','MASS950815E5','Mesa de Otay, TJ',''),
    ])

    precios = [18999,299,899,799,4500,199,499,850,25,120,45,350,3500,180,75]
    now = datetime.now()
    for i in range(12):
        fecha  = now - timedelta(days=random.randint(0,6), hours=random.randint(0,8))
        folio  = f"V-{1001+i}"
        cli_id = random.randint(1,5)
        metodo = random.choice(['Efectivo','Tarjeta','Transferencia'])
        fecha_val = fecha if USE_POSTGRES else fecha.isoformat()
        ins_v = f"INSERT INTO ventas (folio,fecha,cliente_id,subtotal,impuesto,total,metodo_pago,estado) VALUES ({','.join([ph]*8)})"
        if USE_POSTGRES:
            cur.execute(ins_v + " RETURNING id", (folio, fecha_val, cli_id, 0, 0, 0, metodo, 'Completada'))
            venta_id = cur.fetchone()['id']
        else:
            cur.execute(ins_v, (folio, fecha_val, cli_id, 0, 0, 0, metodo, 'Completada'))
            venta_id = cur.lastrowid

        subtotal = 0
        for _ in range(random.randint(1,3)):
            pid = random.randint(1,15); qty = random.randint(1,4)
            price = precios[pid-1]; line = price*qty; subtotal += line
            cur.execute(f"INSERT INTO venta_items (venta_id,producto_id,cantidad,precio_unitario,subtotal) VALUES ({','.join([ph]*5)})",
                        (venta_id,pid,qty,price,line))
        imp = round(subtotal*0.16,2)
        cur.execute(f"UPDATE ventas SET subtotal={ph},impuesto={ph},total={ph} WHERE id={ph}",
                    (subtotal, imp, subtotal+imp, venta_id))

    cfg_vals = [('empresa_nombre','Mi Empresa'),('groq_api_key',''),('iva_pct','16')]
    if USE_POSTGRES:
        for k,v in cfg_vals:
            cur.execute("INSERT INTO config VALUES (%s,%s) ON CONFLICT DO NOTHING",(k,v))
    else:
        for k,v in cfg_vals:
            cur.execute("INSERT OR IGNORE INTO config VALUES (?,?)",(k,v))


# ── CRUD públicos ─────────────────────────────────────────────────────────────

def q(sql: str, params: tuple = ()):
    """SELECT → lista de dicts."""
    with _conn_ctx() as conn:
        cur = conn.cursor()
        cur.execute(_adapt(sql), params)
        return [dict(r) for r in cur.fetchall()]


def run(sql: str, params: tuple = ()):
    """INSERT/UPDATE/DELETE → lastrowid."""
    adapted = _adapt(sql)
    with _conn_ctx() as conn:
        cur = conn.cursor()
        if USE_POSTGRES and adapted.strip().upper().startswith("INSERT"):
            cur.execute(adapted + " RETURNING id", params)
            row = cur.fetchone()
            return row['id'] if row else None
        cur.execute(adapted, params)
        return getattr(cur, 'lastrowid', None)


def run_many(sql: str, rows: list):
    adapted = _adapt(sql)
    with _conn_ctx() as conn:
        conn.cursor().executemany(adapted, rows)


def raw_query(sql: str):
    """Ejecuta SQL libre → (columnas, filas, error_str|None)."""
    try:
        adapted = _adapt(sql)
        with _conn_ctx() as conn:
            cur = conn.cursor()
            cur.execute(adapted)
            if cur.description:
                cols = [d[0] for d in cur.description]
                rows = [list(r.values()) if isinstance(r, dict) else list(r) for r in cur.fetchall()]
                return cols, rows, None
            return [], [], None
    except Exception as e:
        return [], [], str(e)


# ── Config ────────────────────────────────────────────────────────────────────

def get_config(clave: str, default: str = "") -> str:
    rows = q("SELECT valor FROM config WHERE clave=?", (clave,))
    return rows[0]['valor'] if rows else default


def set_config(clave: str, valor: str):
    if USE_POSTGRES:
        with _conn_ctx() as conn:
            conn.cursor().execute(
                "INSERT INTO config (clave,valor) VALUES (%s,%s) ON CONFLICT (clave) DO UPDATE SET valor=EXCLUDED.valor",
                (clave, valor)
            )
    else:
        run("INSERT OR REPLACE INTO config (clave,valor) VALUES (?,?)", (clave, valor))


def next_folio() -> str:
    row = q("SELECT folio FROM ventas ORDER BY id DESC LIMIT 1")
    if not row:
        return "V-1001"
    try:
        return f"V-{int(row[0]['folio'].split('-')[1])+1}"
    except Exception:
        return "V-1001"


def engine_info() -> dict:
    return {
        "motor": "PostgreSQL" if USE_POSTGRES else "SQLite",
        "url":   DATABASE_URL if USE_POSTGRES else _SQLITE_PATH,
        "icono": "🐘" if USE_POSTGRES else "🗃️",
    }

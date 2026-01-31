-- Tabla de sesiones por cliente
CREATE TABLE IF NOT EXISTS sessions (
  phone TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  data TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Tabla de órdenes (opcional / futura)
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  phone TEXT,
  items_json TEXT,
  delivery_method TEXT,
  address TEXT,
  name TEXT,
  payment_method TEXT,
  proof_ok INTEGER,
  total INTEGER,
  created_at TEXT
);


import sqlite3
import os
from datetime import datetime, timedelta

DB_NAME = "inair_reportes.db"

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with tables"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                nombre TEXT NOT NULL,
                prefijo TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'technician',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Clients table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                contacto TEXT,
                telefono TEXT,
                email TEXT,
                direccion TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Client Equipment table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS client_equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                tipo_equipo TEXT NOT NULL,
                modelo TEXT,
                serie TEXT,
                marca TEXT,
                potencia TEXT,
                ultimo_servicio DATE,
                frecuencia_meses INTEGER DEFAULT 1,
                proximo_servicio DATE,
                kit_2000 TEXT,
                kit_4000 TEXT,
                kit_6000 TEXT,
                kit_8000 TEXT,
                kit_16000 TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
            )
        ''')
        
        # Reports table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folio TEXT UNIQUE NOT NULL,
                fecha DATE NOT NULL,
                cliente TEXT NOT NULL,
                tipo_equipo TEXT NOT NULL,
                modelo TEXT,
                serie TEXT,
                marca TEXT,
                potencia TEXT,
                tipo_servicio TEXT NOT NULL,
                descripcion_servicio TEXT,
                tecnico TEXT NOT NULL,
                localidad TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Folios table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS folios (
                prefijo TEXT PRIMARY KEY,
                ultimo_numero INTEGER DEFAULT 0
            )
        ''')
        
        # Draft reports table - stores complete drafts with images and signatures
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS draft_reports (
                folio TEXT PRIMARY KEY,
                form_data TEXT NOT NULL,
                foto1_data TEXT,
                foto2_data TEXT,
                foto3_data TEXT,
                foto4_data TEXT,
                firma_tecnico_data TEXT,
                firma_cliente_data TEXT,
                pdf_preview BLOB,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Check if new columns exist (for migration)
        try:
            cursor.execute("SELECT ultimo_servicio FROM client_equipment LIMIT 1")
        except sqlite3.OperationalError:
            # Columns don't exist, add them
            alter_commands = [
                "ALTER TABLE client_equipment ADD COLUMN ultimo_servicio DATE",
                "ALTER TABLE client_equipment ADD COLUMN frecuencia_meses INTEGER DEFAULT 1",
                "ALTER TABLE client_equipment ADD COLUMN proximo_servicio DATE",
                "ALTER TABLE client_equipment ADD COLUMN kit_2000 TEXT",
                "ALTER TABLE client_equipment ADD COLUMN kit_4000 TEXT",
                "ALTER TABLE client_equipment ADD COLUMN kit_6000 TEXT",
                "ALTER TABLE client_equipment ADD COLUMN kit_8000 TEXT",
                "ALTER TABLE client_equipment ADD COLUMN kit_16000 TEXT"
            ]
            for cmd in alter_commands:
                try:
                    cursor.execute(cmd)
                except sqlite3.OperationalError:
                    pass 

        conn.commit()
        
        # Create default users if none exist
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        if user_count == 0:
            print("No users found. Creating default users...")
            
            # Create default admin
            cursor.execute('''
                INSERT INTO users (username, password, role, nombre, prefijo)
                VALUES (?, ?, ?, ?, ?)
            ''', ('admin', 'admin123', 'admin', 'Administrador', 'ADM'))
            
            # Create default technicians
            default_techs = [
                ('fernando', 'fernando123', 'technician', 'Fernando', 'F'),
                ('cesar', 'cesar123', 'technician', 'César', 'C'),
                ('hiorvard', 'hiorvard123', 'technician', 'Hiorvard', 'H')
            ]
            
            for username, password, role, nombre, prefijo in default_techs:
                cursor.execute('''
                    INSERT INTO users (username, password, role, nombre, prefijo)
                    VALUES (?, ?, ?, ?, ?)
                ''', (username, password, role, nombre, prefijo))
            
            conn.commit()
            print("Default users created:")
            print("  - admin / admin123 (Administrator)")
            print("  - fernando / fernando123 (Technician)")
            print("  - cesar / cesar123 (Technician)")
            print("  - hiorvard / hiorvard123 (Technician)")

# ========== User Functions ==========

def get_all_users():
    """Get all users"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY role, username")
        return [dict(row) for row in cursor.fetchall()]

def get_user_by_username(username):
    """Get user by username"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None

def create_user(username, password, nombre, prefijo, role='technician'):
    """Create a new user"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, password, nombre, prefijo, role)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, password, nombre, prefijo, role))
            return True
    except sqlite3.IntegrityError:
        return False

def delete_user(user_id):
    """Delete a user by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return cursor.rowcount > 0

# ========== Client Functions ==========

def get_all_clients():
    """Get all clients from database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clients ORDER BY nombre")
        return [dict(row) for row in cursor.fetchall()]

def get_client_by_id(client_id):
    """Get client by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def create_client(nombre, contacto='', telefono='', email='', direccion=''):
    """Create a new client"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO clients (nombre, contacto, telefono, email, direccion)
            VALUES (?, ?, ?, ?, ?)
        ''', (nombre, contacto, telefono, email, direccion))
        return cursor.lastrowid

def update_client(client_id, nombre, contacto='', telefono='', email='', direccion=''):
    """Update client information"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE clients
            SET nombre = ?, contacto = ?, telefono = ?, email = ?, direccion = ?
            WHERE id = ?
        ''', (nombre, contacto, telefono, email, direccion, client_id))
        return cursor.rowcount > 0

def delete_client(client_id):
    """Delete a client by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        return cursor.rowcount > 0

# ========== Report Functions ==========

def save_report(folio, fecha, cliente, tipo_equipo, modelo, serie, marca, potencia,
                tipo_servicio, descripcion_servicio, tecnico, localidad):
    """Save report metadata to database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO reports 
            (folio, fecha, cliente, tipo_equipo, modelo, serie, marca, potencia,
             tipo_servicio, descripcion_servicio, tecnico, localidad)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (folio, fecha, cliente, tipo_equipo, modelo, serie, marca, potencia,
              tipo_servicio, descripcion_servicio, tecnico, localidad))
        return cursor.lastrowid

def get_all_reports():
    """Get all reports from database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reports ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

def get_report_by_folio(folio):
    """Get report by folio"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reports WHERE folio = ?", (folio,))
        row = cursor.fetchone()
        return dict(row) if row else None

def search_reports(search_term='', tipo_servicio='', fecha_inicio='', fecha_fin=''):
    """Search reports with filters"""
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM reports WHERE 1=1"
        params = []
        
        if search_term:
            query += " AND (folio LIKE ? OR cliente LIKE ? OR tecnico LIKE ?)"
            search_pattern = f"%{search_term}%"
            params.extend([search_pattern, search_pattern, search_pattern])
        
        if tipo_servicio:
            query += " AND tipo_servicio = ?"
            params.append(tipo_servicio)
        
        if fecha_inicio:
            query += " AND fecha >= ?"
            params.append(fecha_inicio)
        
        if fecha_fin:
            query += " AND fecha <= ?"
            params.append(fecha_fin)
        
        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

# ========== Folio Functions ==========

def get_next_folio(prefijo):
    """Get next folio number for a prefix"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO folios (prefijo, ultimo_numero)
            VALUES (?, 0)
        ''', (prefijo,))
        
        cursor.execute('''
            UPDATE folios
            SET ultimo_numero = ultimo_numero + 1
            WHERE prefijo = ?
        ''', (prefijo,))
        
        cursor.execute("SELECT ultimo_numero FROM folios WHERE prefijo = ?", (prefijo,))
        row = cursor.fetchone()
        numero = row['ultimo_numero'] if row else 1
        
        return f"{prefijo}-{numero:04d}"

# ========== Statistics Functions ==========

def get_dashboard_stats():
    """Get statistics for admin dashboard"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM clients")
        total_clients = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM reports")
        total_reports = cursor.fetchone()['count']
        
        # Count equipment instead of plans
        cursor.execute("SELECT COUNT(*) as count FROM client_equipment")
        active_plans = cursor.fetchone()['count']
        
        return {
            'total_clients': total_clients,
            'total_users': total_users,
            'total_reports': total_reports,
            'active_plans': active_plans
        }

# ========== Client Equipment Functions ==========

def add_client_equipment(client_id, tipo_equipo, modelo='', serie='', marca='', potencia='', 
                        ultimo_servicio=None, frecuencia_meses=1, proximo_servicio=None,
                        kit_2000=None, kit_4000=None, kit_6000=None, kit_8000=None, kit_16000=None):
    """Add equipment to a client with maintenance info"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO client_equipment 
            (client_id, tipo_equipo, modelo, serie, marca, potencia, 
             ultimo_servicio, frecuencia_meses, proximo_servicio,
             kit_2000, kit_4000, kit_6000, kit_8000, kit_16000)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, tipo_equipo, modelo, serie, marca, potencia,
              ultimo_servicio, frecuencia_meses, proximo_servicio,
              kit_2000, kit_4000, kit_6000, kit_8000, kit_16000))
        return cursor.lastrowid

def get_client_equipment(client_id):
    """Get all equipment for a client"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM client_equipment
            WHERE client_id = ?
            ORDER BY tipo_equipo, modelo
        ''', (client_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_equipment_by_id(equipment_id):
    """Get specific equipment by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM client_equipment
            WHERE id = ?
        ''', (equipment_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_client_equipment(equipment_id, tipo_equipo, modelo='', serie='', marca='', potencia='',
                           ultimo_servicio=None, frecuencia_meses=1, proximo_servicio=None,
                           kit_2000=None, kit_4000=None, kit_6000=None, kit_8000=None, kit_16000=None):
    """Update equipment information"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE client_equipment
            SET tipo_equipo = ?, modelo = ?, serie = ?, marca = ?, potencia = ?,
                ultimo_servicio = ?, frecuencia_meses = ?, proximo_servicio = ?,
                kit_2000 = ?, kit_4000 = ?, kit_6000 = ?, kit_8000 = ?, kit_16000 = ?
            WHERE id = ?
        ''', (tipo_equipo, modelo, serie, marca, potencia, 
              ultimo_servicio, frecuencia_meses, proximo_servicio,
              kit_2000, kit_4000, kit_6000, kit_8000, kit_16000,
              equipment_id))
        return cursor.rowcount > 0

def delete_client_equipment(equipment_id):
    """Delete equipment by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM client_equipment WHERE id = ?", (equipment_id,))
        return cursor.rowcount > 0

def get_equipment_types_by_client(client_id):
    """Get unique equipment types for a client"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT tipo_equipo
            FROM client_equipment
            WHERE client_id = ?
            ORDER BY tipo_equipo
        ''', (client_id,))
        return [row['tipo_equipo'] for row in cursor.fetchall()]

def get_models_by_client_and_type(client_id, tipo_equipo):
    """Get equipment models for a specific client and equipment type"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, modelo, serie, marca, potencia
            FROM client_equipment
            WHERE client_id = ? AND tipo_equipo = ?
            ORDER BY modelo
        ''', (client_id, tipo_equipo))
        return [dict(row) for row in cursor.fetchall()]

# ========== Draft Report Functions ==========

def save_draft_report(folio, form_data, foto1=None, foto2=None, foto3=None, foto4=None,
                      firma_tecnico=None, firma_cliente=None, pdf_preview=None):
    """Save or update draft report with all data including images as Base64"""
    import json
    from datetime import datetime
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if draft exists
        cursor.execute("SELECT folio FROM draft_reports WHERE folio = ?", (folio,))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing draft
            cursor.execute('''
                UPDATE draft_reports
                SET form_data = ?,
                    foto1_data = ?,
                    foto2_data = ?,
                    foto3_data = ?,
                    foto4_data = ?,
                    firma_tecnico_data = ?,
                    firma_cliente_data = ?,
                    pdf_preview = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE folio = ?
            ''', (json.dumps(form_data) if isinstance(form_data, dict) else form_data,
                  foto1, foto2, foto3, foto4,
                  firma_tecnico, firma_cliente,
                  pdf_preview, folio))
        else:
            # Insert new draft
            cursor.execute('''
                INSERT INTO draft_reports
                (folio, form_data, foto1_data, foto2_data, foto3_data, foto4_data,
                 firma_tecnico_data, firma_cliente_data, pdf_preview, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')
            ''', (folio,
                  json.dumps(form_data) if isinstance(form_data, dict) else form_data,
                  foto1, foto2, foto3, foto4,
                  firma_tecnico, firma_cliente,
                  pdf_preview))
        
        return True

def get_draft_by_folio(folio):
    """Get complete draft report by folio"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM draft_reports WHERE folio = ?", (folio,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_all_drafts(status=None):
    """Get all draft reports, optionally filtered by status"""
    with get_db() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute('''
                SELECT * FROM draft_reports 
                WHERE status = ?
                ORDER BY updated_at DESC
            ''', (status,))
        else:
            cursor.execute("SELECT * FROM draft_reports ORDER BY updated_at DESC")
        return [dict(row) for row in cursor.fetchall()]

def delete_draft(folio):
    """Delete a draft report by folio"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM draft_reports WHERE folio = ?", (folio,))
        return cursor.rowcount > 0

def mark_draft_as_sent(folio):
    """Mark a draft report as sent"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE draft_reports
            SET status = 'sent', updated_at = CURRENT_TIMESTAMP
            WHERE folio = ?
        ''', (folio,))
        return cursor.rowcount > 0

def update_draft_pdf(folio, pdf_data):
    """Update only the PDF preview for a draft"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE draft_reports
            SET pdf_preview = ?, updated_at = CURRENT_TIMESTAMP
            WHERE folio = ?
        ''', (pdf_data, folio))
        return cursor.rowcount > 0

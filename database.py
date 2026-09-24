import sqlite3
import pandas as pd
from datetime import datetime
import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = "purchase_ledger.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parties (
            party_id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_name TEXT UNIQUE NOT NULL,
            contact_info TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT UNIQUE NOT NULL,
            category TEXT,
            current_rate REAL NOT NULL,
            updated_at TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_bills (
            bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_id INTEGER,
            invoice_number TEXT UNIQUE NOT NULL,
            date TEXT NOT NULL,
            total_amount REAL NOT NULL,
            FOREIGN KEY (party_id) REFERENCES parties(party_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bill_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER,
            item_id INTEGER,
            quantity REAL NOT NULL,
            purchase_rate REAL NOT NULL,
            previous_rate REAL,
            FOREIGN KEY (bill_id) REFERENCES purchase_bills(bill_id),
            FOREIGN KEY (item_id) REFERENCES items(item_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS party_ledgers (
            ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_id INTEGER,
            date TEXT NOT NULL,
            reference_no TEXT,
            debit REAL DEFAULT 0.0,
            credit REAL DEFAULT 0.0,
            running_balance REAL DEFAULT 0.0,
            FOREIGN KEY (party_id) REFERENCES parties(party_id)
        )
    ''')
    
    conn.commit()
    conn.close()

def seed_sample_data():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM parties")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO parties (party_name) VALUES ('ABC Steel Corp')")
        party_id = cursor.lastrowid
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("INSERT INTO items (item_name, category, current_rate, updated_at) VALUES ('TMT Bar 12mm', 'Raw Material', 550.0, ?)", (today,))
        
        # Seed a dummy ledger entry so tables aren't completely empty
        cursor.execute(
            "INSERT INTO party_ledgers (party_id, date, reference_no, debit, credit, running_balance) VALUES (?, ?, ?, ?, ?, ?)",
            (party_id, today, "INIT-001", 1000.0, 0.0, 1000.0)
        )
        conn.commit()
    conn.close()

def process_new_bill(party_name, invoice_no, bill_date, items_list, total_amount):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT party_id FROM parties WHERE party_name = ?", (party_name,))
        row = cursor.fetchone()
        if row:
            party_id = row['party_id']
        else:
            cursor.execute("INSERT INTO parties (party_name) VALUES (?)", (party_name,))
            party_id = cursor.lastrowid
            
        cursor.execute(
            "INSERT INTO purchase_bills (party_id, invoice_number, date, total_amount) VALUES (?, ?, ?, ?)",
            (party_id, invoice_no, bill_date, total_amount)
        )
        bill_id = cursor.lastrowid
        
        for item in items_list:
            item_name = item['item_name']
            new_rate = item['rate']
            quantity = item['quantity']
            category = item.get('category', 'General')
            
            cursor.execute("SELECT item_id, current_rate FROM items WHERE item_name = ?", (item_name,))
            item_row = cursor.fetchone()
            
            if item_row:
                item_id = item_row['item_id']
                previous_rate = item_row['current_rate']
                cursor.execute("UPDATE items SET current_rate = ?, updated_at = ? WHERE item_id = ?", (new_rate, bill_date, item_id))
            else:
                previous_rate = new_rate
                cursor.execute("INSERT INTO items (item_name, category, current_rate, updated_at) VALUES (?, ?, ?, ?)", (item_name, category, new_rate, bill_date))
                item_id = cursor.lastrowid
                
            cursor.execute(
                "INSERT INTO bill_items (bill_id, item_id, quantity, purchase_rate, previous_rate) VALUES (?, ?, ?, ?, ?)",
                (bill_id, item_id, quantity, new_rate, previous_rate)
            )
            
        cursor.execute("SELECT running_balance FROM party_ledgers WHERE party_id = ? ORDER BY ledger_id DESC LIMIT 1", (party_id,))
        last_ledger = cursor.fetchone()
        last_balance = last_ledger['running_balance'] if last_ledger else 0.0
        new_balance = last_balance + total_amount
        
        cursor.execute(
            "INSERT INTO party_ledgers (party_id, date, reference_no, debit, credit, running_balance) VALUES (?, ?, ?, ?, ?, ?)",
            (party_id, bill_date, invoice_no, total_amount, 0.0, new_balance)
        )
        conn.commit()
        return True, "Success"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def fetch_ledger_statement(party_name=None):
    conn = get_connection()
    query = """
        SELECT l.date, p.party_name, l.reference_no, l.debit, l.credit, l.running_balance
        FROM party_ledgers l
        JOIN parties p ON l.party_id = p.party_id
    """
    if party_name:
        query += " WHERE p.party_name = ?"
        df = pd.read_sql_query(query, conn, params=(party_name,))
    else:
        df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def fetch_item_price_tracker():
    conn = get_connection()
    query = """
        SELECT i.item_name, i.category, bi.previous_rate as 'Old Rate (₹)', i.current_rate as 'New Rate (₹)', i.updated_at as 'Last Purchased'
        FROM items i
        LEFT JOIN bill_items bi ON i.item_id = bi.item_id
        GROUP BY i.item_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

init_db()
seed_sample_data()

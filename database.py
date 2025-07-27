import sqlite3
from datetime import datetime, timedelta
import json

def init_db():
    """Initialize the database with required tables."""
    conn = sqlite3.connect('ups_history.db')
    c = conn.cursor()
    
    # Create table for raw UPS readings
    c.execute('''
        CREATE TABLE IF NOT EXISTS ups_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            data JSON NOT NULL
        )
    ''')
    
    # Create index on timestamp for faster queries
    c.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON ups_readings(timestamp)')
    
    conn.commit()
    conn.close()

def store_reading(data):
    """Store a UPS reading in the database."""
    conn = sqlite3.connect('ups_history.db')
    c = conn.cursor()
    
    c.execute(
        'INSERT INTO ups_readings (timestamp, data) VALUES (?, ?)',
        (datetime.now().isoformat(), json.dumps(data))
    )
    
    conn.commit()
    conn.close()

def get_readings(hours=24):
    """Get readings from the last N hours."""
    conn = sqlite3.connect('ups_history.db')
    c = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    c.execute(
        'SELECT timestamp, data FROM ups_readings WHERE timestamp > ? ORDER BY timestamp',
        (cutoff,)
    )
    
    readings = [
        {
            'timestamp': row[0],
            'data': json.loads(row[1])
        }
        for row in c.fetchall()
    ]
    
    conn.close()
    return readings

def cleanup_old_readings(days=7):
    """Remove readings older than N days."""
    conn = sqlite3.connect('ups_history.db')
    c = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    
    c.execute('DELETE FROM ups_readings WHERE timestamp < ?', (cutoff,))
    
    conn.commit()
    conn.close()

def get_power_events(days=7):
    """Get power events (transfers to battery) from the last N days."""
    conn = sqlite3.connect('ups_history.db')
    c = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    
    # Get readings where NUMXFERS changed or STATUS contains "ONBATT"
    c.execute('''
        WITH numbered_rows AS (
            SELECT 
                timestamp,
                data,
                LAG(json_extract(data, '$.NUMXFERS')) OVER (ORDER BY timestamp) as prev_transfers,
                json_extract(data, '$.NUMXFERS') as curr_transfers,
                json_extract(data, '$.STATUS') as status
            FROM ups_readings 
            WHERE timestamp > ?
        )
        SELECT timestamp, data
        FROM numbered_rows
        WHERE (curr_transfers != prev_transfers AND prev_transfers IS NOT NULL)
           OR status LIKE '%ONBATT%'
        ORDER BY timestamp
    ''', (cutoff,))
    
    events = [
        {
            'timestamp': row[0],
            'data': json.loads(row[1])
        }
        for row in c.fetchall()
    ]
    
    conn.close()
    return events 
import sqlite3
from datetime import datetime, timedelta
import json
import os

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

def get_power_statistics(days=7):
    """Get power usage statistics from historical data."""
    conn = sqlite3.connect('ups_history.db')
    c = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    
    # Get average, min, max watts and total readings
    c.execute('''
        WITH parsed_data AS (
            SELECT 
                timestamp,
                CAST(json_extract(data, '$.WATTS') AS FLOAT) as watts,
                CAST(json_extract(data, '$.LOADPCT') AS FLOAT) as load_pct
            FROM ups_readings 
            WHERE timestamp > ?
            AND json_extract(data, '$.WATTS') IS NOT NULL
            AND CAST(json_extract(data, '$.WATTS') AS FLOAT) > 0
        )
        SELECT 
            COUNT(*) as total_readings,
            AVG(watts) as avg_watts,
            MIN(watts) as min_watts,
            MAX(watts) as max_watts,
            AVG(load_pct) as avg_load
        FROM parsed_data
    ''', (cutoff,))
    
    result = c.fetchone()
    
    if result:
        stats = {
            'total_readings': result[0],
            'avg_watts': round(result[1], 2) if result[1] else 0,
            'min_watts': round(result[2], 2) if result[2] else 0,
            'max_watts': round(result[3], 2) if result[3] else 0,
            'avg_load': round(result[4], 2) if result[4] else 0,
            'days_analyzed': days
        }
        
        # Calculate costs based on average watts
        avg_kwh_per_hour = stats['avg_watts'] / 1000
        avg_kwh_per_day = avg_kwh_per_hour * 24
        avg_kwh_per_month = avg_kwh_per_day * 30.44  # Average days per month
        avg_kwh_per_year = avg_kwh_per_day * 365.25  # Account for leap years
        
        # Get electricity rate from environment
        electricity_rate = float(os.getenv('ELECTRICITY_RATE', 0.124))
        
        stats.update({
            'cost_per_hour': round(avg_kwh_per_hour * electricity_rate, 3),
            'cost_per_day': round(avg_kwh_per_day * electricity_rate, 2),
            'cost_per_month': round(avg_kwh_per_month * electricity_rate, 2),
            'cost_per_year': round(avg_kwh_per_year * electricity_rate, 2),
            'electricity_rate': electricity_rate
        })
    else:
        stats = {
            'total_readings': 0,
            'avg_watts': 0,
            'min_watts': 0,
            'max_watts': 0,
            'avg_load': 0,
            'days_analyzed': days,
            'cost_per_hour': 0,
            'cost_per_day': 0,
            'cost_per_month': 0,
            'cost_per_year': 0,
            'electricity_rate': float(os.getenv('ELECTRICITY_RATE', 0.124))
        }
    
    conn.close()
    return stats 
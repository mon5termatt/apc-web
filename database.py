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
    
    # Create table for acknowledged events
    c.execute('''
        CREATE TABLE IF NOT EXISTS acknowledged_events (
            event_timestamp DATETIME PRIMARY KEY,
            acknowledged_at DATETIME NOT NULL
        )
    ''')
    
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

def get_readings(hours=24, max_points=200):
    """Get readings from the last N hours with data aggregation for longer periods."""
    conn = sqlite3.connect('ups_history.db')
    c = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    # Initialize readings list
    readings = []
    
    # Calculate the start time for the requested period
    start_time = datetime.now() - timedelta(hours=hours)
    
    # For longer periods, use aggregation to reduce data points
    if hours > 168:  # 7 days or more - use hourly aggregation
        # Use hourly intervals for periods longer than 7 days
        c.execute('''
            SELECT 
                strftime('%Y-%m-%d %H:00', timestamp, 'localtime') as time_bucket,
                AVG(CAST(json_extract(data, '$.WATTS') AS FLOAT)) as avg_watts,
                AVG(CAST(json_extract(data, '$.AMPS') AS FLOAT)) as avg_amps,
                AVG(CAST(json_extract(data, '$.LOADPCT') AS FLOAT)) as avg_load,
                AVG(CAST(json_extract(data, '$.BCHARGE') AS FLOAT)) as avg_battery,
                COUNT(*) as sample_count,
                MIN(timestamp) as first_timestamp,
                MAX(timestamp) as last_timestamp
            FROM ups_readings 
            WHERE timestamp > ?
            GROUP BY time_bucket
            ORDER BY time_bucket
        ''', (cutoff,))
        
        rows = c.fetchall()
        
        # Limit to max_points and sample evenly
        if len(rows) > max_points:
            step = len(rows) // max_points
            rows = rows[::step][:max_points]
        
        for row in rows:
            # Create aggregated data structure
            aggregated_data = {
                'WATTS': round(row[1], 1) if row[1] else 0,
                'AMPS': round(row[2], 2) if row[2] else 0,
                'LOADPCT': round(row[3], 1) if row[3] else 0,
                'BCHARGE': round(row[4], 1) if row[4] else 0,
                'SAMPLE_COUNT': row[5]
            }
            
            readings.append({
                'timestamp': row[6],  # Use first timestamp of the bucket
                'data': aggregated_data
            })
    elif hours > 72:  # 3-7 days - use 15-minute intervals
        # Use 15-minute intervals (00, 15, 30, 45) for periods 3-7 days
        c.execute('''
            SELECT 
                strftime('%Y-%m-%d %H:00', timestamp, 'localtime') || 
                CASE 
                    WHEN CAST(strftime('%M', timestamp, 'localtime') AS INTEGER) < 15 THEN ':00'
                    WHEN CAST(strftime('%M', timestamp, 'localtime') AS INTEGER) < 30 THEN ':15'
                    WHEN CAST(strftime('%M', timestamp, 'localtime') AS INTEGER) < 45 THEN ':30'
                    ELSE ':45'
                END as time_bucket,
                AVG(CAST(json_extract(data, '$.WATTS') AS FLOAT)) as avg_watts,
                AVG(CAST(json_extract(data, '$.AMPS') AS FLOAT)) as avg_amps,
                AVG(CAST(json_extract(data, '$.LOADPCT') AS FLOAT)) as avg_load,
                AVG(CAST(json_extract(data, '$.BCHARGE') AS FLOAT)) as avg_battery,
                COUNT(*) as sample_count,
                MIN(timestamp) as first_timestamp,
                MAX(timestamp) as last_timestamp
            FROM ups_readings 
            WHERE timestamp > ?
            GROUP BY time_bucket
            ORDER BY time_bucket
        ''', (cutoff,))
        
        rows = c.fetchall()
        
        # Limit to max_points and sample evenly
        if len(rows) > max_points:
            step = len(rows) // max_points
            rows = rows[::step][:max_points]
        
        for row in rows:
            # Create aggregated data structure
            aggregated_data = {
                'WATTS': round(row[1], 1) if row[1] else 0,
                'AMPS': round(row[2], 2) if row[2] else 0,
                'LOADPCT': round(row[3], 1) if row[3] else 0,
                'BCHARGE': round(row[4], 1) if row[4] else 0,
                'SAMPLE_COUNT': row[5]
            }
            
            readings.append({
                'timestamp': row[6],  # Use first timestamp of the bucket
                'data': aggregated_data
            })
    else:
        # For shorter periods, get all data but limit points
        c.execute(
            'SELECT timestamp, data FROM ups_readings WHERE timestamp > ? ORDER BY timestamp',
            (cutoff,)
        )
        
        rows = c.fetchall()
        
        # Limit to max_points and sample evenly
        if len(rows) > max_points:
            step = len(rows) // max_points
            rows = rows[::step][:max_points]
        
        readings = [
            {
                'timestamp': row[0],
                'data': json.loads(row[1])
            }
            for row in rows
        ]
    
    # Fill in zeros before the first reading if there's a gap
    if readings:
        first_reading_time = datetime.fromisoformat(readings[0]['timestamp'].replace('Z', '+00:00'))
        if first_reading_time > start_time:
            # Add zero readings from start_time to first_reading_time
            if hours > 168:  # Hourly aggregation
                # Start from the hour before the first reading and go backward
                current_time = first_reading_time.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
                while current_time >= start_time:
                    zero_reading = {
                        'timestamp': current_time.isoformat(),
                        'data': {
                            'WATTS': 0,
                            'AMPS': 0,
                            'LOADPCT': 0,
                            'BCHARGE': 0,
                            'SAMPLE_COUNT': 0
                        }
                    }
                    readings.insert(0, zero_reading)
                    current_time -= timedelta(hours=1)
            else:  # Raw data - only add zero if there's a significant gap
                time_diff = first_reading_time - start_time
                if time_diff.total_seconds() > 300:  # Only if gap is more than 5 minutes
                    zero_reading = {
                        'timestamp': start_time.isoformat(),
                        'data': {
                            'WATTS': 0,
                            'AMPS': 0,
                            'LOADPCT': 0,
                            'BCHARGE': 0
                        }
                    }
                    readings.insert(0, zero_reading)
    
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
    # Exclude acknowledged events
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
        SELECT r.timestamp, r.data
        FROM numbered_rows r
        LEFT JOIN acknowledged_events a ON r.timestamp = a.event_timestamp
        WHERE a.event_timestamp IS NULL
        AND (
            (r.curr_transfers != r.prev_transfers AND r.prev_transfers IS NOT NULL)
            OR r.status LIKE '%ONBATT%'
        )
        ORDER BY r.timestamp
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

def clear_power_events():
    """Mark all current power events as acknowledged."""
    conn = sqlite3.connect('ups_history.db')
    c = conn.cursor()
    
    try:
        # Get all unacknowledged events
        events = get_power_events(days=7)  # Get recent events
        now = datetime.now().isoformat()
        
        # Mark them as acknowledged
        c.executemany(
            'INSERT OR IGNORE INTO acknowledged_events (event_timestamp, acknowledged_at) VALUES (?, ?)',
            [(event['timestamp'], now) for event in events]
        )
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error acknowledging power events: {e}")
        return False
    finally:
        conn.close() 
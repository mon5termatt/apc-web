#!/usr/bin/env python3
"""
Background UPS Data Collector
Continuously polls the UPS and stores data in the database.
This runs independently of the web interface.
"""

import os
import time
import subprocess
import json
from datetime import datetime
from dotenv import load_dotenv
import database

# Load environment variables
load_dotenv()

# UPS Configuration
UPS_VA = int(os.getenv('UPS_VA', 3000))
UPS_WATTS = int(os.getenv('UPS_WATTS', 2700))
POWER_FACTOR = float(os.getenv('POWER_FACTOR', 0.9))
NOMINAL_VOLTAGE = int(os.getenv('NOMINAL_VOLTAGE', 120))
ELECTRICITY_RATE = float(os.getenv('ELECTRICITY_RATE', 0.124))

def calculate_watts(load_percent):
    """Calculate watts from load percentage."""
    try:
        load_pct = float(load_percent)
        return round(UPS_WATTS * load_pct / 100, 1)
    except (ValueError, TypeError):
        return 0.0

def calculate_amps(watts, voltage=120):
    """Calculate amps from watts and voltage."""
    try:
        return round(watts / voltage, 2)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0.0

def calculate_power_cost(watts):
    """Calculate hourly power cost."""
    try:
        return round((watts / 1000) * ELECTRICITY_RATE, 3)
    except (ValueError, TypeError):
        return 0.0

def calculate_daily_cost(watts):
    """Calculate daily power cost."""
    try:
        return round((watts / 1000) * ELECTRICITY_RATE * 24, 2)
    except (ValueError, TypeError):
        return 0.0

def calculate_weekly_cost(watts):
    """Calculate weekly power cost."""
    try:
        return round((watts / 1000) * ELECTRICITY_RATE * 168, 2)
    except (ValueError, TypeError):
        return 0.0

def calculate_monthly_cost(watts):
    """Calculate monthly power cost."""
    try:
        return round((watts / 1000) * ELECTRICITY_RATE * 730.484, 2)
    except (ValueError, TypeError):
        return 0.0

def format_duration(seconds):
    """Format duration in seconds to HH:MM:SS."""
    try:
        seconds = int(seconds)
        if seconds == 0:
            return "None"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    except (ValueError, TypeError):
        return "Unknown"

def get_ups_data():
    """Get UPS data and return processed status."""
    try:
        # Try using system apcaccess first
        try:
            cmd = ['/sbin/apcaccess', '-h', os.getenv('APCUPSD_HOST', '10.0.0.13')]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                # Parse the key-value output into a dictionary
                status = {}
                for line in result.stdout.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        status[key.strip()] = value.strip()

                # Clean up values
                for key in status:
                    if isinstance(status[key], str):
                        status[key] = status[key].replace('Percent', '').replace('Volts', '').replace('Minutes', '').replace('Seconds', '').replace('Hz', '').replace('C', '').strip()

                # Calculate power metrics
                try:
                    load_pct = float(status.get('LOADPCT', '0'))
                    watts = calculate_watts(load_pct)
                    voltage = float(status.get('LINEV', NOMINAL_VOLTAGE))
                    amps = calculate_amps(watts, voltage)
                    status['WATTS'] = f"{watts}"
                    status['AMPS'] = f"{amps}"
                    status['VOLTAGE'] = f"{voltage}"
                    status['COST_HOUR'] = f"{calculate_power_cost(watts)}"
                    status['COST_DAILY'] = f"{calculate_daily_cost(watts)}"
                    status['COST_WEEKLY'] = f"{calculate_weekly_cost(watts)}"
                    status['COST_MONTHLY'] = f"{calculate_monthly_cost(watts)}"
                except ValueError:
                    print(f"Warning: Could not calculate power metrics")

                # Add configuration values
                status['UPS_VA'] = UPS_VA
                status['UPS_WATTS'] = UPS_WATTS
                status['POWER_FACTOR'] = POWER_FACTOR
                status['NOMINAL_VOLTAGE'] = NOMINAL_VOLTAGE
                status['ELECTRICITY_RATE'] = ELECTRICITY_RATE

                # Format any time durations
                if 'TONBATT' in status:
                    status['TONBATT_FORMATTED'] = format_duration(status['TONBATT'])
                if 'CUMONBATT' in status:
                    status['CUMONBATT_FORMATTED'] = format_duration(status['CUMONBATT'])

                # Add timestamp
                status['TIMESTAMP'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                return status
        except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            print(f"System apcaccess failed: {str(e)}, falling back to Python package")

        # Fall back to Python apcaccess package
        try:
            from apcaccess import status as apc
            import socket
            
            # Set socket timeout for the connection
            socket.setdefaulttimeout(10)
            
            ups = apc.parse(apc.get(
                host=os.getenv('APCUPSD_HOST', '10.0.0.13'),
                port=int(os.getenv('APCUPSD_PORT', 3551))
            ))

            # Clean up values
            for key in ups:
                if isinstance(ups[key], str):
                    ups[key] = ups[key].replace('Percent', '').replace('Volts', '').replace('Minutes', '').replace('Seconds', '').replace('Hz', '').replace('C', '').strip()

            # Calculate power metrics
            try:
                load_pct = float(ups.get('LOADPCT', '0'))
                watts = calculate_watts(load_pct)
                voltage = float(ups.get('LINEV', NOMINAL_VOLTAGE))
                amps = calculate_amps(watts, voltage)
                ups['WATTS'] = f"{watts}"
                ups['AMPS'] = f"{amps}"
                ups['VOLTAGE'] = f"{voltage}"
                ups['COST_HOUR'] = f"{calculate_power_cost(watts)}"
                ups['COST_DAILY'] = f"{calculate_daily_cost(watts)}"
                ups['COST_WEEKLY'] = f"{calculate_weekly_cost(watts)}"
                ups['COST_MONTHLY'] = f"{calculate_monthly_cost(watts)}"
            except ValueError:
                print(f"Warning: Could not calculate power metrics")

            # Add configuration values
            ups['UPS_VA'] = UPS_VA
            ups['UPS_WATTS'] = UPS_WATTS
            ups['POWER_FACTOR'] = POWER_FACTOR
            ups['NOMINAL_VOLTAGE'] = NOMINAL_VOLTAGE
            ups['ELECTRICITY_RATE'] = ELECTRICITY_RATE
            
            # Format any time durations
            if 'TONBATT' in ups:
                ups['TONBATT_FORMATTED'] = format_duration(ups['TONBATT'])
            if 'CUMONBATT' in ups:
                ups['CUMONBATT_FORMATTED'] = format_duration(ups['CUMONBATT'])

            # Add timestamp
            ups['TIMESTAMP'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            return ups
        except Exception as e:
            print(f"Error using Python apcaccess: {str(e)}")
            return None

    except Exception as e:
        print(f"Error getting UPS status: {str(e)}")
        return None

def main():
    """Main data collection loop."""
    print("Starting UPS Data Collector...")
    
    # Initialize database
    database.init_db()
    
    # Data collection interval (seconds)
    COLLECTION_INTERVAL = 5
    
    consecutive_failures = 0
    max_failures = 10
    
    while True:
        try:
            # Get UPS data
            ups_data = get_ups_data()
            
            if ups_data and ups_data.get('STATUS'):
                # Store the reading
                database.store_reading(ups_data)
                consecutive_failures = 0
                
                # Log successful collection
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Data collected: {ups_data.get('STATUS')} - Load: {ups_data.get('LOADPCT')}% - Watts: {ups_data.get('WATTS')}")
                
                # Clean up old readings periodically (every 30 minutes)
                if datetime.now().minute % 30 == 0 and datetime.now().second < 10:
                    database.cleanup_old_readings(days=7)
                    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Cleaned up old readings")
                    
            else:
                consecutive_failures += 1
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Failed to get UPS data (attempt {consecutive_failures}/{max_failures})")
                
                if consecutive_failures >= max_failures:
                    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Too many consecutive failures, pausing for 60 seconds")
                    time.sleep(60)
                    consecutive_failures = 0
            
            # Wait for next collection
            time.sleep(COLLECTION_INTERVAL)
            
        except KeyboardInterrupt:
            print("\nStopping UPS Data Collector...")
            break
        except Exception as e:
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Unexpected error: {str(e)}")
            time.sleep(COLLECTION_INTERVAL)

if __name__ == "__main__":
    main() 
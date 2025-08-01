from flask import Flask, render_template, jsonify, request
import os
import argparse
import subprocess
import json
from dotenv import load_dotenv
from datetime import datetime
import database

# Load environment variables
load_dotenv()

# Initialize database
database.init_db()

# UPS Configuration - Read from environment variables with defaults
UPS_VA = int(os.getenv('UPS_VA', 3000))
UPS_WATTS = int(os.getenv('UPS_WATTS', 2700))
POWER_FACTOR = float(os.getenv('POWER_FACTOR', 0.9))  # Actual power factor (2700W/3000VA)
NOMINAL_VOLTAGE = int(os.getenv('NOMINAL_VOLTAGE', 120))  # Nominal voltage for warnings
ELECTRICITY_RATE = float(os.getenv('ELECTRICITY_RATE', 0.124))  # Cost per kWh in dollars

app = Flask(__name__)

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
        # 24 hours in a day
        return round((watts / 1000) * ELECTRICITY_RATE * 24, 2)
    except (ValueError, TypeError):
        return 0.0

def calculate_weekly_cost(watts):
    """Calculate weekly power cost."""
    try:
        # 168 hours in a week (24 * 7)
        return round((watts / 1000) * ELECTRICITY_RATE * 168, 2)
    except (ValueError, TypeError):
        return 0.0

def calculate_monthly_cost(watts):
    """Calculate monthly power cost."""
    try:
        # ~730.484 hours in an average month (24 * 365.242 / 12)
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

def simulate_power_event():
    """Simulate a power event for testing purposes."""
    from datetime import datetime, timedelta
    
    # Simulate UPS running on battery
    status = {
        'STATUS': 'ONBATT',
        'LOADPCT': '25.0',
        'BCHARGE': '85.0',
        'TIMELEFT': '45.0',
        'LINEV': '0.0',  # No input voltage
        'OUTPUTV': '121.6',
        'LINEFREQ': '0.0',
        'ITEMP': '22.5',
        'BATTV': '54.2',
        'NUMXFERS': '1',
        'TONBATT': '300',  # 5 minutes on battery
        'CUMONBATT': '1800',  # 30 minutes total
        'LASTXFER': 'Low line voltage',
        'MODEL': 'Smart-UPS 3000 XL',
        'SERIALNO': 'JS0745010850',
        'FIRMWARE': '691.17.D',
        'TIMESTAMP': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Calculate power metrics
    try:
        load_pct = float(status.get('LOADPCT', '0'))
        watts = calculate_watts(load_pct)
        voltage = float(status.get('OUTPUTV', NOMINAL_VOLTAGE))  # Use output voltage for amps calc
        amps = calculate_amps(watts, voltage)
        status['WATTS'] = f"{watts}"
        status['AMPS'] = f"{amps}"
        status['VOLTAGE'] = f"{voltage}"
        status['COST_HOUR'] = f"{calculate_power_cost(watts)}"
        status['COST_DAILY'] = f"{calculate_daily_cost(watts)}"
        status['COST_WEEKLY'] = f"{calculate_weekly_cost(watts)}"
        status['COST_MONTHLY'] = f"{calculate_monthly_cost(watts)}"
    except ValueError:
        app.logger.warning("Could not calculate power metrics")

    # Add configuration values
    status['UPS_VA'] = UPS_VA
    status['UPS_WATTS'] = UPS_WATTS
    status['POWER_FACTOR'] = POWER_FACTOR
    status['NOMINAL_VOLTAGE'] = NOMINAL_VOLTAGE
    status['ELECTRICITY_RATE'] = ELECTRICITY_RATE

    # Format time durations
    status['TONBATT_FORMATTED'] = format_duration(status['TONBATT'])
    status['CUMONBATT_FORMATTED'] = format_duration(status['CUMONBATT'])
    
    return status

def get_ups_status():
    """Get UPS status from APCUPSD with enhanced metrics."""
    # Check if simulation mode is enabled
    if os.getenv('SIMULATE_POWER_EVENT', '').lower() == 'true':
        app.logger.info("Simulating power event")
        return simulate_power_event()
    
    try:
        # Try using system apcaccess first
        try:
            cmd = ['/sbin/apcaccess', '-h', os.getenv('APCUPSD_HOST', '10.0.0.13')]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)  # 10 second timeout
            if result.returncode == 0:
                # Parse the key-value output into a dictionary
                status = {}
                for line in result.stdout.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        status[key.strip()] = value.strip()

                # Clean up values (remove units like Percent, Volts, etc.)
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
                    app.logger.warning("Could not calculate power metrics")

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
            app.logger.warning(f"System apcaccess failed: {str(e)}, falling back to Python package")
            app.logger.error(f"UPS connection issue - system apcaccess: {str(e)}")

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
                app.logger.warning("Could not calculate power metrics")

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
            app.logger.error(f"Error using Python apcaccess: {str(e)}")
            app.logger.error(f"UPS connection issue - Python apcaccess: {str(e)}")
            return None

    except Exception as e:
        app.logger.error(f"Error getting UPS status: {str(e)}")
        app.logger.error(f"Critical UPS connection failure: {str(e)}")
        return None

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/api/status')
def status():
    """API endpoint to get UPS status."""
    try:
        ups_status = get_ups_status()
        if ups_status is None:
            return jsonify({'error': 'Failed to get UPS status - no data available'}), 503
        return jsonify(ups_status)
    except Exception as e:
        app.logger.error(f"Error in status endpoint: {str(e)}")
        return jsonify({'error': f'UPS status error: {str(e)}'}), 500

@app.route('/api/history')
def history():
    """Get historical readings."""
    try:
        hours = int(request.args.get('hours', 24))
        hours = min(max(1, hours), 168)  # Limit between 1 hour and 7 days
        readings = database.get_readings(hours=hours)
        return jsonify(readings)
    except Exception as e:
        app.logger.error(f"Error getting history: {str(e)}")
        return jsonify({'error': 'Failed to get history'}), 500

@app.route('/api/events')
def events():
    """Get power events (transfers to battery)."""
    try:
        days = int(request.args.get('days', 7))
        days = min(max(1, days), 7)  # Limit between 1 and 7 days
        events = database.get_power_events(days=days)
        return jsonify(events)
    except Exception as e:
        app.logger.error(f"Error getting events: {str(e)}")
        return jsonify({'error': 'Failed to get events'}), 500

@app.route('/api/power_stats')
def power_stats():
    """Get power usage statistics and cost estimates."""
    try:
        days = int(request.args.get('days', 7))
        days = min(max(1, days), 30)  # Limit between 1 and 30 days
        stats = database.get_power_statistics(days=days)
        return jsonify(stats)
    except Exception as e:
        app.logger.error(f"Error getting power statistics: {str(e)}")
        return jsonify({'error': 'Failed to get power statistics'}), 500

@app.route('/api/health')
def health():
    """Health check endpoint to monitor UPS connection status."""
    try:
        # Check if we can get UPS status
        ups_status = get_ups_status()
        if ups_status is None:
            return jsonify({
                'status': 'unhealthy',
                'message': 'Cannot connect to UPS',
                'timestamp': datetime.now().isoformat()
            }), 503
        
        # Check if we have recent data
        recent_readings = database.get_readings(hours=1)
        if not recent_readings:
            return jsonify({
                'status': 'warning',
                'message': 'No recent data in database',
                'timestamp': datetime.now().isoformat()
            }), 200
        
        return jsonify({
            'status': 'healthy',
            'message': 'UPS connection working',
            'timestamp': datetime.now().isoformat(),
            'last_reading': recent_readings[-1]['timestamp'] if recent_readings else None
        }), 200
        
    except Exception as e:
        app.logger.error(f"Health check error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Health check failed: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/events/acknowledge', methods=['POST'])
def acknowledge_events():
    """Mark all power events as read."""
    try:
        if database.clear_power_events():
            return jsonify({
                'status': 'success',
                'message': 'Power events cleared successfully',
                'timestamp': datetime.now().isoformat()
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to clear power events',
                'timestamp': datetime.now().isoformat()
            }), 500
    except Exception as e:
        app.logger.error(f"Error clearing power events: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to clear power events: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    # Set debug mode based on environment variable or command line flag [[memory:2787140]]
    debug_mode = args.debug or os.getenv('DEBUG', '').lower() == 'true'
    
    app.run(host='0.0.0.0', port=5000, debug=debug_mode) 
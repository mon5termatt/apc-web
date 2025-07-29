# APC UPS Web Monitor

A comprehensive web-based monitoring system for APC UPS devices with real-time statistics, historical data, and advanced features.

## Features

- **Real-time Monitoring**: Live UPS status, power consumption, and battery health
- **Historical Charts**: Interactive charts showing load, battery, temperature, voltage, and power costs over time
- **Power Cost Analysis**: Calculate hourly, daily, weekly, and monthly electricity costs
- **Mobile Responsive**: Optimized for desktop and mobile devices
- **Dark/Light Mode**: Toggle between themes
- **URL Parameters**: Configure display via URL parameters for automation
- **Power Event Simulation**: Test system behavior during power outages
- **Data Persistence**: SQLite database for historical data storage
- **Continuous Data Collection**: Background service ensures data is always collected
- **Fallback System**: Uses cached data when UPS is temporarily unavailable
- **Health Monitoring**: Built-in health checks and monitoring endpoints
- **Automatic Recovery**: Services restart automatically if they crash

## Architecture

The system uses a **two-service architecture** for maximum reliability:

1. **Data Collector Service** (`apc-data-collector`): Continuously polls the UPS every 5 seconds and stores data in the database
2. **Web Interface Service** (`apc-web`): Serves the web interface and API endpoints, reads from the database

This separation ensures that data collection continues even if the web interface is not being accessed.

## Requirements

- Python 3.8+
- APCUPSD running and accessible on the network
- pip (Python package manager)
- systemd (for service management)

## Quick Start

### Option 1: Using the provided script
```bash
./run.sh
```

### Option 2: Manual setup
1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the environment template:
   ```bash
   cp empty.env .env
   ```
4. Edit `.env` file with your configuration
5. Install and start the services:
   ```bash
   # Install services
   sudo cp apc-web.service /etc/systemd/system/
   sudo cp apc-data-collector.service /etc/systemd/system/
   sudo systemctl daemon-reload
   
   # Enable and start services
   sudo systemctl enable apc-web apc-data-collector
   sudo systemctl start apc-web apc-data-collector
   ```

## Configuration

Edit the `.env` file to customize your setup:

```bash
# APCUPSD Configuration
APCUPSD_HOST=10.0.0.13
APCUPSD_PORT=3551

# UPS Hardware Configuration
UPS_VA=3000
UPS_WATTS=2700
POWER_FACTOR=0.9
NOMINAL_VOLTAGE=120

# Electricity Cost Configuration
ELECTRICITY_RATE=0.124

# Application Settings
FLASK_ENV=production
SIMULATE_POWER_EVENT=false
DEBUG=false
```

### Configuration Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APCUPSD_HOST` | UPS server IP/hostname | `10.0.0.13` |
| `APCUPSD_PORT` | UPS server port | `3551` |
| `UPS_VA` | UPS rating in VA | `3000` |
| `UPS_WATTS` | UPS rating in Watts | `2700` |
| `POWER_FACTOR` | Power factor ratio | `0.9` |
| `NOMINAL_VOLTAGE` | Nominal voltage for warnings | `120` |
| `ELECTRICITY_RATE` | Cost per kWh in dollars | `0.124` |
| `FLASK_ENV` | Flask environment mode | `production` |
| `SIMULATE_POWER_EVENT` | Enable power event simulation | `false` |
| `DEBUG` | Enable debug logging | `false` |

## Running the Services

### Development Mode
```bash
# Start data collector in background
python data_collector.py &

# Start web interface
python app.py --debug
```

### Production Mode (Recommended)
```bash
# Both services run automatically via systemd
sudo systemctl status apc-web apc-data-collector
```

### Service Management
```bash
# Check service status
sudo systemctl status apc-web
sudo systemctl status apc-data-collector

# View logs
sudo journalctl -u apc-web -f
sudo journalctl -u apc-data-collector -f

# Restart services
sudo systemctl restart apc-web apc-data-collector

# Stop services
sudo systemctl stop apc-web apc-data-collector
```

### Using Docker Compose
```bash
docker-compose up -d
```

## Monitoring & Health Checks

### Health Check Endpoint
```bash
curl http://localhost:5000/api/health
```

Returns:
- `healthy`: UPS connection working, data being collected
- `warning`: No recent data in database
- `unhealthy`: Cannot connect to UPS

### Service Monitoring
```bash
# Check if data is being collected
sudo journalctl -u apc-data-collector --since "5 minutes ago"

# Check web interface logs
sudo journalctl -u apc-web --since "5 minutes ago"

# Monitor database growth
sqlite3 ups_history.db "SELECT COUNT(*) FROM ups_readings WHERE timestamp > datetime('now', '-1 hour');"
```

## URL Parameters

The application supports URL parameters for automated configuration:

### Basic Parameters
- `?cycle` - Auto-start chart cycling
- `?fullscreen` - Enter fullscreen mode
- `?cycle&fullscreen` - Start cycling in fullscreen

### Chart Types
- `?chart=load` - Load, Power & Current
- `?chart=battery` - Battery Level & Runtime
- `?chart=temperature` - Temperature
- `?chart=voltage` - Input/Output Voltage
- `?chart=cost` - Power Cost
- `?chart=amps` - Current Draw

### Time Ranges
- `?hours=1` - Last Hour
- `?hours=24` - Last 24 Hours
- `?hours=72` - Last 3 Days
- `?hours=168` - Last 7 Days

### Examples
- `http://localhost:5000/?chart=amps&cycle` - Amps chart with cycling
- `http://localhost:5000/?chart=load&hours=24&cycle` - 24h load data with cycling
- `http://localhost:5000/?cycle&fullscreen` - Fullscreen cycling mode

## Features

### Real-time Monitoring
- **Power Statistics**: Watts, amps, load percentage, and power factor
- **Battery Status**: Charge level, runtime remaining, battery voltage
- **Temperature Monitoring**: Internal UPS temperature with warnings
- **Voltage Tracking**: Input/output voltage stability
- **Cost Analysis**: Real-time electricity cost calculations

### Historical Data
- **Interactive Charts**: Multiple chart types with time range selection
- **Data Persistence**: SQLite database stores historical readings
- **Continuous Collection**: Data collected every 5 seconds regardless of web traffic
- **Automatic Cleanup**: Old data automatically removed after 7 days
- **Export Ready**: Data available via API endpoints

### Power Event Detection
- **Event Logging**: Automatic detection and logging of power events
- **Battery Transfers**: Track when UPS switches to battery power
- **Duration Tracking**: Monitor time spent on battery power
- **Simulation Mode**: Test system behavior with simulated power events

### User Interface
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Theme Toggle**: Switch between light and dark modes
- **Chart Cycling**: Automatic rotation through different chart types
- **Fullscreen Mode**: Dedicated fullscreen display for monitoring
- **Warning Overlay**: Flashing border when UPS is on battery power

## API Endpoints

- `GET /` - Main web interface
- `GET /api/status` - Current UPS status (JSON)
- `GET /api/history?hours=N` - Historical data (JSON)
- `GET /api/events` - Power events (JSON)
- `GET /api/health` - System health check (JSON)

## Troubleshooting

### Common Issues

1. **Cannot connect to UPS**
   - Verify `APCUPSD_HOST` and `APCUPSD_PORT` in `.env`
   - Check network connectivity to UPS server
   - Ensure APCUPSD is running and accessible
   - Check data collector logs: `journalctl -u apc-data-collector -f`

2. **No historical data**
   - Check if data collector is running: `systemctl status apc-data-collector`
   - Verify database file permissions
   - Check data collector logs for connection errors
   - Test UPS connection manually: `apcaccess --host 10.0.0.13 --port 3551`

3. **Incorrect power calculations**
   - Update `UPS_WATTS`, `UPS_VA`, and `POWER_FACTOR` in `.env`
   - Verify `ELECTRICITY_RATE` for accurate cost calculations

4. **Services not starting**
   - Check service logs: `journalctl -u apc-web -u apc-data-collector`
   - Verify Python dependencies are installed
   - Check file permissions and paths

### Debug Mode
Enable debug logging to troubleshoot issues:
```bash
# For web interface
python app.py --debug

# For data collector
python data_collector.py
```

### Health Monitoring
```bash
# Check system health
curl http://localhost:5000/api/health

# Monitor data collection
sqlite3 ups_history.db "SELECT timestamp FROM ups_readings ORDER BY timestamp DESC LIMIT 5;"

# Check for data gaps
sqlite3 ups_history.db "SELECT timestamp FROM ups_readings WHERE timestamp > datetime('now', '-2 hours') ORDER BY timestamp;"
```

## Development

### Project Structure
```
apc-web/
├── app.py                    # Main Flask application
├── data_collector.py         # Background data collector
├── database.py               # Database operations
├── templates/                # HTML templates
├── requirements.txt          # Python dependencies
├── empty.env                 # Environment template
├── run.sh                    # Quick start script
├── apc-web.service          # Web interface systemd service
├── apc-data-collector.service # Data collector systemd service
└── docker-compose.yml       # Docker configuration
```

### Service Architecture
- **Data Collector**: Runs every 5 seconds, stores data in database
- **Web Interface**: Serves web pages and API, reads from database
- **Database**: SQLite database with automatic cleanup
- **Monitoring**: Health checks and detailed logging

### Adding New Features
1. Update environment variables in `empty.env`
2. Add configuration reading in `app.py` and `data_collector.py`
3. Update templates as needed
4. Test with different UPS configurations
5. Update service files if needed

## License

This project is open source and available under the MIT License. 
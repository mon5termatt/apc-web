# APC UPS Web Monitor

A simple web server that displays real-time statistics from a networked APCUPSD installation.

## Requirements

- Python 3.8+
- APCUPSD running and accessible on the network
- pip (Python package manager)

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your APCUPSD host configuration:
   ```
   APCUPSD_HOST=localhost
   APCUPSD_PORT=3551
   DEBUG=false
   ```

## Running the Server

Start the web server:
```bash
python app.py
```

By default, the server runs on http://localhost:5000

To enable debug mode, either:
- Set DEBUG=true in .env file
- Run with --debug flag: `python app.py --debug` 
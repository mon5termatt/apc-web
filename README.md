# APC UPS Web Monitor

A simple web server that displays real-time statistics from a networked APCUPSD installation.

Note, this software was set up to work with <b>MY UPS</b>. not yours. you <b>WILL</b> have to change the settings to fit your needs. 
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/b2c9feea-16a8-4192-8685-1a7d18bd36fc" />

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

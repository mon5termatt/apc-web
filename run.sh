#!/bin/bash

# Check if .env file exists, if not create one with default values
if [ ! -f .env ]; then
    echo "Creating .env file with default configuration..."
    cat > .env << EOF
# APCUPSD Configuration
# Set this to the IP address or hostname of your APCUPSD server
APCUPSD_HOST=10.0.0.13

# Flask Environment (development/production)
FLASK_ENV=production
EOF
    echo ".env file created with default values. Edit it to configure your APCUPSD host."
fi

# Run with Docker Compose
echo "Starting APC Web Monitor..."
docker-compose up -d

echo "Application is running at http://localhost:5000"
echo "To view logs: docker-compose logs -f"
echo "To stop: docker-compose down" 
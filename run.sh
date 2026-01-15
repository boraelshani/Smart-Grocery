#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"

# Run the Flask app using the virtual environment's Python interpreter
echo "Starting Smart Grocery..."
./venv/bin/python app.py

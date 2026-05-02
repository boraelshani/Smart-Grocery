#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app
print(f"Starting Smart Grocery on http://127.0.0.1:5001")
app.run(debug=False, host='127.0.0.1', port=5001)

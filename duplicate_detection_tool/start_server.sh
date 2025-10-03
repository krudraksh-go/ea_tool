#!/bin/bash

# Start script for Duplicate Detection Tool
# Makes it easy to launch the FastAPI server

echo "================================================"
echo "  JIRA Duplicate Detection Tool"
echo "================================================"
echo ""
echo "Starting FastAPI server..."
echo ""
echo "The web interface will be available at:"
echo "  http://localhost:8080"
echo "  or from external network: http://[VM_IP]:8080"
echo ""
echo "Press Ctrl+C to stop the server"
echo "================================================"
echo ""

# Activate virtual environment if it exists
# if [ -d "../venv" ]; then
#     echo "Activating virtual environment..."
#     source ../venv/bin/activate
# fi

# Run the FastAPI app
python app.py


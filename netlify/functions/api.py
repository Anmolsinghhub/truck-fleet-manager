import json
import os
import re
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import serverless_wsgi

app = Flask(__name__)
CORS(app)

# Determine the path to data.json relative to this file
# On Netlify Functions, the files are typically in the root of the function's deployment
DATA_FILE_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data.json')
DATA_FILE_NETLIFY = os.path.join(os.getcwd(), 'data.json')

def load_data():
    # Try multiple common locations for Netlify
    paths_to_try = [
        DATA_FILE_LOCAL,
        DATA_FILE_NETLIFY,
        'data.json',
        '/var/task/data.json'
    ]
    
    for path in paths_to_try:
        if os.path.exists(path):
            print(f"Found data file at: {path}")
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error reading {path}: {e}")
    
    print(f"Data file not found in any of: {paths_to_try}")
    # Fallback to hardcoded initial data if file is missing
    return [
        {
            "id": 1,
            "vehicleNo": "RJ-14-GB-1234",
            "type": "12 Wheeler Truck",
            "driver": {"name": "Rajesh Kumar", "number": "+91 98765 43210", "age": 42},
            "maintenance": {"lastDate": "2024-03-15", "issue": "Oil Change", "cost": 15000, "tires": []},
            "trips": []
        },
        {
            "id": 2,
            "vehicleNo": "RJ-14-GB-5678",
            "type": "12 Wheeler Truck",
            "driver": {"name": "Suresh Singh", "number": "+91 91234 56789", "age": 38},
            "maintenance": {"lastDate": "2024-02-20", "issue": "Repair", "cost": 22000, "tires": []},
            "trips": []
        },
        {
            "id": 3,
            "vehicleNo": "RJ-14-GB-9012",
            "type": "12 Wheeler Truck",
            "driver": {"name": "Amit Sharma", "number": "+91 88776 65544", "age": 45},
            "maintenance": {"lastDate": "2024-04-01", "issue": "Service", "cost": 8000, "tires": []},
            "trips": []
        }
    ]

def save_data(data):
    # On Netlify Functions, we can't save to data.json permanently.
    # We will try to write it, but it's mainly for local testing.
    # In production, this will fail or not persist.
    try:
        # Check if we have write access to the directory
        if os.access(os.path.dirname(DATA_FILE_LOCAL), os.W__OK):
            with open(DATA_FILE_LOCAL, 'w') as f:
                json.dump(data, f, indent=2)
    except:
        pass

@app.route('/api/fleet', methods=['GET'])
def get_fleet():
    return jsonify(load_data())

@app.route('/api/webhook', methods=['POST'])
def whatsapp_webhook():
    # Handle both JSON (simulator) and Form Data (Twilio)
    if request.is_json:
        data = request.json
    else:
        data = request.form

    message_body = data.get('Body', '').strip()
    sender = data.get('From', '')

    print(f"Received message from {sender}: {message_body}")

    # Regex to parse the detailed message
    pattern = r"Truck:\s*(?P<truck>[\w-]+),\s*From:\s*(?P<from>[\w\s]+),\s*To:\s*(?P<to>[\w\s]+),\s*Rev:\s*(?P<rev>\d+),\s*Fuel:\s*(?P<fuel>\d+),\s*Salary:\s*(?P<salary>\d+),\s*Cuts:\s*(?P<cuts>\d+),\s*Tolls:\s*(?P<tolls>\d+),\s*Bribe:\s*(?P<bribe>\d+),\s*Repair:\s*(?P<repair>\d+),\s*Misc:\s*(?P<misc>\d+)"
    match = re.search(pattern, message_body, re.IGNORECASE)

    if not match:
        return jsonify({
            "status": "error", 
            "message": "Invalid format. Use the standard Truck: [No], From: [City]... template."
        }), 400

    trip_info = match.groupdict()
    fleet = load_data()
    
    truck = next((t for t in fleet if t['vehicleNo'].lower() == trip_info['truck'].lower()), None)
    
    if not truck:
        return jsonify({"status": "error", "message": f"Truck {trip_info['truck']} not found"}), 404

    revenue = int(trip_info['rev'])
    breakdown = {
        "fuel": int(trip_info['fuel']),
        "salary": int(trip_info['salary']),
        "cuts": int(trip_info['cuts']),
        "tolls": int(trip_info['tolls']),
        "bribe": int(trip_info['bribe']),
        "repair": int(trip_info['repair']),
        "misc": int(trip_info['misc'])
    }
    total_cost = sum(breakdown.values())

    new_trip = {
        "id": f"T{datetime.now().strftime('%y%m%d%H%M')}",
        "date": datetime.now().strftime('%Y-%m-%d'),
        "start": trip_info['from'].strip(),
        "destination": trip_info['to'].strip(),
        "range": 0,
        "timeTaken": "Unknown",
        "oilConsumed": 0,
        "mileage": 0,
        "revenue": revenue,
        "cost": total_cost,
        "costBreakdown": breakdown,
        "profit": revenue - total_cost
    }

    truck['trips'].insert(0, new_trip)
    save_data(fleet)

    # If it's from Twilio, we should return a TwiML response (XML)
    if not request.is_json:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Message>✅ Trip recorded for {truck['vehicleNo']}. Total Cost: ₹{total_cost}, Profit: ₹{new_trip['profit']}</Message>
        </Response>""", 200, {'Content-Type': 'application/xml'}

    return jsonify({
        "status": "success", 
        "message": f"Trip recorded for {truck['vehicleNo']}. Total Cost: ₹{total_cost}, Profit: ₹{new_trip['profit']}"
    })

def handler(event, context):
    return serverless_wsgi.handle_request(app, event, context)

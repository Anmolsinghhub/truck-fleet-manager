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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, '..', 'data.json')

def load_data():
    if not os.path.exists(DATA_FILE):
        print(f"Data file not found at {DATA_FILE}")
        return []
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading data: {e}")
        return []

def save_data(data):
    # This won't actually persist on Netlify Functions
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

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

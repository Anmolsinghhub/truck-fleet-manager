from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
from datetime import datetime
import re

app = Flask(__name__)
CORS(app)

DATA_FILE = 'data.json'

def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/api/fleet', methods=['GET'])
def get_fleet():
    return jsonify(load_data())

@app.route('/api/webhook', methods=['POST'])
def whatsapp_webhook():
    """
    Simulated WhatsApp Webhook.
    Expected message format: 
    Truck: [No], From: [City], To: [City], Rev: [Amt], Fuel: [Amt], Salary: [Amt], Cuts: [Amt], Tolls: [Amt], Bribe: [Amt], Repair: [Amt], Misc: [Amt]
    Example: Truck: RJ-14-GB-1234, From: Jaipur, To: Delhi, Rev: 18000, Fuel: 5000, Salary: 2000, Cuts: 500, Tolls: 1000, Bribe: 200, Repair: 0, Misc: 300
    """
    data = request.json
    message_body = data.get('Body', '').strip()
    sender = data.get('From', '')

    print(f"Received message from {sender}: {message_body}")

    # Regex to parse the detailed message
    pattern = r"Truck:\s*(?P<truck>[\w-]+),\s*From:\s*(?P<from>[\w\s]+),\s*To:\s*(?P<to>[\w\s]+),\s*Rev:\s*(?P<rev>\d+),\s*Fuel:\s*(?P<fuel>\d+),\s*Salary:\s*(?P<salary>\d+),\s*Cuts:\s*(?P<cuts>\d+),\s*Tolls:\s*(?P<tolls>\d+),\s*Bribe:\s*(?P<bribe>\d+),\s*Repair:\s*(?P<repair>\d+),\s*Misc:\s*(?P<misc>\d+)"
    match = re.search(pattern, message_body, re.IGNORECASE)

    if not match:
        return jsonify({
            "status": "error", 
            "message": "Invalid format. Use: Truck: [No], From: [City], To: [City], Rev: [Amt], Fuel: [Amt], Salary: [Amt], Cuts: [Amt], Tolls: [Amt], Bribe: [Amt], Repair: [Amt], Misc: [Amt]"
        }), 400

    trip_info = match.groupdict()
    fleet = load_data()
    
    truck = next((t for t in fleet if t['vehicleNo'].lower() == trip_info['truck'].lower()), None)
    
    if not truck:
        return jsonify({"status": "error", "message": f"Truck {trip_info['truck']} not found in fleet"}), 404

    # Calculate total cost from breakdown
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

    return jsonify({
        "status": "success", 
        "message": f"Trip recorded for {truck['vehicleNo']}. Total Cost: ₹{total_cost}, Profit: ₹{new_trip['profit']}"
    })

# Serve frontend files
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    app.run(port=8000, debug=True)

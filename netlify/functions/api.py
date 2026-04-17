import json
import os
import re
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import serverless_wsgi
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Standard Flask app
app = Flask(__name__)
CORS(app)

# Add a simple health check route at the root of the function
@app.route('/api/', methods=['GET'])
@app.route('/.netlify/functions/api/', methods=['GET'])
def health_check():
    return jsonify({"status": "active", "message": "FleetPro API is running"})

# Supabase Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

def get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing Supabase URL or Key environment variables")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Fallback data if database is empty
INITIAL_FLEET = [
    {
        "id": 1,
        "vehicleNo": "RJ-14-GB-1234",
        "type": "12 Wheeler Truck",
        "driver": {"name": "Rajesh Kumar", "number": "+91 98765 43210", "age": 42},
        "maintenance": {"lastDate": "2024-03-15", "issue": "Oil Change", "cost": 15000, "tires": []}
    },
    {
        "id": 2,
        "vehicleNo": "RJ-14-GB-5678",
        "type": "12 Wheeler Truck",
        "driver": {"name": "Suresh Singh", "number": "+91 91234 56789", "age": 38},
        "maintenance": {"lastDate": "2024-02-20", "issue": "Clutch Repair", "cost": 22000, "tires": []}
    },
    {
        "id": 3,
        "vehicleNo": "RJ-14-GB-9012",
        "type": "12 Wheeler Truck",
        "driver": {"name": "Amit Sharma", "number": "+91 88776 65544", "age": 45},
        "maintenance": {"lastDate": "2024-04-01", "issue": "Routine Service", "cost": 8000, "tires": []}
    }
]

# Support for multiple path variations for the same route
@app.route('/api/fleet', methods=['GET'])
@app.route('/.netlify/functions/api/fleet', methods=['GET'])
def get_fleet():
    try:
        supabase = get_supabase()
        response = supabase.table('trips').select("*").order('date', desc=True).execute()
        all_trips = response.data or []

        fleet = []
        for truck in INITIAL_FLEET:
            truck_copy = truck.copy()
            truck_copy['trips'] = [t for t in all_trips if t['vehicleNo'] == truck['vehicleNo']]
            fleet.append(truck_copy)
        
        return jsonify(fleet)
    except Exception as e:
        print(f"Supabase Error: {e}")
        return jsonify([dict(t, trips=[]) for t in INITIAL_FLEET])

@app.route('/api/webhook', methods=['POST'])
@app.route('/.netlify/functions/api/webhook', methods=['POST'])
def whatsapp_webhook():
    if request.is_json:
        data = request.json
    else:
        data = request.form

    message_body = data.get('Body', '').strip()
    sender = data.get('From', '')

    pattern = r"Truck:\s*(?P<truck>[\w-]+),\s*From:\s*(?P<from>[\w\s]+),\s*To:\s*(?P<to>[\w\s]+),\s*Rev:\s*(?P<rev>\d+),\s*Fuel:\s*(?P<fuel>\d+),\s*Salary:\s*(?P<salary>\d+),\s*Cuts:\s*(?P<cuts>\d+),\s*Tolls:\s*(?P<tolls>\d+),\s*Bribe:\s*(?P<bribe>\d+),\s*Repair:\s*(?P<repair>\d+),\s*Misc:\s*(?P<misc>\d+)"
    match = re.search(pattern, message_body, re.IGNORECASE)

    if not match:
        return jsonify({"status": "error", "message": "Invalid format."}), 400

    trip_info = match.groupdict()
    vehicle_no = trip_info['truck'].upper()
    
    if not any(t['vehicleNo'] == vehicle_no for t in INITIAL_FLEET):
        return jsonify({"status": "error", "message": f"Truck {vehicle_no} not found"}), 404

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
        "vehicleNo": vehicle_no,
        "date": datetime.now().strftime('%Y-%m-%d'),
        "start": trip_info['from'].strip(),
        "destination": trip_info['to'].strip(),
        "revenue": revenue,
        "cost": total_cost,
        "costBreakdown": breakdown,
        "profit": revenue - total_cost,
        "range": 0,
        "timeTaken": "Unknown",
        "oilConsumed": 0,
        "mileage": 0
    }

    try:
        supabase = get_supabase()
        supabase.table('trips').insert(new_trip).execute()
        
        if not request.is_json:
            return f"""<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Message>✅ Trip recorded for {vehicle_no}. Profit: ₹{new_trip['profit']}</Message>
            </Response>""", 200, {'Content-Type': 'application/xml'}

        return jsonify({"status": "success", "message": f"Trip recorded for {vehicle_no}"})
    except Exception as e:
        print(f"Supabase Insert Error: {e}")
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

def handler(event, context):
    return serverless_wsgi.handle_request(app, event, context)

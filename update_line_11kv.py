"""
UPDATE 11kV LINE DASHBOARD
GID: 723552635 - Automatically adds upload date
"""

import os
import pandas as pd
import requests
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv
from io import StringIO

load_dotenv()

# ========== CONFIG ==========
SHEET_ID = os.getenv('SHEET_ID')
SHEET_GID = os.getenv('LINE_11KV_GID')
COLLECTION_NAME = "line_11kv"

MONGO_URI = os.getenv('MONGO_URI')
MONGO_DB = os.getenv('MONGO_DB')

def log_message(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def safe_int(v): 
    try:
        if pd.isna(v) or v == '':
            return 0
        return int(float(str(v).replace(',', '')))
    except:
        return 0

def safe_float(v): 
    try:
        if pd.isna(v) or v == '':
            return 0.0
        return float(str(v).replace(',', ''))
    except:
        return 0.0

def safe_str(v): 
    return str(v).strip() if pd.notna(v) else ''

def fetch_data():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}"
    log_message(f"📤 Fetching 11kV Line data...")
    
    response = requests.get(url)
    response.raise_for_status()
    
    df = pd.read_csv(StringIO(response.text)).fillna('')
    log_message(f"✅ Fetched {len(df)} rows")
    return df.to_dict('records')

def transform_data(data):
    """Transform data with automatic date fields"""
    transformed = []
    
    # Get today's date for data_as_on_date
    upload_date = datetime.now().strftime('%Y-%m-%d')
    upload_timestamp = datetime.now()
    
    log_message(f"📅 Data will be stamped with date: {upload_date}")
    
    for row in data:
        doc = {
            "name": safe_str(row.get('Line Name') or row.get('Name')),
            "from_substation": safe_str(row.get('From Substation')),
            "to_substation": safe_str(row.get('To Substation')),
            "length_km": safe_float(row.get('Length KM')),
            "conductor_type": safe_str(row.get('Conductor Type')),
            "poles": safe_int(row.get('Poles')),
            "dtr_count": safe_int(row.get('DTR Count')),
            "augmentation_progress": safe_int(row.get('Augmentation %')),
            "status": safe_str(row.get('Status') or 'Active'),
            
            # DATE FIELDS - Automatically added
            "data_as_on_date": upload_date,           # Today's date (YYYY-MM-DD)
            "upload_timestamp": upload_timestamp,      # Full timestamp
            "last_updated": upload_timestamp,          # Keep for compatibility
            "updated_via": "Google Sheets Auto Sync"
        }
        if doc['name']:
            transformed.append(doc)
    return transformed

def update_mongodb(docs):
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db[COLLECTION_NAME]
    
    before = collection.count_documents({})
    log_message(f"📊 Before: {before} records")
    
    if docs:
        collection.delete_many({})
        collection.insert_many(docs)
        after = collection.count_documents({})
        log_message(f"✅ Inserted {len(docs)} new records")
        log_message(f"📊 After: {after} records")
        log_message(f"📅 Data stamped with date: {docs[0]['data_as_on_date']}")
    
    client.close()

def main():
    print("\n" + "="*60)
    print("🔌 11kV LINE DASHBOARD UPDATER")
    print("="*60)
    print(f"GID: {SHEET_GID}")
    print(f"Collection: {COLLECTION_NAME}")
    print("-"*60)
    
    try:
        data = fetch_data()
        if not data:
            return
        
        transformed = transform_data(data)
        log_message(f"🔄 Transformed {len(transformed)} records")
        
        if transformed:
            print(f"\n📅 These records will be stamped with date: {datetime.now().strftime('%Y-%m-%d')}")
            confirm = input("\nUpdate database? (y/n): ").lower()
            if confirm == 'y':
                update_mongodb(transformed)
                print("✅ Update complete!")
            else:
                print("❌ Update cancelled")
        else:
            print("❌ No valid data to transform")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("="*60)

if __name__ == "__main__":
    main()
"""
GOOGLE SHEETS TO MONGODB UPDATER - PUBLIC SHEET VERSION
No authentication needed! Just use your Sheet ID.
Automatically adds upload date to each record.
"""

import os
import pandas as pd
import requests
from pymongo import MongoClient
from datetime import datetime
import json
from dotenv import load_dotenv
from io import StringIO

# Load environment variables
load_dotenv()

# ========== CONFIGURATION ==========
# Get Sheet ID from .env file
SHEET_ID = os.getenv('SHEET_ID', '12ifSl_us1fzuLuQ74dUPnZbP8nlLt9ceMcloBMVUFeUE')

# Sheet GID (0 for centers/administrative overview)
SHEET_GID = os.getenv('CENTERS_GID', '0')

# MongoDB Connection
MONGO_URI = os.getenv('MONGO_URI', 'mongodb+srv://simple_user:Rahul1234@cluster0.5nt5nwr.mongodb.net/')
MONGO_DB = os.getenv('MONGO_DB', 'ims_siliguri')
COLLECTION_NAME = "centers"

# Log file
LOG_FILE = "update_log.txt"

# ========== FUNCTIONS ==========
def log_message(message):
    """Write to log file"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {message}\n")

def fetch_from_public_sheet():
    """Fetch data from public Google Sheet using CSV export"""
    try:
        # Public CSV export URL (no authentication needed!)
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}"
        
        log_message(f"📤 Fetching from: {url}")
        
        # Download the CSV
        response = requests.get(url)
        response.raise_for_status()
        
        # Read CSV into pandas
        csv_data = StringIO(response.text)
        df = pd.read_csv(csv_data)
        
        # Clean data
        df = df.fillna('')  # Replace NaN with empty string
        
        # Convert to list of dictionaries
        data = df.to_dict('records')
        
        log_message(f"✅ Successfully fetched {len(data)} rows")
        log_message(f"📋 Columns found: {', '.join(df.columns)}")
        
        return data, df.columns.tolist()
        
    except Exception as e:
        log_message(f"❌ Error fetching data: {e}")
        log_message("\n🔍 Troubleshooting tips:")
        log_message("1. Make sure your Sheet ID is correct in .env file")
        log_message("2. Make sure your Google Sheet is public (Anyone with link can view)")
        log_message("3. Try opening this URL in browser to test:")
        log_message(f"   {url}")
        return None, None

def transform_data(data, columns):
    """Transform to MongoDB format with automatic date fields"""
    transformed = []
    skipped = 0
    
    # Get today's date for data_as_on_date
    upload_date = datetime.now().strftime('%Y-%m-%d')
    upload_timestamp = datetime.now()
    
    log_message(f"\n🔄 Transforming data... (Data will be stamped with date: {upload_date})")
    
    for idx, row in enumerate(data):
        try:
            # Skip completely empty rows
            if not any(str(v).strip() for v in row.values()):
                skipped += 1
                continue
            
            # Create document - ADJUST THESE BASED ON YOUR COLUMN NAMES
            doc = {
                "name": str(row.get('Center Name') or row.get('Name') or row.get('Center') or '').strip(),
                "region": str(row.get('Region') or row.get('Zone') or '').strip(),
                "division": str(row.get('Division') or row.get('Circle') or '').strip(),
                "ccc_type": str(row.get('Type') or row.get('CCC Type') or 'CCC').strip(),
                "total_consumers": safe_int(row.get('Consumers') or row.get('Total Consumers') or 0),
                "total_staff": safe_int(row.get('Staff') or row.get('Total Staff') or 0),
                "total_dtr": safe_int(row.get('DTR') or row.get('DTRs') or 0),
                "atc_loss_last_month": safe_float(row.get('ATC Last') or row.get('ATC Loss Last') or 0),
                "atc_loss_running_month": safe_float(row.get('ATC Current') or row.get('ATC Loss Current') or 0),
                "td_loss_last_month": safe_float(row.get('TD Last') or row.get('T&D Last') or 0),
                "td_loss_running_month": safe_float(row.get('TD Current') or row.get('T&D Current') or 0),
                
                # DATE FIELDS - Automatically added
                "data_as_on_date": upload_date,           # Today's date (YYYY-MM-DD)
                "upload_timestamp": upload_timestamp,      # Full timestamp
                "last_updated": upload_timestamp,          # For compatibility
                "updated_via": "Google Sheets Auto Sync"
            }
            
            # Only keep if name exists
            if doc['name']:
                transformed.append(doc)
            else:
                skipped += 1
                
        except Exception as e:
            log_message(f"⚠️ Error processing row {idx+1}: {e}")
            skipped += 1
    
    log_message(f"✅ Transformed {len(transformed)} valid records")
    if skipped > 0:
        log_message(f"⚠️ Skipped {skipped} rows")
    
    return transformed

def safe_int(value):
    """Safely convert to int - IMPROVED VERSION"""
    try:
        if pd.isna(value) or value == '' or value is None:
            return 0
        # Handle string numbers with commas
        if isinstance(value, str):
            value = value.replace(',', '').strip()
        return int(float(value))
    except (ValueError, TypeError):
        return 0

def safe_float(value):
    """Safely convert to float - IMPROVED VERSION"""
    try:
        if pd.isna(value) or value == '' or value is None:
            return 0.0
        # Handle string numbers with commas
        if isinstance(value, str):
            value = value.replace(',', '').strip()
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def update_mongodb(documents):
    """Update MongoDB with new data"""
    client = None
    try:
        # Connect to MongoDB
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        collection = db[COLLECTION_NAME]
        
        # Get current count
        before_count = collection.count_documents({})
        log_message(f"\n📊 Current records in database: {before_count}")
        
        if not documents:
            log_message("❌ No documents to insert")
            return False
        
        # Create backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{COLLECTION_NAME}_backup_{timestamp}"
        
        if before_count > 0:
            log_message(f"📦 Creating backup in '{backup_name}'...")
            backup_collection = db[backup_name]
            for doc in collection.find():
                if '_id' in doc:
                    doc.pop('_id')
                backup_collection.insert_one(doc)
            log_message(f"✅ Backup created with {before_count} records")
        
        # Clear main collection
        log_message("🔄 Clearing main collection...")
        collection.delete_many({})
        
        # Insert new data
        log_message(f"📥 Inserting {len(documents)} new records...")
        result = collection.insert_many(documents)
        
        # Show date info
        log_message(f"📅 Data stamped with date: {documents[0]['data_as_on_date']}")
        
        # Verify
        after_count = collection.count_documents({})
        log_message(f"✅ Database now has {after_count} records")
        
        return after_count == len(documents)
        
    except Exception as e:
        log_message(f"❌ MongoDB error: {e}")
        return False
    finally:
        if client:
            client.close()

def show_sample(data, n=3):
    """Show sample data"""
    log_message(f"\n📋 Sample data (first {n} rows):")
    for i, row in enumerate(data[:n]):
        # Show only first few columns for brevity
        preview = {k: v for k, v in list(row.items())[:5]}
        log_message(f"  Row {i+1}: {json.dumps(preview, default=str)}")

# ========== MAIN ==========
def main():
    log_message("\n" + "="*60)
    log_message("🚀 GOOGLE SHEETS TO MONGODB UPDATER")
    log_message("="*60)
    log_message(f"Computer: {os.environ.get('COMPUTERNAME', 'Unknown')}")
    log_message(f"Sheet ID: {SHEET_ID}")
    log_message(f"Sheet GID: {SHEET_GID}")
    log_message(f"Collection: {COLLECTION_NAME}")
    log_message("-"*60)
    
    # Check if Sheet ID is set
    if SHEET_ID == 'YOUR_SHEET_ID_HERE' or not SHEET_ID:
        log_message("❌ Sheet ID not found in .env file!")
        log_message("\nPlease edit your .env file and add:")
        log_message("SHEET_ID=your_actual_sheet_id_here")
        return
    
    # Fetch data
    log_message("\n📤 STEP 1: Fetching from Google Sheets...")
    data, columns = fetch_from_public_sheet()
    
    if not data:
        return
    
    # Show sample
    show_sample(data)
    
    # Transform data
    log_message("\n🔄 STEP 2: Transforming data...")
    transformed = transform_data(data, columns)
    
    if not transformed:
        log_message("❌ No valid data after transformation")
        return
    
    # Confirm
    log_message(f"\n📊 Ready to update {len(transformed)} records")
    log_message(f"📅 These records will be stamped with date: {datetime.now().strftime('%Y-%m-%d')}")
    
    # Ask for confirmation
    confirm = input("\nProceed with update? (y/n): ").strip().lower()
    if confirm != 'y':
        log_message("❌ Update cancelled")
        return
    
    # Update MongoDB
    log_message("\n💾 STEP 3: Updating MongoDB...")
    success = update_mongodb(transformed)
    
    # Summary
    log_message("\n" + "="*60)
    if success:
        log_message("✅✅✅ UPDATE SUCCESSFUL! ✅✅✅")
        log_message(f"📅 All records stamped with date: {datetime.now().strftime('%Y-%m-%d')}")
    else:
        log_message("❌❌❌ UPDATE FAILED! ❌❌❌")
    log_message("="*60)

if __name__ == "__main__":
    main()
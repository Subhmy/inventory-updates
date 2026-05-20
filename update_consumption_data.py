"""
Google Sheets to MongoDB Sync – Inventory Consumption Data
Last Updated: May 19, 2026 - FIXED: Material code decimal issue
"""

import os
import sys
import pandas as pd
import requests
import time
from datetime import datetime
from io import StringIO
from dotenv import load_dotenv

# Add the path to your main project folder
MAIN_PROJECT_PATH = r"D:\inventory-system-siliguri-main"
sys.path.append(MAIN_PROJECT_PATH)

# Now import from app
from app.models.mongo_utils import get_db

load_dotenv()

# Google Sheet ID
SHEET_ID = "1280OvDiM6ff8HRGIpv5x-znxEa5Zfhn1LT9J9E9n0IM"

# Sheet GIDs
SHEET_GIDS = {
    'material_master': 0,
    'transactions_summary': 1477122622,
    'storage_locations': 820449762,
    'current_stock': 329988797
}


def fetch_sheet_data(sheet_name, gid):
    """Fetch CSV data from Google Sheets"""
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    print(f"📥 Fetching {sheet_name}...")
    try:
        r = requests.get(url, timeout=120)
        if r.status_code == 200:
            df = pd.read_csv(StringIO(r.text))
            print(f"   ✅ Loaded {len(df)} rows")
            return df
        else:
            print(f"   ❌ HTTP {r.status_code}")
            return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def clean_transactions_data(df):
    """Clean and prepare transactions data - FIXED for decimal material codes"""
    if df is None or df.empty:
        return df
    
    print(f"   🔄 Cleaning {len(df)} records...")
    
    # Convert period to string and clean
    if 'period' in df.columns:
        df['period'] = df['period'].astype(str).str.strip()
    
    # Convert numeric columns
    numeric_cols = ['consumption_quantity', 'incoming_quantity', 'transaction_count', 'year', 'month', 'quarter']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Handle date formats - convert various date formats to consistent YYYY-MM
    def normalize_period(period_str):
        if not period_str:
            return period_str
        period_str = str(period_str).strip()
        # Handle MM/DD/YYYY format
        if '/' in period_str:
            parts = period_str.split('/')
            if len(parts) == 3:
                return f"{parts[2]}-{parts[0].zfill(2)}"
        return period_str
    
    if 'period' in df.columns:
        df['period'] = df['period'].apply(normalize_period)
    
    # CRITICAL FIX: Clean material_code - remove .0 and convert to string without decimals
    if 'material_code' in df.columns:
        # Convert to string first
        df['material_code'] = df['material_code'].astype(str).str.strip()
        # Remove .0 at the end if present
        df['material_code'] = df['material_code'].str.replace(r'\.0$', '', regex=True)
        # Remove any other decimal points
        df['material_code'] = df['material_code'].str.replace(r'\.\d+$', '', regex=True)
        print(f"   📊 Sample material codes after cleaning: {df['material_code'].unique()[:5]}")
    
    # Fill missing values
    if 'plant' in df.columns:
        df['plant'] = df['plant'].fillna('all').astype(str).str.strip()
    
    if 'material_group' in df.columns:
        df['material_group'] = df['material_group'].fillna('Uncategorized').astype(str).str.strip()
    
    if 'unit' in df.columns:
        df['unit'] = df['unit'].fillna('Units').astype(str).str.strip()
    
    if 'material_description' in df.columns:
        df['material_description'] = df['material_description'].fillna('Unknown').astype(str).str.strip()
    
    print(f"   ✅ Cleaned {len(df)} records")
    return df


def clean_material_master(df):
    """Clean material master data"""
    if df is None or df.empty:
        return df
    
    # Clean material_code - remove .0
    if 'Material_Code' in df.columns:
        df['Material_Code'] = df['Material_Code'].astype(str).str.strip()
        df['Material_Code'] = df['Material_Code'].str.replace(r'\.0$', '', regex=True)
        df['Material_Code'] = df['Material_Code'].str.replace(r'\.\d+$', '', regex=True)
    
    return df


def update_mongodb(collection_name, df, batch_size=1000):
    """Update MongoDB collection in batches"""
    if df is None or df.empty:
        print(f"   ⚠️ No data for {collection_name}")
        return
    
    db = get_db()
    if db is None:
        print("   ❌ DB connection failed")
        return
    
    coll = db[collection_name]
    
    # Clear existing
    try:
        result = coll.delete_many({})
        print(f"   🗑️  Cleared {result.deleted_count} records from {collection_name}")
    except Exception as e:
        print(f"   ⚠️ Delete issue: {e}")
    
    # Convert to records
    records = df.to_dict('records')
    total = len(records)
    inserted = 0
    
    print(f"   🔄 Inserting {total} records in batches of {batch_size}...")
    
    for i in range(0, total, batch_size):
        batch = records[i:i+batch_size]
        try:
            coll.insert_many(batch, ordered=False)
            inserted += len(batch)
            print(f"   📦 Batch {i//batch_size + 1}: {len(batch)} records ({inserted}/{total})")
        except Exception as e:
            print(f"   ⚠️ Batch error: {e}")
            # Try one by one
            for record in batch:
                try:
                    coll.insert_one(record)
                    inserted += 1
                except:
                    pass
    
    print(f"   ✅ {inserted} records → {collection_name}")


def create_consumption_summary(db):
    """Create consumption_summary from inventory_transactions"""
    print("\n📊 Creating consumption_summary from inventory_transactions...")
    
    # Clear existing
    db.consumption_summary.delete_many({})
    
    # Get all transactions
    all_transactions = list(db.inventory_transactions.find({}))
    print(f"   📊 Total transactions: {len(all_transactions)}")
    
    if not all_transactions:
        print("   ⚠️ No transactions found")
        return
    
    # Filter to consumption records (consumption_quantity > 0)
    consumption_records = [t for t in all_transactions if t.get('consumption_quantity', 0) > 0]
    print(f"   📊 Consumption records: {len(consumption_records)}")
    
    if not consumption_records:
        print("   ⚠️ No consumption records found")
        return
    
    # Convert to DataFrame for easier processing
    df = pd.DataFrame(consumption_records)
    
    # Remove _id field
    if '_id' in df.columns:
        df = df.drop('_id', axis=1)
    
    # Ensure required columns exist
    required_cols = ['period', 'period_type', 'material_code', 'material_description', 
                     'material_group', 'consumption_quantity', 'unit', 'plant', 'year', 'month', 'quarter']
    
    for col in required_cols:
        if col not in df.columns:
            df[col] = None
    
    # Rename consumption_quantity to quantity for consistency
    df['quantity'] = df['consumption_quantity']
    
    # Select and order columns
    final_cols = ['period', 'period_type', 'material_code', 'material_name', 'quantity', 
                  'unit', 'material_group', 'plant', 'year', 'month', 'quarter', 'last_updated']
    
    # Create material_name from material_description
    df['material_name'] = df['material_description']
    
    # Fill missing values
    df['material_name'] = df['material_name'].fillna('Unknown')
    df['unit'] = df['unit'].fillna('Units')
    df['material_group'] = df['material_group'].fillna('Uncategorized')
    df['plant'] = df['plant'].fillna('all')
    df['last_updated'] = datetime.now()
    
    # Keep only needed columns
    for col in final_cols:
        if col not in df.columns:
            df[col] = None
    
    df = df[final_cols]
    
    print(f"   📊 Final consumption summary records: {len(df)}")
    
    # Update MongoDB
    update_mongodb('consumption_summary', df, batch_size=1000)
    
    # Verify specific material
    rbt_count = db.consumption_summary.count_documents({'material_code': '502010921'})
    if rbt_count > 0:
        print(f"\n   ✅ SUCCESS: {rbt_count} records found for material 502010921 (COND ACSR RBT 50SMM)")
        
        # Show summary for RBT material
        pipeline = [
            {'$match': {'material_code': '502010921'}},
            {'$group': {
                '_id': None,
                'total_quantity': {'$sum': '$quantity'},
                'record_count': {'$sum': 1},
                'plants': {'$addToSet': '$plant'}
            }}
        ]
        result = list(db.consumption_summary.aggregate(pipeline))
        if result:
            print(f"   📊 Total consumption for RBT 50SMM: {result[0]['total_quantity']:.2f} KM")
            print(f"   📊 Number of records: {result[0]['record_count']}")
            print(f"   📊 Plants with data: {sorted(result[0]['plants'])}")
    else:
        print(f"\n   ⚠️ WARNING: No records found for material 502010921")
        print(f"   Available materials (first 10): {db.consumption_summary.distinct('material_code')[:10]}")


def main():
    print("=" * 70)
    print("📊 INVENTORY DATA SYNC - FIXED (Material Code Decimal Issue)")
    print("=" * 70)
    
    try:
        # 1. Fetch transactions_summary (MAIN DATA)
        print("\n" + "-" * 50)
        print("STEP 1: Fetching transactions_summary from Google Sheets")
        print("-" * 50)
        trans_df = fetch_sheet_data('transactions_summary', SHEET_GIDS['transactions_summary'])
        
        if trans_df is not None:
            # Check for RBT material before cleaning
            rbt_before = trans_df[trans_df['material_code'].astype(str).str.contains('502010921', na=False)]
            if not rbt_before.empty:
                print(f"\n   ✅ Found {len(rbt_before)} records for material 502010921 before cleaning")
            else:
                print(f"\n   ⚠️ Material 502010921 not found in source data!")
                print(f"   Available material codes: {trans_df['material_code'].astype(str).unique()[:5]}")
            
            # Clean data
            trans_df = clean_transactions_data(trans_df)
            
            # Verify after cleaning
            rbt_after = trans_df[trans_df['material_code'] == '502010921']
            if not rbt_after.empty:
                print(f"\n   ✅ After cleaning: {len(rbt_after)} records for material 502010921")
                print(f"   📊 Total consumption: {rbt_after['consumption_quantity'].sum():.2f} KM")
            
            # Update inventory_transactions
            print(f"\n   📤 Updating inventory_transactions...")
            update_mongodb('inventory_transactions', trans_df, batch_size=500)
        
        # 2. Fetch material_master
        print("\n" + "-" * 50)
        print("STEP 2: Fetching material_master")
        print("-" * 50)
        mat_df = fetch_sheet_data('material_master', SHEET_GIDS['material_master'])
        if mat_df is not None:
            mat_df = clean_material_master(mat_df)
            update_mongodb('material_master', mat_df, batch_size=500)
        
        # 3. Fetch storage_locations
        print("\n" + "-" * 50)
        print("STEP 3: Fetching storage_locations")
        print("-" * 50)
        loc_df = fetch_sheet_data('storage_locations', SHEET_GIDS['storage_locations'])
        if loc_df is not None:
            update_mongodb('storage_locations', loc_df, batch_size=500)
        
        # 4. Create consumption_summary
        print("\n" + "-" * 50)
        print("STEP 4: Creating consumption_summary")
        print("-" * 50)
        db = get_db()
        if db is not None:
            create_consumption_summary(db)
        
        print("\n" + "=" * 70)
        print("✅ SYNC COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
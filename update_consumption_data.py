"""
Google Sheets to MongoDB Sync – Inventory Consumption Data
Last Updated: May 22, 2026 - FIXED: Plant code decimal removal (.0)
"""

import os
import sys
import pandas as pd
import requests
import time
import re
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


def clean_plant_codes(value):
    """Clean plant code - remove .0 and convert to string"""
    if pd.isna(value):
        return 'all'
    # Convert to string
    val_str = str(value).strip()
    # Remove .0 at the end
    val_str = re.sub(r'\.0$', '', val_str)
    # Remove any other decimal points
    val_str = re.sub(r'\.\d+$', '', val_str)
    # Handle 'nan' string
    if val_str.lower() == 'nan':
        return 'all'
    return val_str


def clean_material_codes(value):
    """Clean material code - remove .0 and convert to string"""
    if pd.isna(value):
        return ''
    # Convert to string
    val_str = str(value).strip()
    # Remove .0 at the end
    val_str = re.sub(r'\.0$', '', val_str)
    # Remove any other decimal points
    val_str = re.sub(r'\.\d+$', '', val_str)
    return val_str


def clean_transactions_data(df):
    """Clean and prepare transactions data - FIXED: cleans plant codes"""
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
    
    def normalize_period(period_str):
        if not period_str:
            return period_str
        period_str = str(period_str).strip()
        if '/' in period_str:
            parts = period_str.split('/')
            if len(parts) == 3:
                return f"{parts[2]}-{parts[0].zfill(2)}"
        return period_str
    
    if 'period' in df.columns:
        df['period'] = df['period'].apply(normalize_period)
    
    # Clean material_code - remove .0
    if 'material_code' in df.columns:
        df['material_code'] = df['material_code'].apply(clean_material_codes)
        print(f"   📊 Sample material codes after cleaning: {df['material_code'].unique()[:5]}")
    
    # ============ CRITICAL FIX: Clean plant codes - remove .0 ============
    if 'plant' in df.columns:
        df['plant'] = df['plant'].apply(clean_plant_codes)
        print(f"   📊 Sample plant codes after cleaning: {df['plant'].unique()[:10]}")
    
    # Clean material_group
    if 'material_group' in df.columns:
        df['material_group'] = df['material_group'].fillna('Uncategorized').astype(str).str.strip()
    
    # Clean unit
    if 'unit' in df.columns:
        df['unit'] = df['unit'].fillna('Units').astype(str).str.strip()
    
    # Clean material_description
    if 'material_description' in df.columns:
        df['material_description'] = df['material_description'].fillna('Unknown').astype(str).str.strip()
    
    print(f"   ✅ Cleaned {len(df)} records")
    return df


def process_current_stock(df, storage_locations_df):
    """
    Process current stock data and map plant codes to division names
    FIXED: cleans plant codes before processing
    """
    if df is None or df.empty:
        return None
    
    print(f"   📋 Processing {len(df)} stock records...")
    
    # Create plant to division mapping from storage_locations
    plant_to_division = {}
    if storage_locations_df is not None and not storage_locations_df.empty:
        for _, row in storage_locations_df.iterrows():
            plant = clean_plant_codes(row.get('Plant', ''))
            division = str(row.get('division', '')).strip()
            if plant and division and plant != 'all':
                plant_to_division[plant] = division
    print(f"   📋 Loaded {len(plant_to_division)} plant-to-division mappings")
    print(f"   📋 Sample plants: {list(plant_to_division.keys())[:5]}")
    
    records = []
    for _, row in df.iterrows():
        # Get plant code and clean it
        plant = clean_plant_codes(row.get('plant', ''))
        if not plant or plant == 'all':
            continue
        
        # Get division name from mapping
        division_name = plant_to_division.get(plant, plant)
        
        # Get material code and clean it
        material_code = clean_material_codes(row.get('material_code', ''))
        if not material_code:
            continue
        
        # Get current stock value
        current_stock = 0
        if 'current_stock' in df.columns:
            try:
                current_stock = float(row.get('current_stock', 0))
            except:
                current_stock = 0
        
        # Get stock value
        stock_value = 0
        if 'stock_value' in df.columns:
            try:
                stock_value = float(row.get('stock_value', 0))
            except:
                stock_value = 0
        
        record = {
            'plant': plant,
            'division': division_name,
            'material_code': material_code,
            'material_description': str(row.get('material_description', '')).strip() if 'material_description' in df.columns else '',
            'storage_location': str(row.get('storage_location', '')).strip() if 'storage_location' in df.columns else plant,
            'unit': str(row.get('unit', 'Units')).strip() if 'unit' in df.columns else 'Units',
            'current_stock': current_stock,
            'stock_value': stock_value,
            'material_group': str(row.get('material_group', '')).strip() if 'material_group' in df.columns else '',
            'last_updated': datetime.now()
        }
        records.append(record)
    
    print(f"   📊 Processed {len(records)} stock records")
    if records:
        sample = records[0]
        print(f"   📝 Sample: Plant {sample['plant']} ({sample['division']}) - {sample['material_code']}: {sample['current_stock']} {sample['unit']}")
    
    return pd.DataFrame(records) if records else None


def process_storage_locations(df):
    """Process storage locations data - FIXED: cleans plant codes"""
    if df is None or df.empty:
        return df
    
    print(f"   📋 Processing {len(df)} storage locations...")
    
    records = []
    for _, row in df.iterrows():
        plant = clean_plant_codes(row.get('Plant', ''))
        if not plant or plant == 'all':
            continue
        
        record = {
            'plant': plant,
            'location_name': str(row.get('location_name', '')).strip(),
            'type': str(row.get('type', '')).strip(),
            'region': str(row.get('region', '')).strip(),
            'division': str(row.get('division', '')).strip(),
            'last_updated': datetime.now()
        }
        records.append(record)
    
    print(f"   📊 Processed {len(records)} storage locations")
    print(f"   📋 Sample plants: {[r['plant'] for r in records[:5]]}")
    return pd.DataFrame(records) if records else None


def process_material_master(df):
    """Process material master data - FIXED: cleans material codes"""
    if df is None or df.empty:
        return df
    
    print(f"   📋 Processing {len(df)} material master records...")
    
    records = []
    for _, row in df.iterrows():
        material_code = clean_material_codes(row.get('Material_Code', ''))
        if not material_code:
            continue
        
        record = {
            'Material_Code': material_code,
            'Material Description': str(row.get('Material Description', '')).strip(),
            'Unit of Entry': str(row.get('Unit of Entry', '')).strip(),
            'Material Group': str(row.get('Material Group', '')).strip(),
            'Manual_Min_stock': row.get('Manual_Min_stock', None),
            'Manual_Reorder_level': row.get('Manual_Reorder_level', None),
            'Unit_Price': row.get('Unit_Price', None),
            'last_updated': datetime.now()
        }
        records.append(record)
    
    print(f"   📊 Processed {len(records)} material master records")
    return pd.DataFrame(records) if records else None


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
    
    try:
        result = coll.delete_many({})
        print(f"   🗑️  Cleared {result.deleted_count} records from {collection_name}")
    except Exception as e:
        print(f"   ⚠️ Delete issue: {e}")
    
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
            for record in batch:
                try:
                    coll.insert_one(record)
                    inserted += 1
                except:
                    pass
    
    print(f"   ✅ {inserted} records → {collection_name}")


def create_consumption_summary(db):
    """Create consumption_summary from inventory_transactions - FIXED: cleans plant codes"""
    print("\n📊 Creating consumption_summary from inventory_transactions...")
    
    db.consumption_summary.delete_many({})
    
    all_transactions = list(db.inventory_transactions.find({}))
    print(f"   📊 Total transactions: {len(all_transactions)}")
    
    if not all_transactions:
        print("   ⚠️ No transactions found")
        return
    
    consumption_records = [t for t in all_transactions if t.get('consumption_quantity', 0) > 0]
    print(f"   📊 Consumption records: {len(consumption_records)}")
    
    if not consumption_records:
        print("   ⚠️ No consumption records found")
        return
    
    df = pd.DataFrame(consumption_records)
    
    if '_id' in df.columns:
        df = df.drop('_id', axis=1)
    
    required_cols = ['period', 'period_type', 'material_code', 'material_description', 
                     'material_group', 'consumption_quantity', 'unit', 'plant', 'year', 'month', 'quarter']
    
    for col in required_cols:
        if col not in df.columns:
            df[col] = None
    
    # ============ CRITICAL FIX: Clean plant codes in consumption_summary ============
    if 'plant' in df.columns:
        df['plant'] = df['plant'].apply(clean_plant_codes)
        print(f"   📊 Plant codes in consumption_summary after cleaning: {df['plant'].unique()[:10]}")
    
    # Clean material codes
    if 'material_code' in df.columns:
        df['material_code'] = df['material_code'].apply(clean_material_codes)
    
    df['quantity'] = df['consumption_quantity']
    final_cols = ['period', 'period_type', 'material_code', 'material_name', 'quantity', 
                  'unit', 'material_group', 'plant', 'year', 'month', 'quarter', 'last_updated']
    
    df['material_name'] = df['material_description']
    df['material_name'] = df['material_name'].fillna('Unknown')
    df['unit'] = df['unit'].fillna('Units')
    df['material_group'] = df['material_group'].fillna('Uncategorized')
    df['last_updated'] = datetime.now()
    
    for col in final_cols:
        if col not in df.columns:
            df[col] = None
    
    df = df[final_cols]
    
    print(f"   📊 Final consumption summary records: {len(df)}")
    update_mongodb('consumption_summary', df, batch_size=1000)
    
    # Verify plant codes
    plants = db.consumption_summary.distinct('plant')
    print(f"   📊 Distinct plants in consumption_summary: {sorted(plants)[:15]}")


def main():
    print("=" * 70)
    print("📊 INVENTORY DATA SYNC - COMPLETE (Plant Code Fixed)")
    print("=" * 70)
    
    try:
        # 1. Fetch storage_locations FIRST (needed for plant mapping)
        print("\n" + "-" * 50)
        print("STEP 1: Fetching storage_locations")
        print("-" * 50)
        loc_df = fetch_sheet_data('storage_locations', SHEET_GIDS['storage_locations'])
        storage_locations_df = process_storage_locations(loc_df) if loc_df is not None else None
        if storage_locations_df is not None:
            update_mongodb('storage_locations', storage_locations_df, batch_size=500)
        
        # 2. Fetch current_stock (using storage_locations for mapping)
        print("\n" + "-" * 50)
        print("STEP 2: Fetching current_stock")
        print("-" * 50)
        stock_df = fetch_sheet_data('current_stock', SHEET_GIDS['current_stock'])
        if stock_df is not None:
            processed_stock = process_current_stock(stock_df, storage_locations_df)
            if processed_stock is not None and not processed_stock.empty:
                update_mongodb('current_stock', processed_stock, batch_size=500)
            else:
                print("   ⚠️ No valid stock records found")
        else:
            print("   ❌ Failed to fetch current_stock sheet")
        
        # 3. Fetch material_master
        print("\n" + "-" * 50)
        print("STEP 3: Fetching material_master")
        print("-" * 50)
        mat_df = fetch_sheet_data('material_master', SHEET_GIDS['material_master'])
        if mat_df is not None:
            processed_material_master = process_material_master(mat_df)
            update_mongodb('material_master', processed_material_master, batch_size=500)
        
        # 4. Fetch transactions_summary
        print("\n" + "-" * 50)
        print("STEP 4: Fetching transactions_summary")
        print("-" * 50)
        trans_df = fetch_sheet_data('transactions_summary', SHEET_GIDS['transactions_summary'])
        if trans_df is not None:
            trans_df = clean_transactions_data(trans_df)
            update_mongodb('inventory_transactions', trans_df, batch_size=500)
        
        # 5. Create consumption_summary
        print("\n" + "-" * 50)
        print("STEP 5: Creating consumption_summary")
        print("-" * 50)
        db = get_db()
        if db is not None:
            create_consumption_summary(db)
        
        # 6. Verification
        print("\n" + "-" * 50)
        print("STEP 6: Verification")
        print("-" * 50)
        if db is not None:
            stock_count = db.current_stock.count_documents({})
            loc_count = db.storage_locations.count_documents({})
            trans_count = db.inventory_transactions.count_documents({})
            summary_count = db.consumption_summary.count_documents({})
            print(f"   📊 current_stock: {stock_count} records")
            print(f"   📊 storage_locations: {loc_count} records")
            print(f"   📊 inventory_transactions: {trans_count} records")
            print(f"   📊 consumption_summary: {summary_count} records")
            
            # Show sample plants from consumption_summary
            plants = db.consumption_summary.distinct('plant')
            print(f"   📊 Plants in consumption_summary: {sorted(plants)[:15]}")
            
            # Check for decimal issue
            decimal_plants = [p for p in plants if '.0' in str(p)]
            if decimal_plants:
                print(f"   ⚠️ WARNING: Still found decimal plants: {decimal_plants[:5]}")
            else:
                print(f"   ✅ No decimal plants found - FIXED!")
        
        print("\n" + "=" * 70)
        print("✅ SYNC COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
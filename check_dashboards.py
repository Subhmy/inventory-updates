"""
Check data for all three dashboards
Run this to verify your data is correctly loaded in SEPARATE collections
"""

from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
MONGO_DB = os.getenv('MONGO_DB')

# Define the three collections
COLLECTIONS = {
    "substation": {
        "name": "substation_33_11kv",
        "display": "🏭 33/11kV SUB-STATION",
        "icon": "🏭"
    },
    "line_33kv": {
        "name": "line_33kv",
        "display": "⚡ 33kV LINE",
        "icon": "⚡"
    },
    "line_11kv": {
        "name": "line_11kv",
        "display": "🔌 11kV LINE",
        "icon": "🔌"
    }
}

def print_header(text):
    print("\n" + "="*70)
    print(f" {text}")
    print("="*70)

def print_success(text):
    print(f"   ✅ {text}")

def print_warning(text):
    print(f"   ⚠️  {text}")

def print_error(text):
    print(f"   ❌ {text}")

def check_substation_collection(collection):
    """Check 33/11kV Sub-Station collection"""
    total = collection.count_documents({})
    print(f"\n{COLLECTIONS['substation']['icon']} {COLLECTIONS['substation']['display']} DASHBOARD")
    print("-" * 50)
    print_success(f"Total records: {total}")
    
    if total == 0:
        print_error("No data found! Run update_substation_33_11kv.py first.")
        return False
    
    # Aggregation stats
    pipeline = [
        {"$group": {
            "_id": None,
            "total_capacity": {"$sum": "$capacity_mva"},
            "total_ptrs": {"$sum": "$ptr_count"},
            "total_dtrs": {"$sum": "$dtr_count"},
            "avg_capacity": {"$avg": "$capacity_mva"}
        }}
    ]
    stats = list(collection.aggregate(pipeline))
    if stats:
        print_success(f"Total Capacity: {stats[0].get('total_capacity', 0):.2f} MVA")
        print_success(f"Total PTRs: {stats[0].get('total_ptrs', 0)}")
        print_success(f"Total DTRs: {stats[0].get('total_dtrs', 0)}")
        print_success(f"Avg Capacity: {stats[0].get('avg_capacity', 0):.2f} MVA")
    
    # Sample record
    sample = collection.find_one({}, {
        'name': 1, 'region': 1, 'division': 1, 
        'capacity_mva': 1, 'ptr_count': 1, 'dtr_count': 1
    })
    if sample:
        print("\n   📋 Sample record:")
        for key, value in sample.items():
            if key != '_id':
                print(f"      • {key}: {value}")
    
    return True

def check_line_33kv_collection(collection):
    """Check 33kV Line collection"""
    total = collection.count_documents({})
    print(f"\n{COLLECTIONS['line_33kv']['icon']} {COLLECTIONS['line_33kv']['display']} DASHBOARD")
    print("-" * 50)
    print_success(f"Total records: {total}")
    
    if total == 0:
        print_error("No data found! Run update_line_33kv.py first.")
        return False
    
    # Aggregation stats
    pipeline = [
        {"$group": {
            "_id": None,
            "total_length": {"$sum": "$length_km"},
            "avg_length": {"$avg": "$length_km"},
            "total_towers": {"$sum": "$towers"},
            "avg_augmentation": {"$avg": "$augmentation_progress"}
        }}
    ]
    stats = list(collection.aggregate(pipeline))
    if stats:
        print_success(f"Total Length: {stats[0].get('total_length', 0):.2f} km")
        print_success(f"Avg Length: {stats[0].get('avg_length', 0):.2f} km")
        print_success(f"Total Towers: {stats[0].get('total_towers', 0)}")
        print_success(f"Avg Augmentation: {stats[0].get('avg_augmentation', 0):.1f}%")
    
    # Sample record
    sample = collection.find_one({}, {
        'name': 1, 'from_substation': 1, 'to_substation': 1,
        'length_km': 1, 'conductor_type': 1, 'towers': 1
    })
    if sample:
        print("\n   📋 Sample record:")
        for key, value in sample.items():
            if key != '_id':
                print(f"      • {key}: {value}")
    
    return True

def check_line_11kv_collection(collection):
    """Check 11kV Line collection"""
    total = collection.count_documents({})
    print(f"\n{COLLECTIONS['line_11kv']['icon']} {COLLECTIONS['line_11kv']['display']} DASHBOARD")
    print("-" * 50)
    print_success(f"Total records: {total}")
    
    if total == 0:
        print_error("No data found! Run update_line_11kv.py first.")
        return False
    
    # Aggregation stats
    pipeline = [
        {"$group": {
            "_id": None,
            "total_length": {"$sum": "$length_km"},
            "avg_length": {"$avg": "$length_km"},
            "total_poles": {"$sum": "$poles"},
            "total_dtrs": {"$sum": "$dtr_count"},
            "avg_augmentation": {"$avg": "$augmentation_progress"}
        }}
    ]
    stats = list(collection.aggregate(pipeline))
    if stats:
        print_success(f"Total Length: {stats[0].get('total_length', 0):.2f} km")
        print_success(f"Avg Length: {stats[0].get('avg_length', 0):.2f} km")
        print_success(f"Total Poles: {stats[0].get('total_poles', 0)}")
        print_success(f"Total DTRs: {stats[0].get('total_dtrs', 0)}")
        print_success(f"Avg Augmentation: {stats[0].get('avg_augmentation', 0):.1f}%")
    
    # Sample record
    sample = collection.find_one({}, {
        'name': 1, 'from_substation': 1, 'to_substation': 1,
        'length_km': 1, 'conductor_type': 1, 'poles': 1, 'dtr_count': 1
    })
    if sample:
        print("\n   📋 Sample record:")
        for key, value in sample.items():
            if key != '_id':
                print(f"      • {key}: {value}")
    
    return True

def get_summary_stats(db):
    """Get summary statistics across all dashboards"""
    print("\n" + "="*70)
    print(" 📊 SUMMARY STATISTICS")
    print("="*70)
    
    total_records = 0
    dashboard_stats = []
    
    # Check each collection
    for key, config in COLLECTIONS.items():
        try:
            count = db[config["name"]].count_documents({})
            total_records += count
            status = "✅" if count > 0 else "❌"
            print(f"   {config['icon']} {config['display']}: {count} records {status}")
        except Exception as e:
            print(f"   {config['icon']} {config['display']}: Error - {e}")
    
    print("-" * 70)
    print_success(f"TOTAL RECORDS ACROSS ALL DASHBOARDS: {total_records}")
    
    return total_records

def main():
    print_header(f"DASHBOARD DATA VERIFICATION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Connect to MongoDB
    try:
        print("\n📦 Connecting to MongoDB...")
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        print_success(f"Connected to database: {MONGO_DB}")
        
        # List all collections
        collections = db.list_collection_names()
        print_success(f"Available collections: {', '.join(collections)}")
        
    except Exception as e:
        print_error(f"Failed to connect to MongoDB: {e}")
        input("\nPress Enter to exit...")
        return
    
    # Check each dashboard
    all_success = True
    
    # Check 33/11kV Sub-Station
    try:
        substation_collection = db[COLLECTIONS["substation"]["name"]]
        if not check_substation_collection(substation_collection):
            all_success = False
    except Exception as e:
        print_error(f"Error checking substation collection: {e}")
        all_success = False
    
    # Check 33kV Line
    try:
        line_33kv_collection = db[COLLECTIONS["line_33kv"]["name"]]
        if not check_line_33kv_collection(line_33kv_collection):
            all_success = False
    except Exception as e:
        print_error(f"Error checking 33kV line collection: {e}")
        all_success = False
    
    # Check 11kV Line
    try:
        line_11kv_collection = db[COLLECTIONS["line_11kv"]["name"]]
        if not check_line_11kv_collection(line_11kv_collection):
            all_success = False
    except Exception as e:
        print_error(f"Error checking 11kV line collection: {e}")
        all_success = False
    
    # Show summary
    total = get_summary_stats(db)
    
    # Final verdict
    print_header("FINAL VERDICT")
    
    if all_success and total > 0:
        print("   ✅✅✅ ALL DASHBOARDS HAVE DATA! ✅✅✅")
        print("\n   🎉 Your setup is complete and working perfectly!")
        print("\n   To update data again, run:")
        print("   • run_all_updates.bat  (updates everything)")
    elif total > 0:
        print("   ⚠️  SOME DASHBOARDS HAVE DATA, SOME ARE EMPTY")
        print("\n   Run the individual updaters for empty dashboards:")
        print("   • python update_substation_33_11kv.py")
        print("   • python update_line_33kv.py")
        print("   • python update_line_11kv.py")
    else:
        print("   ❌❌❌ NO DATA FOUND IN ANY DASHBOARD! ❌❌❌")
        print("\n   Please run the updaters first:")
        print("   • run_all_updates.bat")
        print("\n   Make sure your Google Sheets have data and are public!")
    
    client.close()
    print("\n" + "="*70)

if __name__ == "__main__":
    main()
    input("\nPress Enter to exit...")
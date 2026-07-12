#!/usr/bin/env python3
"""
Fix file paths in the database after sorting
"""

from alloy_db import get_db
import os
from pathlib import Path

# Mapping of old patterns to new locations
OLD_BASE = "/Users/r/desktop/ndfeb_data"
NEW_BASE = "/Users/r/desktop/ndfeb_data/sorted_v2"

# File type to folder mapping
FOLDER_MAP = {
    'XRD': 'xrd',
    'VSM': 'mh',
    'MH': 'mh',
    'SEM': 'sem',
    'EDS': 'icp',
    'CSV': 'icp',
}

def fix_paths():
    db = get_db()
    
    # Get all characterization records
    db.cursor.execute("""
        SELECT id, sample_id, char_type, file_path 
        FROM characterization
        WHERE file_path IS NOT NULL AND file_path != ''
    """)
    
    records = db.cursor.fetchall()
    fixed = 0
    not_found = []
    
    for row in records:
        char_id = row['id']
        sample_id = row['sample_id']
        char_type = row['char_type']
        old_path = row['file_path']
        
        # Skip if path is already in sorted folder
        if 'sorted_v2' in old_path:
            continue
        
        # Extract filename
        filename = os.path.basename(old_path)
        
        # Determine new folder
        folder = FOLDER_MAP.get(char_type, 'other')
        
        # Build new path
        new_path = os.path.join(NEW_BASE, folder, filename)
        
        # Check if file exists
        if os.path.exists(new_path):
            # Update database
            db.cursor.execute(
                "UPDATE characterization SET file_path = %s WHERE id = %s",
                (new_path, char_id)
            )
            fixed += 1
            print(f"✅ {sample_id} ({char_type}): {filename} → fixed")
        else:
            # Try to find the file
            found = False
            for folder_name in ['xrd', 'mh', 'sem', 'icp', 'other']:
                test_path = os.path.join(NEW_BASE, folder_name, filename)
                if os.path.exists(test_path):
                    db.cursor.execute(
                        "UPDATE characterization SET file_path = %s WHERE id = %s",
                        (test_path, char_id)
                    )
                    fixed += 1
                    found = True
                    print(f"✅ {sample_id} ({char_type}): {filename} → found in {folder_name}")
                    break
            
            if not found:
                not_found.append((sample_id, char_type, filename))
                print(f"❌ {sample_id} ({char_type}): {filename} → not found")
    
    db.commit()
    db.close()
    
    print(f"\n📊 Summary:")
    print(f"  Fixed: {fixed}")
    print(f"  Not found: {len(not_found)}")
    
    if not_found:
        print("\n❌ Files not found:")
        for sample_id, char_type, filename in not_found:
            print(f"  {sample_id} ({char_type}): {filename}")

if __name__ == "__main__":
    fix_paths()

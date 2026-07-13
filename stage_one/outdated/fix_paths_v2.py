#!/usr/bin/env python3
"""
Fix file paths - also handles .raw to .xy conversion
"""

from alloy_db import get_db
import os
from pathlib import Path

NEW_BASE = "/Users/r/desktop/ndfeb_data/sorted_v2"

def fix_paths():
    db = get_db()
    
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
        
        # Skip if already fixed
        if 'sorted_v2' in old_path:
            print(f"⏭️  {sample_id}: already fixed")
            continue
        
        # Extract filename and base
        filename = os.path.basename(old_path)
        base = os.path.splitext(filename)[0]
        
        # Determine new folder
        if char_type == 'XRD':
            folder = 'xrd'
            # Try .xy first, then .raw
            for ext in ['.xy', '.raw']:
                new_path = os.path.join(NEW_BASE, folder, base + ext)
                if os.path.exists(new_path):
                    db.cursor.execute(
                        "UPDATE characterization SET file_path = %s WHERE id = %s",
                        (new_path, char_id)
                    )
                    fixed += 1
                    print(f"✅ {sample_id}: {filename} → {base}{ext}")
                    break
            else:
                not_found.append((sample_id, char_type, filename))
                print(f"❌ {sample_id}: {filename} not found")
        elif char_type in ['VSM', 'MH']:
            folder = 'mh'
            new_path = os.path.join(NEW_BASE, folder, filename)
            if os.path.exists(new_path):
                db.cursor.execute(
                    "UPDATE characterization SET file_path = %s WHERE id = %s",
                    (new_path, char_id)
                )
                fixed += 1
                print(f"✅ {sample_id}: {filename} → fixed")
            else:
                not_found.append((sample_id, char_type, filename))
                print(f"❌ {sample_id}: {filename} not found")
        else:
            # Other types
            for folder in ['sem', 'icp', 'other']:
                new_path = os.path.join(NEW_BASE, folder, filename)
                if os.path.exists(new_path):
                    db.cursor.execute(
                        "UPDATE characterization SET file_path = %s WHERE id = %s",
                        (new_path, char_id)
                    )
                    fixed += 1
                    print(f"✅ {sample_id}: {filename} → found in {folder}")
                    break
            else:
                not_found.append((sample_id, char_type, filename))
                print(f"❌ {sample_id}: {filename} not found")
    
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

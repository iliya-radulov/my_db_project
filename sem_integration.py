"""
SEM Integration Module
Parses .tif files and stores metadata in the database
"""

import os
import re
from pathlib import Path
from parse_sem_fast import parse_sem_file
from alloy_db import get_db

def import_sem_file(file_path, sample_id, db=None):
    """
    Import an SEM .tif file and store metadata in the database
    
    Args:
        file_path: Path to the .tif file
        sample_id: Sample ID to link to
        db: Optional database connection (if None, creates one)
    
    Returns:
        dict with import results
    """
    close_db = False
    if db is None:
        db = get_db()
        close_db = True
    
    try:
        # Parse the SEM file
        result = parse_sem_file(file_path)
        
        if 'error' in result:
            return {'success': False, 'error': result['error']}
        
        # Create characterization record
        char_id = db.add_characterization(
            sample_id=sample_id,
            char_type='SEM',
            instrument='Zeiss SEM',
            file_path=file_path,
            parameters={
                'magnification': result.get('magnification'),
                'eht_kv': result.get('eht_kv'),
                'working_distance_mm': result.get('working_distance_mm'),
                'image_size': result.get('image_size'),
                'pixel_size_nm': result.get('pixel_size_nm'),
                'detector': result.get('detector'),
                'signal_a': result.get('signal_a'),
                'signal_b': result.get('signal_b'),
                'date': result.get('date'),
                'operator': result.get('operator'),
            },
            notes=f"Imported SEM: {os.path.basename(file_path)}"
        )
        
        # Store key metadata as properties
        properties = [
            ('magnification', result.get('magnification'), 'X'),
            ('eht_voltage', result.get('eht_kv'), 'kV'),
            ('working_distance', result.get('working_distance_mm'), 'mm'),
            ('pixel_size', result.get('pixel_size_nm'), 'nm'),
        ]
        
        for name, value, unit in properties:
            if value:
                # Extract numeric value if possible
                try:
                    num_value = re.sub(r'[^0-9.]', '', str(value))
                    if num_value:
                        db.add_property(
                            characterization_id=char_id,
                            property_name=name,
                            property_value=float(num_value),
                            property_unit=unit,
                            confidence_score=0.9
                        )
                except:
                    pass
        
        return {
            'success': True,
            'char_id': char_id,
            'sample_id': sample_id,
            'file': result['file'],
            'magnification': result.get('magnification'),
            'eht': result.get('eht_kv'),
            'wd': result.get('working_distance_mm')
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}
        
    finally:
        if close_db:
            db.close()


def import_sem_files(folder_path, sample_id=None, db=None):
    """
    Import all .tif files from a folder
    """
    close_db = False
    if db is None:
        db = get_db()
        close_db = True
    
    results = []
    folder = Path(folder_path)
    tif_files = list(folder.glob('*.tif')) + list(folder.glob('*.tiff'))
    
    if not tif_files:
        print(f"No .tif files found in {folder_path}")
        return []
    
    print(f"📄 Found {len(tif_files)} .tif files to import")
    
    for file_path in tif_files:
        print(f"\n📄 Processing: {file_path.name}")
        result = import_sem_file(str(file_path), sample_id, db)
        results.append(result)
        
        if result['success']:
            print(f"  ✅ Imported: {result['file']}")
            print(f"     Mag: {result.get('magnification', 'N/A')}")
            print(f"     EHT: {result.get('eht', 'N/A')}")
        else:
            print(f"  ❌ Error: {result.get('error', 'Unknown error')}")
    
    if close_db:
        db.close()
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        sample_id = sys.argv[2] if len(sys.argv) > 2 else "TEST-SEM"
        
        print(f"📄 Testing SEM import: {file_path}")
        result = import_sem_file(file_path, sample_id)
        
        if result['success']:
            print(f"\n✅ Import successful!")
            print(f"  Sample: {result['sample_id']}")
            print(f"  File: {result['file']}")
            print(f"  Characterization ID: {result['char_id']}")
            if result.get('magnification'):
                print(f"  Magnification: {result['magnification']}")
            if result.get('eht'):
                print(f"  EHT: {result['eht']}")
        else:
            print(f"\n❌ Import failed: {result.get('error')}")
    else:
        print("Usage: python sem_integration.py <file_path> [sample_id]")

"""
XRD Integration Module - Fixed version
Parses .xy files and stores results in the database
"""

import os
import numpy as np
from pathlib import Path
from parse_xy_v2 import parse_and_analyze_xy, print_xrd_report
from alloy_db import get_db

def ensure_float(value):
    """Convert numpy float to Python float"""
    if value is None:
        return None
    if isinstance(value, (np.float64, np.float32, np.float16)):
        return float(value)
    if isinstance(value, (np.int64, np.int32, np.int16, np.int8)):
        return int(value)
    return value

def import_xrd_file(file_path, sample_id, db=None):
    """
    Import an XRD .xy file and store results in the database
    """
    close_db = False
    if db is None:
        db = get_db()
        close_db = True
    
    try:
        # Parse the XRD file
        result = parse_and_analyze_xy(file_path, sample_id)
        
        if result.get('error'):
            return {'success': False, 'error': result['error']}
        
        # Get or create characterization record
        char_id = db.add_characterization(
            sample_id=sample_id,
            char_type='XRD',
            instrument='Bruker D8',
            file_path=file_path,
            parameters={
                'range': result['range'],
                'step': result['step'],
                'n_points': result['n_points'],
                'n_peaks': result['n_peaks'],
                'max_intensity': ensure_float(result['max_intensity'])
            },
            notes=f"Imported XRD: {os.path.basename(file_path)}"
        )
        
        # Store lattice parameters as properties
        if result.get('lattice_a'):
            db.add_property(
                characterization_id=char_id,
                property_name='lattice_parameter_a',
                property_value=ensure_float(result['lattice_a']),
                property_unit='Å',
                confidence_score=0.8
            )
        
        if result.get('lattice_c'):
            db.add_property(
                characterization_id=char_id,
                property_name='lattice_parameter_c',
                property_value=ensure_float(result['lattice_c']),
                property_unit='Å',
                confidence_score=0.8
            )
        
        # Store number of peaks as a property
        db.add_property(
            characterization_id=char_id,
            property_name='n_peaks',
            property_value=ensure_float(result['n_peaks']),
            property_unit='',
            confidence_score=0.9
        )
        
        return {
            'success': True,
            'char_id': char_id,
            'sample_id': sample_id,
            'file': result['file'],
            'lattice_a': ensure_float(result.get('lattice_a')),
            'n_peaks': result['n_peaks']
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}
        
    finally:
        if close_db:
            db.close()


def import_xrd_files(folder_path, sample_id=None, db=None):
    """
    Import all .xy files from a folder
    """
    close_db = False
    if db is None:
        db = get_db()
        close_db = True
    
    results = []
    folder = Path(folder_path)
    xy_files = list(folder.glob('*.xy'))
    
    if not xy_files:
        print(f"No .xy files found in {folder_path}")
        return []
    
    print(f"📄 Found {len(xy_files)} .xy files to import")
    
    for file_path in xy_files:
        print(f"\n📄 Processing: {file_path.name}")
        result = import_xrd_file(str(file_path), sample_id, db)
        results.append(result)
        
        if result['success']:
            print(f"  ✅ Imported: {result['file']}")
            if result.get('lattice_a'):
                print(f"     a = {result['lattice_a']:.4f} Å")
            print(f"     peaks = {result.get('n_peaks', 'N/A')}")
        else:
            print(f"  ❌ Error: {result.get('error', 'Unknown error')}")
    
    if close_db:
        db.close()
    
    return results


if __name__ == "__main__":
    # Test with a single file
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        sample_id = sys.argv[2] if len(sys.argv) > 2 else "TEST-XRD"
        
        print(f"📄 Testing XRD import: {file_path}")
        result = import_xrd_file(file_path, sample_id)
        
        if result['success']:
            print(f"\n✅ Import successful!")
            print(f"  Sample: {result['sample_id']}")
            print(f"  File: {result['file']}")
            print(f"  Characterization ID: {result['char_id']}")
            if result.get('lattice_a'):
                print(f"  a = {result['lattice_a']:.4f} Å")
            print(f"  Peaks: {result['n_peaks']}")
        else:
            print(f"\n❌ Import failed: {result.get('error')}")
    else:
        print("Usage: python xrd_integration_fixed.py <file_path> [sample_id]")

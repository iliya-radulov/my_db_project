"""
XRD Integration Module
Parses .xy files and stores results in the database
"""

import os
from pathlib import Path
from parse_xy_v2 import parse_and_analyze_xy, print_xrd_report
from alloy_db import get_db

def import_xrd_file(file_path, sample_id, db=None):
    """
    Import an XRD .xy file and store results in the database
    
    Args:
        file_path: Path to the .xy file
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
                'max_intensity': result['max_intensity']
            },
            notes=f"Imported XRD: {os.path.basename(file_path)}"
        )
        
        # Store lattice parameters as properties
        if result.get('lattice_a'):
            db.add_property(
                characterization_id=char_id,
                property_name='lattice_parameter_a',
                property_value=result['lattice_a'],
                property_unit='Å',
                confidence_score=0.8
            )
        
        if result.get('lattice_c'):
            db.add_property(
                characterization_id=char_id,
                property_name='lattice_parameter_c',
                property_value=result['lattice_c'],
                property_unit='Å',
                confidence_score=0.8
            )
        
        # Store c/a ratio
        if result.get('lattice_a') and result.get('lattice_c'):
            c_over_a = result['lattice_c'] / result['lattice_a']
            db.add_property(
                characterization_id=char_id,
                property_name='c_a_ratio',
                property_value=c_over_a,
                property_unit='',
                confidence_score=0.7
            )
        
        # Store number of peaks as a property
        db.add_property(
            characterization_id=char_id,
            property_name='n_peaks',
            property_value=result['n_peaks'],
            property_unit='',
            confidence_score=0.9
        )
        
        return {
            'success': True,
            'char_id': char_id,
            'sample_id': sample_id,
            'file': result['file'],
            'lattice_a': result.get('lattice_a'),
            'n_peaks': result['n_peaks']
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}
        
    finally:
        if close_db:
            db.close()


def import_xrd_files(folder_path, sample_id=None, db=None):
    """
    Import all .xy files from a folder
    
    Args:
        folder_path: Path to folder containing .xy files
        sample_id: Sample ID to link to (optional)
        db: Optional database connection
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
            print(f"     a = {result.get('lattice_a', 'N/A'):.4f} Å" if result.get('lattice_a') else "     a = N/A")
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
        print("Usage: python xrd_integration.py <file_path> [sample_id]")

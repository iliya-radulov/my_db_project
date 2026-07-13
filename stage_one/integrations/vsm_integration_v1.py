"""
VSM Integration Module
Parses .dat files and stores magnetic properties in the database
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from stage_one.parsers.parse_vsm_v1 import parse_vsm_file
from stage_one.alloy.alloy_db_v1 import get_db

def import_vsm_file(file_path, sample_id, db=None):
    """
    Import a VSM .dat file and store results in the database
    
    Args:
        file_path: Path to the .dat file
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
        # Parse the VSM file
        result = parse_vsm_file(file_path)
        
        if 'error' in result:
            return {'success': False, 'error': result['error']}
        
        # Create characterization record
        char_id = db.add_characterization(
            sample_id=sample_id,
            char_type='VSM',
            instrument='PPMS',
            file_path=file_path,
            parameters={
                'n_points': result['n_points'],
                'max_field': result['max_field'],
                'mass': result.get('mass')
            },
            notes=f"Imported VSM: {os.path.basename(file_path)}"
        )
        
        # Store magnetic properties
        properties = [
            ('saturation_moment', result['ms'], 'emu'),
            ('remanence', result['mr'], 'emu'),
            ('coercivity', result['hc'], 'Oe'),
        ]
        
        for name, value, unit in properties:
            if value is not None:
                db.add_property(
                    characterization_id=char_id,
                    property_name=name,
                    property_value=value,
                    property_unit=unit,
                    confidence_score=0.85
                )
        
        # Store mass-normalized properties if mass is available
        if result.get('ms_per_g'):
            db.add_property(
                characterization_id=char_id,
                property_name='saturation_moment_per_g',
                property_value=result['ms_per_g'],
                property_unit='emu/g',
                confidence_score=0.85
            )
        
        return {
            'success': True,
            'char_id': char_id,
            'sample_id': sample_id,
            'file': os.path.basename(file_path),
            'ms': result['ms'],
            'hc': result['hc'],
            'mr': result['mr']
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}
        
    finally:
        if close_db:
            db.close()


def import_vsm_files(folder_path, sample_id=None, db=None):
    """
    Import all .dat files from a folder
    """
    close_db = False
    if db is None:
        db = get_db()
        close_db = True
    
    results = []
    folder = Path(folder_path)
    dat_files = list(folder.glob('*.dat'))
    
    if not dat_files:
        print(f"No .dat files found in {folder_path}")
        return []
    
    print(f"📄 Found {len(dat_files)} .dat files to import")
    
    for file_path in dat_files:
        print(f"\n📄 Processing: {file_path.name}")
        result = import_vsm_file(str(file_path), sample_id, db)
        results.append(result)
        
        if result['success']:
            print(f"  ✅ Imported: {result['file']}")
            print(f"     Ms = {result.get('ms', 'N/A'):.4f} emu")
            print(f"     Hc = {result.get('hc', 'N/A'):.1f} Oe")
        else:
            print(f"  ❌ Error: {result.get('error', 'Unknown error')}")
    
    if close_db:
        db.close()
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        sample_id = sys.argv[2] if len(sys.argv) > 2 else "TEST-VSM"
        
        print(f"📄 Testing VSM import: {file_path}")
        result = import_vsm_file(file_path, sample_id)
        
        if result['success']:
            print(f"\n✅ Import successful!")
            print(f"  Sample: {result['sample_id']}")
            print(f"  File: {result['file']}")
            print(f"  Characterization ID: {result['char_id']}")
            if result.get('ms'):
                print(f"  Ms = {result['ms']:.4f} emu")
            if result.get('hc'):
                print(f"  Hc = {result['hc']:.1f} Oe")
        else:
            print(f"\n❌ Import failed: {result.get('error')}")
    else:
        print("Usage: python vsm_integration.py <file_path> [sample_id]")

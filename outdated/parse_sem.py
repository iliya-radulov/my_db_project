#!/usr/bin/env python3
"""
SEM Metadata Parser for Zeiss .tif files
Extracts key parameters from TIFF metadata
"""

from PIL import Image
from PIL.TiffTags import TAGS
import os
from pathlib import Path

def parse_sem_file(file_path):
    """Extract SEM metadata from .tif file"""
    
    try:
        img = Image.open(file_path)
        metadata = img.tag_v2
        
        # Key parameters to extract
        sem_data = {
            'file': os.path.basename(file_path),
            'width': None,
            'height': None,
            'magnification': None,
            'eht_kv': None,
            'working_distance_mm': None,
            'detector': None,
            'signal_a': None,
            'signal_b': None,
            'date': None,
            'operator': None,
            'sample_id': None,
            'pixel_size_nm': None,
            'image_size': None,
        }
        
        # Extract basic image info
        sem_data['width'] = metadata.get('ImageWidth', None)
        sem_data['height'] = metadata.get('ImageLength', None)
        
        if sem_data['width'] and sem_data['height']:
            sem_data['image_size'] = f"{sem_data['width']} x {sem_data['height']}"
        
        # Extract Zeiss-specific metadata (stored as ASCII strings)
        for tag, value in metadata.items():
            tag_name = TAGS.get(tag, str(tag))
            
            if tag_name == 'AP_MAG':
                # Magnification like "1.00 K X"
                if isinstance(value, bytes):
                    value = value.decode('utf-8', errors='ignore').strip()
                sem_data['magnification'] = value
            
            elif tag_name == 'AP_ACTUALKV':
                # EHT voltage like "10.00 kV"
                if isinstance(value, bytes):
                    value = value.decode('utf-8', errors='ignore').strip()
                sem_data['eht_kv'] = value
            
            elif tag_name == 'AP_WD':
                # Working distance like "7.1 mm"
                if isinstance(value, bytes):
                    value = value.decode('utf-8', errors='ignore').strip()
                sem_data['working_distance_mm'] = value
            
            elif tag_name == 'DP_DETECTOR_CHANNEL':
                # Detector channel like "Signal A = SE2"
                if isinstance(value, bytes):
                    value = value.decode('utf-8', errors='ignore').strip()
                sem_data['detector'] = value
            
            elif tag_name == 'DP_SIGNALAZ1':
                # Signal A like "SE2"
                if isinstance(value, bytes):
                    value = value.decode('utf-8', errors='ignore').strip()
                sem_data['signal_a'] = value
            
            elif tag_name == 'DP_IMPLIED_DETECTOR':
                # Signal B like "InLens"
                if isinstance(value, bytes):
                    value = value.decode('utf-8', errors='ignore').strip()
                sem_data['signal_b'] = value
            
            elif tag_name == 'AP_DATE':
                # Date like "5 Jul 2023"
                if isinstance(value, bytes):
                    value = value.decode('utf-8', errors='ignore').strip()
                sem_data['date'] = value
            
            elif tag_name == 'SV_OPERATOR':
                # Operator name
                if isinstance(value, bytes):
                    value = value.decode('utf-8', errors='ignore').strip()
                if value:
                    sem_data['operator'] = value
            
            elif tag_name == 'SV_SAMPLE_ID':
                # Sample ID like "Sample #2"
                if isinstance(value, bytes):
                    value = value.decode('utf-8', errors='ignore').strip()
                sem_data['sample_id'] = value
            
            elif tag_name == 'AP_PIXEL_SIZE':
                # Pixel size like "277.3 nm"
                if isinstance(value, bytes):
                    value = value.decode('utf-8', errors='ignore').strip()
                sem_data['pixel_size_nm'] = value
        
        # Also check for tags stored as tuples (like 34118)
        for tag, value in metadata.items():
            if tag == 34118 or tag == 34119:
                # This is the complex metadata block, skip for now
                pass
        
        return sem_data
        
    except Exception as e:
        return {'error': str(e), 'file': os.path.basename(file_path)}


def print_sem_summary(result):
    """Print a formatted SEM summary"""
    if 'error' in result:
        print(f"❌ Error: {result['error']}")
        return
    
    print(f"\n🔬 SEM Metadata: {result.get('file', 'Unknown')}")
    print("-" * 50)
    print(f"  Image Size: {result.get('image_size', 'N/A')}")
    print(f"  Magnification: {result.get('magnification', 'N/A')}")
    print(f"  EHT: {result.get('eht_kv', 'N/A')}")
    print(f"  Working Distance: {result.get('working_distance_mm', 'N/A')}")
    print(f"  Detector: {result.get('detector', 'N/A')}")
    print(f"  Signal A: {result.get('signal_a', 'N/A')}")
    print(f"  Signal B: {result.get('signal_b', 'N/A')}")
    print(f"  Pixel Size: {result.get('pixel_size_nm', 'N/A')}")
    print(f"  Date: {result.get('date', 'N/A')}")
    print(f"  Operator: {result.get('operator', 'N/A')}")
    print(f"  Sample ID: {result.get('sample_id', 'N/A')}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "/Users/r/Desktop/NdFeB_data/sorted_v2/sem/230705-2_01.tif"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    print(f"📄 Parsing: {file_path}")
    result = parse_sem_file(file_path)
    print_sem_summary(result)

#!/usr/bin/env python3
"""
SEM Metadata Parser for Zeiss .tif files - V3
Extracts metadata from the 34118/34119 tags (stored as strings)
"""

import os
import re
from pathlib import Path
from PIL import Image
from PIL.TiffTags import TAGS

def parse_sem_file(file_path):
    """Extract SEM metadata from .tif file"""
    
    try:
        img = Image.open(file_path)
        metadata = img.tag_v2
        
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
        
        # Basic image info
        sem_data['width'] = metadata.get('ImageWidth', None)
        sem_data['height'] = metadata.get('ImageLength', None)
        if sem_data['width'] and sem_data['height']:
            sem_data['image_size'] = f"{sem_data['width']} x {sem_data['height']}"
        
        # Extract metadata from tags 34118 and 34119
        for tag_id in [34118, 34119]:
            if tag_id in metadata:
                data = metadata[tag_id]
                if isinstance(data, str):
                    text = data
                elif isinstance(data, bytes):
                    text = data.decode('latin-1', errors='ignore')
                else:
                    continue
                
                # Look for key patterns
                patterns = {
                    'magnification': r'Mag\s*=\s*([\d.]+\s*[KkMm]?\s*X?)',
                    'eht_kv': r'EHT\s*=\s*([\d.]+\s*kV)',
                    'working_distance_mm': r'WD\s*=\s*([\d.]+\s*mm)',
                    'signal_a': r'Signal A\s*=\s*(\w+)',
                    'signal_b': r'Signal B\s*=\s*(\w+)',
                    'detector': r'Detector\s*=\s*(\w+)',
                    'date': r'Date[:\s]*([\d]+\s+[A-Za-z]+\s+[\d]+)',
                    'operator': r'Operator\s*=\s*(\w+)',
                    'sample_id': r'Sample ID\s*=\s*(.+)',
                    'pixel_size_nm': r'Pixel Size\s*=\s*([\d.]+\s*nm)',
                }
                
                for key, pattern in patterns.items():
                    if sem_data[key] is None:  # Only find if not already found
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            sem_data[key] = match.group(1).strip()
        
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

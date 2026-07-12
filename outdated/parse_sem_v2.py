#!/usr/bin/env python3
"""
SEM Metadata Parser for Zeiss .tif files - V2
Extracts metadata from the binary 34118/34119 tags
"""

import os
import struct
import re
from pathlib import Path
from PIL import Image
from PIL.TiffTags import TAGS

def extract_strings_from_bytes(data):
    """Extract readable strings from binary data"""
    strings = []
    current = []
    for byte in data:
        if 32 <= byte <= 126:  # Printable ASCII
            current.append(chr(byte))
        else:
            if len(current) > 3:  # At least 4 chars to be meaningful
                strings.append(''.join(current))
            current = []
    if len(current) > 3:
        strings.append(''.join(current))
    return strings


def parse_sem_file_v2(file_path):
    """Extract SEM metadata from .tif file - V2"""
    
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
                if isinstance(data, bytes):
                    # Extract readable strings
                    strings = extract_strings_from_bytes(data)
                    for s in strings:
                        s = s.strip()
                        if not s or len(s) < 2:
                            continue
                        
                        # Look for key patterns
                        if 'Mag =' in s or 'AP_MAG' in s:
                            # Magnification
                            match = re.search(r'Mag\s*=\s*([\d.]+\s*[KkMm]?\s*X?)', s)
                            if match:
                                sem_data['magnification'] = match.group(1).strip()
                        
                        if 'EHT =' in s or 'AP_ACTUALKV' in s:
                            match = re.search(r'EHT\s*=\s*([\d.]+\s*kV)', s)
                            if match:
                                sem_data['eht_kv'] = match.group(1).strip()
                        
                        if 'WD =' in s or 'AP_WD' in s:
                            match = re.search(r'WD\s*=\s*([\d.]+\s*mm)', s)
                            if match:
                                sem_data['working_distance_mm'] = match.group(1).strip()
                        
                        if 'Signal A =' in s:
                            match = re.search(r'Signal A\s*=\s*(\w+)', s)
                            if match:
                                sem_data['signal_a'] = match.group(1).strip()
                        
                        if 'Signal B =' in s:
                            match = re.search(r'Signal B\s*=\s*(\w+)', s)
                            if match:
                                sem_data['signal_b'] = match.group(1).strip()
                        
                        if 'Detector =' in s:
                            match = re.search(r'Detector\s*=\s*(\w+)', s)
                            if match:
                                sem_data['detector'] = match.group(1).strip()
                        
                        if 'Date:' in s:
                            match = re.search(r'Date:\s*([\d]+\s+[A-Za-z]+\s+[\d]+)', s)
                            if match:
                                sem_data['date'] = match.group(1).strip()
                        
                        if 'Operator =' in s:
                            match = re.search(r'Operator\s*=\s*(\w+)', s)
                            if match:
                                sem_data['operator'] = match.group(1).strip()
                        
                        if 'Sample ID =' in s:
                            match = re.search(r'Sample ID\s*=\s*(.+)', s)
                            if match:
                                sem_data['sample_id'] = match.group(1).strip()
                        
                        if 'Pixel Size =' in s or 'AP_PIXEL_SIZE' in s:
                            match = re.search(r'Pixel Size\s*=\s*([\d.]+\s*nm)', s)
                            if match:
                                sem_data['pixel_size_nm'] = match.group(1).strip()
        
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
    result = parse_sem_file_v2(file_path)
    print_sem_summary(result)

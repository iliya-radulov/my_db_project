#!/usr/bin/env python3
"""
SEM Metadata Parser for Zeiss .tif files - Fast version
Only extracts key fields: magnification, EHT, WD, detector, signal
"""

import os
import re
from pathlib import Path
from PIL import Image
from PIL.TiffTags import TAGS

# Key patterns to search for - only the most important ones
KEY_PATTERNS = {
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

def parse_sem_file(file_path, max_size_mb=50):
    """Fast SEM metadata extraction - only reads header, not full image"""
    
    sem_data = {
        'file': os.path.basename(file_path),
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
    
    try:
        # Open the image with lazy loading (only reads header)
        img = Image.open(file_path)
        
        # Get basic image info (fast)
        width = img.tag_v2.get('ImageWidth', None)
        height = img.tag_v2.get('ImageLength', None)
        if width and height:
            sem_data['image_size'] = f"{width} x {height}"
        
        # Only read the metadata tags (not the image data)
        metadata = img.tag_v2
        
        # Check tags 34118 and 34119 for metadata
        text_data = []
        for tag_id in [34118, 34119]:
            if tag_id in metadata:
                data = metadata[tag_id]
                if isinstance(data, str):
                    text_data.append(data)
                elif isinstance(data, bytes):
                    try:
                        text_data.append(data.decode('latin-1', errors='ignore'))
                    except:
                        pass
        
        # Combine all text data
        full_text = ' '.join(text_data)
        
        # Extract key fields using regex (fast)
        for key, pattern in KEY_PATTERNS.items():
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                sem_data[key] = match.group(1).strip()
        
        # Close the image to free resources
        img.close()
        
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

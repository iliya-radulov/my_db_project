#!/usr/bin/env python3
"""
XRD Parser for Bruker .raw files
Extracts 2θ, intensity, and metadata
"""

import os
import struct
import numpy as np
from pathlib import Path
from datetime import datetime

class BrukerRawParser:
    """Parse Bruker .raw XRD files"""
    
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.metadata = {}
        self.two_theta = None
        self.intensity = None
        
    def parse(self):
        """Parse the .raw file"""
        with open(self.file_path, 'rb') as f:
            raw_data = f.read()
        
        # Bruker .raw file format:
        # - Header (ASCII, usually 512 bytes or variable)
        # - Binary data (intensity values as 32-bit floats)
        
        # Find the header end (look for null bytes)
        header_end = raw_data.find(b'\x00' * 4)
        if header_end == -1:
            # Try to find start of binary data
            header_end = 512  # Default header size
        
        # Extract header
        header = raw_data[:header_end]
        try:
            header_text = header.decode('ascii', errors='ignore')
        except:
            header_text = ''
        
        # Parse metadata from header
        self.metadata = self._parse_header(header_text)
        
        # Extract binary data (intensity values as 32-bit floats)
        binary_data = raw_data[header_end:]
        
        # Determine if data is 32-bit floats
        try:
            # Try to parse as 32-bit floats
            if len(binary_data) % 4 == 0:
                intensity = np.frombuffer(binary_data, dtype=np.float32)
            else:
                # Try 16-bit integers
                intensity = np.frombuffer(binary_data, dtype=np.int16)
                intensity = intensity.astype(np.float32)
        except:
            intensity = np.array([])
        
        self.intensity = intensity
        
        # Generate 2θ values
        if 'start' in self.metadata and 'end' in self.metadata and 'step' in self.metadata:
            start = self.metadata['start']
            end = self.metadata['end']
            step = self.metadata['step']
            self.two_theta = np.arange(start, end + step, step)
        else:
            # Guess based on intensity length
            self.two_theta = np.linspace(10, 90, len(intensity))
        
        return self
    
    def _parse_header(self, header_text):
        """Parse header text for metadata"""
        metadata = {}
        lines = header_text.split('\n')
        for line in lines[:50]:  # Only first 50 lines
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                if key in ['start', 'end', 'step', 'time', 'filename']:
                    try:
                        metadata[key] = float(value)
                    except:
                        metadata[key] = value
        return metadata
    
    def find_peaks(self, prominence=0.1):
        """Find peaks in the XRD pattern"""
        from scipy.signal import find_peaks as scipy_find_peaks
        
        if self.intensity is None or len(self.intensity) == 0:
            return []
        
        # Normalize intensity
        intensity_norm = self.intensity / np.max(self.intensity)
        
        # Find peaks
        peaks, properties = scipy_find_peaks(
            intensity_norm,
            prominence=prominence,
            height=0.1,
            distance=10  # Minimum distance between peaks in points
        )
        
        peak_results = []
        for idx in peaks:
            if idx < len(self.two_theta):
                peak_results.append({
                    'two_theta': float(self.two_theta[idx]),
                    'intensity': float(self.intensity[idx]),
                    'normalized_intensity': float(intensity_norm[idx]),
                    'index': int(idx)
                })
        
        return peak_results
    
    def get_summary(self):
        """Get a summary of the XRD data"""
        return {
            'file': os.path.basename(self.file_path),
            'start': self.metadata.get('start', None),
            'end': self.metadata.get('end', None),
            'step': self.metadata.get('step', None),
            'n_points': len(self.intensity) if self.intensity is not None else 0,
            'max_intensity': float(np.max(self.intensity)) if self.intensity is not None and len(self.intensity) > 0 else None,
            'peaks': self.find_peaks()[:10]  # First 10 peaks
        }


def parse_xrd_file(file_path):
    """Convenience function to parse an XRD file"""
    parser = BrukerRawParser(file_path)
    parser.parse()
    return parser


if __name__ == "__main__":
    # Test with an XRD file
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # Default to one of your XRD files
        file_path = "/Users/r/desktop/ndfeb_data/sorted_v2/xrd/0107.raw"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    print(f"📄 Parsing: {file_path}")
    parser = parse_xrd_file(file_path)
    
    print("\n📊 Metadata:")
    for key, value in parser.metadata.items():
        print(f"  {key}: {value}")
    
    print(f"\n📈 Data: {len(parser.intensity)} points")
    print(f"  Max intensity: {np.max(parser.intensity):.1f}")
    print(f"  Min intensity: {np.min(parser.intensity):.1f}")
    
    peaks = parser.find_peaks()
    print(f"\n🔍 Found {len(peaks)} peaks (first 5):")
    for peak in peaks[:5]:
        print(f"  2θ = {peak['two_theta']:.3f}°, intensity = {peak['intensity']:.1f}")

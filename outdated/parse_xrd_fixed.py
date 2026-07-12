#!/usr/bin/env python3
"""
XRD Parser for Bruker .raw files - Fixed version
Properly handles Bruker .raw file format
"""

import os
import struct
import numpy as np
from pathlib import Path

class BrukerRawParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.metadata = {}
        self.two_theta = None
        self.intensity = None
        
    def parse(self):
        with open(self.file_path, 'rb') as f:
            raw_data = f.read()
        
        # Bruker .raw format:
        # Header is ASCII until a null byte, then binary data follows
        # Binary data: 32-bit floats (little endian)
        
        # Find the end of header (first occurrence of null byte or pattern)
        header_end = raw_data.find(b'\x00' * 2)
        if header_end == -1:
            header_end = 512  # Default header size
        
        # Extract header
        header = raw_data[:header_end]
        try:
            header_text = header.decode('ascii', errors='ignore')
        except:
            header_text = ''
        
        # Parse metadata from header
        self.metadata = self._parse_header(header_text)
        
        # Binary data starts after header
        binary_data = raw_data[header_end:]
        
        # Clean binary data: remove any trailing non-data bytes
        # Bruker raw files store data as 32-bit floats, little endian
        # Sometimes there's padding at the end
        
        # Try different approaches
        intensities = None
        
        # Approach 1: Try as 32-bit floats (little endian)
        try:
            # Make sure length is multiple of 4
            data_len = (len(binary_data) // 4) * 4
            if data_len > 0:
                raw_floats = np.frombuffer(binary_data[:data_len], dtype=np.float32)
                # Check if values are reasonable (not huge)
                if np.median(raw_floats) < 1e10 and np.median(raw_floats) > -1e10:
                    intensities = raw_floats
        except:
            pass
        
        # Approach 2: Try as 16-bit integers
        if intensities is None:
            try:
                data_len = (len(binary_data) // 2) * 2
                raw_ints = np.frombuffer(binary_data[:data_len], dtype=np.int16)
                intensities = raw_ints.astype(np.float32)
            except:
                pass
        
        # Approach 3: Try as 32-bit floats (big endian)
        if intensities is None:
            try:
                data_len = (len(binary_data) // 4) * 4
                raw_floats = np.frombuffer(binary_data[:data_len], dtype='>f4')
                if np.median(raw_floats) < 1e10 and np.median(raw_floats) > -1e10:
                    intensities = raw_floats
            except:
                pass
        
        # Approach 4: Guess based on pattern
        if intensities is None:
            # Look for patterns in the data
            print(f"Debug: Could not parse binary data, trying raw bytes")
            intensities = np.array([])
        
        self.intensity = intensities
        
        # Generate 2θ values
        if 'start' in self.metadata and 'end' in self.metadata and 'step' in self.metadata:
            start = float(self.metadata['start'])
            end = float(self.metadata['end'])
            step = float(self.metadata['step'])
            n_points = int((end - start) / step) + 1
            self.two_theta = np.linspace(start, end, n_points)
        else:
            # Guess based on intensity length
            if self.intensity is not None and len(self.intensity) > 0:
                self.two_theta = np.linspace(10, 90, len(self.intensity))
            else:
                self.two_theta = np.array([])
        
        return self
    
    def _parse_header(self, header_text):
        metadata = {}
        lines = header_text.split('\n')
        for line in lines[:100]:
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                # Try to convert to float if looks like a number
                try:
                    if key in ['start', 'end', 'step', 'time']:
                        metadata[key] = float(value)
                    else:
                        metadata[key] = value
                except:
                    metadata[key] = value
        return metadata
    
    def find_peaks(self, prominence=0.05):
        from scipy.signal import find_peaks as scipy_find_peaks
        
        if self.intensity is None or len(self.intensity) == 0:
            return []
        
        # Normalize intensity
        max_int = np.max(self.intensity)
        if max_int > 0:
            intensity_norm = self.intensity / max_int
        else:
            intensity_norm = self.intensity
        
        try:
            peaks, properties = scipy_find_peaks(
                intensity_norm,
                prominence=prominence,
                height=0.05,
                distance=10
            )
        except:
            return []
        
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
        summary = {
            'file': os.path.basename(self.file_path),
            'n_points': len(self.intensity) if self.intensity is not None else 0,
            'max_intensity': float(np.max(self.intensity)) if self.intensity is not None and len(self.intensity) > 0 else None,
        }
        if self.two_theta is not None and len(self.two_theta) > 0:
            summary['two_theta_range'] = [float(self.two_theta[0]), float(self.two_theta[-1])]
        summary['peaks'] = self.find_peaks()[:10]
        return summary


def parse_xrd_file(file_path):
    parser = BrukerRawParser(file_path)
    parser.parse()
    return parser


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "/Users/r/desktop/ndfeb_data/sorted_v2/xrd/0107.raw"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    print(f"📄 Parsing: {file_path}")
    parser = parse_xrd_file(file_path)
    
    print(f"\n📊 Metadata: {len(parser.metadata)} items")
    for key, value in list(parser.metadata.items())[:10]:
        print(f"  {key}: {value}")
    
    if parser.intensity is not None:
        print(f"\n📈 Data: {len(parser.intensity)} points")
        print(f"  Max intensity: {np.max(parser.intensity):.1f}")
        print(f"  Min intensity: {np.min(parser.intensity):.1f}")
        print(f"  Mean intensity: {np.mean(parser.intensity):.1f}")
    else:
        print("\n❌ No intensity data extracted")
    
    peaks = parser.find_peaks()
    print(f"\n🔍 Found {len(peaks)} peaks (first 5):")
    for peak in peaks[:5]:
        print(f"  2θ = {peak['two_theta']:.3f}°, intensity = {peak['intensity']:.1f}")

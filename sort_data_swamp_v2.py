#!/usr/bin/env python3
"""
Data Swamp Sorter v2
Organizes messy research data folders into clean subfolders by file type.
No database connection needed.
Updated: Added images, archives, fixed Origin detection
"""

import os
import shutil
import re
from pathlib import Path
from datetime import datetime
import argparse

# File type definitions
FILE_TYPES = {
    'xrd': {
        'extensions': ['.raw', '.xy', '.xrdml'],
        'folders': ['xrd'],
        'description': 'XRD data files'
    },
    'sem': {
        'extensions': ['.tif', '.tiff', '.hdr'],
        'folders': ['sem'],
        'description': 'SEM images and headers'
    },
    'mh': {
        'extensions': ['.dat'],
        'folders': ['mh', 'MH'],
        'description': 'Magnetic measurement data'
    },
    'icp': {
        'extensions': ['.csv', '.xlsx'],
        'folders': ['icp', 'ICPOES'],
        'description': 'ICP-OES composition data'
    },
    'process': {
        'extensions': ['.CSV'],  # Case-sensitive for your deformation files
        'folders': ['process', 'SPS'],
        'description': 'Process/deformation data'
    },
    'origin': {
        'extensions': ['.opju', '.opj'],
        'folders': ['origin'],
        'description': 'Origin project files'
    },
    'images': {
        'extensions': ['.jpg', '.jpeg', '.png', '.bmp', '.gif'],
        'folders': ['images'],
        'description': 'Images (photos, screenshots)'
    },
    'archives': {
        'extensions': ['.zip', '.rar', '.7z', '.tar', '.gz'],
        'folders': ['archives'],
        'description': 'Compressed archives'
    },
    'presentation': {
        'extensions': ['.pptx', '.pdf', '.docx', '.doc'],
        'folders': ['presentations', 'Draft', 'Reports'],
        'description': 'Presentations and documents'
    },
    'other': {
        'extensions': [],  # Catch-all
        'folders': ['other'],
        'description': 'Uncategorized files'
    }
}

# Sample name patterns (for automatic detection)
SAMPLE_PATTERNS = [
    (r'^(\d{4})\.raw$', '0107'),  # 0107.raw → sample 0107
    (r'^(\d{4})\.xy$', '0107'),
    (r'^RP(\d+)[a-z]?', 'RP'),     # RP1a → sample RP1
    (r'^HCS(\d+)[a-z]?', 'HCS'),
    (r'^HDS(\d+)[a-z]?', 'HDS'),
    (r'^MQU', 'MQU'),
]


def detect_file_type(file_path: str) -> str:
    """Detect file type based on extension and content."""
    path = Path(file_path)
    ext = path.suffix.lower()
    name = path.name
    
    # Check by extension first
    for file_type, info in FILE_TYPES.items():
        if ext in info['extensions']:
            return file_type
    
    # Check by folder name (if file is already in a recognizable folder)
    parent = path.parent.name.lower()
    for file_type, info in FILE_TYPES.items():
        for folder in info['folders']:
            if folder.lower() in parent:
                return file_type
    
    # Check content for CSV files (deformation data has specific columns)
    if ext == '.csv':
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline()
                if 'AV Pyro top' in first_line or 'AV Control TC' in first_line:
                    return 'process'
                if 'Element' in first_line and 'wt%' in first_line:
                    return 'icp'
                if 'Nr.;Datum;Zeit' in first_line:
                    return 'process'
        except:
            pass
    
    return 'other'


def detect_sample_id(file_path: str) -> str:
    """Try to detect sample ID from filename."""
    name = Path(file_path).stem
    
    # Check common patterns
    for pattern, prefix in SAMPLE_PATTERNS:
        match = re.search(pattern, name)
        if match:
            if prefix == 'RP' or prefix == 'HCS' or prefix == 'HDS':
                return f"{prefix}{match.group(1)}"
            return match.group(1) if len(match.groups()) > 0 else prefix
    
    # Check for dates (YYYYMMDD)
    date_match = re.search(r'(\d{8})', name)
    if date_match:
        return f"SAMPLE-{date_match.group(1)}"
    
    return None


def sort_folder(input_path: str, output_path: str = None, dry_run: bool = False):
    """
    Sort files from input_path into subfolders by type.
    
    Args:
        input_path: Path to the messy data folder
        output_path: Where to put sorted files (default: input_path)
        dry_run: If True, only show what would be done
    """
    input_path = Path(input_path).resolve()
    if not input_path.exists():
        print(f"❌ Input path not found: {input_path}")
        return
    
    if output_path is None:
        output_path = input_path / 'sorted_v2'
    else:
        output_path = Path(output_path).resolve()
    
    print(f"📂 Input:  {input_path}")
    print(f"📁 Output: {output_path}")
    print("-" * 50)
    
    # Statistics
    stats = {ftype: 0 for ftype in FILE_TYPES.keys()}
    unknown_files = []
    
    # Walk through all files
    for root, dirs, files in os.walk(input_path):
        root_path = Path(root)
        
        # Skip output directory if inside input
        if output_path in root_path.parents or root_path == output_path:
            continue
        
        for file in files:
            file_path = root_path / file
            
            # Skip hidden files
            if file.startswith('.'):
                continue
            
            # Detect type
            file_type = detect_file_type(str(file_path))
            sample_id = detect_sample_id(str(file_path))
            
            if dry_run:
                print(f"[DRY RUN] {file} → {file_type} (sample: {sample_id})")
                stats[file_type] += 1
                continue
            
            # Create destination folder
            dest_folder = output_path / file_type
            dest_folder.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            try:
                dest_path = dest_folder / file
                if not dest_path.exists():  # Avoid overwriting
                    shutil.copy2(file_path, dest_path)
                    print(f"✅ {file} → {file_type}/")
                else:
                    # Add timestamp to avoid overwriting
                    stem = Path(file).stem
                    ext = Path(file).suffix
                    new_name = f"{stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                    dest_path = dest_folder / new_name
                    shutil.copy2(file_path, dest_path)
                    print(f"⚠️  {file} → {file_type}/{new_name} (duplicate)")
                
                stats[file_type] += 1
                
            except Exception as e:
                print(f"❌ Failed to copy {file}: {e}")
    
    # Print summary
    print("\n" + "="*50)
    print("📊 Summary:")
    for ftype, count in stats.items():
        if count > 0:
            print(f"  {ftype}: {count} files")
    print("="*50)
    
    # Show what's in "other" if it exists
    if stats.get('other', 0) > 0:
        other_folder = output_path / 'other'
        if other_folder.exists():
            print("\n📁 Files in 'other' folder (check if they need new categories):")
            for f in sorted(other_folder.iterdir())[:20]:
                print(f"  - {f.name}")
            if len(list(other_folder.iterdir())) > 20:
                print(f"  ... and {len(list(other_folder.iterdir())) - 20} more")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Sort messy research data into organized folders')
    parser.add_argument('input_path', help='Path to the messy data folder')
    parser.add_argument('--output', '-o', help='Output folder (default: input_path/sorted_v2)')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Show what would be done without copying')
    
    args = parser.parse_args()
    sort_folder(args.input_path, args.output, args.dry_run)

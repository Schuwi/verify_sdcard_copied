#!/usr/bin/env python3
import os
import sys
import re
import argparse
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Install necessary packages:
# pip install exifread

import exifread

def get_image_metadata(file_path):
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            # Extract relevant EXIF fields
            datetime_original = tags.get('EXIF DateTimeOriginal')
            camera_model = tags.get('Image Model')
            serial_number = tags.get('EXIF BodySerialNumber')
            shutter_count = tags.get('EXIF ShutterCount')
            # Build a unique identifier
            metadata_id = f"{datetime_original} | {shutter_count} | {camera_model} | {serial_number}"
            return metadata_id
    except Exception as e:
        print(f"Error reading EXIF data from {file_path}: {e}")
        return None

def get_video_metadata(file_path):
    # Read the first few kilobytes to compute a partial hash
    try:
        with open(file_path, 'rb') as f:
            data = f.read(8192)  # Read first 8KB
            return hash(data)
    except Exception as e:
        print(f"Error reading video file {file_path}: {e}")
        return None

def build_sdcard_metadata(sdcard_dir, extensions):
    sdcard_metadata = {}
    for root, dirs, files in os.walk(sdcard_dir):
        for file in files:
            if file.lower().endswith(extensions):
                file_path = os.path.join(root, file)
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.cr2', '.cr3', '.nef')):
                    # Image file
                    metadata_id = get_image_metadata(file_path)
                else:
                    # Video file
                    metadata_id = get_video_metadata(file_path)
                if metadata_id:
                    sdcard_metadata[metadata_id] = file_path
    return sdcard_metadata

def traverse_pc_directory(pc_dir, sdcard_metadata, exclusion_regex, extensions):
    regex = re.compile(exclusion_regex) if exclusion_regex else None
    # Collect files with their modified time for sorting
    file_list = []
    for root, dirs, files in os.walk(pc_dir):
        # Exclude directories matching the regex
        rel_root = os.path.relpath(root, pc_dir)
        if regex and regex.search(rel_root):
            continue
        for file in files:
            if file.lower().endswith(extensions):
                file_path = os.path.join(root, file)
                try:
                    mtime = os.path.getmtime(file_path)
                    file_list.append((file_path, mtime))
                except Exception as e:
                    print(f"Error accessing file {file_path}: {e}")
    # Sort files starting with the newest
    file_list.sort(key=lambda x: x[1], reverse=True)
    # Traverse files
    for file_path, _ in file_list:
        # Print the current subdirectory being searched
        print(f"Searching in: {os.path.dirname(file_path)}")#, end='\r')
        if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.cr2', '.cr3')):
            metadata_id = get_image_metadata(file_path)
        else:
            metadata_id = get_video_metadata(file_path)
        if metadata_id in sdcard_metadata:
            # Match found, remove from sdcard_metadata
            del sdcard_metadata[metadata_id]
            if not sdcard_metadata:
                print("\nAll files have been matched. Terminating early.")
                return
    print()  # For newline after the last print

def main():
    parser = argparse.ArgumentParser(description='Verify SD card files have been copied to PC.')
    parser.add_argument('sdcard_dir', help='Path to the SD card directory')
    parser.add_argument('pc_dir', help='Path to the PC base directory to search')
    parser.add_argument('--extensions', nargs='+', default=['.jpg', '.jpeg', '.png', '.mov', '.mp4', '.cr2', '.cr3'],
                        help='List of file extensions to include (e.g., .jpg .mov)')
    parser.add_argument('--exclude', default='',
                        help='Relative path exclusion regex for PC directory traversal')
    args = parser.parse_args()

    print("Building metadata map of SD card files...")
    sdcard_metadata = build_sdcard_metadata(args.sdcard_dir, tuple(ext.lower() for ext in args.extensions))
    print(f"Total files to match from SD card: {len(sdcard_metadata)}")

    if not sdcard_metadata:
        print("No files found on SD card with the specified extensions.")
        sys.exit()

    print("Traversing PC directory to find matches...")
    traverse_pc_directory(args.pc_dir, sdcard_metadata, args.exclude, tuple(ext.lower() for ext in args.extensions))

    if sdcard_metadata:
        print("\nFiles on SD card not found on PC:")
        for metadata_id, file_path in sdcard_metadata.items():
            print(f"- {file_path}")
    else:
        print("All files from SD card are present on PC.")

if __name__ == '__main__':
    main()


#!/home/schuwi/software/verify_sdcard_copied/venv/bin/python
import os
import sys
import re
import argparse
import blake3
import threading
from datetime import datetime

# Install blake3 if not already installed:
# pip install blake3

def get_file_hash(file_path):
    hasher = blake3.blake3()
    try:
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(8192)
                if not data:
                    break
                hasher.update(data)
        return hasher.hexdigest()
    except Exception as e:
        print(f"Error hashing file {file_path}: {e}")
        return None

def build_sdcard_hashmap(sdcard_dir, extensions):
    sdcard_hashes = {}
    for root, dirs, files in os.walk(sdcard_dir):
        for file in files:
            if file.lower().endswith(extensions):
                file_path = os.path.join(root, file)
                file_hash = get_file_hash(file_path)
                if file_hash:
                    sdcard_hashes[file_hash] = file_path
    return sdcard_hashes

def traverse_pc_directory(pc_dir, sdcard_hashes, exclusion_regex, extensions):
    regex = re.compile(exclusion_regex) if exclusion_regex else None
    # Collect files with their modified time for sorting
    file_list = []
    for root, dirs, files in os.walk(pc_dir):
        # Exclude directories matching the regex
        if regex and regex.search(os.path.relpath(root, pc_dir)):
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
        print(f"Searching in: {os.path.dirname(file_path)}", end='\r')
        file_hash = get_file_hash(file_path)
        if file_hash in sdcard_hashes:
            # Match found, remove from sdcard_hashes
            del sdcard_hashes[file_hash]
            if not sdcard_hashes:
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

    print("Building hash map of SD card files...")
    sdcard_hashes = build_sdcard_hashmap(args.sdcard_dir, tuple(ext.lower() for ext in args.extensions))
    print(f"Total files to match from SD card: {len(sdcard_hashes)}")

    if not sdcard_hashes:
        print("No files found on SD card with the specified extensions.")
        sys.exit()

    print("Traversing PC directory to find matches...")
    traverse_pc_directory(args.pc_dir, sdcard_hashes, args.exclude, tuple(ext.lower() for ext in args.extensions))

    if sdcard_hashes:
        print("\nFiles on SD card not found on PC:")
        for file_hash, file_path in sdcard_hashes.items():
            print(f"- {file_path}")
    else:
        print("All files from SD card are present on PC.")

if __name__ == '__main__':
    main()


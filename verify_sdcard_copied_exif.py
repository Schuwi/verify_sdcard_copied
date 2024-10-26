#!/usr/bin/env python3
import os
import sys
import re
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import exifread

image_endings = ('.jpg', '.jpeg', '.png', '.cr2', '.cr3', '.nef')

def get_image_metadata(file_path):
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            # Extract relevant EXIF fields
            datetime_original = tags.get('EXIF DateTimeOriginal')
            subsectime_original = tags.get('EXIF SubSecTimeOriginal')
            camera_model = tags.get('Image Model')
            serial_number = tags.get('EXIF BodySerialNumber')
            # Build a unique identifier
            metadata_id = f"{datetime_original}-{subsectime_original} | {camera_model} | {serial_number}"
            # Convert datetime to timestamp for earliest capture time
            if datetime_original:
                capture_time = datetime.strptime(str(datetime_original), '%Y:%m:%d %H:%M:%S')
                capture_timestamp = capture_time.timestamp()
            else:
                capture_timestamp = None
            return metadata_id, capture_timestamp
    except Exception as e:
        print(f"Error reading EXIF data from {file_path}: {e}")
        return None, None

def get_video_metadata(file_path):
    # Read the first few kilobytes to compute a partial hash
    try:
        with open(file_path, 'rb') as f:
            data = f.read(8192)  # Read first 8KB
            return hash(data), None  # No capture time
    except Exception as e:
        print(f"Error reading video file {file_path}: {e}")
        return None, None

def build_sdcard_metadata(sdcard_dir, extensions):
    sdcard_metadata = {}
    earliest_capture_timestamp = None
    i = 0
    for root, dirs, files in os.walk(sdcard_dir):
        for file in files:
            if file.lower().endswith(extensions):
                i += 1
                file_path = os.path.join(root, file)
                if file.lower().endswith(image_endings):
                    # Image file
                    metadata_id, capture_timestamp = get_image_metadata(file_path)
                else:
                    # Video file
                    metadata_id, capture_timestamp = get_video_metadata(file_path)
                if metadata_id:
                    if metadata_id in sdcard_metadata:
                        print(f"Warning: Duplicate metadata ID found for files '{file_path}' and '{sdcard_metadata[metadata_id]}': {metadata_id}")
                    sdcard_metadata[metadata_id] = file_path
                    if capture_timestamp:
                        if earliest_capture_timestamp is None or capture_timestamp < earliest_capture_timestamp:
                            earliest_capture_timestamp = capture_timestamp
    if i != len(sdcard_metadata):
        print(f"Warning: Only {len(sdcard_metadata)} out of {i} files will be compared.")
    return sdcard_metadata, earliest_capture_timestamp

last_print = None
def print_overwrite(message):
    # Clear the line before printing the new message
    global last_print
    if last_print:
        sys.stdout.write(' ' * len(last_print) + '\r')
    sys.stdout.write(message + '\r')
    sys.stdout.flush()

    last_print = message

def traverse_pc_directory(pc_dir, sdcard_metadata, exclusion_regex, extensions, earliest_capture_timestamp):
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
    i = 0
    found_files = 0
    last_message = None
    for file_path, mtime in file_list:
        # Early termination if file is older than earliest capture time
        if earliest_capture_timestamp and mtime < earliest_capture_timestamp:
            print("\nReached files older than earliest capture time. Terminating search.")
            return found_files
        # Print the current subdirectory being searched
        message = f"Searching in: {os.path.dirname(file_path)}"
        # Do not print the same message twice, stdout is slow
        if message != last_message:
            last_message = message
            print_overwrite(f"{message} ({datetime.fromtimestamp(mtime)}, {i}/{len(file_list)})")
        i += 1
        if file_path.lower().endswith(image_endings):
            metadata_id, _ = get_image_metadata(file_path)
        else:
            metadata_id, _ = get_video_metadata(file_path)
        if metadata_id in sdcard_metadata:
            # Match found, remove from sdcard_metadata
            del sdcard_metadata[metadata_id]
            found_files += 1
            if not sdcard_metadata:
                print("\nAll files have been matched. Terminating early.")
                return found_files
    print()  # For newline after the last print
    return found_files

def main():
    parser = argparse.ArgumentParser(description='Verify SD card files have been copied to PC.')
    parser.add_argument('sdcard_dir', help='Path to the SD card directory')
    parser.add_argument('pc_dir', help='Path to the PC base directory to search')
    parser.add_argument('--extensions', nargs='+', default=(list(image_endings) + ['.mov', '.mp4']),
                        help='List of file extensions to include (e.g., .jpg .mov)')
    parser.add_argument('--exclude', default='',
                        help='Relative path exclusion regex for PC directory traversal')
    args = parser.parse_args()

    print("Building metadata map of SD card files...")
    sdcard_metadata, earliest_capture_timestamp = build_sdcard_metadata(args.sdcard_dir, tuple(ext.lower() for ext in args.extensions))
    print(f"Total files to match from SD card: {len(sdcard_metadata)}")

    if earliest_capture_timestamp:
        earliest_capture_datetime = datetime.fromtimestamp(earliest_capture_timestamp)
        print(f"Earliest capture time from SD card: {earliest_capture_datetime}")
    else:
        print("Could not determine earliest capture time from SD card files.")

    if not sdcard_metadata:
        print("No files found on SD card with the specified extensions.")
        sys.exit()

    looking_for = len(sdcard_metadata)
    print("Traversing PC directory to find matches...")
    found = traverse_pc_directory(args.pc_dir, sdcard_metadata, args.exclude, tuple(ext.lower() for ext in args.extensions), earliest_capture_timestamp)
    if looking_for != found:
        print(f"Warning: Only {found} out of {looking_for} files were found on the PC. This could indicate a bug in this script.")

    if sdcard_metadata:
        print(f"\nFiles on SD card not found on PC ({len(sdcard_metadata)}):")
        for metadata_id, file_path in sdcard_metadata.items():
            print(f"- {file_path}")
    else:
        print("All files from SD card are present on PC.")

if __name__ == '__main__':
    main()

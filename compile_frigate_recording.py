#!/usr/bin/env python3
"""
Compile Frigate recordings into a single MP4 file.

Usage:
    python compile_frigate_recording.py --date 2026-04-13 --start 14:30 --end 15:45 --camera "Bryggers" --output output.mp4
"""

import argparse
import os
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path


def parse_time(time_str):
    """Parse time string in HH:MM format."""
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        raise ValueError(f"Invalid time format: {time_str}. Use HH:MM format.")


def parse_date(date_str):
    """Parse date string in YYYY-MM-DD format."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD format.")


def get_time_minutes(time_obj):
    """Convert time object to total minutes since midnight."""
    return time_obj.hour * 60 + time_obj.minute


def get_file_key(filename):
    """Extract minute.second from filename (e.g., '14.30.mp4' -> (14, 30))."""
    try:
        base = filename.replace(".mp4", "")
        parts = base.split(".")
        if len(parts) == 2:
            return (int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        pass
    return None


def get_file_timestamp(hour, minute, second):
    """Get absolute minute count for a file timestamp within a day."""
    return hour * 60 + minute + second / 60.0


def find_recording_files(base_path, date, start_time, end_time, camera, timezone_offset_hours=0):
    """
    Find all recording files within the specified time range.
    
    Args:
        timezone_offset_hours: Hours to add to input times to match Frigate's timezone.
                              Use 2 if Frigate is 2 hours ahead of your input timezone.
    
    Returns a list of absolute paths to MP4 files sorted by time.
    """
    date_obj = parse_date(date)
    start_time_obj = parse_time(start_time)
    end_time_obj = parse_time(end_time)
    
    # Apply timezone offset
    start_dt = datetime.combine(date_obj, start_time_obj) + timedelta(hours=timezone_offset_hours)
    end_dt = datetime.combine(date_obj, end_time_obj) + timedelta(hours=timezone_offset_hours)
    
    date_obj = start_dt.date()
    start_time_obj = start_dt.time()
    end_time_obj = end_dt.time()
    
    recording_files = []
    
    # Check if we cross midnight (end time is earlier than start time)
    crosses_midnight = end_time_obj < start_time_obj
    
    if crosses_midnight:
        # Check from start_hour to 23, then 0 to end_hour next day
        hours_today = list(range(start_time_obj.hour, 24))
        hours_tomorrow = list(range(0, end_time_obj.hour + 1))
        dates_and_hours = [(date_obj, h) for h in hours_today] + \
                          [((date_obj + timedelta(days=1)), h) for h in hours_tomorrow]
    else:
        # Normal case: all in the same day
        hours_today = list(range(start_time_obj.hour, end_time_obj.hour + 1))
        dates_and_hours = [(date_obj, h) for h in hours_today]
    
    for check_date, hour in dates_and_hours:
        hour_path = base_path / str(check_date) / f"{hour:02d}" / camera
        
        if not hour_path.exists():
            continue
        
        # Find all MP4 files in this hour
        for file in sorted(hour_path.glob("*.mp4")):
            file_key = get_file_key(file.name)
            if file_key is None:
                continue
            
            minute, second = file_key
            file_time = start_time_obj.__class__(hour, minute, second)  # Create a time object
            
            # Check if this file's time is within range
            if crosses_midnight:
                # File is included if: it's after start today OR it's before/equal to end tomorrow
                within_range = file_time >= start_time_obj or file_time <= end_time_obj
            else:
                # File is included if: it's >= start AND <= end
                within_range = start_time_obj <= file_time <= end_time_obj
            
            if within_range:
                recording_files.append(file)
    
    return recording_files


def create_concat_file(files, concat_file):
    """Create FFmpeg concat demuxer file."""
    with open(concat_file, "w") as f:
        for file_path in files:
            # FFmpeg requires absolute paths and escaped characters
            abs_path = str(file_path.resolve())
            # Escape single quotes in path
            abs_path = abs_path.replace("'", "'\\''")
            f.write(f"file '{abs_path}'\n")


def compile_recordings(base_path, date, start_time, end_time, camera, output_file, copy_codec=True, timezone_offset_hours=0):
    """
    Compile Frigate recordings into a single MP4 file.
    
    Args:
        base_path: Path to Frigate storage (/mnt/frigate)
        date: Date in YYYY-MM-DD format
        start_time: Start time in HH:MM format (in your local timezone)
        end_time: End time in HH:MM format (in your local timezone)
        camera: Camera name (folder name in Frigate)
        output_file: Output MP4 filename
        copy_codec: If True, copy without re-encoding (faster). If False, re-encode.
        timezone_offset_hours: Hours to add to convert from your timezone to Frigate's timezone.
                              If Frigate is 2 hours ahead, use 2.
    """
    base_path = Path(base_path)
    recordings_path = base_path / "recordings"
    
    if not recordings_path.exists():
        raise FileNotFoundError(f"Recordings directory not found: {recordings_path}")
    
    print(f"Searching for recordings...")
    print(f"  Date: {date}")
    print(f"  Camera: {camera}")
    print(f"  Time: {start_time} - {end_time} (input timezone)")
    if timezone_offset_hours != 0:
        print(f"  Timezone offset: +{timezone_offset_hours} hours")
    
    # Find all relevant files
    files = find_recording_files(recordings_path, date, start_time, end_time, camera, timezone_offset_hours)
    
    if not files:
        raise ValueError("No recording files found for the specified parameters.")
    
    print(f"Found {len(files)} recording segments")
    for f in files[:5]:  # Show first 5 files
        print(f"  - {f.name}")
    if len(files) > 5:
        print(f"  ... and {len(files) - 5} more")
    
    # Create temporary concat file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        concat_file = tmp.name
        create_concat_file(files, concat_file)
    
    try:
        # Build FFmpeg command
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
        ]
        
        if copy_codec:
            cmd.extend(["-c", "copy"])
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "medium",
                "-c:a", "aac",
            ])
        
        cmd.extend([
            "-y",  # Overwrite output file
            str(output_path),
        ])
        
        print(f"\nCompiling video...")
        print(f"Output: {output_path}")
        
        result = subprocess.run(cmd, check=True, capture_output=False)
        
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"\nSuccess! Created {output_path} ({size_mb:.2f} MB)")
        
    finally:
        # Clean up temporary concat file
        try:
            os.remove(concat_file)
        except:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="Compile Frigate recordings into a single MP4 file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compile recordings from 2:30 PM to 3:45 PM
  python compile_frigate_recording.py \\
    --date 2026-04-13 --start 14:30 --end 15:45 \\
    --camera "Bryggers" --output output.mp4

  # Using default Frigate path
  python compile_frigate_recording.py \\
    --date 2026-04-13 --start 09:00 --end 10:00 \\
    --camera "Driveway" --output driveway_recording.mp4
        """
    )
    
    parser.add_argument(
        "--date",
        required=True,
        help="Date in YYYY-MM-DD format"
    )
    parser.add_argument(
        "--start",
        required=True,
        help="Start time in HH:MM format (24-hour)"
    )
    parser.add_argument(
        "--end",
        required=True,
        help="End time in HH:MM format (24-hour)"
    )
    parser.add_argument(
        "--camera",
        required=True,
        help="Camera name (as it appears in Frigate)"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output MP4 filename"
    )
    parser.add_argument(
        "--frigate-path",
        default="/mnt/frigate",
        help="Path to Frigate storage (default: /mnt/frigate)"
    )
    parser.add_argument(
        "--reencode",
        action="store_true",
        help="Re-encode video (slower but handles some edge cases)"
    )
    parser.add_argument(
        "--timezone-offset",
        type=int,
        default=0,
        help="Hours to add to convert from input timezone to Frigate's timezone (default: 0). Use 2 if Frigate is 2 hours ahead."
    )
    
    args = parser.parse_args()
    
    try:
        compile_recordings(
            args.frigate_path,
            args.date,
            args.start,
            args.end,
            args.camera,
            args.output,
            copy_codec=not args.reencode,
            timezone_offset_hours=args.timezone_offset
        )
    except Exception as e:
        print(f"Error: {e}", file=__import__("sys").stderr)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

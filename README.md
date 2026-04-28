# Frigate Recording Compiler

A Python script to compile Frigate surveillance recordings into a single MP4 file. Perfect for extracting clips from specific time periods and cameras.

## Requirements

- Python 3.6+
- FFmpeg (with concat demuxer support)

### Install FFmpeg

**Ubuntu/Debian:**
```bash
sudo apt-get install ffmpeg
```

## Installation

No additional Python dependencies needed - only uses standard library!

## Usage

```bash
python compile_frigate_recording.py \
  --date YYYY-MM-DD \
  --start HH:MM \
  --end HH:MM \
  --camera "CAMERA_NAME" \
  --output output.mp4
```

## Parameters

- `--date` (required): Recording date in YYYY-MM-DD format
- `--start` (required): Start time in HH:MM format (24-hour)
- `--end` (required): End time in HH:MM format (24-hour)
- `--camera` (required): Camera name (folder name in your Frigate installation)
- `--output` (required): Output MP4 filename
- `--frigate-path` (optional): Path to Frigate storage (default: `/mnt/frigate`)
- `--reencode` (optional): Re-encode video (slower but handles some codec issues)
- `--timezone-offset` (optional): Hours to add to convert from your timezone to Frigate's timezone (default: 0). Use 2 if Frigate is 2 hours ahead of your local time.

## Examples

### Extract a 1-hour clip

```bash
python compile_frigate_recording.py \
  --date 2026-04-13 \
  --start 14:30 \
  --end 15:30 \
  --camera "Bryggers" \
  --output bryggers_afternoon.mp4
```

### Extract from Driveway camera, early morning

```bash
python compile_frigate_recording.py \
  --date 2026-04-12 \
  --start 06:00 \
  --end 07:00 \
  --camera "Driveway" \
  --output driveway_morning.mp4
```

### Extract across midnight (previous day to next day)

```bash
python compile_frigate_recording.py \
  --date 2026-04-12 \
  --start 23:00 \
  --end 01:00 \
  --camera "Road" \
  --output road_overnight.mp4
```

### Custom Frigate path

```bash
python compile_frigate_recording.py \
  --date 2026-04-13 \
  --start 10:00 \
  --end 11:00 \
  --camera "Loft" \
  --output loft_clip.mp4 \
  --frigate-path /custom/frigate/path
```

### Re-encode video (if you encounter codec issues)

```bash
python compile_frigate_recording.py \
  --date 2026-04-13 \
  --start 14:00 \
  --end 15:00 \
  --camera "EntreD340P" \
  --output output.mp4 \
  --reencode
```

### Handle timezone differences (Frigate 2 hours ahead)

```bash
python compile_frigate_recording.py \
  --date 2026-04-28 \
  --start 17:50 \
  --end 18:10 \
  --camera "Bryggers" \
  --output bryggers_clip.mp4 \
  --timezone-offset 2
```

## How It Works

1. **Finds** all MP4 segments from your Frigate recordings that fall within the specified time range
2. **Creates** a temporary FFmpeg concat file listing all segments in order
3. **Compiles** the segments into a single MP4 using FFmpeg's concat demuxer
4. **Cleans up** temporary files

By default, video codec is copied (not re-encoded) for maximum speed. Use `--reencode` if you encounter issues.

## Frigate Directory Structure

The script expects Frigate recordings to be organized as:

```
/mnt/frigate/recordings/
  YYYY-MM-DD/
    HH/
      CAMERA_NAME/
        MM.SS.mp4
```

Example:
```
/mnt/frigate/recordings/2026-04-13/14/Bryggers/30.45.mp4
```

## Camera Names

List available cameras from your Frigate installation:

```bash
ls /mnt/frigate/recordings/2026-04-13/00/
```

You should see directory names for each camera (e.g., "Bryggers", "Driveway", "Road", etc.).

## Troubleshooting

### "No recording files found"
- Verify the date is correct and has recordings
- Check the camera name matches exactly (case-sensitive)
- Ensure the time range contains recordings

### "FFmpeg not found"
- Install FFmpeg (see Requirements section)

### Output file is corrupted
- Try using `--reencode` flag to re-encode the video
- Ensure you have enough disk space

### Slow compilation
- This is normal when compiling many segments - it's still fast compared to re-encoding
- Use `--reencode` only if necessary, as it will be significantly slower

## Performance

- **Without `--reencode`** (default): Very fast (just copying streams)
- **With `--reencode`**: Much slower but ensures compatibility

For most use cases, the default (copy codec) is recommended.

## Notes

- Time range is inclusive (includes all files from start through end times)
- Handles time ranges crossing midnight (e.g., 23:00 to 01:00)
- Only requires Python 3.6+ and FFmpeg - no heavy dependencies!

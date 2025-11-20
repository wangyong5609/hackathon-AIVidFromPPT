"""
Video synthesis core module - FFmpeg implementation
Responsible for combining multiple image segments with audio into a complete video
"""

import os
import subprocess
import json


def parse_srt_file(srt_path):
    """
    Parse SRT subtitle file

    Args:
        srt_path (str): SRT subtitle file path

    Returns:
        list: Subtitle list, each element is a dictionary:
            - start: Start time (seconds)
            - end: End time (seconds)
            - text: Subtitle text
    """
    subtitles = []

    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split subtitle blocks by empty lines
    blocks = content.strip().split('\n\n')

    for block in blocks:
        lines = block.split('\n')
        if len(lines) >= 3:
            # Parse timeline, format: 00:00:01,000 --> 00:00:03,000
            time_line = lines[1]
            start_str, end_str = time_line.split(' --> ')

            # Convert time string to seconds
            start_time = srt_time_to_seconds(start_str)
            end_time = srt_time_to_seconds(end_str)

            # Subtitle text may have multiple lines
            text = '\n'.join(lines[2:])

            subtitles.append({
                'start': start_time,
                'end': end_time,
                'text': text
            })

    return subtitles


def srt_time_to_seconds(time_str):
    """
    Convert SRT time format to seconds

    Args:
        time_str (str): Time string, format: 00:00:01,000

    Returns:
        float: Seconds
    """
    # Format: HH:MM:SS,mmm
    time_part, ms_part = time_str.split(',')
    h, m, s = map(int, time_part.split(':'))
    ms = int(ms_part)

    return h * 3600 + m * 60 + s + ms / 1000.0


def get_audio_duration(audio_path):
    """
    Get audio file duration using FFprobe

    Args:
        audio_path (str): Audio file path

    Returns:
        float: Duration in seconds
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        audio_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def get_video_info(video_path):
    """
    Get video dimensions and duration using FFprobe

    Args:
        video_path (str): Video file path

    Returns:
        dict: Video information with keys 'width', 'height', 'duration'
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,duration',
        '-of', 'json',
        video_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)

    stream = data['streams'][0]
    return {
        'width': stream['width'],
        'height': stream['height'],
        'duration': float(stream.get('duration', 0))
    }


def remove_green_background(video_path, output_path):
    """
    Remove green screen background from video using chromakey filter

    Args:
        video_path (str): Input video file path with green background
        output_path (str): Output video file path with transparent background

    Returns:
        str: Output video file path
    """
    print(f"Removing green background from video: {video_path}")

    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output file
        '-i', video_path,
        '-vf', 'chromakey=0x00ff00:0.3:0.2,format=yuva420p',
        '-c:v', 'libvpx-vp9',  # VP9 codec supports alpha channel
        '-pix_fmt', 'yuva420p',
        '-b:v', '2M',
        '-c:a', 'libopus',  # Use Opus audio codec for WebM
        '-b:a', '128k',
        '-auto-alt-ref', '0',  # Disable alt-ref frames for VP9 (better compatibility)
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"FFmpeg green screen removal stderr: {result.stderr}")
        raise RuntimeError(f"Green screen removal failed with return code {result.returncode}")

    print(f"Green background removed successfully: {output_path}")
    return output_path


def srt_to_ass(srt_path, ass_path, font_name='STHeiti Medium'):
    """
    Convert SRT subtitle to ASS format with Chinese font support

    Args:
        srt_path (str): Input SRT file path
        ass_path (str): Output ASS file path
        font_name (str): Font name to use
    """
    subtitles = parse_srt_file(srt_path)

    # ASS file header with Chinese font
    ass_content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,0,2,10,10,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Convert subtitles to ASS format
    for sub in subtitles:
        start_time = seconds_to_ass_time(sub['start'])
        end_time = seconds_to_ass_time(sub['end'])
        text = sub['text'].replace('\n', '\\N')
        ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}\n"

    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)

    print(f"Converted SRT to ASS: {ass_path}")


def seconds_to_ass_time(seconds):
    """
    Convert seconds to ASS time format (H:MM:SS.CS)

    Args:
        seconds (float): Time in seconds

    Returns:
        str: ASS time format
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def process_single_segment(image_path, audio_path, output_path, video_path=None, subtitle_path=None):
    """
    Process a single segment: convert image to video with audio duration, optionally overlay digital human video, add subtitles

    Args:
        image_path (str): Image file path
        audio_path (str): Audio file path (required)
        output_path (str): Output video file path
        video_path (str): Digital human video file path (optional)
        subtitle_path (str): Subtitle file path (optional)

    Returns:
        str: Output video file path
    """
    # Get audio duration
    audio_duration = get_audio_duration(audio_path)
    print(f"Audio duration: {audio_duration} seconds")

    # Build FFmpeg command
    # Base: create video from image with audio
    if video_path:
        # Complex filter for overlaying digital human video with green screen removal
        # 1. Create background video from image
        # 2. Apply chromakey filter to digital human video to remove green background
        # 3. Loop/trim digital human video to match audio duration
        # 4. Scale digital human video to 1/5 of background width
        # 5. Overlay at bottom-right corner

        # First, get video info to calculate scaling
        video_info = get_video_info(video_path)

        # Build complex filter with inline chromakey
        # Chromakey parameters balanced for removing green background while preserving the person:
        # - similarity: 0.25 (moderate - removes green background but preserves person)
        # - blend: 0.1 (moderate edge blending)
        filter_complex = (
            # Input 0 (image): loop and scale to create background
            "[0:v]loop=loop=-1:size=1:start=0,scale=1920:1080,setsar=1,fps=24[bg];"
            # Input 1 (digital human video): apply chromakey with balanced parameters, trim or loop to match duration, scale
            f"[1:v]chromakey=0x00ff00:0.25:0.1,trim=duration={audio_duration},setpts=PTS-STARTPTS,"
            # Scale to 3/20 of background width (288 pixels), maintain aspect ratio
            "scale=288:-1[human];"
            # Overlay human video on background at bottom-right with 20px padding
            "[bg][human]overlay=W-w-20:H-h-20[outv]"
        )

        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file
            '-loop', '1',  # Loop image
            '-i', image_path,  # Input 0: background image
            '-i', video_path,  # Input 1: digital human video (with green background)
            '-i', audio_path,  # Input 2: audio
            '-filter_complex', filter_complex,
            '-map', '[outv]',  # Use filtered video
            '-map', '2:a',  # Use audio from input 2
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-t', str(audio_duration),  # Duration from audio
            '-pix_fmt', 'yuv420p',
            output_path
        ]
    else:
        # Simple: just image + audio
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file
            '-loop', '1',  # Loop image
            '-i', image_path,  # Input: background image
            '-i', audio_path,  # Input: audio
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-tune', 'stillimage',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-t', str(audio_duration),  # Duration from audio
            '-pix_fmt', 'yuv420p',
            '-vf', 'scale=1920:1080,fps=24',
            output_path
        ]

    # Execute FFmpeg command
    print(f"Executing FFmpeg command...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"FFmpeg stderr: {result.stderr}")
        raise RuntimeError(f"FFmpeg failed with return code {result.returncode}")

    # If subtitles are provided, add them using drawtext filter (most reliable for Chinese)
    if subtitle_path:
        temp_output = output_path + '.temp.mp4'
        os.rename(output_path, temp_output)

        # Find available Chinese font file
        # Support Windows, macOS, and Linux font paths
        font_paths = [
            # Windows paths (common Chinese fonts)
            'C:/Windows/Fonts/msyh.ttc',  # Microsoft YaHei
            'C:/Windows/Fonts/msyhbd.ttc',  # Microsoft YaHei Bold
            'C:/Windows/Fonts/simhei.ttf',  # SimHei (黑体)
            'C:/Windows/Fonts/simsun.ttc',  # SimSun (宋体)
            'C:/Windows/Fonts/simkai.ttf',  # KaiTi (楷体)
            'C:/Windows/Fonts/STXIHEI.TTF',  # STXihei
            # Linux paths (common Chinese fonts)
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
            '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/arphic/uming.ttc',
            '/usr/share/fonts/truetype/arphic/ukai.ttc',
            # macOS paths
            '/System/Library/Fonts/STHeiti Medium.ttc',
            '/System/Library/Fonts/STHeiti Light.ttc',
            '/System/Library/Fonts/PingFang.ttc',
            '/System/Library/Fonts/Hiragino Sans GB.ttc',
            '/Library/Fonts/Arial Unicode.ttf'
        ]

        font_file = None
        for font_path in font_paths:
            if os.path.exists(font_path):
                font_file = font_path
                print(f"Found Chinese font: {font_file}")
                break

        if not font_file:
            print("Warning: No Chinese font found in standard locations")
            print("Attempting to use system default font")
            # Try to use fc-match to find a Chinese font on Linux/macOS
            try:
                result = subprocess.run(['fc-match', '-f', '%{file}', ':lang=zh'],
                                        capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    font_file = result.stdout.strip()
                    print(f"Found font via fc-match: {font_file}")
                else:
                    # Last resort: try common font names
                    font_file = 'Microsoft YaHei' if os.name == 'nt' else 'Arial'
            except Exception as e:
                print(f"Could not find font with fc-match: {e}")
                # Use platform-specific fallback
                font_file = 'Microsoft YaHei' if os.name == 'nt' else 'Arial'

        # Parse SRT file
        subtitles = parse_srt_file(subtitle_path)

        # Build drawtext filter chain for each subtitle
        # Each subtitle becomes a separate drawtext that's enabled only during its time range
        drawtext_filters = []

        for i, sub in enumerate(subtitles):
            # Escape text for FFmpeg (escape single quotes and colons)
            text = sub['text'].replace("'", "'\\\\\\''").replace(':', '\\:')

            # Enable subtitle only during its time range
            enable_condition = f"between(t,{sub['start']},{sub['end']})"

            # Build drawtext filter
            drawtext = (
                f"drawtext=fontfile='{font_file}'"
                f":text='{text}'"
                f":x=(w-text_w)/2"  # Center horizontally
                f":y=h-th-50"  # 50px from bottom
                f":fontsize=48"
                f":fontcolor=white"
                f":borderw=3"
                f":bordercolor=black"
                f":enable='{enable_condition}'"
            )
            drawtext_filters.append(drawtext)

        # Combine all drawtext filters
        vf_filter = ','.join(drawtext_filters)

        # Add subtitles using drawtext filter
        subtitle_cmd = [
            'ffmpeg',
            '-y',
            '-i', temp_output,
            '-vf', vf_filter,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'copy',
            output_path
        ]

        print(f"Adding subtitles with drawtext using font: {font_file}")
        print(f"Total {len(subtitles)} subtitle entries")
        result = subprocess.run(subtitle_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"FFmpeg subtitle stderr: {result.stderr}")
            # Restore original if subtitle adding fails
            os.rename(temp_output, output_path)
        else:
            # Remove temporary file
            os.remove(temp_output)

    print(f"Segment processed successfully: {output_path}")
    return output_path


def synthesize_video(segments_data, output_path="output/final_video.mp4", transition_duration=0):
    """
    Synthesize final video from image and audio segments

    Processing logic:
    1. First synthesize each segment completely (image + audio + optional digital human video + optional subtitles)
    2. Then concatenate the finished segment videos in order

    Args:
        segments_data (list): Segment data list, each element contains:
            - image_path: Image file path
            - audio_path: Audio file path (required)
            - video_path: Digital human video file path (optional)
            - subtitle_path: Subtitle file path (optional, starts from 0s for each segment)
        output_path (str): Output video file path
        transition_duration (float): Transition duration (seconds), default 0 (no transition)

    Returns:
        str: Output video file path
    """
    print(f"Starting video synthesis, total {len(segments_data)} segments")

    # Ensure output directory and temp directory exist
    output_dir = os.path.dirname(output_path) or 'output'
    os.makedirs(output_dir, exist_ok=True)

    # Create temp directory in the same parent as output directory
    temp_dir = os.path.join(os.path.dirname(output_dir) or '.', 'temp')
    os.makedirs(temp_dir, exist_ok=True)

    # Step 1: Process and save each segment individually
    segment_video_paths = []
    total_segments = len(segments_data)

    for i, segment in enumerate(segments_data, 1):
        print(f"Processing segment {i}/{total_segments}...")

        # Output path for this segment in temp directory
        segment_output_path = os.path.join(temp_dir, f'segment_{i}.mp4')

        # Process single segment completely
        process_single_segment(
            image_path=segment['image_path'],
            audio_path=segment['audio_path'],
            output_path=segment_output_path,
            video_path=segment.get('video_path'),
            subtitle_path=segment.get('subtitle_path')
        )

        segment_video_paths.append(segment_output_path)

    # Step 2: Concatenate all segments using FFmpeg concat demuxer
    print("Concatenating all segments...")

    # Create concat file list in temp directory
    concat_file_path = os.path.join(temp_dir, 'concat_list.txt')
    with open(concat_file_path, 'w', encoding='utf-8') as f:
        for seg_path in segment_video_paths:
            # Use absolute path to avoid issues
            abs_path = os.path.abspath(seg_path)
            f.write(f"file '{abs_path}'\n")

    # Concatenate using concat demuxer (fastest and most reliable)
    concat_cmd = [
        'ffmpeg',
        '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_file_path,
        '-c', 'copy',  # Stream copy for fastest concatenation
        output_path
    ]

    print(f"Executing FFmpeg concatenation...")
    result = subprocess.run(concat_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"FFmpeg concatenation stderr: {result.stderr}")
        raise RuntimeError(f"FFmpeg concatenation failed with return code {result.returncode}")

    # Clean up temporary segment files
    print("Cleaning up temporary segment files...")
    for seg_path in segment_video_paths:
        try:
            os.remove(seg_path)
        except Exception as e:
            print(f"Warning: Failed to remove temporary file {seg_path}: {e}")

    # Clean up concat file
    try:
        os.remove(concat_file_path)
    except Exception as e:
        print(f"Warning: Failed to remove concat file {concat_file_path}: {e}")

    print("Video synthesis complete!")
    return output_path

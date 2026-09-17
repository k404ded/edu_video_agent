"""
Video Maker: Assembles the final educational video (final_video.mp4)
by synchronizing rendered 1080p PPT slide visuals with their spoken AI voice-over audio clips.

Encodes with standard H.264 (yuv420p) video and AAC audio for 100% universal playback
across browsers, Windows Media Player, macOS, and mobile devices.
"""
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List
import imageio_ffmpeg

from config import VIDEO_FPS
from media.tts_generator import get_audio_duration_seconds, get_ffmpeg_binary


def assemble_video(
    slide_image_paths: List[str],
    slide_audio_paths: List[str],
    output_dir: str = "output/generated",
    fps: int = VIDEO_FPS,
    slide_buffer_seconds: float = 0.5,
) -> str:
    """
    Creates final_video.mp4 by:
    1. For each slide image + audio pair, rendering an exact-length video clip.
    2. Seamlessly concatenating all clips into one master MP4.
    Returns the absolute path to final_video.mp4.
    """
    if len(slide_image_paths) != len(slide_audio_paths):
        raise ValueError(
            f"Mismatched count: {len(slide_image_paths)} images vs {len(slide_audio_paths)} audio files."
        )

    media_dir = os.path.abspath(output_dir)
    segments_dir = os.path.join(media_dir, "segments")
    os.makedirs(segments_dir, exist_ok=True)

    ffmpeg_exe = get_ffmpeg_binary()
    final_video_path = os.path.join(media_dir, "final_video.mp4")

    segment_paths: List[str] = []

    for idx, (img_path, aud_path) in enumerate(zip(slide_image_paths, slide_audio_paths)):
        seg_output = os.path.join(segments_dir, f"segment_{idx:03d}.mp4")
        audio_dur = get_audio_duration_seconds(aud_path)
        total_segment_dur = max(audio_dur + slide_buffer_seconds, 1.5)

        # Build segment: loop single image with audio and slight comfortable trailing pause
        # Try libx264 first, fallback to mpeg4 if libx264 is unavailable on the host
        rendered = False
        last_error = None
        for vcodec in ["libx264", "mpeg4"]:
            cmd = [
                ffmpeg_exe,
                "-y",
                "-loop", "1",
                "-framerate", str(fps),
                "-i", str(Path(img_path).resolve()),
                "-i", str(Path(aud_path).resolve()),
                "-af", f"apad=pad_dur={slide_buffer_seconds}",
                "-t", f"{total_segment_dur:.3f}",
                "-c:v", vcodec,
                "-tune", "stillimage",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                seg_output
            ]
            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
                if res.returncode == 0 and os.path.exists(seg_output) and os.path.getsize(seg_output) > 0:
                    rendered = True
                    break
                else:
                    last_error = res.stderr
            except Exception as e:
                last_error = str(e)

        if not rendered:
            print(f"[VideoMaker] Segment {idx} failed to render: {last_error}")
            return ""

        segment_paths.append(seg_output)

    if not segment_paths:
        return ""

    # Concatenate all segments into final_video.mp4
    concat_list_file = os.path.join(segments_dir, "segments_list.txt")
    with open(concat_list_file, "w", encoding="utf-8") as f:
        for seg in segment_paths:
            norm_path = str(Path(seg).resolve()).replace("\\", "/")
            f.write(f"file '{norm_path}'\n")

    # Try fast stream copy concat first, then re-encode concat fallback
    concat_success = False
    for concat_args in [
        ["-c", "copy"],
        ["-c:v", "libx264", "-c:a", "aac"],
        ["-c:v", "mpeg4", "-c:a", "aac"],
    ]:
        concat_cmd = [
            ffmpeg_exe,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_file,
            *concat_args,
            final_video_path
        ]
        try:
            res = subprocess.run(concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
            if res.returncode == 0 and os.path.exists(final_video_path) and os.path.getsize(final_video_path) > 0:
                concat_success = True
                break
        except Exception as e:
            print(f"[VideoMaker] Concat attempt notice: {e}")

    if concat_success and os.path.exists(final_video_path):
        return final_video_path
    return ""

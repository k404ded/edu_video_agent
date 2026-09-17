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
    master_audio_path: str = "",
) -> str:
    """
    Creates final_video.mp4 by synchronizing slide visuals with voice-over narration.
    1. Primary Method: Ultra-fast single-pass concat demuxer (takes < 1 second).
    2. Secondary Fallback: Multi-codec (libx264 -> mpeg4).
    3. Tertiary Fallback: Segment-by-segment assembly.
    Returns the absolute path to final_video.mp4, or empty string on failure.
    """
    if len(slide_image_paths) != len(slide_audio_paths):
        raise ValueError(
            f"Mismatched count: {len(slide_image_paths)} images vs {len(slide_audio_paths)} audio files."
        )
    if not slide_image_paths:
        return ""

    media_dir = os.path.abspath(output_dir)
    os.makedirs(media_dir, exist_ok=True)
    final_video_path = os.path.join(media_dir, "final_video.mp4")

    # Resolve master audio file
    master_audio = master_audio_path if master_audio_path and os.path.exists(master_audio_path) else os.path.join(media_dir, "voiceover.wav")
    if not os.path.exists(master_audio) or os.path.getsize(master_audio) == 0:
        from media.tts_generator import combine_wav_files
        try:
            combine_wav_files(slide_audio_paths, master_audio)
        except Exception as e:
            print(f"[VideoMaker] Could not prepare master audio: {e}")

    ffmpeg_exe = get_ffmpeg_binary()

    # Calculate exact duration for each slide from its audio
    durations = []
    for aud_p in slide_audio_paths:
        dur = get_audio_duration_seconds(aud_p)
        durations.append(max(dur + slide_buffer_seconds, 1.5))

    # -------------------------------------------------------------------------
    # METHOD 1: Fast Single-Pass Concat Demuxer (< 1 second, low RAM & CPU)
    # -------------------------------------------------------------------------
    concat_script = os.path.join(media_dir, "slides_concat.txt")
    try:
        with open(concat_script, "w", encoding="utf-8") as f:
            for img_p, dur in zip(slide_image_paths, durations):
                norm_img = str(Path(img_p).resolve()).replace("\\", "/")
                f.write(f"file '{norm_img}'\n")
                f.write(f"duration {dur:.3f}\n")
            # Concat demuxer requirement: repeat the last image so its duration takes effect
            norm_last = str(Path(slide_image_paths[-1]).resolve()).replace("\\", "/")
            f.write(f"file '{norm_last}'\n")

        codec_options = [
            ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage"],
            ["-c:v", "libx264", "-preset", "veryfast"],
            ["-c:v", "mpeg4", "-q:v", "3"],
        ]

        for vcodec_args in codec_options:
            cmd = [
                ffmpeg_exe,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_script,
                "-i", master_audio,
                *vcodec_args,
                "-pix_fmt", "yuv420p",
                "-threads", "1",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                "-movflags", "+faststart",
                final_video_path,
            ]
            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
                if res.returncode == 0 and os.path.exists(final_video_path) and os.path.getsize(final_video_path) > 1000:
                    return final_video_path
                else:
                    print(f"[VideoMaker] Single-pass attempt notice: {res.stderr[-200:] if res.stderr else 'unknown'}")
            except Exception as e:
                print(f"[VideoMaker] Single-pass execution notice: {e}")
    except Exception as e:
        print(f"[VideoMaker] Single-pass script creation notice: {e}")

    # -------------------------------------------------------------------------
    # METHOD 2: Segment-by-segment encoding fallback
    # -------------------------------------------------------------------------
    segments_dir = os.path.join(media_dir, "segments")
    os.makedirs(segments_dir, exist_ok=True)
    segment_paths: List[str] = []

    for idx, (img_path, aud_path) in enumerate(zip(slide_image_paths, slide_audio_paths)):
        seg_output = os.path.join(segments_dir, f"segment_{idx:03d}.mp4")
        audio_dur = get_audio_duration_seconds(aud_path)
        total_segment_dur = max(audio_dur + slide_buffer_seconds, 1.5)

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
                "-threads", "1",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                seg_output,
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

        if rendered:
            segment_paths.append(seg_output)

    if segment_paths and len(segment_paths) == len(slide_image_paths):
        concat_list_file = os.path.join(segments_dir, "segments_list.txt")
        with open(concat_list_file, "w", encoding="utf-8") as f:
            for seg in segment_paths:
                norm_path = str(Path(seg).resolve()).replace("\\", "/")
                f.write(f"file '{norm_path}'\n")

        for concat_args in [["-c", "copy"], ["-c:v", "libx264", "-c:a", "aac"], ["-c:v", "mpeg4", "-c:a", "aac"]]:
            concat_cmd = [
                ffmpeg_exe,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list_file,
                *concat_args,
                "-movflags", "+faststart",
                final_video_path,
            ]
            try:
                res = subprocess.run(concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
                if res.returncode == 0 and os.path.exists(final_video_path) and os.path.getsize(final_video_path) > 0:
                    return final_video_path
            except Exception:
                pass

    if os.path.exists(final_video_path) and os.path.getsize(final_video_path) > 1000:
        return final_video_path
    return ""


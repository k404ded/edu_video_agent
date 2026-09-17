"""
TTS Generator: Synthesizes natural spoken AI voice-over audio (.wav) for each educational section.

Uses Microsoft Edge Neural TTS (edge-tts) for studio-grade human narration,
with automatic fallback to Windows native SpeechSynthesizer or timed PCM WAV if offline/cloud.
Produces both per-section .wav clips and a concatenated master voiceover.wav.
"""
import os
import wave
import asyncio
import threading
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Tuple
import edge_tts
import imageio_ffmpeg

from config import TTS_VOICE
from models.schema import PipelineResult, SlideOutput


def get_ffmpeg_binary() -> str:
    """Finds a valid FFmpeg executable cross-platform (Windows & Linux)."""
    try:
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg:
        return which_ffmpeg
    return "ffmpeg"


def get_audio_duration_seconds(wav_path: str) -> float:
    """Returns the exact duration of a WAV file in seconds using standard library wave."""
    try:
        with wave.open(wav_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate) if rate > 0 else 0.0
    except Exception:
        return 0.0


def _convert_to_wav(input_path: str, output_wav_path: str) -> None:
    """Converts any audio file to 44.1kHz 16-bit stereo PCM WAV via FFmpeg."""
    ffmpeg_exe = get_ffmpeg_binary()
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", str(input_path),
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        "-ac", "2",
        str(output_wav_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg audio conversion failed: {res.stderr}")


def _synthesize_edge_tts(text: str, output_mp3: str, voice: str = TTS_VOICE) -> None:
    """
    Runs edge-tts async synthesis safely in a dedicated worker thread with
    its own independent event loop to avoid Streamlit event-loop collisions.
    """
    worker_error = None

    def _worker():
        nonlocal worker_error
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                communicate = edge_tts.Communicate(text, voice)
                loop.run_until_complete(communicate.save(output_mp3))
            finally:
                loop.close()
        except Exception as err:
            worker_error = err

    t = threading.Thread(target=_worker)
    t.start()
    t.join(timeout=30.0)

    if worker_error:
        raise worker_error
    if not os.path.exists(output_mp3) or os.path.getsize(output_mp3) == 0:
        raise RuntimeError("Edge-TTS did not produce valid audio.")


def _synthesize_windows_speech_fallback(text: str, output_wav: str) -> bool:
    """Offline Windows fallback using PowerShell System.Speech.Synthesis."""
    if os.name != "nt":
        return False
    try:
        escaped_text = text.replace('"', '""').replace("'", "''")
        escaped_wav = str(Path(output_wav).resolve()).replace("'", "''")
        ps_cmd = (
            f'Add-Type -AssemblyName System.Speech; '
            f'$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
            f'$synth.SetOutputToWaveFile(\'{escaped_wav}\'); '
            f'$synth.Speak(\'{escaped_text}\'); '
            f'$synth.Dispose();'
        )
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True)
        return res.returncode == 0 and os.path.exists(output_wav) and os.path.getsize(output_wav) > 500
    except Exception:
        return False


def _synthesize_pcm_silence(text: str, output_wav: str) -> None:
    """Safe cross-platform fallback that produces a clean PCM WAV timed to narration word count."""
    words = len(text.split())
    duration_sec = max(words / 2.5, 2.0)
    sample_rate = 44100
    num_samples = int(sample_rate * duration_sec)
    with wave.open(output_wav, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00\x00\x00" * num_samples)


def synthesize_text_to_wav(text: str, output_wav_path: str, voice: str = TTS_VOICE) -> str:
    """
    Synthesizes speech for the provided text and saves as a standard PCM .wav file.
    Tries edge-tts first; falls back to Windows speech or timed audio seamlessly without crashing.
    """
    clean_text = text.strip()
    if not clean_text:
        clean_text = "Let's continue to the next concept."

    os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)

    # 1. Try edge-tts first
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
            tmp_mp3_path = tmp_mp3.name

        _synthesize_edge_tts(clean_text, tmp_mp3_path, voice=voice)
        _convert_to_wav(tmp_mp3_path, output_wav_path)
        if os.path.exists(tmp_mp3_path):
            os.remove(tmp_mp3_path)
        return output_wav_path
    except Exception as e:
        print(f"[TTS] edge-tts error: {e}. Using fallback audio generator.")

    # 2. Try Windows PowerShell fallback if on Windows
    if _synthesize_windows_speech_fallback(clean_text, output_wav_path):
        return output_wav_path

    # 3. Clean timed audio fallback (guarantees pipeline never crashes on cloud/Linux)
    _synthesize_pcm_silence(clean_text, output_wav_path)
    return output_wav_path


def combine_wav_files(wav_paths: List[str], output_wav_path: str) -> str:
    """Concatenates multiple WAV files into one master WAV file using FFmpeg."""
    if not wav_paths:
        raise ValueError("No WAV files provided to combine.")

    if len(wav_paths) == 1:
        _convert_to_wav(wav_paths[0], output_wav_path)
        return output_wav_path

    ffmpeg_exe = get_ffmpeg_binary()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        for p in wav_paths:
            norm_path = str(Path(p).resolve()).replace("\\", "/")
            f.write(f"file '{norm_path}'\n")
        list_file = f.name

    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        "-ac", "2",
        str(output_wav_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if os.path.exists(list_file):
        os.remove(list_file)

    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg audio concatenation failed: {res.stderr}")

    return output_wav_path


def generate_voiceover(
    result: PipelineResult,
    output_dir: str = "output/generated",
    voice: str = TTS_VOICE,
) -> Tuple[str, List[str]]:
    """
    Generates spoken audio for all slides in the PipelineResult:
    1. Title slide introduction audio
    2. Section slide voiceovers
    3. Combined master voiceover.wav
    Returns (master_voiceover_wav_path, list_of_slide_audio_paths).
    """
    media_dir = os.path.abspath(output_dir)
    audio_dir = os.path.join(media_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    slide_audio_paths: List[str] = []

    # 1. Title slide audio introduction
    title_text = (
        f"Welcome to this presentation on {result.document_summary.main_topic}. "
        f"Our key objective is to {result.document_summary.learning_objective.rstrip('.')}."
    )
    title_audio_path = os.path.join(audio_dir, "slide_0_title.wav")
    synthesize_text_to_wav(title_text, title_audio_path, voice=voice)
    slide_audio_paths.append(title_audio_path)

    # 2. Section slide voiceovers
    for idx, slide_out in enumerate(result.slide_outputs, start=1):
        sec_audio_path = os.path.join(audio_dir, f"slide_{idx}_{slide_out.section_index}.wav")
        synthesize_text_to_wav(slide_out.voice_over, sec_audio_path, voice=voice)
        slide_audio_paths.append(sec_audio_path)

    # 3. Master combined voiceover.wav
    master_wav_path = os.path.join(media_dir, "voiceover.wav")
    combine_wav_files(slide_audio_paths, master_wav_path)

    return master_wav_path, slide_audio_paths

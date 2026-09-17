"""
Verification test: runs the educational media pipeline on the user's sample EV text.
Checks that presentation.pptx, voiceover.wav, and final_video.mp4 are created properly.
"""
import os
import wave
from agents.orchestrator import run_pipeline

SAMPLE_TEXT = """Introduction to Electric Vehicles

Electric vehicles use electric motors instead of conventional internal combustion engines.
They are powered by batteries that store electrical energy.

The main components of an EV include the battery pack,
electric motor, inverter, and charging system."""

def test_pipeline():
    print("[TEST] Running end-to-end pipeline with EV sample content...")
    def status_cb(msg):
        print(f"  -> {msg}")

    test_out_dir = "output/test_ev_media"
    result = run_pipeline(
        pasted_text=SAMPLE_TEXT,
        progress_callback=status_cb,
        generate_media=True,
        output_dir=test_out_dir,
    )

    print("\n[VERIFICATION]")
    print(f"1. Main Topic: {result.document_summary.main_topic}")
    print(f"2. Sections generated: {len(result.slide_outputs)}")

    # 1. Check PPTX
    assert result.pptx_path and os.path.exists(result.pptx_path), "PPTX file missing!"
    pptx_size = os.path.getsize(result.pptx_path)
    print(f"3. PPTX generated: {result.pptx_path} ({pptx_size:,} bytes) - OK")

    # 2. Check WAV
    assert result.audio_path and os.path.exists(result.audio_path), "WAV audio file missing!"
    wav_size = os.path.getsize(result.audio_path)
    with wave.open(result.audio_path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        dur = frames / float(rate)
    print(f"4. Audio WAV generated: {result.audio_path} ({wav_size:,} bytes, {dur:.2f}s duration) - OK")

    # 3. Check MP4
    assert result.video_path and os.path.exists(result.video_path), "MP4 video file missing!"
    mp4_size = os.path.getsize(result.video_path)
    print(f"5. Video MP4 generated: {result.video_path} ({mp4_size:,} bytes) - OK")

    print("\nSUCCESS: All three media outputs generated and verified!")

if __name__ == "__main__":
    test_pipeline()

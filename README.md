# Educational Video Script & Storyboard Generator — Base MVP

An AI-assisted tool that converts educational content (PPTX / PDF / pasted text) into a
source-grounded instructional video script and storyboard, ready to hand off to
Audiate (voice) and Camtasia (screen recording/editing).

This is **Phase 1 only**: PPT/PDF → script + storyboard. No TTS, no video rendering,
no editing automation. See "Future Extensibility" below.

## Architecture

```
Upload (PPTX / PDF / text)
        ↓
[1] CONTENT ANALYZER       (agents/content_analyzer.py)
        ↓
[2] SCRIPT GENERATOR         (agents/script_generator.py)
    STORYBOARD GENERATOR     (same module — shared grounded context)
        ↓
[3] QUALITY CHECKER         (agents/quality_checker.py)
        ↓
    STRUCTURED SLIDE CONTENT (PipelineResult)
        ↓
   ┌────────────────────────┬────────────────────────┐
   │                        │                        │
   ↓                        ↓                        ↓
PPT GENERATOR          TTS GENERATOR           SLIDE RENDERER
(media/ppt_generator.py) (media/tts_generator.py) (media/slide_renderer.py)
   ↓                        ↓                        ↓
presentation.pptx        voiceover.wav          1080p slide frames
   │                        │                        │
   │                        └───────────┬────────────┘
   │                                    ↓
   │                               VIDEO MAKER
   │                           (media/video_maker.py)
   │                                    ↓
   ↓                                    ↓
presentation.pptx                 final_video.mp4
```


Orchestrated by `agents/orchestrator.py`. Every stage receives structured data
(dataclasses in `models/schema.py`), not free text, so the pipeline stays predictable
and each stage's output can be inspected/tested independently.

**Source grounding:** the Content Analyzer and Script/Storyboard Generator only ever
see the extracted source text for the section they're working on. The Quality Checker
independently re-compares the *generated* voice-over/on-screen text against that same
*original* source text — not against the analysis — specifically to catch hallucinated
facts, altered numbers, dropped points, and terminology drift.

## Folder Structure

```
edu_video_agent/
├── main.py                  # Streamlit UI
├── config.py                # API key / model / pipeline settings
├── requirements.txt
├── .env.example
├── ingestion/               # PPTX/PDF/text extraction
├── agents/                  # Analyzer, script generator, QA checker, orchestrator
├── media/                   # PPT generator, TTS generator, slide renderer, video maker
├── prompts/                 # Prompt templates
├── models/                  # Structured schemas & dataclasses
└── output/                  # Text formatters & media output directory
```

## Setup & Running

1. **Navigate to the project directory:**
   ```powershell
   cd c:\Users\kimaya\Downloads\edu_video_agent\edu_video_agent
   ```

2. **Run the Streamlit app:**
   ```powershell
   ..\venv\Scripts\streamlit.exe run main.py
   ```
   Open your browser at `http://localhost:8501`.

## Demo Flow

1. Upload an educational `.pptx` or `.pdf` (or paste educational text into the text box).
2. Click **🚀 Generate Presentation, Audio & Video**.
3. Watch the live progress log as each stage runs:
   - Content extraction & document analysis
   - Script & storyboard generation
   - Source-grounding QA verification
   - Editable PowerPoint (.pptx) creation
   - Natural AI voice-over (.wav) synthesis
   - 1080p slide visual rendering
   - Final educational video (.mp4) encoding
4. Enjoy the results in the web UI:
   - **🎬 Watch the video** directly in the browser player & download `final_video.mp4`.
   - **🎙️ Listen to the narration** track & download `voiceover.wav`.
   - **📊 Download `presentation.pptx`** with 16:9 widescreen layout & speaker notes.
   - Inspect the four tabs: **Content Understanding**, **Voice-over Script**, **Storyboard**, **QA Report**.

## Media Outputs

- **Editable PowerPoint (`presentation.pptx`)**: 16:9 widescreen slides with structured cards, formatted bullets, key terms, learning objectives, and presenter speaker notes.
- **AI Voice-Over Audio (`voiceover.wav`)**: Studio-quality spoken narration generated with neural speech synthesis.
- **Final Educational Video (`final_video.mp4`)**: Crisp 1080p slides perfectly synchronized with spoken voice-over narration (H.264 / AAC).

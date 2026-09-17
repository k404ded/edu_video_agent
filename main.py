"""
Educational Video Script & Storyboard Generator — Streamlit UI.

Run with: streamlit run main.py
"""
import os
import sys
import tempfile
from pathlib import Path

# Ensure edu_video_agent directory is in sys.path and is the working directory
_CURRENT_DIR = Path(__file__).resolve().parent
if str(_CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(_CURRENT_DIR))
os.chdir(_CURRENT_DIR)

import streamlit as st

from config import GEMINI_API_KEY, SUPPORTED_EXTENSIONS, MODEL_NAME
from agents.orchestrator import run_pipeline
from output import formatter

st.set_page_config(
    page_title="Educational Video, PPTX & Audio Generator",
    page_icon="🎬",
    layout="wide",
)

# --------------------------------------------------------------------
# Sidebar configuration
# --------------------------------------------------------------------
AVAILABLE_MODELS = {
    "gemini-3.5-flash-lite": "⚡ Gemini 3.5 Flash Lite (Sub-second, Recommended)",
    "gemini-3.1-flash-lite": "⚡ Gemini 3.1 Flash Lite (Fast)",
    "gemini-3.8-flash": "Gemini 3.8 Flash (Standard)",
    "gemini-3.7-flash": "Gemini 3.7 Flash (Reasoning)",
}

with st.sidebar:
    st.header("⚙️ Model & Speed Settings")
    default_idx = (
        list(AVAILABLE_MODELS.keys()).index(MODEL_NAME)
        if MODEL_NAME in AVAILABLE_MODELS
        else 0
    )
    selected_model = st.selectbox(
        "Active AI Model",
        options=list(AVAILABLE_MODELS.keys()),
        format_func=lambda x: AVAILABLE_MODELS.get(x, x),
        index=default_idx,
        help="Gemini 3.5 Flash Lite runs in under ~1s per call and eliminates 503 high-demand timeouts.",
    )
    st.caption("🚀 Section processing runs in parallel via multi-threading for maximum speed.")

# --------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------
if "result" not in st.session_state:
    st.session_state.result = None
if "edited_text" not in st.session_state:
    st.session_state.edited_text = {}

# --------------------------------------------------------------------
# Header
# --------------------------------------------------------------------
st.title("🎬 Educational Content & Video Generator")
st.caption(
    "Transforms educational content into an editable PowerPoint presentation (.pptx), "
    "natural AI voice-over audio (.wav), and a synchronized instructional video (.mp4)."
)

if not GEMINI_API_KEY:
    st.warning(
        "No GEMINI_API_KEY found in environment. Set it in a `.env` file "
        "before generating (see README.md)."
    )

# --------------------------------------------------------------------
# Input area
# --------------------------------------------------------------------
with st.container(border=True):
    st.subheader("1. Provide source content")

    col1, col2 = st.columns([3, 2])
    with col1:
        uploaded_file = st.file_uploader(
            "Upload a PPTX or PDF file",
            type=["pptx", "pdf"],
            help=f"Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )
    with col2:
        st.markdown("**Supported input:** `.pptx`, `.pdf`, or pasted text below")
        generate_media = st.checkbox("Generate complete media outputs (PPTX + WAV + MP4)", value=True)

    pasted_text = st.text_area(
        "...or paste educational content directly (optional if a file is uploaded)",
        height=140,
        placeholder="Paste slide/section text here. Example:\n\nIntroduction to Electric Vehicles\nElectric vehicles use electric motors instead of conventional internal combustion engines...",
    )

    generate_clicked = st.button("🚀 Generate Presentation, Audio & Video", type="primary", use_container_width=False)

# --------------------------------------------------------------------
# Pipeline execution
# --------------------------------------------------------------------
if generate_clicked:
    if not uploaded_file and not pasted_text.strip():
        st.error("Please upload a file or paste some text first.")
    elif not GEMINI_API_KEY:
        st.error("GEMINI_API_KEY is not set. Add it to your .env file and restart the app.")
    else:
        status_box = st.status("Starting educational pipeline...", expanded=True)

        def progress_callback(msg):
            status_box.write(msg)

        try:
            file_path = None
            if uploaded_file:
                suffix = Path(uploaded_file.name).suffix.lower()
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    file_path = tmp.name

            result = run_pipeline(
                file_path=file_path,
                pasted_text=pasted_text if not uploaded_file else None,
                progress_callback=progress_callback,
                generate_media=generate_media,
                model_name=selected_model,
            )
            st.session_state.result = result
            st.session_state.edited_text = {}
            status_box.update(label="All generation stages complete!", state="complete", expanded=False)
        except Exception as e:
            status_box.update(label="Generation failed.", state="error", expanded=True)
            st.error(f"Pipeline error: {e}")

# --------------------------------------------------------------------
# Output area
# --------------------------------------------------------------------
result = st.session_state.result

if result:
    st.subheader("2. Generated Educational Media & Content")

    ds = result.document_summary
    with st.container(border=True):
        c1, c2 = st.columns(2)
        c1.markdown(f"**Main Topic:** {ds.main_topic}")
        c1.markdown(f"**Audience Level:** {ds.audience_level}")
        c2.markdown(f"**Learning Objective:** {ds.learning_objective}")
        if ds.notes:
            st.caption(f"Analyzer notes: {ds.notes}")

    # ================================================================
    # THREE FINAL MEDIA OUTPUTS SHOWCASE
    # ================================================================
    if result.video_path or result.audio_path or result.pptx_path:
        st.markdown("### 🎥 Final Media Outputs")
        media_col1, media_col2 = st.columns([3, 2])

        with media_col1:
            st.markdown("#### 🎬 Final Educational Video (.mp4)")
            if result.video_path and os.path.exists(result.video_path):
                st.video(result.video_path)
                with open(result.video_path, "rb") as vf:
                    st.download_button(
                        "⬇️ Download final_video.mp4",
                        data=vf.read(),
                        file_name="final_video.mp4",
                        mime="video/mp4",
                        type="primary",
                        use_container_width=True,
                    )
            else:
                st.info("Video was not generated or media toggle was off.")

        with media_col2:
            st.markdown("#### 🎙️ Spoken AI Voice-Over (.wav)")
            if result.audio_path and os.path.exists(result.audio_path):
                st.audio(result.audio_path, format="audio/wav")
                with open(result.audio_path, "rb") as af:
                    st.download_button(
                        "⬇️ Download voiceover.wav",
                        data=af.read(),
                        file_name="voiceover.wav",
                        mime="audio/wav",
                        use_container_width=True,
                    )
            else:
                st.info("Audio track not found.")

            st.markdown("---")
            st.markdown("#### 📊 Editable PowerPoint (.pptx)")
            if result.pptx_path and os.path.exists(result.pptx_path):
                st.caption(f"Includes {len(result.slide_outputs) + 1} 16:9 widescreen slides with presenter notes.")
                with open(result.pptx_path, "rb") as pf:
                    st.download_button(
                        "⬇️ Download presentation.pptx",
                        data=pf.read(),
                        file_name="presentation.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True,
                    )
            else:
                st.info("Presentation file not found.")

        st.divider()

    # ================================================================
    # EXISTING TEXT & STORYBOARD TABS
    # ================================================================
    st.markdown("### 📋 Content, Script & Storyboard Breakdown")
    tab_understanding, tab_script, tab_storyboard, tab_qa = st.tabs(
        ["📖 Content Understanding", "🎙️ Voice-over Script", "🖼️ Storyboard", "✅ QA Report"]
    )


    # --- Content Understanding tab ---
    with tab_understanding:
        st.markdown("Per-section breakdown (learning objective, on-screen content, visual action, "
                     "voice-over, duration, key terms, source reference).")
        for slide in result.slide_outputs:
            with st.expander(f"{slide.section_index}. {slide.section_title}", expanded=False):
                st.text(formatter.format_section_block(result, slide.section_index))
        st.download_button(
            "Copy / Export full breakdown (.txt)",
            data=formatter.format_all_sections(result),
            file_name="content_understanding.txt",
            mime="text/plain",
        )

    # --- Voice-over Script tab ---
    with tab_script:
        script_text = formatter.format_complete_voiceover_script(result)
        st.text_area("Complete voice-over script", value=script_text, height=500, key="script_area")
        st.download_button(
            "Copy / Export voice-over script (.txt)",
            data=script_text,
            file_name="voiceover_script.txt",
            mime="text/plain",
        )

    # --- Storyboard tab ---
    with tab_storyboard:
        storyboard_text = formatter.format_complete_storyboard(result)
        st.text_area("Complete storyboard", value=storyboard_text, height=500, key="storyboard_area")
        st.download_button(
            "Copy / Export storyboard (.txt)",
            data=storyboard_text,
            file_name="storyboard.txt",
            mime="text/plain",
        )

    # --- QA Report tab ---
    with tab_qa:
        qa_text = formatter.format_qa_report(result)
        high = sum(1 for i in result.qa_issues if i.severity == "high")
        med = sum(1 for i in result.qa_issues if i.severity == "medium")
        low = sum(1 for i in result.qa_issues if i.severity == "low")
        m1, m2, m3 = st.columns(3)
        m1.metric("High severity", high)
        m2.metric("Medium severity", med)
        m3.metric("Low severity", low)
        st.text_area("QA report", value=qa_text, height=400, key="qa_area")
        st.download_button(
            "Copy / Export QA report (.txt)",
            data=qa_text,
            file_name="qa_report.txt",
            mime="text/plain",
        )

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔄 Regenerate all"):
            st.session_state.result = None
            st.rerun()
    with col_b:
        st.download_button(
            "⬇️ Export everything (single .txt)",
            data=formatter.format_full_export(result),
            file_name="full_video_package.txt",
            mime="text/plain",
            type="primary",
        )
else:
    st.info("Upload a file or paste content above, then click **Generate Script & Storyboard**.")

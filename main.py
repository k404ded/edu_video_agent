"""
Educational Video Script & Storyboard Generator — Streamlit UI.

Run with: streamlit run main.py
"""
import os
import sys
import tempfile
import base64
import json
from pathlib import Path

# Ensure edu_video_agent directory is in sys.path and is the working directory
_CURRENT_DIR = Path(__file__).resolve().parent
if str(_CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(_CURRENT_DIR))
os.chdir(_CURRENT_DIR)

import streamlit as st
import streamlit.components.v1 as components

from config import get_api_key, SUPPORTED_EXTENSIONS, MODEL_NAME
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
    "gemini-3.5-flash-lite": "⚡ Gemini 3.5 Flash Lite (Fast & Sub-second, Recommended)",
    "gemini-3.6-flash": "🚀 Gemini 3.6 Flash (High Quality)",
    "gemini-3.1-flash-lite": "⚡ Gemini 3.1 Flash Lite (Preview)",
    "gemini-flash-latest": "🌐 Gemini Flash Latest",
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

active_api_key = get_api_key()
if not active_api_key:
    st.warning(
        "No GEMINI_API_KEY found in environment or secrets. "
        "Set it in a `.env` file locally, or in Streamlit Cloud Secrets (see Settings)."
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
        st.success("🎬 **Full Media Package:** Generates an HD Synchronized Video, AI Voice Narration (.wav), and an editable 16:9 PowerPoint (.pptx).")

    pasted_text = st.text_area(
        "...or paste educational content directly (optional if a file is uploaded)",
        height=140,
        placeholder="Paste slide/section text here. Example:\n\nIntroduction to Electric Vehicles\nElectric vehicles use electric motors instead of conventional internal combustion engines...",
    )

    generate_clicked = st.button("🚀 Generate Presentation, Audio & Video", type="primary", use_container_width=True)

# --------------------------------------------------------------------
# Pipeline execution
# --------------------------------------------------------------------
if generate_clicked:
    if not uploaded_file and not pasted_text.strip():
        st.error("Please upload a file or paste some text first.")
    elif not get_api_key():
        st.error("GEMINI_API_KEY is not set. Add it to your .env file or Streamlit Cloud Secrets.")
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
                generate_media=True,
                model_name=selected_model,
            )
            st.session_state.result = result
            st.session_state.edited_text = {}
            status_box.update(label="All generation stages complete!", state="complete", expanded=False)
        except Exception as e:
            status_box.update(label="Generation failed.", state="error", expanded=True)
            st.error(f"Pipeline error: {e}")

def render_interactive_video_player(result):
    """Renders a responsive, client-side synchronized presentation video player in HTML5."""
    from media.tts_generator import get_audio_duration_seconds

    if not result.audio_path or not os.path.exists(result.audio_path):
        st.info("Audio narration track not available.")
        return

    try:
        with open(result.audio_path, "rb") as af:
            audio_b64 = base64.b64encode(af.read()).decode("utf-8")

        slide_data = []
        curr_time = 0.0
        for idx, s_path in enumerate(result.slide_image_paths):
            if not os.path.exists(s_path):
                continue
            with open(s_path, "rb") as sf:
                s_b64 = base64.b64encode(sf.read()).decode("utf-8")

            dur = 3.5
            if result.section_audio_paths and idx < len(result.section_audio_paths):
                dur = max(get_audio_duration_seconds(result.section_audio_paths[idx]) + 0.5, 1.5)

            slide_data.append({
                "index": idx + 1,
                "start": round(curr_time, 2),
                "end": round(curr_time + dur, 2),
                "src": f"data:image/png;base64,{s_b64}",
            })
            curr_time += dur

        if not slide_data:
            st.info("Slide visual frames not available.")
            return

        slides_json = json.dumps(slide_data)
        total_sec = max(round(curr_time, 1), 1.0)
        total_min = int(total_sec // 60)
        total_rem_sec = int(total_sec % 60)

        player_html = f"""
        <div style="width:100%; font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif; background:#0f172a; border-radius:12px; overflow:hidden; box-shadow:0 8px 24px rgba(0,0,0,0.25); color:#fff;">
          <div style="position:relative; width:100%; padding-top:56.25%; background:#020617;">
            <img id="active-slide" src="{slide_data[0]['src']}" style="position:absolute; top:0; left:0; width:100%; height:100%; object-fit:contain;" />
            <div id="slide-badge" style="position:absolute; top:12px; right:12px; background:rgba(15,23,42,0.85); backdrop-filter:blur(6px); padding:4px 12px; border-radius:6px; font-size:12px; font-weight:600; color:#38bdf8; border:1px solid rgba(56,189,248,0.3);">Slide 1 / {len(slide_data)}</div>
          </div>
          <div style="padding:10px 14px; background:#1e293b; display:flex; flex-direction:column; gap:6px;">
            <div style="display:flex; align-items:center; gap:10px;">
              <button id="play-btn" onclick="togglePlay()" style="background:#2563eb; border:none; color:white; width:36px; height:36px; border-radius:50%; cursor:pointer; display:flex; align-items:center; justify-content:center; font-size:15px;">▶</button>
              <button onclick="prevSlide()" style="background:#334155; border:none; color:white; padding:6px 10px; border-radius:6px; cursor:pointer; font-size:12px;">⏮ Prev</button>
              <button onclick="nextSlide()" style="background:#334155; border:none; color:white; padding:6px 10px; border-radius:6px; cursor:pointer; font-size:12px;">Next ⏭</button>
              <input type="range" id="seek-bar" value="0" min="0" max="{total_sec}" step="0.1" oninput="seekAudio(this.value)" style="flex:1; cursor:pointer; accent-color:#38bdf8;" />
              <span id="time-display" style="font-size:12px; color:#94a3b8; font-variant-numeric:tabular-nums; min-width:80px; text-align:right;">00:00 / {total_min:02d}:{total_rem_sec:02d}</span>
            </div>
            <audio id="player-audio" src="data:audio/wav;base64,{audio_b64}" preload="auto"></audio>
          </div>
        </div>
        <script>
          const slides = {slides_json};
          const audio = document.getElementById('player-audio');
          const slideImg = document.getElementById('active-slide');
          const badge = document.getElementById('slide-badge');
          const playBtn = document.getElementById('play-btn');
          const seekBar = document.getElementById('seek-bar');
          const timeDisp = document.getElementById('time-display');

          function fmtTime(sec) {{
            const m = Math.floor(sec / 60);
            const s = Math.floor(sec % 60);
            return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
          }}

          function updateSlide(t) {{
            for (let i = 0; i < slides.length; i++) {{
              if (t >= slides[i].start && (t < slides[i].end || i === slides.length - 1)) {{
                if (slideImg.src !== slides[i].src) {{
                  slideImg.src = slides[i].src;
                  badge.innerText = 'Slide ' + slides[i].index + ' / ' + slides.length;
                }}
                break;
              }}
            }}
          }}

          audio.ontimeupdate = function() {{
            seekBar.value = audio.currentTime;
            timeDisp.innerText = fmtTime(audio.currentTime) + ' / ' + fmtTime(audio.duration || {total_sec});
            updateSlide(audio.currentTime);
          }};

          audio.onended = function() {{
            playBtn.innerText = '▶';
          }};

          function togglePlay() {{
            if (audio.paused) {{
              audio.play();
              playBtn.innerText = '⏸';
            }} else {{
              audio.pause();
              playBtn.innerText = '▶';
            }}
          }}

          function seekAudio(val) {{
            audio.currentTime = parseFloat(val);
            updateSlide(audio.currentTime);
          }}

          function prevSlide() {{
            const t = audio.currentTime;
            for (let i = slides.length - 1; i >= 0; i--) {{
              if (slides[i].start < t - 0.5) {{
                audio.currentTime = slides[i].start;
                updateSlide(slides[i].start);
                return;
              }}
            }}
            audio.currentTime = 0;
            updateSlide(0);
          }}

          function nextSlide() {{
            const t = audio.currentTime;
            for (let i = 0; i < slides.length; i++) {{
              if (slides[i].start > t + 0.1) {{
                audio.currentTime = slides[i].start;
                updateSlide(slides[i].start);
                return;
              }}
            }}
          }}
        </script>
        """
        components.html(player_html, height=480)
    except Exception as e:
        st.warning(f"Interactive player notice: {e}")


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
    st.markdown("### 🎥 Final Media Outputs")
    media_col1, media_col2 = st.columns([3, 2])

    with media_col1:
        st.markdown("#### 🎬 Final Educational Video")
        if result.video_path and os.path.exists(result.video_path) and os.path.getsize(result.video_path) > 1000:
            with open(result.video_path, "rb") as vf:
                video_bytes = vf.read()
            st.video(video_bytes, format="video/mp4")
            st.download_button(
                "⬇️ Download final_video.mp4",
                data=video_bytes,
                file_name="final_video.mp4",
                mime="video/mp4",
                type="primary",
                use_container_width=True,
            )
        elif result.slide_image_paths and result.audio_path:
            render_interactive_video_player(result)
            st.caption("📺 Playing in Synchronized HD Educational Presentation Mode.")
            if getattr(result, "video_error", None):
                with st.expander("ℹ️ Direct MP4 File Download Note", expanded=False):
                    st.caption(f"Server encoder notice: {result.video_error}")
                    st.info("Tip for Streamlit Cloud: To enable standalone .mp4 download export, click '⋮' in the top right of your Streamlit Cloud app dashboard and select 'Rebuild with clear cache' so Debian installs FFmpeg from packages.txt.")
        else:
            st.info("Video media is currently being prepared.")

        with media_col2:
            st.markdown("#### 🎙️ Spoken AI Voice-Over (.wav)")
            if result.audio_path and os.path.exists(result.audio_path):
                with open(result.audio_path, "rb") as af:
                    audio_bytes = af.read()
                st.audio(audio_bytes, format="audio/wav")
                st.download_button(
                    "⬇️ Download voiceover.wav",
                    data=audio_bytes,
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

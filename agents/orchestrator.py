"""
Orchestrator: runs the modular pipeline end-to-end.

    CONTENT ANALYZER -> SCRIPT/STORYBOARD GENERATOR -> QUALITY CHECKER -> FINAL OUTPUT

Exposes a `run_pipeline` generator so the UI can show progress
per-stage rather than blocking on one long call.
"""
import time
from typing import List, Optional, Callable

from config import MEDIA_OUTPUT_DIR
from models.schema import Section, PipelineResult
from ingestion.extractor import extract_sections
from agents import content_analyzer, script_generator, quality_checker
from media.ppt_generator import generate_presentation
from media.tts_generator import generate_voiceover
from media.slide_renderer import render_all_slides
from media.video_maker import assemble_video


def run_pipeline(
    file_path: Optional[str] = None,
    pasted_text: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
    generate_media: bool = True,
    output_dir: Optional[str] = None,
    model_name: Optional[str] = None,
) -> PipelineResult:
    """
    Runs the full pipeline and returns a PipelineResult.
    progress_callback(str), if provided, is called with a short status
    message before each stage (used by the Streamlit UI for live progress).
    
    When generate_media is True, automatically produces:
    1. presentation.pptx (editable PowerPoint)
    2. voiceover.wav (AI voice-over audio)
    3. final_video.mp4 (synchronized slides + spoken narration)
    """
    out_dir = output_dir or MEDIA_OUTPUT_DIR

    def report(msg):
        if progress_callback:
            progress_callback(msg)

    t0 = time.time()
    report("Extracting content from source document...")
    sections: List[Section] = extract_sections(file_path=file_path, pasted_text=pasted_text)
    if not sections:
        raise ValueError("No extractable content found in the provided input.")

    report(f"Analyzing overall document ({len(sections)} sections found)...")
    t_stage = time.time()
    document_summary = content_analyzer.analyze_document(sections, model_name=model_name)
    report(f"Document analysis complete ({time.time() - t_stage:.1f}s). Analyzing sections in parallel...")

    t_stage = time.time()
    analyses = content_analyzer.analyze_all_sections(sections, model_name=model_name)
    report(f"Section analyses complete ({time.time() - t_stage:.1f}s). Generating scripts & storyboards in parallel...")

    t_stage = time.time()
    slide_outputs = script_generator.generate_all(sections, analyses, model_name=model_name)
    report(f"Script generation complete ({time.time() - t_stage:.1f}s). Running quality checks in parallel...")

    t_stage = time.time()
    qa_issues = quality_checker.check_all(sections, slide_outputs, model_name=model_name)
    report(f"Quality checks complete ({time.time() - t_stage:.1f}s).")

    result = PipelineResult(
        document_summary=document_summary,
        sections=sections,
        analyses=analyses,
        slide_outputs=slide_outputs,
        qa_issues=qa_issues,
    )

    if generate_media and slide_outputs:
        report("Generating editable PowerPoint presentation (presentation.pptx)...")
        pptx_path = generate_presentation(result, output_dir=out_dir)
        result.pptx_path = pptx_path

        report("Generating spoken AI voice-over audio (voiceover.wav)...")
        master_audio_path, section_audio_paths = generate_voiceover(result, output_dir=out_dir)
        result.audio_path = master_audio_path
        result.section_audio_paths = section_audio_paths

        report("Rendering 1080p slide frames for video...")
        slide_images = render_all_slides(result, output_dir=out_dir)
        result.slide_image_paths = slide_images

        report("Assembling final educational video with narration (final_video.mp4)...")
        video_path = assemble_video(slide_images, section_audio_paths, output_dir=out_dir)
        result.video_path = video_path

    total_time = time.time() - t0
    report(f"Done in {total_time:.1f}s total.")
    return result

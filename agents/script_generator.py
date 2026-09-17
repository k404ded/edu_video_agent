"""
SCRIPT GENERATOR + STORYBOARD GENERATOR stages.

Combined into one LLM call per section (same underlying model, two
responsibilities) since both need the same grounded context and the
MVP spec explicitly allows shared-model stages to avoid unnecessary
complexity. Output is still cleanly split into on-screen content /
visual action / voice-over per the required format.
"""
import json
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

from config import MAX_SECTION_CHARS, NARRATION_WPM, CONCURRENT_WORKERS
from models.schema import Section, ContentAnalysis, SlideOutput
from prompts.prompts import GROUNDING_RULES, SCRIPT_AND_STORYBOARD_PROMPT
from agents.llm_client import call_llm_json


def _truncate(text: str) -> str:
    if len(text) <= MAX_SECTION_CHARS:
        return text
    return text[:MAX_SECTION_CHARS] + "\n[...content truncated for length...]"


def generate_slide_output(
    section: Section,
    analysis: ContentAnalysis,
    model_name: Optional[str] = None,
) -> SlideOutput:
    prompt = SCRIPT_AND_STORYBOARD_PROMPT.format(
        grounding_rules=GROUNDING_RULES,
        wpm=NARRATION_WPM,
        section_index=section.index,
        section_title=section.title,
        section_text=_truncate(section.raw_text) or "(no extractable text)",
        analysis_json=json.dumps(analysis.__dict__, indent=2),
    )
    data = call_llm_json(prompt, model_name=model_name)
    return SlideOutput(
        section_index=section.index,
        section_title=section.title,
        learning_objective=data.get("learning_objective", ""),
        on_screen_content=data.get("on_screen_content", ""),
        visual_action=data.get("visual_action", ""),
        voice_over=data.get("voice_over", ""),
        estimated_duration_seconds=int(data.get("estimated_duration_seconds", 0) or 0),
        key_terms=analysis.key_terms,
        source_reference=data.get("source_reference", ""),
    )


def generate_all(
    sections: List[Section],
    analyses: List[ContentAnalysis],
    model_name: Optional[str] = None,
) -> List[SlideOutput]:
    """Generates slide outputs and storyboards in parallel using a thread pool."""
    analysis_by_index = {a.section_index: a for a in analyses}
    paired = [
        (section, analysis_by_index[section.index])
        for section in sections
        if section.index in analysis_by_index
    ]
    if not paired:
        return []
    if len(paired) == 1:
        s, a = paired[0]
        return [generate_slide_output(s, a, model_name=model_name)]

    workers = min(len(paired), CONCURRENT_WORKERS)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(
            lambda item: generate_slide_output(item[0], item[1], model_name=model_name),
            paired,
        ))
    return results

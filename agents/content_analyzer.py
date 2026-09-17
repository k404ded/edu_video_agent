"""
CONTENT ANALYZER stage.

Reads the whole document to determine topic/objective, then analyzes
each section individually to extract key points, terms, numbers,
steps, and ambiguities. Purely extractive/structuring — no narration
or visual instructions are produced here.
"""
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

from config import MAX_SECTION_CHARS, CONCURRENT_WORKERS
from models.schema import Section, ContentAnalysis, DocumentSummary
from prompts.prompts import GROUNDING_RULES, DOCUMENT_SUMMARY_PROMPT, SECTION_ANALYSIS_PROMPT
from agents.llm_client import call_llm_json


def _truncate(text: str) -> str:
    if len(text) <= MAX_SECTION_CHARS:
        return text
    return text[:MAX_SECTION_CHARS] + "\n[...content truncated for length...]"


def analyze_document(sections: List[Section], model_name: Optional[str] = None) -> DocumentSummary:
    all_text = "\n\n".join(
        f"SECTION {s.index}: {s.title}\n{_truncate(s.raw_text)}" for s in sections
    )
    prompt = DOCUMENT_SUMMARY_PROMPT.format(
        grounding_rules=GROUNDING_RULES,
        all_sections_text=all_text,
    )
    data = call_llm_json(prompt, model_name=model_name)
    return DocumentSummary(
        main_topic=data.get("main_topic", ""),
        learning_objective=data.get("learning_objective", ""),
        audience_level=data.get("audience_level", ""),
        notes=data.get("notes", ""),
    )


def analyze_section(section: Section, model_name: Optional[str] = None) -> ContentAnalysis:
    prompt = SECTION_ANALYSIS_PROMPT.format(
        grounding_rules=GROUNDING_RULES,
        section_index=section.index,
        section_title=section.title,
        section_text=_truncate(section.raw_text) or "(no extractable text)",
        section_notes=section.notes or "(none)",
    )
    data = call_llm_json(prompt, model_name=model_name)
    return ContentAnalysis(
        section_index=section.index,
        section_title=section.title,
        key_points=data.get("key_points", []),
        key_terms=data.get("key_terms", []),
        numbers_and_specs=data.get("numbers_and_specs", []),
        procedural_steps=data.get("procedural_steps", []),
        ambiguities=data.get("ambiguities", []),
    )


def analyze_all_sections(sections: List[Section], model_name: Optional[str] = None) -> List[ContentAnalysis]:
    """Analyzes all sections in parallel using a thread pool while preserving section order."""
    if not sections:
        return []
    if len(sections) == 1:
        return [analyze_section(sections[0], model_name=model_name)]

    workers = min(len(sections), CONCURRENT_WORKERS)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(lambda s: analyze_section(s, model_name=model_name), sections))
    return results

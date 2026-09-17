"""
QUALITY CHECKER stage.

Cross-checks each generated slide output against its ORIGINAL source
text (never against the analysis or against other sections) to catch
hallucination, dropped points, altered numbers, terminology drift,
sequence issues, and unclear phrasing.
"""
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

from config import MAX_SECTION_CHARS, CONCURRENT_WORKERS
from models.schema import Section, SlideOutput, QAIssue
from prompts.prompts import QA_PROMPT
from agents.llm_client import call_llm_json


def _truncate(text: str) -> str:
    if len(text) <= MAX_SECTION_CHARS:
        return text
    return text[:MAX_SECTION_CHARS] + "\n[...content truncated for length...]"


def check_section(
    section: Section,
    slide_output: SlideOutput,
    model_name: Optional[str] = None,
) -> List[QAIssue]:
    prompt = QA_PROMPT.format(
        section_index=section.index,
        section_title=section.title,
        section_text=_truncate(section.raw_text) or "(no extractable text)",
        voice_over=slide_output.voice_over,
        on_screen_content=slide_output.on_screen_content,
    )
    data = call_llm_json(prompt, model_name=model_name)
    if not isinstance(data, list):
        return []
    issues = []
    for item in data:
        issues.append(QAIssue(
            section_index=section.index,
            section_title=section.title,
            issue_type=item.get("issue_type", "unclear"),
            description=item.get("description", ""),
            severity=item.get("severity", "medium"),
        ))
    return issues


def check_all(
    sections: List[Section],
    slide_outputs: List[SlideOutput],
    model_name: Optional[str] = None,
) -> List[QAIssue]:
    """Runs quality / source-grounding checks in parallel using a thread pool."""
    outputs_by_index = {o.section_index: o for o in slide_outputs}
    paired = [
        (section, outputs_by_index[section.index])
        for section in sections
        if section.index in outputs_by_index
    ]
    if not paired:
        return []
    if len(paired) == 1:
        s, o = paired[0]
        return check_section(s, o, model_name=model_name)

    workers = min(len(paired), CONCURRENT_WORKERS)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        issue_lists = list(executor.map(
            lambda item: check_section(item[0], item[1], model_name=model_name),
            paired,
        ))

    all_issues = []
    for issues in issue_lists:
        all_issues.extend(issues)
    return all_issues

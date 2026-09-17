"""
Formats a PipelineResult into the human-readable outputs specified
in the project brief: per-section blocks, a complete voice-over
script, a complete storyboard, and a QA report. Also handles
plain-text export.
"""
from models.schema import PipelineResult


def format_section_block(result: PipelineResult, section_index: int) -> str:
    slide = next((s for s in result.slide_outputs if s.section_index == section_index), None)
    if not slide:
        return ""
    key_terms = ", ".join(slide.key_terms) if slide.key_terms else "(none identified)"
    return f"""SLIDE / SECTION:
{slide.section_index}. {slide.section_title}

LEARNING OBJECTIVE:
{slide.learning_objective}

ON-SCREEN CONTENT:
{slide.on_screen_content}

VISUAL ACTION:
{slide.visual_action}

VOICE-OVER:
{slide.voice_over}

ESTIMATED DURATION:
~{slide.estimated_duration_seconds} seconds

KEY TERMS:
{key_terms}

SOURCE REFERENCE:
{slide.source_reference}
"""


def format_all_sections(result: PipelineResult) -> str:
    blocks = [format_section_block(result, s.section_index) for s in result.slide_outputs]
    return "\n" + ("\n" + "-" * 60 + "\n\n").join(blocks)


def format_complete_voiceover_script(result: PipelineResult) -> str:
    lines = [
        f"COMPLETE VOICE-OVER SCRIPT",
        f"Topic: {result.document_summary.main_topic}",
        f"Learning Objective: {result.document_summary.learning_objective}",
        "=" * 60,
        "",
    ]
    total_seconds = 0
    for slide in result.slide_outputs:
        total_seconds += slide.estimated_duration_seconds
        lines.append(f"[{slide.section_index}. {slide.section_title}]  (~{slide.estimated_duration_seconds}s)")
        lines.append(slide.voice_over)
        lines.append("")
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    lines.append(f"Estimated total runtime: {minutes}m {seconds}s")
    return "\n".join(lines)


def format_complete_storyboard(result: PipelineResult) -> str:
    lines = [
        "COMPLETE STORYBOARD",
        "=" * 60,
        "",
    ]
    for slide in result.slide_outputs:
        lines.append(f"[{slide.section_index}. {slide.section_title}]")
        lines.append(f"  ON-SCREEN: {slide.on_screen_content}")
        lines.append(f"  VISUAL ACTION: {slide.visual_action}")
        lines.append(f"  KEY TERMS: {', '.join(slide.key_terms) if slide.key_terms else '(none)'}")
        lines.append("")
    return "\n".join(lines)


def format_qa_report(result: PipelineResult) -> str:
    lines = [
        "CONTENT / TECHNICAL QA REPORT",
        "=" * 60,
        "",
    ]
    if not result.qa_issues:
        lines.append("No issues flagged. Generated content appears consistent with the source material.")
        return "\n".join(lines)

    lines.append(f"{len(result.qa_issues)} issue(s) flagged across {len(result.slide_outputs)} section(s):\n")

    severity_order = {"high": 0, "medium": 1, "low": 2}
    issues_sorted = sorted(result.qa_issues, key=lambda i: severity_order.get(i.severity, 1))

    for issue in issues_sorted:
        lines.append(
            f"[{issue.severity.upper()}] Section {issue.section_index} "
            f"({issue.section_title}) — {issue.issue_type.replace('_', ' ')}"
        )
        lines.append(f"  {issue.description}")
        lines.append("")

    # Summary of ambiguities flagged during analysis (separate from generation QA)
    ambiguous_sections = [a for a in result.analyses if a.ambiguities]
    if ambiguous_sections:
        lines.append("-" * 60)
        lines.append("Ambiguities flagged in source material during analysis:")
        for a in ambiguous_sections:
            for amb in a.ambiguities:
                lines.append(f"  Section {a.section_index} ({a.section_title}): {amb}")

    return "\n".join(lines)


def format_full_export(result: PipelineResult) -> str:
    """Single combined text file for copy/export, matching the required output order."""
    parts = [
        f"EDUCATIONAL VIDEO SCRIPT & STORYBOARD\n",
        f"Main Topic: {result.document_summary.main_topic}",
        f"Learning Objective: {result.document_summary.learning_objective}",
        f"Audience Level: {result.document_summary.audience_level}",
        "\n" + "=" * 60 + "\nPER-SECTION BREAKDOWN\n" + "=" * 60,
        format_all_sections(result),
        "\n" + "=" * 60,
        format_complete_voiceover_script(result),
        "\n" + "=" * 60,
        format_complete_storyboard(result),
        "\n" + "=" * 60,
        format_qa_report(result),
    ]
    return "\n".join(parts)

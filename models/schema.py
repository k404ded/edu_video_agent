"""
Structured data types shared across all pipeline stages.

Keeping these as dataclasses (rather than passing raw dicts everywhere)
makes the pipeline predictable and easy to extend in later phases
(TTS metadata, animation instructions, timing tracks, etc.).
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class Section:
    """One slide (PPTX) or page/chunk (PDF/text) of raw source content."""
    index: int
    title: str
    raw_text: str
    notes: str = ""  # speaker notes, if any (PPTX only)


@dataclass
class ContentAnalysis:
    """Output of the Content Analyzer for a single section."""
    section_index: int
    section_title: str
    key_points: List[str] = field(default_factory=list)
    key_terms: List[str] = field(default_factory=list)
    numbers_and_specs: List[str] = field(default_factory=list)
    procedural_steps: List[str] = field(default_factory=list)
    ambiguities: List[str] = field(default_factory=list)


@dataclass
class DocumentSummary:
    """Whole-document level understanding, produced once from all sections."""
    main_topic: str = ""
    learning_objective: str = ""
    audience_level: str = ""
    notes: str = ""


@dataclass
class SlideOutput:
    """Final assembled output for one slide/section, matching the required format."""
    section_index: int
    section_title: str
    learning_objective: str
    on_screen_content: str
    visual_action: str
    voice_over: str
    estimated_duration_seconds: int
    key_terms: List[str] = field(default_factory=list)
    source_reference: str = ""


@dataclass
class QAIssue:
    section_index: int
    section_title: str
    issue_type: str   # e.g. "unsupported_claim", "altered_number", "dropped_point", "unclear", "sequence"
    description: str
    severity: str = "medium"  # low / medium / high


@dataclass
class PipelineResult:
    document_summary: DocumentSummary
    sections: List[Section]
    analyses: List[ContentAnalysis]
    slide_outputs: List[SlideOutput]
    qa_issues: List[QAIssue]
    pptx_path: Optional[str] = None
    audio_path: Optional[str] = None
    video_path: Optional[str] = None
    slide_image_paths: List[str] = field(default_factory=list)
    section_audio_paths: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "document_summary": asdict(self.document_summary),
            "sections": [asdict(s) for s in self.sections],
            "analyses": [asdict(a) for a in self.analyses],
            "slide_outputs": [asdict(s) for s in self.slide_outputs],
            "qa_issues": [asdict(q) for q in self.qa_issues],
            "pptx_path": self.pptx_path,
            "audio_path": self.audio_path,
            "video_path": self.video_path,
            "slide_image_paths": list(self.slide_image_paths),
            "section_audio_paths": list(self.section_audio_paths),
        }


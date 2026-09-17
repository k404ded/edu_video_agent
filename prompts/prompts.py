"""
Prompt templates for every agent stage.

Kept isolated from agent logic so prompts can be tuned/versioned
without touching pipeline code. Every prompt enforces the same
core rule: the uploaded source is the ONLY source of truth.
"""

GROUNDING_RULES = """
STRICT SOURCE-GROUNDING RULES (apply to everything you produce):
- Treat the provided source text as the single source of truth.
- Do NOT invent technical facts, specifications, numbers, or claims that are not present in the source.
- Do NOT alter numerical values, units, or measurements.
- Do NOT change technical terminology unnecessarily.
- Do NOT reorder procedural/step-based content unless the source itself is disordered and you are asked to fix it.
- Do NOT invent safety requirements or warnings not present in the source.
- If something is unclear, missing, or ambiguous in the source, explicitly flag it instead of guessing.
- Never output anything outside the requested JSON.
"""

DOCUMENT_SUMMARY_PROMPT = """You are the CONTENT ANALYZER stage of an educational video script pipeline.

{grounding_rules}

Below is the full extracted text of an educational document, section by section.
Read all of it and determine the overall topic and learning objective of the WHOLE document.

SOURCE SECTIONS:
{all_sections_text}

Respond with ONLY valid JSON in this exact shape:
{{
  "main_topic": "...",
  "learning_objective": "...",
  "audience_level": "...",
  "notes": "any overall observations about scope, gaps, or inconsistencies across the whole document"
}}
"""

SECTION_ANALYSIS_PROMPT = """You are the CONTENT ANALYZER stage of an educational video script pipeline.

{grounding_rules}

Analyze ONLY the following section from the source document. Extract its key points,
technical terms, exact numbers/specs, procedural steps (if any), and anything ambiguous.

SECTION {section_index}: {section_title}
SOURCE TEXT:
\"\"\"
{section_text}
\"\"\"
SPEAKER NOTES (if any):
\"\"\"
{section_notes}
\"\"\"

Respond with ONLY valid JSON in this exact shape:
{{
  "key_points": ["...", "..."],
  "key_terms": ["...", "..."],
  "numbers_and_specs": ["...", "..."],
  "procedural_steps": ["...", "..."],
  "ambiguities": ["...", "..."]
}}
Use empty arrays where there is nothing to report. Do not pad with invented content.
"""

SCRIPT_AND_STORYBOARD_PROMPT = """You are the SCRIPT GENERATOR and STORYBOARD GENERATOR stages of an
educational video script pipeline, working together on a single section.

{grounding_rules}

Using the section's source text AND the structured analysis already extracted for it,
produce:
1. A natural, spoken-style instructional VOICE-OVER script (not a transcript of the slide text —
   explain it the way a human instructor would narrate it, but introduce nothing that isn't
   supported by the source).
2. ON-SCREEN CONTENT: what the learner should see (concise, can reference the slide's own text/visuals).
3. VISUAL ACTION: concrete screen-recording/editing guidance (e.g. "highlight the block diagram",
   "zoom into the register table", "callout on step 3", "cursor traces the signal path").
4. An estimated duration in seconds for the voice-over, assuming ~{wpm} words per minute.
5. A SOURCE REFERENCE noting where in the section this content comes from (e.g. "slide bullet 2",
   "paragraph 1").

SECTION {section_index}: {section_title}

SOURCE TEXT:
\"\"\"
{section_text}
\"\"\"

STRUCTURED ANALYSIS (already extracted, use it, don't contradict it):
{analysis_json}

Respond with ONLY valid JSON in this exact shape:
{{
  "learning_objective": "what the learner should understand from this section specifically",
  "on_screen_content": "...",
  "visual_action": "...",
  "voice_over": "...",
  "estimated_duration_seconds": 00,
  "source_reference": "..."
}}
"""

QA_PROMPT = """You are the QUALITY CHECKER stage of an educational video script pipeline.

Your job is to compare the GENERATED VOICE-OVER + ON-SCREEN CONTENT for a section against
the ORIGINAL SOURCE TEXT for that same section, and flag any problems. Be strict and literal —
this content will be used to produce a real instructional video, so factual/technical accuracy
matters more than smooth prose.

Check specifically for:
- Unsupported claims: information in the generated content not present in the source.
- Altered numbers/specs: any numeric value, unit, or measurement that doesn't match the source exactly.
- Dropped points: important source content that the generated script omitted.
- Terminology changes: technical terms altered or replaced unnecessarily.
- Sequence problems: steps or ideas presented out of the source's order without reason.
- Unclear sections: parts of the generated script that would confuse a learner.

SECTION {section_index}: {section_title}

ORIGINAL SOURCE TEXT:
\"\"\"
{section_text}
\"\"\"

GENERATED VOICE-OVER:
\"\"\"
{voice_over}
\"\"\"

GENERATED ON-SCREEN CONTENT:
\"\"\"
{on_screen_content}
\"\"\"

Respond with ONLY valid JSON: a list of issues (empty list if none found), each shaped as:
{{
  "issue_type": "unsupported_claim | altered_number | dropped_point | unclear | sequence | terminology",
  "description": "...",
  "severity": "low | medium | high"
}}
Return just the JSON array, e.g. [] or [{{...}}, {{...}}].
"""

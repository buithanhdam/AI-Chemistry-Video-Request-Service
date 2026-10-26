"""Prompt builder cho script generation."""

SYSTEM_PROMPT = (
    "You are a chemistry educator creating short educational video scripts. "
    "Return ONLY valid JSON, no markdown fences, no extra text."
)

SCRIPT_JSON_SCHEMA = """{
  "title": "string",
  "sections": [
    {
      "heading": "string",
      "key_points": ["string", ...],
      "narration": "string (2-4 sentences, spoken style)"
    }
  ],
  "summary": "string"
}"""


def build_script_prompt(query: str, knowledge_yaml: str) -> str:
    return f"""You are a chemistry educator. Given the learner query and knowledge base, generate a short educational script.

Query: {query}
Knowledge:
{knowledge_yaml}

Return ONLY valid JSON matching this schema:
{SCRIPT_JSON_SCHEMA}

Rules:
- 2 to 4 sections maximum
- Each narration is 2-4 sentences, spoken style for TTS
- key_points: 1-3 short bullets per section
- Content must stay consistent with the Knowledge section
"""
"""
Grounded Generation Module (Gemini)
-----------------------------------
Uses Google's official GenAI SDK (google-genai) with structured output
to generate grounded clinical answers based strictly on retrieved context.

Structured Output Schema:
{
  "recommendation": "...",
  "evidence": "...",
  "citations": [{"document": "...", "section": "...", "page": 1}],
  "confidence": "high | medium | low | insufficient"
}

Retrieval-Confidence Gating (added):
The LLM's self-reported "confidence" is never trusted on its own — after
generation, apply_confidence_gate() caps it to what the retrieval scores
actually support (config.RETRIEVAL_CONFIDENCE_THRESHOLDS), and forces a
refusal if the top retrieval score is too weak. This is a programmatic
enforcement of the contract already described in schema/response_schema.json.
"""
import json
import os
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

import config

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

try:
    import jsonschema
except ImportError:
    jsonschema = None


# --- Pydantic Schema for Gemini Structured Output ---

class CitationModel(BaseModel):
    document: str = Field(description="Exact document name from metadata")
    section: str = Field(default="N/A", description="Section title or number if available, else 'N/A'")
    page: int = Field(description="Page number as an integer")


class GroundedResponseModel(BaseModel):
    recommendation: str = Field(description="Direct clinical answer or refusal message")
    evidence: str = Field(default="", description="Exact supporting text excerpt, or empty string if insufficient")
    citations: List[CitationModel] = Field(default_factory=list, description="List of source citations, empty if insufficient")
    confidence: Literal["high", "medium", "low", "insufficient"] = Field(description="Confidence level")


# Path to project JSON schema for validation
SCHEMA_PATH = config.BASE_DIR / "schema" / "response_schema.json"


def load_response_schema() -> Optional[dict]:
    """Loads the JSON schema from schema/response_schema.json if available."""
    if SCHEMA_PATH.exists():
        try:
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def format_context_for_prompt(retrieved_results: list) -> str:
    """Formats retrieved chunks with metadata for inclusion in the prompt."""
    context_blocks = []
    for doc, score in retrieved_results:
        meta = doc.metadata
        doc_name = meta.get("document_name", "Unknown Document")
        page = meta.get("page_number", 1)
        section = meta.get("section", "N/A")
        chunk_id = meta.get("chunk_id", "N/A")

        header = f"[Source Document='{doc_name}', Page={page}, Section='{section}', ChunkID='{chunk_id}']"
        context_blocks.append(f"{header}\n{doc.page_content.strip()}")

    return "\n\n".join(context_blocks)


def create_refusal_response(reason: str, confidence: str = "insufficient") -> dict:
    """Creates a standard refusal dictionary adhering to response_schema.json."""
    return {
        "recommendation": reason,
        "evidence": "",
        "citations": [],
        "confidence": confidence
    }


def validate_citations(response: dict, retrieved_results: list) -> bool:
    """Validates that every citation returned by the LLM corresponds to a real
    document name and page number present in the retrieved chunks."""
    # Refusals or responses with no citations don't require citation checks
    if response.get("confidence") == "insufficient":
        return True

    citations = response.get("citations", [])
    if not citations:
        return True

    # Build the set of valid (document_name, page_number) pairs from retrieval metadata
    valid_sources = set()
    for doc, _ in retrieved_results:
        meta = doc.metadata
        doc_name = meta.get("document_name")
        page_num = meta.get("page_number")
        if doc_name is not None and page_num is not None:
            valid_sources.add((str(doc_name), int(page_num)))

    # Verify every citation against the allowed set
    for cit in citations:
        cit_doc = str(cit.get("document", ""))
        try:
            cit_page = int(cit.get("page", 0))
        except (ValueError, TypeError):
            print(f"\n[Citation Validation Error] Invalid page number format: {cit.get('page')}")
            return False

        if (cit_doc, cit_page) not in valid_sources:
            print(f"\n[Citation Validation Error] Hallucinated citation rejected: Document='{cit_doc}', Page={cit_page}")
            return False

    return True


def retrieval_confidence_bucket(retrieved_results: list) -> tuple[str, float]:
    """
    Determines retrieval quality without treating Chroma distance-derived
    scores as medical confidence percentages.

    The current retrieval scores are only used as a ranking signal.
    We use the presence of relevant retrieved context as the minimum
    requirement and let the grounded generation + citation validation
    control the final response.
    """
    if not retrieved_results:
        return "insufficient", 0.0

    top_score = max(score for _, score in retrieved_results)

    thresholds = config.RETRIEVAL_CONFIDENCE_THRESHOLDS

    if top_score >= thresholds.get("high", 0.75):
        bucket = "high"
    elif top_score >= thresholds.get("medium", 0.55):
        bucket = "medium"
    elif top_score >= thresholds.get("low", 0.35):
        bucket = "low"
    else:
        bucket = "insufficient"

    return bucket, top_score


_CONFIDENCE_RANK = {"insufficient": 0, "low": 1, "medium": 2, "high": 3}


def apply_confidence_gate(result: dict, retrieved_results: list) -> dict:
    """
    Applies a conservative confidence gate.

    Retrieval scores are treated as ranking signals, not probabilities.
    The LLM confidence can never exceed the retrieval bucket.
    """

    bucket, top_score = retrieval_confidence_bucket(retrieved_results)

    if bucket == "insufficient":
        print(
            f"\n[Confidence Gate] Retrieval signal is too weak "
            f"(score={top_score:.3f})."
        )

        return create_refusal_response(
            "The retrieved evidence is too weak to support an answer "
            "from the indexed medical documents."
        )

    llm_confidence = result.get("confidence", "insufficient")

    # Never allow the LLM to claim more confidence than retrieval supports.
    if _CONFIDENCE_RANK.get(llm_confidence, 0) > _CONFIDENCE_RANK[bucket]:
        print(
            f"\n[Confidence Gate] LLM reported '{llm_confidence}', "
            f"but retrieval supports only '{bucket}' "
            f"(ranking score={top_score:.3f})."
        )

        result["confidence"] = bucket

    return result

def generate_grounded_answer(question: str, retrieved_results: list) -> dict:
    """Generates a grounded answer using Gemini constrained by structured output
    and validates both the schema and citations before returning.
    """
    # 1. Validate API Key
    api_key = config.GEMINI_API_KEY
    if not api_key:
        print("\n[Notice] GEMINI_API_KEY is not set.")
        print("To generate answers with Gemini:")
        print("  1. Add your key to .env: GEMINI_API_KEY=your_key_here")
        print("  2. Re-run: python pipeline.py \"your question\"\n")
        return create_refusal_response("GEMINI_API_KEY is missing. Please set GEMINI_API_KEY in your .env file to enable generation.", confidence="error")

    # 2. Check SDK installation
    if genai is None:
        print("\n[Error] google-genai package is not installed.")
        print("Run: pip install google-genai\n")
        return create_refusal_response("google-genai package is missing. Please run 'pip install google-genai'.", confidence="error")

    # 3. Check for empty retrieval results
    if not retrieved_results:
        return create_refusal_response("I cannot answer this question because no relevant context was found in the indexed documents.")

    context_str = format_context_for_prompt(retrieved_results)

    # 4. Construct grounded prompt with strict instructions
    prompt = f"""You are a clinical decision support AI assistant. Your task is to answer the user's clinical question based strictly and ONLY on the provided Context below.

CRITICAL GROUNDING RULES:
1. Answer ONLY using facts directly stated in the Context.
2. Do NOT use outside medical knowledge, general background knowledge, or personal opinion.
3. Do NOT invent, extrapolate, or hallucinate medical advice, document names, section names, or page numbers.
4. If the provided Context does NOT contain sufficient evidence to answer the question:
   - Set "confidence" to "insufficient"
   - Provide a concise refusal statement in "recommendation" explaining that the evidence in the source document is insufficient to answer the question.
   - Set "evidence" to "" (empty string)
   - Set "citations" to [] (empty array)
5. If sufficient evidence IS present:
   - Provide a direct answer in "recommendation".
   - Quote or lightly trim the exact supporting text in "evidence".
   - Include citations in "citations" using the exact "Document" name and "Page" number from the source metadata. If section name is unavailable or 'N/A' in metadata, use "N/A".
   - Set "confidence" to "high", "medium", or "low".

Context:
{context_str}

Question: {question}"""

    # 5. Execute Gemini call using google-genai SDK with structured output
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=GroundedResponseModel,
            )
        )

        response_text = response.text.strip()
        result = json.loads(response_text)

        # 6. Validate against JSON schema — fail safely if invalid
        schema = load_response_schema()
        if schema and jsonschema:
            try:
                jsonschema.validate(instance=result, schema=schema)
            except jsonschema.ValidationError as ve:
                print(f"\n[Validation Error] LLM output failed schema validation: {ve.message}")
                return create_refusal_response("The model response did not meet the required JSON schema.", confidence="error")

        # 7. Programmatic Citation Validation — reject hallucinated citations
        if not validate_citations(result, retrieved_results):
            return create_refusal_response(
                "The generated response contained citation metadata that was not present in the retrieved evidence."
            )

        # 8. Retrieval-Confidence Gating — enforce schema's promised behavior
        result = apply_confidence_gate(result, retrieved_results)

        return result

    except json.JSONDecodeError:
        print("[Error] Could not parse Gemini output as JSON.")
        return create_refusal_response("The model generated an invalid response format.", confidence="error")
    except Exception as e:
        error_msg = str(e)
        print(f"\n[Error] Gemini API Error: {error_msg}")
        if "API_KEY" in error_msg or "INVALID_ARGUMENT" in error_msg:
            print("Please check that your GEMINI_API_KEY in .env is valid.")
        elif "429" in error_msg or "QUOTA" in error_msg.upper():
            print("Gemini API rate limit / quota exceeded. Please try again later.")
        return create_refusal_response(f"Gemini API request failed: {error_msg}", confidence="error")


if __name__ == "__main__":
    print("generate.py is a module. Run pipeline.py to test the full end-to-end flow.")
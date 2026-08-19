"""
eval/run_eval.py // Automated Evaluation Harness (Retrieval set)
--------------------------------------------------
Runs every question in eval/test_cases.csv through the real retrieval +
generation pipeline and fills in the empty metric columns automatically:

- Precision@k     : did the expected (document, page) show up in the
                     top-k retrieved chunks?
- Citation Accuracy: does the LLM's returned citation match the expected
                     (document, page)? For refusal cases, citations must
                     be empty to score 1.
- Faithfulness     : for answered questions, is the "evidence" text
                     actually present in one of the retrieved chunks
                     (not invented)? For refusal cases, was the system
                     correctly at/under the confidence threshold?

Usage (run from the project root, one level above eval/):
    python eval/run_eval.py
"""
import csv
import re
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from query import load_index, retrieve
from generate import generate_grounded_answer

TEST_CASES_PATH = BASE_DIR / "eval" / "test_cases.csv"
RESULTS_PATH = BASE_DIR / "eval" / f"results_{time.strftime('%Y%m%d_%H%M%S')}.csv"


def normalize(text: str) -> str:
    """Lowercase, strip non-alphanumerics — for loose document-name matching
    ('WHO Hypertension Guideline' vs 'WHO_Hypertension_Guideline_2021')."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def parse_expected_source(raw: str) -> tuple[str, int | None]:
    """Parses 'WHO Hypertension Guideline / 3.1 ... / Page 7' into
    (document_name, page_number). Returns (raw, None) if there's no
    parseable page (e.g. 'Not covered by this source')."""
    page_match = re.search(r"Page\s+(\d+)", raw)
    page = int(page_match.group(1)) if page_match else None
    doc_part = raw.split("/")[0].strip()
    return doc_part, page


def precision_at_k(retrieved_results, expected_doc: str, expected_page: int | None) -> str:
    if expected_page is None:
        return "N/A"
    expected_doc_norm = normalize(expected_doc)
    for doc, _score in retrieved_results:
        meta = doc.metadata
        doc_name_norm = normalize(str(meta.get("document_name", "")))
        page = meta.get("page_number")
        if expected_doc_norm in doc_name_norm and page == expected_page:
            return "1"
    return "0"


def citation_accuracy(response: dict, expected_doc: str, expected_page: int | None) -> str:
    citations = response.get("citations", [])
    if expected_page is None:
        # Refusal case: correct behavior is NO citations at all.
        return "1" if not citations else "0"

    expected_doc_norm = normalize(expected_doc)
    for cit in citations:
        cit_doc_norm = normalize(str(cit.get("document", "")))
        if expected_doc_norm in cit_doc_norm and cit.get("page") == expected_page:
            return "1"
    return "0"


def faithfulness(response: dict, retrieved_results: list, expected_page: int | None) -> str:
    if expected_page is None:
        # Refusal case: faithful means it actually refused.
        refused = response.get("confidence") == "insufficient" and not response.get("citations")
        return "1" if refused else "0"

    # Answered case: the "evidence" text must actually appear in one of
    # the retrieved chunks — i.e. not invented by the LLM.
    evidence = normalize(response.get("evidence", ""))
    if not evidence:
        return "0"
    for doc, _score in retrieved_results:
        if evidence[:60] in normalize(doc.page_content):
            return "1"
    return "0"


def run():
    if not TEST_CASES_PATH.exists():
        print(f"[eval] No test file found at {TEST_CASES_PATH}")
        sys.exit(1)

    with open(TEST_CASES_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print(f"[eval] {TEST_CASES_PATH} is empty.")
        sys.exit(1)

    print(f"[eval] Loaded {len(rows)} test cases. Loading vector index ...")
    vectordb = load_index()

    fieldnames = list(rows[0].keys())
    for col in ("Precision@k", "Citation Accuracy", "Faithfulness"):
        if col not in fieldnames:
            fieldnames.append(col)

    scores = {"Precision@k": [], "Citation Accuracy": [], "Faithfulness": []}

    for i, row in enumerate(rows, 1):
        question = row["Question"]
        expected_doc, expected_page = parse_expected_source(row["Expected Source (Document / Section / Page)"])

        print(f"\n[{i}/{len(rows)}] {question}")
        retrieved_results = retrieve(vectordb, question, k=config.TOP_K)
        response = generate_grounded_answer(question, retrieved_results)

        p_at_k = precision_at_k(retrieved_results, expected_doc, expected_page)
        cit_acc = citation_accuracy(response, expected_doc, expected_page)
        faith = faithfulness(response, retrieved_results, expected_page)

        row["Precision@k"] = p_at_k
        row["Citation Accuracy"] = cit_acc
        row["Faithfulness"] = faith

        print(f"    confidence={response.get('confidence')}  "
              f"Precision@k={p_at_k}  Citation Accuracy={cit_acc}  Faithfulness={faith}")

        for col, val in (("Precision@k", p_at_k), ("Citation Accuracy", cit_acc), ("Faithfulness", faith)):
            if val != "N/A":
                scores[col].append(int(val))

    with open(RESULTS_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("\n" + "=" * 60)
    print(" === Retrieval Evaluation Summary ===")
    print("=" * 60)
    for col, vals in scores.items():
        if vals:
            print(f"{col}: {sum(vals)}/{len(vals)} = {100 * sum(vals) / len(vals):.1f}%")
        else:
            print(f"{col}: no scored cases")
    print(f"\nFull results written to: {RESULTS_PATH}")


if __name__ == "__main__":
    run()
"""
Retrieval Module & CLI
----------------------
Loads the Chroma index built by ingest.py, retrieves the top-k most
relevant chunks for a clinical question, and displays them with full citation
metadata (document name, page number, chunk id, score).

Works 100% locally with NO API keys required.

Usage:
    python query.py "What is the target blood pressure for a patient with known cardiovascular disease?"
"""
import sys
from pathlib import Path
from langchain_chroma import Chroma

import config
from ingest import get_embedding_function


def load_index():
    """Loads the persisted ChromaDB vector index."""
    if not config.CHROMA_DIR.exists():
        print(f"\n[Error] Vector database not found at {config.CHROMA_DIR}/")
        print("Please run 'python ingest.py' first to index your documents.\n")
        sys.exit(1)

    embedding_fn = get_embedding_function()
    return Chroma(
        collection_name=config.COLLECTION_NAME,
        embedding_function=embedding_fn,
        persist_directory=str(config.CHROMA_DIR),
        collection_metadata={"hnsw:space": "cosine"},
    )

def retrieve(vectordb, question: str, k: int = None):
    k = k or config.TOP_K

    results = vectordb.similarity_search_with_relevance_scores(
        question,
        k=k * 2
    )

    # Remove duplicated chunks
    unique_results = []
    seen = set()

    for doc, score in results:
        chunk_id = doc.metadata.get("chunk_id")

        if chunk_id in seen:
            continue

        seen.add(chunk_id)
        unique_results.append((doc, score))

        if len(unique_results) >= k:
            break

    return unique_results

def print_results(results):
    """Prints retrieved chunks with similarity scores and citation metadata."""
    if not results:
        print("\nNo matching chunks found in the index.\n")
        return

    print(f"\nTop {len(results)} retrieved chunks:\n")
    for i, (doc, score) in enumerate(results, 1):
        meta = doc.metadata
        doc_name = meta.get("document_name", "Unknown")
        page = meta.get("page_number", "?")
        chunk_id = meta.get("chunk_id", "N/A")
        print(f"[{i}] score={score:.3f}  Document: {doc_name}, page {page}, chunk {chunk_id}")
        preview = doc.page_content.strip().replace("\n", " ")[:200]
        print(f'    "{preview}..."\n')


def main():
    if len(sys.argv) < 2:
        print('Usage: python query.py "your question here"')
        print('Example: python query.py "What is the target blood pressure for a patient with known cardiovascular disease?"')
        sys.exit(1)

    question = " ".join(sys.argv[1:])
    print(f"Question: {question}")

    vectordb = load_index()
    results = retrieve(vectordb, question)
    print_results(results)


if __name__ == "__main__":
    main()
"""
Day 1 Starter — Ingestion Pipeline
-----------------------------------
Loads every PDF in ./data, splits it into overlapping chunks, embeds
those chunks, and stores them in a local ChromaDB collection. Every
chunk carries citation-ready metadata: document name, page number,
and a stable chunk id.

Usage:
    python ingest.py
"""
import sys
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

import config


def get_embedding_function():
    """Returns the embedding function based on config.EMBEDDING_PROVIDER."""
    if config.EMBEDDING_PROVIDER == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=config.OPENAI_EMBEDDING_MODEL)
    else:
        from langchain_community.embeddings import FastEmbedEmbeddings
        return FastEmbedEmbeddings(model_name=config.LOCAL_EMBEDDING_MODEL)


def load_pdfs(data_dir: Path):
    """Loads every PDF in data_dir and returns one LangChain Document per
    page, each carrying page-level metadata (document name, page number)."""
    pdf_files = sorted(data_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {data_dir}/")
        print("Add a guideline PDF there, then re-run this script.")
        sys.exit(1)

    all_docs = []
    for pdf_path in pdf_files:
        print(f"Loading {pdf_path.name} ...")
        loader = PyPDFLoader(str(pdf_path))
        pages = loader.load()
        for page in pages:
            # Normalize metadata: every chunk downstream inherits this
            page.metadata["document_name"] = pdf_path.stem
            page.metadata["page_number"] = page.metadata.get("page", 0) + 1
        all_docs.extend(pages)
        print(f"  -> {len(pages)} pages loaded")
    return all_docs


def chunk_documents(documents):
    """Splits documents into overlapping chunks using a recursive splitter
    that prefers paragraph breaks, then sentence breaks, then words —
    a simple approximation of section-aware chunking."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE * 4,       # ~4 chars per token estimate
        chunk_overlap=config.CHUNK_OVERLAP * 4,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)

    # Attach a stable, citation-ready chunk_id to every chunk
    for i, chunk in enumerate(chunks):
        doc_name = chunk.metadata.get("document_name", "unknown")
        page = chunk.metadata.get("page_number", "?")
        chunk.metadata["chunk_id"] = f"{doc_name}-p{page}-c{i}"

    return chunks


def build_index(chunks):
    """Embeds chunks and persists them into a local Chroma collection."""
    embedding_fn = get_embedding_function()

    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_fn,
        ids=[chunk.metadata["chunk_id"] for chunk in chunks],
        collection_metadata={"hnsw:space": "cosine"},
        collection_name=config.COLLECTION_NAME,
        persist_directory=str(config.CHROMA_DIR),
    )
    print(f"Done. Index saved to {config.CHROMA_DIR}/")
    return vectordb

def main():
    print("=== Day 1 Starter: Ingestion Pipeline ===\n")
    documents = load_pdfs(config.DATA_DIR)
    chunks = chunk_documents(documents)
    print(f"\nCreated {len(chunks)} chunks from {len(documents)} pages.\n")
    build_index(chunks)
    print('\nNext step: run  python query.py "your question here"  to test retrieval.')


if __name__ == "__main__":
    main()

import logging
import re
from functools import lru_cache
from pathlib import Path

import pymupdf
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger("apex_f1_chatbot")

# Project paths
ROOT_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT_DIR / "data"

# Retrieval configuration
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
DEFAULT_TOP_K = 5

PDF_FILES = [
    "About_F1.pdf",
    "F1_Results.pdf",
    "F1_Rules_and_Regulations.pdf",
]

RESULTS_FILE = "F1_Results.pdf"

# Terms that often indicate a championship or season-results question.
RESULT_TERMS = {
    "won",
    "winner",
    "champion",
    "championship",
    "champions",
    "standings",
    "points",
    "season",
    "driver",
    "drivers",
    "constructor",
    "constructors",
    "race",
    "result",
    "results",
    "finished",
    "position",
}


def split_text(text: str) -> list[str]:
    """Split page text into overlapping chunks."""

    text = " ".join(text.split())

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - CHUNK_OVERLAP

    return chunks


def extract_year(question: str) -> str | None:
    """Find an F1 season year in a question."""

    match = re.search(r"\b(19\d{2}|20\d{2})\b", question)
    return match.group(1) if match else None


def expand_question(question: str) -> str:
    """
    Expand common F1 questions with useful search terms.

    This helps short questions such as 'Who won in 2025?'
    match compact season-result tables.
    """

    expanded = question.strip()
    normalized = question.lower()
    year = extract_year(question)

    if not year:
        return expanded

    if any(term in normalized for term in (
        "who won",
        "champion",
        "championship",
        "season winner",
        "driver title",
        "drivers title",
    )):
        expanded += (
            f" {year} Formula 1 F1 Drivers Championship "
            "champion winner final standings driver points"
        )

    if any(term in normalized for term in (
        "constructor",
        "constructors",
        "team champion",
        "team championship",
    )):
        expanded += (
            f" {year} Formula 1 Constructors Championship "
            "team champion standings points"
        )

    return expanded


@lru_cache(maxsize=1)
def load_pdf_index():
    """
    Load configured PDFs and create a TF-IDF search index.

    Each chunk keeps its original filename and page number.
    The index is cached between questions.
    """

    documents = []

    if not PDF_DIR.exists():
        logger.warning("PDF folder not found: %s", PDF_DIR)
        return [], None, None

    for filename in PDF_FILES:
        pdf_path = PDF_DIR / filename

        if not pdf_path.exists():
            logger.warning("PDF file not found: %s", pdf_path)
            continue

        try:
            with pymupdf.open(pdf_path) as pdf:
                for page_number, page in enumerate(pdf, start=1):
                    page_text = page.get_text("text", sort=True)

                    if not page_text.strip():
                        continue

                    for chunk in split_text(page_text):
                        documents.append({
                            "source": filename,
                            "page": page_number,
                            "text": chunk,
                        })

            logger.info("Processed PDF: %s", filename)

        except Exception:
            logger.exception("Failed to process PDF: %s", filename)

    if not documents:
        logger.warning("No searchable PDF text was extracted.")
        return [], None, None

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
        token_pattern=r"(?u)\b\w+\b",
    )

    try:
        matrix = vectorizer.fit_transform(
            [document["text"] for document in documents]
        )
    except ValueError:
        logger.warning("PDF text could not be indexed.")
        return [], None, None

    logger.info(
        "PDF index ready: %d searchable chunks.",
        len(documents),
    )

    return documents, vectorizer, matrix


def retrieve_context(
    question: str,
    top_k: int = DEFAULT_TOP_K,
) -> str:
    """
    Retrieve relevant PDF passages.

    Year-specific questions prioritize matching season data in
    F1_Results.pdf. TF-IDF remains available for other questions.
    """

    if not question or not question.strip():
        return ""

    documents, vectorizer, matrix = load_pdf_index()

    if not documents or vectorizer is None or matrix is None:
        logger.warning("PDF retrieval unavailable: index is empty.")
        return ""

    try:
        year = extract_year(question)
        search_question = expand_question(question)

        question_vector = vectorizer.transform([search_question])

        scores = cosine_similarity(
            question_vector,
            matrix,
        ).ravel()

        normalized_question = question.lower()
        is_results_question = (
            year is not None
            and any(term in normalized_question for term in RESULT_TERMS)
        )

        ranked_passages = []

        for index, document in enumerate(documents):
            text = document["text"]
            normalized_text = text.lower()
            score = float(scores[index])

            # Give exact year matches priority for season questions.
            if is_results_question:
                year_pattern = rf"(?<!\d){re.escape(year)}(?!\d)"

                if re.search(year_pattern, text):
                    score += 0.35

                    # Season tables are most likely in the results PDF.
                    if document["source"] == RESULTS_FILE:
                        score += 0.30

                    # Boost chunks that include standings-related details.
                    if any(
                        term in normalized_text
                        for term in (
                            "points",
                            "mclaren",
                            "verstappen",
                            "norris",
                            "standings",
                        )
                    ):
                        score += 0.10

                elif document["source"] == RESULTS_FILE:
                    # Do not favor unrelated years from the results PDF.
                    score *= 0.80

            # Ignore unrelated passages for ordinary questions.
            if score <= 0:
                continue

            ranked_passages.append({
                **document,
                "score": score,
            })

        ranked_passages.sort(
            key=lambda passage: passage["score"],
            reverse=True,
        )

        if not ranked_passages:
            logger.info("No relevant PDF passages found for: %s", question)
            return ""

        # Log results so retrieval can be verified in the terminal.
        logger.info(
            "PDF retrieval question=%r year=%s",
            question,
            year or "none",
        )

        for passage in ranked_passages[:top_k]:
            logger.info(
                "PDF match score=%.4f source=%s page=%s text=%r",
                passage["score"],
                passage["source"],
                passage["page"],
                passage["text"][:250],
            )

        context_sections = []

        for passage in ranked_passages[:top_k]:
            context_sections.append(
                f"[Source: {passage['source']}, "
                f"page {passage['page']}]\n"
                f"{passage['text']}"
            )

        context = "\n\n---\n\n".join(context_sections)

        logger.info(
            "Retrieved %d PDF passages for the question.",
            min(top_k, len(ranked_passages)),
        )

        return context

    except Exception:
        logger.exception("Failed to retrieve PDF context.")
        return ""


def debug_pdf_search(year: str = "2025") -> None:
    """
    Print chunks containing a specified year.
    Useful for confirming the PDF was indexed correctly.
    """

    documents, _, _ = load_pdf_index()

    print(f"\n--- PDF DEBUG: {year} ---")
    print(f"Total indexed chunks: {len(documents)}")

    year_pattern = rf"(?<!\d){re.escape(year)}(?!\d)"
    matches = 0

    for document in documents:
        if re.search(year_pattern, document["text"]):
            matches += 1
            print(
                f"\nFile: {document['source']} | "
                f"Page: {document['page']}"
            )
            print(document["text"][:700])

    if matches == 0:
        print(f"No indexed PDF chunks contain {year}.")

    print(f"\nTotal matching chunks: {matches}")

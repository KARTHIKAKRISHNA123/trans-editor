import logging
from src.extractor import extract_document, DocumentData
from src.translator import translate_with_comparison, translate_robust
from src.document_writer import save_translated_document
from config.settings import MIN_TEXT_LENGTH

logger = logging.getLogger(__name__)

def translate_document(
    input_path: str,
    output_path: str | None = None,
    use_judge: bool = True,
) -> dict:
    
    logger.info(f"Extracting: {input_path}")
    doc_data: DocumentData = extract_document(input_path)
    logger.info(
        f"Found {len(doc_data.paragraphs)} paragraphs, "
        f"{len(doc_data.tables)} tables."
    )
        
    para_translations = []
    comparisons       = []
    flagged           = []

    for i, para_data in enumerate(doc_data.paragraphs):
        text = para_data.full_text
        if not text or len(text.strip()) < MIN_TEXT_LENGTH:
            para_translations.append(text)
            continue

        logger.info(f"Translating paragraph {i+1}/{len(doc_data.paragraphs)}")

        if use_judge:
            result = translate_with_comparison(text)
            comparisons.append(result)
            para_translations.append(result["best"])

            if result["judge"]["flagged"]:
                flagged.append({
                    "paragraph_index": i,
                    "original":        text,
                    "best":            result["best"],
                    "scores": {
                        "gemini": result["judge"].get("gemini_score", 0),
                        # .get("gemini_score", 0) means:
                        # try to read "gemini_score" from the dict
                        # if it doesn't exist → return 0 instead of crashing
                        # dict["key"] crashes on missing key
                        # dict.get("key", default) never crashes
                        "groq":   result["judge"].get("groq_score", 0),
                    },
                    "reason": result["judge"].get("reason", "No reason."),
                    # same defensive pattern for reason
                })
        else:
            # Synergy: translate_robust handles the fallback automatically
            translation = translate_robust(text)
            para_translations.append(translation)

    table_translations = {}

    for table_idx, table_data in enumerate(doc_data.tables):
        for (row, col), cell_paragraphs in table_data.cells.items():
            for para_idx, para_data in enumerate(cell_paragraphs):
                text = para_data.full_text

                if not text or len(text.strip()) < MIN_TEXT_LENGTH:
                    table_translations[(table_idx, row, col, para_idx)] = text
                    continue

                # Synergy: translate_robust handles the fallback automatically
                translation = translate_robust(text)
                table_translations[(table_idx, row, col, para_idx)] = translation
                
    logger.info("Writing translated document...")
    saved_path = save_translated_document(
        doc_data           = doc_data,
        para_translations  = para_translations,
        table_translations = table_translations,
        original_path      = input_path,
        output_path        = output_path,
    )

    return {
        "output_path":  saved_path,
        "para_count":   len(para_translations),
        "table_count":  len(table_translations),
        "flagged":      flagged,
        "comparisons":  comparisons,
    }
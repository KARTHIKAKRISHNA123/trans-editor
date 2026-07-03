import logging
from pathlib import Path

from config.settings import MIN_TEXT_LENGTH, OUTPUT_SUFFIX
from src.extractor import DocumentData, ParagraphData


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

def _replace_paragraph_text(para_data: ParagraphData, translated_text: str) -> None:
    if not translated_text or len(translated_text.strip()) < MIN_TEXT_LENGTH:
        return
    
    para = para_data.para_ref

    bold      = False
    italic    = False
    underline = False

    if para_data.runs:
        bold      = para_data.runs[0].bold
        italic    = para_data.runs[0].italic
        underline = para_data.runs[0].underline
    
    for run in para.runs:
        para._p.remove(run._r)
        new_run = para.add_run(translated_text)
        new_run.bold      = bold
        new_run.italic    = italic
        new_run.underline = underline


def _apply_paragraph_translations(
    para_list:    list,
    translations: list[str]
) -> int:
        
        if len(para_list) != len(translations):
            raise ValueError(
            f"Length mismatch: {len(para_list)} paragraphs "
            f"but {len(translations)} translations."
        )

        updated = 0

        for para_data, translation in zip(para_list, translations):
            # zip() pairs each ParagraphData with its corresponding Tamil string
            # Example: zip([p1, p2, p3], ["த1", "த2", "த3"])
            #          → (p1, "த1"), (p2, "த2"), (p3, "த3")
            if translation and translation.strip():
                _replace_paragraph_text(para_data, translation)
                updated += 1

        return updated

def _apply_table_translations(
    doc_data:           DocumentData,
    table_translations: dict
) -> int:
      
    updated = 0

    for table_idx, table_data in enumerate(doc_data.tables):
        for (row, col), cell_paragraphs in table_data.cells.items():
            for para_idx, para_data in enumerate(cell_paragraphs):
                key = (table_idx, row, col, para_idx)

                if key in table_translations:
                    translation = table_translations[key]
                    if translation and translation.strip():
                        _replace_paragraph_text(para_data, translation)
                        updated += 1

    return updated

def save_translated_document(
    doc_data:           DocumentData,
    para_translations:  list[str],
    table_translations: dict,
    original_path:      str,
    output_path:        str | None = None,
) -> str:
     

        # Auto-generate output path if caller didn't specify one
    if output_path is None:
        # Path("D:/docs/report.docx").stem   → "report"
        # Path("D:/docs/report.docx").suffix → ".docx"
        # Path("D:/docs/report.docx").parent → Path("D:/docs")
        p = Path(original_path)
        output_path = str(p.parent / (p.stem + OUTPUT_SUFFIX + p.suffix))

    logger.info("Applying paragraph translations...")
    para_count = _apply_paragraph_translations(
        doc_data.paragraphs,
        para_translations
    )
    logger.info(f"Updated {para_count} paragraphs.")

    logger.info("Applying table translations...")
    table_count = _apply_table_translations(doc_data, table_translations)
    logger.info(f"Updated {table_count} table cell paragraphs.")

    try:
        doc_data.doc_ref.save(output_path)
        logger.info(f"Saved: {output_path}")
        return output_path
    
    except PermissionError:
        # This happens when the file is open in Microsoft Word
        raise RuntimeError(
            f"Cannot save to {output_path}. "
            f"Close the file in Word and try again."
        )
    except Exception as e:
        raise RuntimeError(f"Failed to save: {e}")



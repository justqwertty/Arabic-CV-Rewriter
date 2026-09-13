import pytest

from extract import ExtractionError, extract_text


def test_extract_pdf_returns_text(clean_pdf_bytes):
    text = extract_text(clean_pdf_bytes, ".pdf")
    assert "Ahmed Hassan" in text
    assert "Software Engineer" in text


def test_extract_docx_returns_text(clean_docx_bytes):
    text = extract_text(clean_docx_bytes, ".docx")
    assert "Ahmed Hassan" in text
    assert "Software Engineer" in text


def test_extract_pdf_empty_raises(empty_pdf_bytes):
    with pytest.raises(ExtractionError, match="scanned image"):
        extract_text(empty_pdf_bytes, ".pdf")


def test_extract_docx_empty_raises(empty_docx_bytes):
    with pytest.raises(ExtractionError, match="scanned image"):
        extract_text(empty_docx_bytes, ".docx")


def test_extract_corrupt_pdf_raises(corrupt_file_bytes):
    with pytest.raises(ExtractionError, match="Could not read"):
        extract_text(corrupt_file_bytes, ".pdf")


def test_extract_corrupt_docx_raises(corrupt_file_bytes):
    with pytest.raises(ExtractionError, match="Could not read"):
        extract_text(corrupt_file_bytes, ".docx")


def test_extract_unsupported_extension_raises(clean_pdf_bytes):
    with pytest.raises(ExtractionError, match="Unsupported"):
        extract_text(clean_pdf_bytes, ".txt")

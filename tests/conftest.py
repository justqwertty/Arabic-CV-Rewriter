"""Shared fixtures for generating in-memory PDF/DOCX test files.

Fixtures are built at test time with reportlab/python-docx rather than
checked in as binary files, so there is nothing to keep in sync by hand.
"""
from __future__ import annotations

import io

import pytest
from docx import Document
from reportlab.pdfgen import canvas


def _make_pdf_bytes(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for line in lines:
        c.drawString(72, y, line)
        y -= 20
    c.save()
    return buf.getvalue()


def _make_empty_pdf_bytes() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.showPage()
    c.save()
    return buf.getvalue()


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def clean_pdf_bytes() -> bytes:
    return _make_pdf_bytes(["Ahmed Hassan", "Software Engineer", "5 years experience in backend systems"])


@pytest.fixture
def empty_pdf_bytes() -> bytes:
    return _make_empty_pdf_bytes()


@pytest.fixture
def clean_docx_bytes() -> bytes:
    return _make_docx_bytes(["Ahmed Hassan", "Software Engineer", "5 years experience in backend systems"])


@pytest.fixture
def empty_docx_bytes() -> bytes:
    return _make_docx_bytes([])


@pytest.fixture
def corrupt_file_bytes() -> bytes:
    return b"this is not a valid pdf or docx file, just plain garbage bytes"

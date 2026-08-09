import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import doc_service

def test_pdf_generation():
    """
    Test PDF report creation.
    """
    title = "Drilling Analysis Report"
    content = "The core grade is 1.84% Cu.\nThis aligns with general mine expectations."
    table_data = [
        ["Shaft ID", "Grade", "Tonnage"],
        ["Shaft 1", "1.45%", "2500T"],
        ["Shaft 2", "1.84%", "4800T"]
    ]
    pdf_bytes = doc_service.create_pdf_from_content(title, content, table_data)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF") # PDF header identification

def test_docx_generation():
    """
    Test DOCX file creation.
    """
    title = "Financial Budget Guidelines"
    content = "Please adhere strictly to department ceilings."
    docx_bytes = doc_service.create_docx_from_content(title, content)
    assert len(docx_bytes) > 0
    # DOCX standard PK zip header
    assert docx_bytes.startswith(b"PK\x03\x04")

def test_xlsx_generation():
    """
    Test Excel file creation.
    """
    data = {
        "Month": ["Jan", "Feb", "Mar"],
        "Spend": [12000, 15000, 14000]
    }
    df = pd.DataFrame(data)
    xlsx_bytes = doc_service.create_xlsx_from_dataframe(df)
    assert len(xlsx_bytes) > 0
    assert xlsx_bytes.startswith(b"PK\x03\x04")

"""
PDF Parser for extracting text, tables, and metadata from PDF documents.
Handles contracts, bills of lading, and other logistics documents.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import io
from pathlib import Path

# PDF parsing libraries
try:
    import pypdf
    from pypdf import PdfReader
except ImportError:
    pypdf = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from pdfminer.high_level import extract_text as pdfminer_extract
    from pdfminer.layout import LAParams
except ImportError:
    pdfminer_extract = None

logger = logging.getLogger(__name__)


class PDFParser:
    """Parser for PDF documents with text and table extraction."""

    def __init__(
        self,
        extract_tables: bool = True,
        extract_images: bool = False,
        library: str = "pdfplumber"  # Options: 'pypdf', 'pdfplumber', 'pdfminer'
    ):
        """
        Initialize PDF parser.

        Args:
            extract_tables: Whether to extract tables
            extract_images: Whether to extract embedded images
            library: PDF parsing library to use
        """
        self.extract_tables = extract_tables
        self.extract_images = extract_images
        self.library = library

        if library == "pdfplumber" and pdfplumber is None:
            raise ImportError("pdfplumber not installed. Run: pip install pdfplumber")
        elif library == "pypdf" and pypdf is None:
            raise ImportError("pypdf not installed. Run: pip install pypdf")
        elif library == "pdfminer" and pdfminer_extract is None:
            raise ImportError("pdfminer.six not installed. Run: pip install pdfminer.six")

        logger.info(f"PDF parser initialized with library: {library}")

    def parse(
        self,
        content: bytes,
        filename: Optional[str] = None
    ) -> Dict:
        """
        Parse PDF document.

        Args:
            content: PDF file content as bytes
            filename: Original filename for metadata

        Returns:
            Parsed document with text, tables, and metadata
        """
        if self.library == "pdfplumber":
            return self._parse_with_pdfplumber(content, filename)
        elif self.library == "pypdf":
            return self._parse_with_pypdf(content, filename)
        elif self.library == "pdfminer":
            return self._parse_with_pdfminer(content, filename)
        else:
            raise ValueError(f"Unknown library: {self.library}")

    def _parse_with_pdfplumber(
        self,
        content: bytes,
        filename: Optional[str] = None
    ) -> Dict:
        """Parse PDF using pdfplumber (best for tables)."""
        pdf_file = io.BytesIO(content)
        text_content = []
        tables = []
        metadata = {}

        try:
            with pdfplumber.open(pdf_file) as pdf:
                # Extract metadata
                metadata = {
                    'num_pages': len(pdf.pages),
                    'parser': 'pdfplumber',
                    'filename': filename
                }

                if pdf.metadata:
                    metadata.update({
                        'title': pdf.metadata.get('Title'),
                        'author': pdf.metadata.get('Author'),
                        'subject': pdf.metadata.get('Subject'),
                        'creator': pdf.metadata.get('Creator'),
                        'producer': pdf.metadata.get('Producer'),
                        'creation_date': pdf.metadata.get('CreationDate'),
                    })

                # Extract text and tables from each page
                for page_num, page in enumerate(pdf.pages, start=1):
                    # Extract text
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append({
                            'page': page_num,
                            'text': page_text
                        })

                    # Extract tables
                    if self.extract_tables:
                        page_tables = page.extract_tables()
                        for table_idx, table in enumerate(page_tables):
                            tables.append({
                                'page': page_num,
                                'table_index': table_idx,
                                'data': table,
                                'markdown': self._table_to_markdown(table)
                            })

            logger.info(f"Parsed PDF: {metadata['num_pages']} pages, {len(tables)} tables")

            return {
                'text': text_content,
                'tables': tables,
                'metadata': metadata,
                'full_text': '\n\n'.join([p['text'] for p in text_content if p['text']])
            }

        except Exception as e:
            logger.error(f"Error parsing PDF with pdfplumber: {e}")
            raise

    def _parse_with_pypdf(
        self,
        content: bytes,
        filename: Optional[str] = None
    ) -> Dict:
        """Parse PDF using pypdf (lightweight, fast)."""
        pdf_file = io.BytesIO(content)
        text_content = []
        metadata = {}

        try:
            reader = PdfReader(pdf_file)

            # Extract metadata
            metadata = {
                'num_pages': len(reader.pages),
                'parser': 'pypdf',
                'filename': filename
            }

            if reader.metadata:
                metadata.update({
                    'title': reader.metadata.get('/Title'),
                    'author': reader.metadata.get('/Author'),
                    'subject': reader.metadata.get('/Subject'),
                    'creator': reader.metadata.get('/Creator'),
                    'producer': reader.metadata.get('/Producer'),
                })

            # Extract text from each page
            for page_num, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    text_content.append({
                        'page': page_num,
                        'text': page_text
                    })

            logger.info(f"Parsed PDF with pypdf: {metadata['num_pages']} pages")

            return {
                'text': text_content,
                'tables': [],  # pypdf doesn't extract tables well
                'metadata': metadata,
                'full_text': '\n\n'.join([p['text'] for p in text_content if p['text']])
            }

        except Exception as e:
            logger.error(f"Error parsing PDF with pypdf: {e}")
            raise

    def _parse_with_pdfminer(
        self,
        content: bytes,
        filename: Optional[str] = None
    ) -> Dict:
        """Parse PDF using pdfminer (good for complex layouts)."""
        pdf_file = io.BytesIO(content)

        try:
            # Extract text with layout analysis
            laparams = LAParams()
            text = pdfminer_extract(pdf_file, laparams=laparams)

            # Basic metadata
            metadata = {
                'parser': 'pdfminer',
                'filename': filename
            }

            logger.info(f"Parsed PDF with pdfminer: {len(text)} characters")

            return {
                'text': [{'page': 1, 'text': text}],  # pdfminer doesn't separate pages easily
                'tables': [],
                'metadata': metadata,
                'full_text': text
            }

        except Exception as e:
            logger.error(f"Error parsing PDF with pdfminer: {e}")
            raise

    def _table_to_markdown(self, table: List[List]) -> str:
        """
        Convert table data to Markdown format.

        Args:
            table: 2D list representing table data

        Returns:
            Markdown formatted table string
        """
        if not table or len(table) < 2:
            return ""

        markdown_lines = []

        # Header row
        header = table[0]
        markdown_lines.append("| " + " | ".join(str(cell or "") for cell in header) + " |")

        # Separator
        markdown_lines.append("| " + " | ".join(["---"] * len(header)) + " |")

        # Data rows
        for row in table[1:]:
            markdown_lines.append("| " + " | ".join(str(cell or "") for cell in row) + " |")

        return "\n".join(markdown_lines)

    def extract_contract_fields(self, parsed_doc: Dict) -> Dict:
        """
        Extract common contract fields from parsed PDF.

        Args:
            parsed_doc: Parsed document from parse()

        Returns:
            Dictionary of extracted contract fields
        """
        full_text = parsed_doc.get('full_text', '')

        # Simple keyword-based extraction (can be enhanced with NER)
        contract_fields = {}

        # Extract contract ID
        import re

        contract_id_pattern = r'Contract\s*(?:ID|Number|No\.?):\s*([A-Z0-9\-]+)'
        match = re.search(contract_id_pattern, full_text, re.IGNORECASE)
        if match:
            contract_fields['contract_id'] = match.group(1)

        # Extract vendor name
        vendor_pattern = r'Vendor:\s*([A-Za-z\s&.,]+?)(?:\n|Date)'
        match = re.search(vendor_pattern, full_text, re.IGNORECASE)
        if match:
            contract_fields['vendor_name'] = match.group(1).strip()

        # Extract dates
        date_pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        dates = re.findall(date_pattern, full_text)
        if dates:
            contract_fields['dates_found'] = dates

        logger.info(f"Extracted contract fields: {list(contract_fields.keys())}")
        return contract_fields

    def parse_bill_of_lading(self, content: bytes) -> Dict:
        """
        Specialized parser for Bill of Lading documents.

        Args:
            content: PDF file content

        Returns:
            Structured bill of lading data
        """
        parsed_doc = self.parse(content, filename="bill_of_lading.pdf")

        # Extract specific fields
        bol_data = {
            'document_type': 'bill_of_lading',
            'parsed_at': datetime.utcnow().isoformat(),
            'text': parsed_doc['full_text'],
            'tables': parsed_doc['tables'],
            'metadata': parsed_doc['metadata']
        }

        # Can add specific field extraction logic here
        return bol_data


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    parser = PDFParser(extract_tables=True, library="pdfplumber")

    # Parse a PDF file
    with open("sample_contract.pdf", "rb") as f:
        content = f.read()

    result = parser.parse(content, filename="sample_contract.pdf")

    print(f"Pages: {result['metadata']['num_pages']}")
    print(f"Tables: {len(result['tables'])}")
    print(f"Text preview: {result['full_text'][:500]}...")

    # Extract contract fields
    fields = parser.extract_contract_fields(result)
    print(f"Contract fields: {fields}")

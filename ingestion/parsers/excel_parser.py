"""
Excel Parser for extracting data from Excel files (.xlsx, .xls).
Handles shipment logs, inventory data, and structured logistics data.
"""

import logging
from typing import Dict, List, Optional, Union
from datetime import datetime
import io
import pandas as pd
import openpyxl

logger = logging.getLogger(__name__)


class ExcelParser:
    """Parser for Excel files with sheet and table extraction."""

    def __init__(
        self,
        parse_all_sheets: bool = True,
        preserve_formatting: bool = False
    ):
        """
        Initialize Excel parser.

        Args:
            parse_all_sheets: Whether to parse all sheets or just the first
            preserve_formatting: Preserve cell formatting information
        """
        self.parse_all_sheets = parse_all_sheets
        self.preserve_formatting = preserve_formatting
        logger.info("Excel parser initialized")

    def parse(
        self,
        content: bytes,
        filename: Optional[str] = None
    ) -> Dict:
        """
        Parse Excel file.

        Args:
            content: Excel file content as bytes
            filename: Original filename

        Returns:
            Parsed document with sheets, tables, and metadata
        """
        excel_file = io.BytesIO(content)
        sheets_data = []
        metadata = {}

        try:
            # Read Excel file
            xl = pd.ExcelFile(excel_file)

            metadata = {
                'num_sheets': len(xl.sheet_names),
                'sheet_names': xl.sheet_names,
                'parser': 'pandas+openpyxl',
                'filename': filename
            }

            # Parse each sheet
            sheets_to_parse = xl.sheet_names if self.parse_all_sheets else [xl.sheet_names[0]]

            for sheet_name in sheets_to_parse:
                df = pd.read_excel(xl, sheet_name=sheet_name)

                sheet_data = {
                    'sheet_name': sheet_name,
                    'num_rows': len(df),
                    'num_columns': len(df.columns),
                    'columns': df.columns.tolist(),
                    'data': df.to_dict('records'),
                    'markdown': df.to_markdown(index=False),
                    'html': df.to_html(index=False),
                    'csv': df.to_csv(index=False)
                }

                # Extract summary statistics
                sheet_data['summary'] = {
                    'numeric_columns': df.select_dtypes(include=['number']).columns.tolist(),
                    'text_columns': df.select_dtypes(include=['object']).columns.tolist(),
                    'date_columns': df.select_dtypes(include=['datetime']).columns.tolist(),
                    'null_counts': df.isnull().sum().to_dict()
                }

                sheets_data.append(sheet_data)

            logger.info(f"Parsed Excel: {len(sheets_data)} sheets")

            return {
                'sheets': sheets_data,
                'metadata': metadata
            }

        except Exception as e:
            logger.error(f"Error parsing Excel file: {e}")
            raise

    def parse_with_formatting(
        self,
        content: bytes,
        filename: Optional[str] = None
    ) -> Dict:
        """
        Parse Excel file with cell formatting information.

        Args:
            content: Excel file content as bytes
            filename: Original filename

        Returns:
            Parsed document with formatting details
        """
        excel_file = io.BytesIO(content)

        try:
            wb = openpyxl.load_workbook(excel_file, data_only=False)

            sheets_data = []
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]

                sheet_data = {
                    'sheet_name': sheet_name,
                    'num_rows': ws.max_row,
                    'num_columns': ws.max_column,
                    'cells': []
                }

                # Extract cell data with formatting
                for row in ws.iter_rows():
                    row_data = []
                    for cell in row:
                        cell_info = {
                            'value': cell.value,
                            'row': cell.row,
                            'column': cell.column,
                            'font': {
                                'bold': cell.font.bold,
                                'italic': cell.font.italic,
                                'color': str(cell.font.color) if cell.font.color else None
                            } if cell.font else None,
                            'fill': str(cell.fill.fgColor) if cell.fill else None,
                            'number_format': cell.number_format
                        }
                        row_data.append(cell_info)
                    sheet_data['cells'].append(row_data)

                sheets_data.append(sheet_data)

            logger.info(f"Parsed Excel with formatting: {len(sheets_data)} sheets")

            return {
                'sheets': sheets_data,
                'metadata': {
                    'num_sheets': len(sheets_data),
                    'parser': 'openpyxl',
                    'filename': filename
                }
            }

        except Exception as e:
            logger.error(f"Error parsing Excel with formatting: {e}")
            raise

    def extract_named_ranges(
        self,
        content: bytes
    ) -> Dict[str, pd.DataFrame]:
        """
        Extract named ranges from Excel file.

        Args:
            content: Excel file content

        Returns:
            Dictionary mapping range names to DataFrames
        """
        excel_file = io.BytesIO(content)
        named_ranges = {}

        try:
            wb = openpyxl.load_workbook(excel_file)

            for name, cells in wb.defined_names.items():
                # Get the range coordinates
                if cells.destinations:
                    for sheet_name, cell_range in cells.destinations:
                        ws = wb[sheet_name]
                        data = []
                        for row in ws[cell_range]:
                            data.append([cell.value for cell in row])

                        df = pd.DataFrame(data[1:], columns=data[0]) if len(data) > 1 else pd.DataFrame(data)
                        named_ranges[name] = df

            logger.info(f"Extracted {len(named_ranges)} named ranges")
            return named_ranges

        except Exception as e:
            logger.error(f"Error extracting named ranges: {e}")
            return {}

    def parse_shipment_logs(
        self,
        content: bytes
    ) -> List[Dict]:
        """
        Specialized parser for shipment log Excel files.

        Args:
            content: Excel file content

        Returns:
            List of shipment records with normalized fields
        """
        parsed = self.parse(content)

        shipments = []
        for sheet in parsed['sheets']:
            for record in sheet['data']:
                # Normalize field names
                normalized = self._normalize_shipment_record(record)
                if normalized:
                    shipments.append(normalized)

        logger.info(f"Parsed {len(shipments)} shipment records")
        return shipments

    def _normalize_shipment_record(self, record: Dict) -> Optional[Dict]:
        """
        Normalize shipment record field names.

        Args:
            record: Raw record from Excel

        Returns:
            Normalized record or None if invalid
        """
        # Common field name variations
        field_mappings = {
            'shipment_id': ['Shipment ID', 'ShipmentID', 'ID', 'Shipment No'],
            'vendor_id': ['Vendor ID', 'VendorID', 'Supplier_No', 'Supplier ID'],
            'origin': ['Origin', 'From', 'Source', 'Departure'],
            'destination': ['Destination', 'To', 'Target', 'Arrival'],
            'status': ['Status', 'State', 'Condition'],
            'departure_date': ['Departure Date', 'Dept Date', 'Start Date'],
            'arrival_date': ['Arrival Date', 'Arr Date', 'End Date'],
            'cargo_type': ['Cargo Type', 'Product', 'Goods Type'],
            'weight': ['Weight', 'Weight (kg)', 'Weight_KG']
        }

        normalized = {}

        for standard_field, variations in field_mappings.items():
            for variation in variations:
                if variation in record:
                    normalized[standard_field] = record[variation]
                    break

        # Only return if we found critical fields
        if 'shipment_id' in normalized:
            return normalized

        return None

    def to_chunks(
        self,
        parsed_doc: Dict,
        chunk_by: str = "row"  # Options: 'row', 'sheet', 'table'
    ) -> List[Dict]:
        """
        Convert parsed Excel document into chunks for RAG.

        Args:
            parsed_doc: Parsed document from parse()
            chunk_by: Chunking strategy

        Returns:
            List of chunks with metadata
        """
        chunks = []

        for sheet in parsed_doc['sheets']:
            if chunk_by == "sheet":
                # One chunk per sheet
                chunk = {
                    'content': sheet['markdown'],
                    'type': 'table',
                    'metadata': {
                        'sheet_name': sheet['sheet_name'],
                        'num_rows': sheet['num_rows'],
                        'num_columns': sheet['num_columns'],
                        'format': 'excel_sheet'
                    }
                }
                chunks.append(chunk)

            elif chunk_by == "row":
                # One chunk per row (with headers)
                headers = sheet['columns']
                for idx, row_data in enumerate(sheet['data']):
                    # Create mini-table with headers
                    mini_table = [headers, list(row_data.values())]
                    df = pd.DataFrame([row_data])

                    chunk = {
                        'content': df.to_markdown(index=False),
                        'type': 'table_row',
                        'metadata': {
                            'sheet_name': sheet['sheet_name'],
                            'row_index': idx,
                            'format': 'excel_row',
                            'data': row_data
                        }
                    }
                    chunks.append(chunk)

            elif chunk_by == "table":
                # Detect logical tables within sheet (simplified)
                # For now, treat entire sheet as one table
                chunk = {
                    'content': sheet['markdown'],
                    'type': 'table',
                    'metadata': {
                        'sheet_name': sheet['sheet_name'],
                        'format': 'excel_table'
                    }
                }
                chunks.append(chunk)

        logger.info(f"Created {len(chunks)} chunks from Excel")
        return chunks


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    parser = ExcelParser(parse_all_sheets=True)

    # Parse Excel file
    with open("sample_shipments.xlsx", "rb") as f:
        content = f.read()

    result = parser.parse(content, filename="sample_shipments.xlsx")

    print(f"Sheets: {result['metadata']['num_sheets']}")
    for sheet in result['sheets']:
        print(f"\nSheet: {sheet['sheet_name']}")
        print(f"  Rows: {sheet['num_rows']}, Columns: {sheet['num_columns']}")
        print(f"  Columns: {sheet['columns']}")

    # Convert to chunks
    chunks = parser.to_chunks(result, chunk_by="row")
    print(f"\nCreated {len(chunks)} chunks")

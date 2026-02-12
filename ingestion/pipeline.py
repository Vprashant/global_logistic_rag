"""
Main ingestion pipeline orchestrating data flow from sources to vector database.
Handles multiple data sources, processing, and storage.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from ingestion.connectors.s3_connector import S3Connector
from ingestion.connectors.database_connector import DatabaseConnector
from ingestion.connectors.kafka_connector import KafkaConnector
from ingestion.connectors.api_connector import APIConnector

from ingestion.parsers.pdf_parser import PDFParser
from ingestion.parsers.excel_parser import ExcelParser
from ingestion.parsers.image_parser import ImageParser

from ingestion.processors.chunking import get_chunker

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Main ingestion pipeline for the RAG system.
    Coordinates data ingestion, parsing, processing, and storage.
    """

    def __init__(
        self,
        vector_db_client=None,
        metadata_db_client=None,
        config: Optional[Dict] = None
    ):
        """
        Initialize ingestion pipeline.

        Args:
            vector_db_client: Vector database client
            metadata_db_client: Metadata/lineage database client
            config: Pipeline configuration
        """
        self.vector_db = vector_db_client
        self.metadata_db = metadata_db_client
        self.config = config or {}

        # Initialize connectors
        self.s3_connector = None
        self.db_connector = None
        self.kafka_connector = None
        self.api_connector = None

        # Initialize parsers
        self.pdf_parser = PDFParser(extract_tables=True)
        self.excel_parser = ExcelParser(parse_all_sheets=True)
        self.image_parser = None  # Initialized on demand

        # Initialize chunker
        chunking_strategy = self.config.get('chunking_strategy', 'recursive')
        self.chunker = get_chunker(
            strategy=chunking_strategy,
            chunk_size=self.config.get('chunk_size', 1000),
            chunk_overlap=self.config.get('chunk_overlap', 200)
        )

        logger.info("Ingestion pipeline initialized")

    def ingest_s3_documents(
        self,
        bucket: str,
        prefix: str = "",
        file_extensions: Optional[List[str]] = None,
        batch_size: int = 10
    ) -> Dict[str, int]:
        """
        Ingest documents from S3 bucket.

        Args:
            bucket: S3 bucket name
            prefix: S3 prefix/folder
            file_extensions: Allowed file extensions
            batch_size: Batch size for processing

        Returns:
            Statistics dictionary
        """
        if self.s3_connector is None:
            self.s3_connector = S3Connector()

        logger.info(f"Starting S3 ingestion: s3://{bucket}/{prefix}")

        stats = {
            'total_documents': 0,
            'successful': 0,
            'failed': 0,
            'total_chunks': 0
        }

        try:
            # Stream documents in batches
            for batch in self.s3_connector.stream_objects(
                bucket=bucket,
                prefix=prefix,
                batch_size=batch_size
            ):
                stats['total_documents'] += len(batch)

                # Process batch
                for document in batch:
                    try:
                        processed_doc = self._process_document(document)

                        if processed_doc:
                            # Store in vector DB
                            self._store_document(processed_doc)
                            stats['successful'] += 1
                            stats['total_chunks'] += len(processed_doc.get('chunks', []))

                    except Exception as e:
                        logger.error(f"Error processing document: {e}")
                        stats['failed'] += 1
                        continue

            logger.info(f"S3 ingestion complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"S3 ingestion error: {e}")
            raise

    def ingest_database_records(
        self,
        query: str,
        query_name: str,
        connection_string: Optional[str] = None,
        batch_size: int = 1000
    ) -> Dict[str, int]:
        """
        Ingest records from database.

        Args:
            query: SQL query
            query_name: Descriptive name for lineage
            connection_string: Database connection string
            batch_size: Batch size for streaming

        Returns:
            Statistics dictionary
        """
        if self.db_connector is None:
            if connection_string is None:
                raise ValueError("connection_string required")
            self.db_connector = DatabaseConnector(connection_string)

        logger.info(f"Starting database ingestion: {query_name}")

        stats = {
            'total_records': 0,
            'successful': 0,
            'failed': 0,
            'total_chunks': 0
        }

        try:
            # Stream query results
            for batch in self.db_connector.ingest_custom_query(
                query=query,
                query_name=query_name,
                batch_size=batch_size
            ):
                stats['total_records'] += len(batch)

                # Process batch
                for document in batch:
                    try:
                        processed_doc = self._process_database_record(document)

                        if processed_doc:
                            self._store_document(processed_doc)
                            stats['successful'] += 1
                            stats['total_chunks'] += len(processed_doc.get('chunks', []))

                    except Exception as e:
                        logger.error(f"Error processing record: {e}")
                        stats['failed'] += 1
                        continue

            logger.info(f"Database ingestion complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Database ingestion error: {e}")
            raise

    def ingest_kafka_stream(
        self,
        topic: str,
        batch_size: int = 50,
        max_batches: Optional[int] = None
    ) -> Dict[str, int]:
        """
        Ingest real-time data from Kafka stream.

        Args:
            topic: Kafka topic
            batch_size: Messages per batch
            max_batches: Maximum batches to process

        Returns:
            Statistics dictionary
        """
        if self.kafka_connector is None:
            bootstrap_servers = self.config.get('kafka_bootstrap_servers', 'localhost:9092')
            self.kafka_connector = KafkaConnector(bootstrap_servers=bootstrap_servers)

        logger.info(f"Starting Kafka ingestion: topic={topic}")

        stats = {
            'total_messages': 0,
            'successful': 0,
            'failed': 0,
            'total_chunks': 0
        }

        try:
            # Consume IoT stream
            for batch in self.kafka_connector.ingest_iot_stream(
                topic=topic,
                batch_size=batch_size
            ):
                stats['total_messages'] += len(batch)

                # Process batch
                for document in batch:
                    try:
                        processed_doc = self._process_streaming_data(document)

                        if processed_doc:
                            self._store_document(processed_doc)
                            stats['successful'] += 1
                            stats['total_chunks'] += len(processed_doc.get('chunks', []))

                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        stats['failed'] += 1
                        continue

                # Check max batches
                if max_batches and stats['total_messages'] // batch_size >= max_batches:
                    break

            logger.info(f"Kafka ingestion complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Kafka ingestion error: {e}")
            raise
        finally:
            if self.kafka_connector:
                self.kafka_connector.stop_consuming()

    def ingest_api_data(
        self,
        api_type: str,
        **kwargs
    ) -> Dict[str, int]:
        """
        Ingest data from external APIs.

        Args:
            api_type: Type of API (port_congestion, weather, shipping_rates)
            **kwargs: API-specific parameters

        Returns:
            Statistics dictionary
        """
        if self.api_connector is None:
            self.api_connector = APIConnector(
                base_url=self.config.get('api_base_url'),
                api_key=self.config.get('api_key')
            )

        logger.info(f"Starting API ingestion: {api_type}")

        stats = {
            'total_documents': 0,
            'successful': 0,
            'failed': 0
        }

        try:
            # Call appropriate API method
            if api_type == 'port_congestion':
                documents = self.api_connector.ingest_port_congestion(**kwargs)
            elif api_type == 'weather':
                documents = self.api_connector.ingest_weather_forecast(**kwargs)
            elif api_type == 'shipping_rates':
                documents = self.api_connector.ingest_shipping_rates(**kwargs)
            else:
                raise ValueError(f"Unknown API type: {api_type}")

            stats['total_documents'] = len(documents)

            # Process documents
            for document in documents:
                try:
                    processed_doc = self._process_api_data(document)

                    if processed_doc:
                        self._store_document(processed_doc)
                        stats['successful'] += 1

                except Exception as e:
                    logger.error(f"Error processing API document: {e}")
                    stats['failed'] += 1
                    continue

            logger.info(f"API ingestion complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"API ingestion error: {e}")
            raise

    def _process_document(self, document: Dict) -> Optional[Dict]:
        """
        Process a document through parsing and chunking.

        Args:
            document: Raw document with content and metadata

        Returns:
            Processed document with chunks
        """
        content = document['content']
        metadata = document['metadata']

        # Determine file type
        filename = metadata.get('filename', metadata.get('key', ''))
        file_ext = filename.split('.')[-1].lower() if filename else ''

        # Parse based on file type
        if file_ext == 'pdf':
            parsed = self.pdf_parser.parse(content, filename)
            text_content = parsed['full_text']

        elif file_ext in ['xlsx', 'xls']:
            parsed = self.excel_parser.parse(content, filename)
            # Convert to chunks directly
            chunks = self.excel_parser.to_chunks(parsed, chunk_by='row')
            return {
                'metadata': metadata,
                'chunks': chunks,
                'parsed_data': parsed
            }

        elif file_ext in ['jpg', 'jpeg', 'png']:
            # Image processing requires VLM
            if self.image_parser is None:
                self.image_parser = ImageParser(
                    vlm_provider=self.config.get('vlm_provider', 'openai'),
                    api_key=self.config.get('openai_api_key')
                )
            parsed = self.image_parser.parse(content, filename)
            text_content = parsed['description']

        else:
            # Plain text or unknown
            text_content = content.decode('utf-8') if isinstance(content, bytes) else str(content)

        # Chunk the text
        chunks = self.chunker.chunk(text_content, metadata)

        return {
            'metadata': metadata,
            'chunks': chunks,
            'original_text': text_content
        }

    def _process_database_record(self, document: Dict) -> Optional[Dict]:
        """Process database record."""
        content = document['content']
        metadata = document['metadata']

        # Convert dict to text representation
        text_content = self._dict_to_text(content)

        # Chunk
        chunks = self.chunker.chunk(text_content, metadata)

        return {
            'metadata': metadata,
            'chunks': chunks,
            'structured_data': content
        }

    def _process_streaming_data(self, document: Dict) -> Optional[Dict]:
        """Process streaming data (IoT, events)."""
        content = document['content']
        metadata = document['metadata']

        # Convert to text
        text_content = self._dict_to_text(content)

        # For streaming data, might not need chunking
        chunks = [{
            'content': text_content,
            'metadata': metadata,
            'chunk_index': 0,
            'total_chunks': 1
        }]

        return {
            'metadata': metadata,
            'chunks': chunks,
            'structured_data': content
        }

    def _process_api_data(self, document: Dict) -> Optional[Dict]:
        """Process API data."""
        return self._process_streaming_data(document)

    def _dict_to_text(self, data: Dict) -> str:
        """Convert dictionary to text representation."""
        lines = []
        for key, value in data.items():
            lines.append(f"{key}: {value}")
        return "\n".join(lines)

    def _store_document(self, document: Dict):
        """
        Store processed document in vector database.

        Args:
            document: Processed document with chunks
        """
        if self.vector_db is None:
            logger.warning("Vector DB not configured, skipping storage")
            return

        # Store each chunk
        for chunk in document['chunks']:
            try:
                self.vector_db.upsert_chunk(chunk)
            except Exception as e:
                logger.error(f"Error storing chunk: {e}")

        # Track lineage
        if self.metadata_db:
            try:
                self.metadata_db.record_ingestion(document['metadata'])
            except Exception as e:
                logger.error(f"Error recording lineage: {e}")


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    pipeline = IngestionPipeline(config={
        'chunking_strategy': 'recursive',
        'chunk_size': 1000,
        'chunk_overlap': 200
    })

    # Ingest from S3
    stats = pipeline.ingest_s3_documents(
        bucket="logistics-contracts",
        prefix="2024/Q1/",
        batch_size=10
    )
    print(f"S3 ingestion stats: {stats}")

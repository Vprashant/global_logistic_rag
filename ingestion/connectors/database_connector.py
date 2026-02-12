"""
Database Connector for ingesting structured data from SAP/Oracle databases.
Supports shipment logs, vendor records, and other structured logistics data.
"""

import logging
from typing import List, Dict, Optional, Generator, Any
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
import pandas as pd

logger = logging.getLogger(__name__)


class DatabaseConnector:
    """Connector for relational databases (SAP, Oracle, PostgreSQL, etc.)."""

    def __init__(
        self,
        connection_string: str,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30
    ):
        """
        Initialize database connector.

        Args:
            connection_string: SQLAlchemy connection string
                Examples:
                - Oracle: "oracle+cx_oracle://user:pass@host:port/service"
                - PostgreSQL: "postgresql://user:pass@host:port/database"
                - SAP HANA: "hana://user:pass@host:port"
            pool_size: Connection pool size
            max_overflow: Max overflow connections
            pool_timeout: Pool timeout in seconds
        """
        self.engine: Engine = create_engine(
            connection_string,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True  # Verify connections before using
        )
        self.metadata = MetaData()
        logger.info(f"Database connector initialized: {self.engine.url.host}")

    def execute_query(
        self,
        query: str,
        params: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Execute SQL query and return results as list of dictionaries.

        Args:
            query: SQL query string
            params: Query parameters for parameterized queries

        Returns:
            List of row dictionaries
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                columns = result.keys()
                rows = [dict(zip(columns, row)) for row in result.fetchall()]

                logger.info(f"Query returned {len(rows)} rows")
                return rows

        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise

    def execute_query_dataframe(
        self,
        query: str,
        params: Optional[Dict] = None
    ) -> pd.DataFrame:
        """
        Execute query and return results as pandas DataFrame.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            pandas DataFrame
        """
        try:
            df = pd.read_sql_query(query, self.engine, params=params)
            logger.info(f"Query returned {len(df)} rows, {len(df.columns)} columns")
            return df

        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise

    def stream_query_results(
        self,
        query: str,
        batch_size: int = 1000,
        params: Optional[Dict] = None
    ) -> Generator[List[Dict], None, None]:
        """
        Stream query results in batches for memory efficiency.

        Args:
            query: SQL query string
            batch_size: Number of rows per batch
            params: Query parameters

        Yields:
            Batches of row dictionaries
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execution_options(stream_results=True).execute(
                    text(query),
                    params or {}
                )
                columns = result.keys()

                while True:
                    batch = result.fetchmany(batch_size)
                    if not batch:
                        break

                    rows = [dict(zip(columns, row)) for row in batch]
                    logger.debug(f"Yielding batch of {len(rows)} rows")
                    yield rows

        except Exception as e:
            logger.error(f"Error streaming query results: {e}")
            raise

    def get_table_schema(self, table_name: str, schema: Optional[str] = None) -> Dict:
        """
        Get table schema information.

        Args:
            table_name: Name of the table
            schema: Database schema name

        Returns:
            Schema information dictionary
        """
        try:
            inspector = sa.inspect(self.engine)
            columns = inspector.get_columns(table_name, schema=schema)

            schema_info = {
                'table_name': table_name,
                'schema': schema,
                'columns': [
                    {
                        'name': col['name'],
                        'type': str(col['type']),
                        'nullable': col['nullable'],
                        'default': col.get('default')
                    }
                    for col in columns
                ],
                'primary_keys': inspector.get_pk_constraint(table_name, schema=schema)
            }

            return schema_info

        except Exception as e:
            logger.error(f"Error getting schema for {table_name}: {e}")
            raise

    def ingest_table(
        self,
        table_name: str,
        schema: Optional[str] = None,
        filters: Optional[Dict] = None,
        columns: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Ingest entire table with optional filtering.

        Args:
            table_name: Name of the table
            schema: Database schema name
            filters: WHERE clause filters (e.g., {"date": "2024-01-01"})
            columns: Specific columns to select (None for all)

        Returns:
            List of row dictionaries with metadata
        """
        try:
            # Build query
            col_str = ", ".join(columns) if columns else "*"
            query = f"SELECT {col_str} FROM "

            if schema:
                query += f"{schema}.{table_name}"
            else:
                query += table_name

            # Add filters
            if filters:
                where_clauses = [f"{k} = :{k}" for k in filters.keys()]
                query += " WHERE " + " AND ".join(where_clauses)

            # Execute query
            rows = self.execute_query(query, filters)

            # Add metadata
            documents = []
            for row in rows:
                document = {
                    'content': row,
                    'metadata': {
                        'source_type': 'database',
                        'table_name': table_name,
                        'schema': schema,
                        'source_uri': f"db://{table_name}",
                        'ingestion_timestamp': datetime.utcnow().isoformat()
                    }
                }
                documents.append(document)

            logger.info(f"Ingested {len(documents)} rows from {table_name}")
            return documents

        except Exception as e:
            logger.error(f"Error ingesting table {table_name}: {e}")
            raise

    def ingest_custom_query(
        self,
        query: str,
        query_name: str,
        params: Optional[Dict] = None,
        batch_size: int = 1000
    ) -> Generator[List[Dict], None, None]:
        """
        Ingest data using custom SQL query with streaming.

        Args:
            query: Custom SQL query
            query_name: Descriptive name for lineage tracking
            params: Query parameters
            batch_size: Batch size for streaming

        Yields:
            Batches of documents with metadata
        """
        for batch in self.stream_query_results(query, batch_size, params):
            documents = []

            for row in batch:
                document = {
                    'content': row,
                    'metadata': {
                        'source_type': 'database',
                        'query_name': query_name,
                        'source_uri': f"db://query/{query_name}",
                        'ingestion_timestamp': datetime.utcnow().isoformat(),
                        'query': query[:200]  # Store truncated query for lineage
                    }
                }
                documents.append(document)

            yield documents

    def ingest_shipment_logs(
        self,
        start_date: str,
        end_date: Optional[str] = None,
        region: Optional[str] = None
    ) -> List[Dict]:
        """
        Specialized method to ingest shipment logs.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD), defaults to today
            region: Filter by region

        Returns:
            List of shipment documents
        """
        query = """
        SELECT
            shipment_id,
            vendor_id,
            origin,
            destination,
            status,
            departure_date,
            arrival_date,
            delay_hours,
            cargo_type,
            weight_kg,
            region
        FROM shipment_logs
        WHERE departure_date >= :start_date
        """

        params = {'start_date': start_date}

        if end_date:
            query += " AND departure_date <= :end_date"
            params['end_date'] = end_date

        if region:
            query += " AND region = :region"
            params['region'] = region

        query += " ORDER BY departure_date DESC"

        rows = self.execute_query(query, params)

        documents = []
        for row in rows:
            document = {
                'content': row,
                'metadata': {
                    'source_type': 'database',
                    'table_name': 'shipment_logs',
                    'document_type': 'shipment_log',
                    'shipment_id': row['shipment_id'],
                    'region': row.get('region'),
                    'status': row.get('status'),
                    'source_uri': f"db://shipment_logs/{row['shipment_id']}",
                    'ingestion_timestamp': datetime.utcnow().isoformat()
                }
            }
            documents.append(document)

        logger.info(f"Ingested {len(documents)} shipment logs")
        return documents

    def close(self):
        """Close database connection pool."""
        self.engine.dispose()
        logger.info("Database connection pool disposed")


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    # PostgreSQL example
    connector = DatabaseConnector(
        "postgresql://user:pass@localhost:5432/logistics"
    )

    # Ingest recent shipments
    shipments = connector.ingest_shipment_logs(
        start_date="2024-01-01",
        region="APAC"
    )
    print(f"Ingested {len(shipments)} shipments")

    # Stream large table
    for batch in connector.ingest_custom_query(
        query="SELECT * FROM vendor_contracts WHERE status = :status",
        query_name="active_contracts",
        params={'status': 'active'},
        batch_size=500
    ):
        print(f"Processing batch of {len(batch)} contracts")

    connector.close()

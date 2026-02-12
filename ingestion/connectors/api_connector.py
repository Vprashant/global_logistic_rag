"""
API Connector for ingesting real-time data from external APIs.
Supports port congestion data, weather forecasts, and other logistics APIs.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import json

logger = logging.getLogger(__name__)


class APIConnector:
    """Connector for external REST APIs."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 0.3
    ):
        """
        Initialize API connector.

        Args:
            base_url: Base URL for the API
            api_key: API authentication key
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts
            backoff_factor: Backoff multiplier for retries
        """
        self.base_url = base_url.rstrip('/') if base_url else None
        self.api_key = api_key
        self.timeout = timeout

        # Create session with retry strategy
        self.session = requests.Session()

        retry_strategy = Retry(
            total=max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "OPTIONS", "POST"],
            backoff_factor=backoff_factor
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers
        self.session.headers.update({
            'User-Agent': 'GlobalLogisticsRAG/1.0',
            'Accept': 'application/json'
        })

        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}'
            })

        logger.info(f"API connector initialized: {base_url}")

    def get(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict:
        """
        Make GET request to API.

        Args:
            endpoint: API endpoint path
            params: Query parameters
            headers: Additional headers

        Returns:
            Response data as dictionary
        """
        url = f"{self.base_url}{endpoint}" if self.base_url else endpoint

        try:
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()

            logger.debug(f"GET {url} - Status: {response.status_code}")
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {url}: {e}")
            raise

    def post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict:
        """
        Make POST request to API.

        Args:
            endpoint: API endpoint path
            data: Form data
            json_data: JSON data
            headers: Additional headers

        Returns:
            Response data as dictionary
        """
        url = f"{self.base_url}{endpoint}" if self.base_url else endpoint

        try:
            response = self.session.post(
                url,
                data=data,
                json=json_data,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()

            logger.debug(f"POST {url} - Status: {response.status_code}")
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {url}: {e}")
            raise

    def ingest_port_congestion(
        self,
        port_codes: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Ingest real-time port congestion data.

        Args:
            port_codes: List of port codes (e.g., ['SGSIN', 'USNYC'])

        Returns:
            List of port congestion documents
        """
        # This is a mock implementation - replace with actual API
        endpoint = "/api/v1/ports/congestion"

        params = {}
        if port_codes:
            params['ports'] = ','.join(port_codes)

        try:
            data = self.get(endpoint, params=params)

            documents = []
            for port_data in data.get('ports', []):
                document = {
                    'content': port_data,
                    'metadata': {
                        'source_type': 'api',
                        'api_name': 'port_congestion',
                        'document_type': 'port_congestion',
                        'port_code': port_data.get('port_code'),
                        'country': port_data.get('country'),
                        'source_uri': f"api://port_congestion/{port_data.get('port_code')}",
                        'ingestion_timestamp': datetime.utcnow().isoformat(),
                        'data_timestamp': port_data.get('timestamp')
                    }
                }
                documents.append(document)

            logger.info(f"Ingested {len(documents)} port congestion records")
            return documents

        except Exception as e:
            logger.error(f"Error ingesting port congestion: {e}")
            return []

    def ingest_weather_forecast(
        self,
        locations: List[Dict[str, float]]
    ) -> List[Dict]:
        """
        Ingest weather forecast data for shipping routes.

        Args:
            locations: List of locations with lat/lon
                Example: [{"lat": 1.290, "lon": 103.851, "name": "Singapore"}]

        Returns:
            List of weather forecast documents
        """
        # Mock implementation - replace with actual weather API
        documents = []

        for location in locations:
            endpoint = "/api/v1/weather/forecast"
            params = {
                'lat': location['lat'],
                'lon': location['lon'],
                'days': 7
            }

            try:
                data = self.get(endpoint, params=params)

                document = {
                    'content': data,
                    'metadata': {
                        'source_type': 'api',
                        'api_name': 'weather_forecast',
                        'document_type': 'weather_forecast',
                        'location': location.get('name'),
                        'latitude': location['lat'],
                        'longitude': location['lon'],
                        'source_uri': f"api://weather/{location.get('name')}",
                        'ingestion_timestamp': datetime.utcnow().isoformat()
                    }
                }
                documents.append(document)

            except Exception as e:
                logger.error(f"Error ingesting weather for {location.get('name')}: {e}")
                continue

        logger.info(f"Ingested {len(documents)} weather forecasts")
        return documents

    def ingest_shipping_rates(
        self,
        routes: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """
        Ingest current shipping rates for various routes.

        Args:
            routes: List of route dictionaries
                Example: [{"origin": "SGSIN", "destination": "USNYC"}]

        Returns:
            List of shipping rate documents
        """
        endpoint = "/api/v1/shipping/rates"

        documents = []

        if not routes:
            # Get all routes
            try:
                data = self.get(endpoint)
                routes_data = data.get('routes', [])
            except Exception as e:
                logger.error(f"Error fetching shipping rates: {e}")
                return []
        else:
            routes_data = []
            for route in routes:
                try:
                    params = {
                        'origin': route['origin'],
                        'destination': route['destination']
                    }
                    data = self.get(endpoint, params=params)
                    routes_data.extend(data.get('routes', []))
                except Exception as e:
                    logger.error(f"Error fetching rate for {route}: {e}")
                    continue

        for rate_data in routes_data:
            document = {
                'content': rate_data,
                'metadata': {
                    'source_type': 'api',
                    'api_name': 'shipping_rates',
                    'document_type': 'shipping_rate',
                    'origin': rate_data.get('origin'),
                    'destination': rate_data.get('destination'),
                    'carrier': rate_data.get('carrier'),
                    'source_uri': f"api://shipping_rates/{rate_data.get('origin')}/{rate_data.get('destination')}",
                    'ingestion_timestamp': datetime.utcnow().isoformat(),
                    'rate_timestamp': rate_data.get('timestamp')
                }
            }
            documents.append(document)

        logger.info(f"Ingested {len(documents)} shipping rates")
        return documents

    def ingest_custom_api(
        self,
        endpoint: str,
        api_name: str,
        document_type: str,
        params: Optional[Dict] = None,
        method: str = "GET",
        data_path: Optional[str] = None,
        id_field: Optional[str] = None
    ) -> List[Dict]:
        """
        Generic method to ingest from any REST API.

        Args:
            endpoint: API endpoint
            api_name: Name for tracking (e.g., 'customs_api')
            document_type: Document type (e.g., 'customs_declaration')
            params: Query parameters
            method: HTTP method (GET or POST)
            data_path: Path to data in response (e.g., 'data.results')
            id_field: Field name for document ID

        Returns:
            List of documents
        """
        try:
            if method.upper() == "GET":
                response = self.get(endpoint, params=params)
            elif method.upper() == "POST":
                response = self.post(endpoint, json_data=params)
            else:
                raise ValueError(f"Unsupported method: {method}")

            # Navigate to data using path
            data = response
            if data_path:
                for key in data_path.split('.'):
                    data = data.get(key, {})

            # Handle both list and single object
            if not isinstance(data, list):
                data = [data]

            documents = []
            for item in data:
                doc_id = item.get(id_field) if id_field else None

                document = {
                    'content': item,
                    'metadata': {
                        'source_type': 'api',
                        'api_name': api_name,
                        'document_type': document_type,
                        'document_id': doc_id,
                        'source_uri': f"api://{api_name}/{doc_id or 'unknown'}",
                        'ingestion_timestamp': datetime.utcnow().isoformat()
                    }
                }
                documents.append(document)

            logger.info(f"Ingested {len(documents)} documents from {api_name}")
            return documents

        except Exception as e:
            logger.error(f"Error ingesting from {api_name}: {e}")
            return []

    def poll_endpoint(
        self,
        endpoint: str,
        interval: int = 60,
        max_polls: Optional[int] = None
    ):
        """
        Poll an API endpoint at regular intervals.

        Args:
            endpoint: API endpoint to poll
            interval: Polling interval in seconds
            max_polls: Maximum number of polls (None for infinite)

        Yields:
            API response data
        """
        poll_count = 0

        while True:
            try:
                data = self.get(endpoint)
                yield {
                    'content': data,
                    'metadata': {
                        'source_type': 'api',
                        'poll_count': poll_count,
                        'ingestion_timestamp': datetime.utcnow().isoformat()
                    }
                }

                poll_count += 1
                if max_polls and poll_count >= max_polls:
                    logger.info(f"Reached max polls: {max_polls}")
                    break

                time.sleep(interval)

            except Exception as e:
                logger.error(f"Error polling {endpoint}: {e}")
                time.sleep(interval)

    def close(self):
        """Close HTTP session."""
        self.session.close()
        logger.info("API connector session closed")


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    connector = APIConnector(
        base_url="https://api.logistics-hub.com",
        api_key="your-api-key"
    )

    # Ingest port congestion
    ports = connector.ingest_port_congestion(
        port_codes=['SGSIN', 'USNYC', 'NLRTM', 'CNSHA']
    )
    print(f"Ingested {len(ports)} port congestion records")

    # Ingest weather forecasts
    locations = [
        {"lat": 1.290, "lon": 103.851, "name": "Singapore"},
        {"lat": 40.713, "lon": -74.006, "name": "New York"}
    ]
    weather = connector.ingest_weather_forecast(locations)
    print(f"Ingested {len(weather)} weather forecasts")

    connector.close()

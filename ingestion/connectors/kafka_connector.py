"""
Kafka Connector for ingesting real-time IoT sensor data streams.
Supports Apache Kafka and Flink for streaming data ingestion.
"""

import json
import logging
from typing import Dict, List, Optional, Callable, Generator
from datetime import datetime
from confluent_kafka import Consumer, Producer, KafkaError, KafkaException
from confluent_kafka.admin import AdminClient
import threading
import queue

logger = logging.getLogger(__name__)


class KafkaConnector:
    """Connector for Apache Kafka streaming data."""

    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str = "logistics-rag-consumer",
        auto_offset_reset: str = "latest",
        enable_auto_commit: bool = True,
        **kafka_config
    ):
        """
        Initialize Kafka connector.

        Args:
            bootstrap_servers: Comma-separated Kafka broker addresses
            group_id: Consumer group ID
            auto_offset_reset: Where to start reading ('earliest' or 'latest')
            enable_auto_commit: Auto-commit offsets
            **kafka_config: Additional Kafka configuration
        """
        self.bootstrap_servers = bootstrap_servers

        # Consumer configuration
        self.consumer_config = {
            'bootstrap.servers': bootstrap_servers,
            'group.id': group_id,
            'auto.offset.reset': auto_offset_reset,
            'enable.auto.commit': enable_auto_commit,
            **kafka_config
        }

        # Producer configuration
        self.producer_config = {
            'bootstrap.servers': bootstrap_servers,
            **kafka_config
        }

        self.consumer: Optional[Consumer] = None
        self.producer: Optional[Producer] = None
        self.is_consuming = False

        logger.info(f"Kafka connector initialized: {bootstrap_servers}")

    def create_consumer(self) -> Consumer:
        """Create and return Kafka consumer."""
        if self.consumer is None:
            self.consumer = Consumer(self.consumer_config)
            logger.info("Kafka consumer created")
        return self.consumer

    def create_producer(self) -> Producer:
        """Create and return Kafka producer."""
        if self.producer is None:
            self.producer = Producer(self.producer_config)
            logger.info("Kafka producer created")
        return self.producer

    def subscribe(self, topics: List[str]):
        """
        Subscribe to Kafka topics.

        Args:
            topics: List of topic names to subscribe to
        """
        consumer = self.create_consumer()
        consumer.subscribe(topics)
        logger.info(f"Subscribed to topics: {topics}")

    def consume_messages(
        self,
        topics: List[str],
        max_messages: Optional[int] = None,
        timeout: float = 1.0
    ) -> Generator[Dict, None, None]:
        """
        Consume messages from Kafka topics.

        Args:
            topics: List of topics to consume from
            max_messages: Maximum number of messages to consume (None for infinite)
            timeout: Poll timeout in seconds

        Yields:
            Message dictionaries with content and metadata
        """
        consumer = self.create_consumer()
        consumer.subscribe(topics)
        self.is_consuming = True

        message_count = 0

        try:
            while self.is_consuming:
                msg = consumer.poll(timeout=timeout)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug(f"Reached end of partition: {msg.topic()}")
                        continue
                    else:
                        raise KafkaException(msg.error())

                # Parse message
                try:
                    value = json.loads(msg.value().decode('utf-8'))
                except json.JSONDecodeError:
                    value = msg.value().decode('utf-8')

                document = {
                    'content': value,
                    'metadata': {
                        'source_type': 'kafka',
                        'topic': msg.topic(),
                        'partition': msg.partition(),
                        'offset': msg.offset(),
                        'timestamp': datetime.fromtimestamp(
                            msg.timestamp()[1] / 1000.0
                        ).isoformat() if msg.timestamp()[1] > 0 else None,
                        'key': msg.key().decode('utf-8') if msg.key() else None,
                        'source_uri': f"kafka://{msg.topic()}/{msg.partition()}/{msg.offset()}",
                        'ingestion_timestamp': datetime.utcnow().isoformat()
                    }
                }

                yield document

                message_count += 1
                if max_messages and message_count >= max_messages:
                    logger.info(f"Reached max messages limit: {max_messages}")
                    break

        except KeyboardInterrupt:
            logger.info("Consumer interrupted by user")
        finally:
            consumer.close()
            logger.info(f"Consumer closed after {message_count} messages")

    def consume_batch(
        self,
        topics: List[str],
        batch_size: int = 100,
        timeout: float = 1.0,
        max_batches: Optional[int] = None
    ) -> Generator[List[Dict], None, None]:
        """
        Consume messages in batches for efficient processing.

        Args:
            topics: List of topics to consume from
            batch_size: Number of messages per batch
            timeout: Poll timeout in seconds
            max_batches: Maximum number of batches to consume

        Yields:
            Batches of message dictionaries
        """
        consumer = self.create_consumer()
        consumer.subscribe(topics)
        self.is_consuming = True

        batch_count = 0
        batch = []

        try:
            while self.is_consuming:
                msg = consumer.poll(timeout=timeout)

                if msg is None:
                    if batch:
                        yield batch
                        batch = []
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        raise KafkaException(msg.error())

                # Parse message
                try:
                    value = json.loads(msg.value().decode('utf-8'))
                except json.JSONDecodeError:
                    value = msg.value().decode('utf-8')

                document = {
                    'content': value,
                    'metadata': {
                        'source_type': 'kafka',
                        'topic': msg.topic(),
                        'partition': msg.partition(),
                        'offset': msg.offset(),
                        'timestamp': datetime.fromtimestamp(
                            msg.timestamp()[1] / 1000.0
                        ).isoformat() if msg.timestamp()[1] > 0 else None,
                        'key': msg.key().decode('utf-8') if msg.key() else None,
                        'source_uri': f"kafka://{msg.topic()}/{msg.partition()}/{msg.offset()}",
                        'ingestion_timestamp': datetime.utcnow().isoformat()
                    }
                }

                batch.append(document)

                if len(batch) >= batch_size:
                    logger.debug(f"Yielding batch of {len(batch)} messages")
                    yield batch
                    batch = []
                    batch_count += 1

                    if max_batches and batch_count >= max_batches:
                        logger.info(f"Reached max batches limit: {max_batches}")
                        break

        except KeyboardInterrupt:
            logger.info("Batch consumer interrupted by user")
        finally:
            if batch:
                yield batch
            consumer.close()
            logger.info(f"Batch consumer closed after {batch_count} batches")

    def ingest_iot_stream(
        self,
        topic: str = "iot-sensors",
        batch_size: int = 50,
        sensor_types: Optional[List[str]] = None
    ) -> Generator[List[Dict], None, None]:
        """
        Specialized method to ingest IoT sensor data.

        Args:
            topic: Kafka topic for IoT data
            batch_size: Messages per batch
            sensor_types: Filter by sensor types (e.g., ['temperature', 'gps'])

        Yields:
            Batches of IoT sensor documents
        """
        for batch in self.consume_batch([topic], batch_size=batch_size):
            filtered_batch = []

            for doc in batch:
                content = doc['content']

                # Filter by sensor type if specified
                if sensor_types:
                    sensor_type = content.get('sensor_type')
                    if sensor_type not in sensor_types:
                        continue

                # Enrich metadata
                doc['metadata'].update({
                    'document_type': 'iot_sensor_data',
                    'sensor_id': content.get('sensor_id'),
                    'sensor_type': content.get('sensor_type'),
                    'location': content.get('location')
                })

                filtered_batch.append(doc)

            if filtered_batch:
                logger.info(f"Yielding IoT batch: {len(filtered_batch)} sensors")
                yield filtered_batch

    def produce_message(
        self,
        topic: str,
        value: Dict,
        key: Optional[str] = None
    ):
        """
        Produce a message to Kafka topic.

        Args:
            topic: Topic name
            value: Message value (dict will be JSON-serialized)
            key: Optional message key
        """
        producer = self.create_producer()

        # Serialize value
        if isinstance(value, dict):
            value_bytes = json.dumps(value).encode('utf-8')
        else:
            value_bytes = str(value).encode('utf-8')

        key_bytes = key.encode('utf-8') if key else None

        producer.produce(
            topic,
            value=value_bytes,
            key=key_bytes,
            callback=self._delivery_callback
        )
        producer.poll(0)

    def _delivery_callback(self, err, msg):
        """Callback for message delivery confirmation."""
        if err:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(
                f"Message delivered to {msg.topic()} [{msg.partition()}] @ {msg.offset()}"
            )

    def flush(self, timeout: float = 10.0):
        """Flush producer queue."""
        if self.producer:
            self.producer.flush(timeout=timeout)
            logger.info("Producer queue flushed")

    def stop_consuming(self):
        """Stop consuming messages."""
        self.is_consuming = False
        logger.info("Consumer stop requested")

    def list_topics(self) -> Dict:
        """
        List available Kafka topics.

        Returns:
            Dictionary of topic metadata
        """
        admin_client = AdminClient({'bootstrap.servers': self.bootstrap_servers})
        metadata = admin_client.list_topics(timeout=10)

        topics = {}
        for topic_name, topic_metadata in metadata.topics.items():
            topics[topic_name] = {
                'partitions': len(topic_metadata.partitions),
                'error': topic_metadata.error
            }

        return topics

    def close(self):
        """Close Kafka connections."""
        if self.consumer:
            self.consumer.close()
            self.consumer = None
        if self.producer:
            self.producer.flush()
            self.producer = None
        logger.info("Kafka connector closed")


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    connector = KafkaConnector(
        bootstrap_servers="localhost:9092",
        group_id="logistics-rag-dev"
    )

    # List available topics
    topics = connector.list_topics()
    print(f"Available topics: {list(topics.keys())}")

    # Consume IoT sensor data in batches
    try:
        for batch in connector.ingest_iot_stream(
            topic="iot-sensors",
            batch_size=10,
            sensor_types=['temperature', 'gps', 'humidity']
        ):
            print(f"Processing batch of {len(batch)} IoT messages")
            for doc in batch:
                sensor_data = doc['content']
                print(f"  Sensor: {sensor_data.get('sensor_id')} - {sensor_data.get('value')}")

    except KeyboardInterrupt:
        print("Stopping consumer...")
    finally:
        connector.close()

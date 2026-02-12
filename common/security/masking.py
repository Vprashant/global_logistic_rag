"""
PII/PHI Masking module using Microsoft Presidio.
Masks sensitive data before storing in vector database.
"""

import logging
from typing import Dict, List, Optional, Set
import re

logger = logging.getLogger(__name__)


class PIIMasker:
    """PII/PHI masking using Presidio and custom rules."""

    def __init__(
        self,
        entities_to_mask: Optional[List[str]] = None,
        mask_char: str = "*",
        use_presidio: bool = True
    ):
        """
        Initialize PII masker.

        Args:
            entities_to_mask: List of entity types to mask
            mask_char: Character to use for masking
            use_presidio: Whether to use Presidio (requires installation)
        """
        self.mask_char = mask_char
        self.use_presidio = use_presidio

        if entities_to_mask is None:
            self.entities_to_mask = [
                'PERSON', 'PHONE_NUMBER', 'EMAIL_ADDRESS',
                'CREDIT_CARD', 'IBAN_CODE', 'US_SSN',
                'US_DRIVER_LICENSE', 'US_PASSPORT'
            ]
        else:
            self.entities_to_mask = entities_to_mask

        # Initialize Presidio if available
        if use_presidio:
            try:
                from presidio_analyzer import AnalyzerEngine
                from presidio_anonymizer import AnonymizerEngine

                self.analyzer = AnalyzerEngine()
                self.anonymizer = AnonymizerEngine()
                logger.info("Presidio initialized for PII masking")

            except ImportError:
                logger.warning("Presidio not installed, using regex-based masking only")
                self.use_presidio = False
                self.analyzer = None
                self.anonymizer = None
        else:
            self.analyzer = None
            self.anonymizer = None

        # Compile regex patterns for common PII
        self.regex_patterns = self._compile_regex_patterns()

        logger.info(f"PII masker initialized: entities={len(self.entities_to_mask)}")

    def mask_text(self, text: str) -> Dict[str, any]:
        """
        Mask PII in text.

        Args:
            text: Text to mask

        Returns:
            Dictionary with masked_text and entities_found
        """
        if self.use_presidio and self.analyzer and self.anonymizer:
            return self._mask_with_presidio(text)
        else:
            return self._mask_with_regex(text)

    def _mask_with_presidio(self, text: str) -> Dict:
        """Mask text using Presidio."""
        try:
            # Analyze text for PII
            results = self.analyzer.analyze(
                text=text,
                entities=self.entities_to_mask,
                language='en'
            )

            # Anonymize detected entities
            anonymized = self.anonymizer.anonymize(
                text=text,
                analyzer_results=results
            )

            masked_text = anonymized.text

            # Extract entity information
            entities_found = [
                {
                    'type': result.entity_type,
                    'start': result.start,
                    'end': result.end,
                    'score': result.score
                }
                for result in results
            ]

            logger.debug(f"Presidio found {len(entities_found)} PII entities")

            return {
                'masked_text': masked_text,
                'entities_found': entities_found,
                'masking_method': 'presidio'
            }

        except Exception as e:
            logger.error(f"Presidio masking error: {e}")
            return self._mask_with_regex(text)

    def _mask_with_regex(self, text: str) -> Dict:
        """Mask text using regex patterns."""
        masked_text = text
        entities_found = []

        for entity_type, pattern in self.regex_patterns.items():
            matches = list(pattern.finditer(masked_text))

            for match in matches:
                # Replace with masked version
                original = match.group(0)
                masked = self.mask_char * len(original)

                # Keep format for some types
                if entity_type == 'EMAIL_ADDRESS':
                    parts = original.split('@')
                    if len(parts) == 2:
                        masked = self.mask_char * len(parts[0]) + '@' + parts[1]

                elif entity_type == 'PHONE_NUMBER':
                    # Keep last 4 digits
                    digits = re.sub(r'\D', '', original)
                    if len(digits) > 4:
                        masked = self.mask_char * (len(digits) - 4) + digits[-4:]
                    else:
                        masked = self.mask_char * len(digits)

                masked_text = masked_text.replace(original, masked, 1)

                entities_found.append({
                    'type': entity_type,
                    'start': match.start(),
                    'end': match.end(),
                    'original_length': len(original)
                })

        logger.debug(f"Regex found {len(entities_found)} PII entities")

        return {
            'masked_text': masked_text,
            'entities_found': entities_found,
            'masking_method': 'regex'
        }

    def _compile_regex_patterns(self) -> Dict[str, re.Pattern]:
        """Compile regex patterns for common PII types."""
        patterns = {
            'EMAIL_ADDRESS': re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            ),
            'PHONE_NUMBER': re.compile(
                r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b'
            ),
            'CREDIT_CARD': re.compile(
                r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11})\b'
            ),
            'US_SSN': re.compile(
                r'\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b'
            ),
            'IBAN_CODE': re.compile(
                r'\b[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}\b'
            )
        }

        return patterns

    def mask_document(self, document: Dict) -> Dict:
        """
        Mask PII in a document structure.

        Args:
            document: Document dictionary with 'content' and 'metadata'

        Returns:
            Masked document with PII tracking
        """
        content = document.get('content', '')

        # Convert content to string if it's a dict
        if isinstance(content, dict):
            content = str(content)

        # Mask the content
        masking_result = self.mask_text(content)

        # Update document
        masked_doc = document.copy()
        masked_doc['content'] = masking_result['masked_text']

        # Add masking metadata
        if 'metadata' not in masked_doc:
            masked_doc['metadata'] = {}

        masked_doc['metadata']['pii_masked'] = True
        masked_doc['metadata']['pii_entities_count'] = len(masking_result['entities_found'])
        masked_doc['metadata']['masking_method'] = masking_result['masking_method']

        # Store entity info (without actual values for security)
        masked_doc['metadata']['pii_entities'] = [
            {
                'type': entity['type'],
                'score': entity.get('score', 1.0)
            }
            for entity in masking_result['entities_found']
        ]

        logger.info(f"Masked document: found {len(masking_result['entities_found'])} PII entities")

        return masked_doc

    def mask_field(self, value: str, field_type: str) -> str:
        """
        Mask a specific field type.

        Args:
            value: Field value
            field_type: Type of field (email, phone, ssn, etc.)

        Returns:
            Masked value
        """
        if field_type.lower() == 'email':
            return self._mask_email(value)
        elif field_type.lower() == 'phone':
            return self._mask_phone(value)
        elif field_type.lower() in ['ssn', 'social_security']:
            return self._mask_ssn(value)
        elif field_type.lower() == 'credit_card':
            return self._mask_credit_card(value)
        elif field_type.lower() == 'bank_account':
            return self._mask_bank_account(value)
        else:
            # Generic masking
            return self.mask_char * len(value)

    def _mask_email(self, email: str) -> str:
        """Mask email address, keeping domain."""
        if '@' in email:
            local, domain = email.split('@', 1)
            return self.mask_char * len(local) + '@' + domain
        return self.mask_char * len(email)

    def _mask_phone(self, phone: str) -> str:
        """Mask phone number, keeping last 4 digits."""
        digits = re.sub(r'\D', '', phone)
        if len(digits) > 4:
            return self.mask_char * (len(digits) - 4) + digits[-4:]
        return self.mask_char * len(digits)

    def _mask_ssn(self, ssn: str) -> str:
        """Mask SSN, showing only last 4 digits."""
        digits = re.sub(r'\D', '', ssn)
        if len(digits) == 9:
            return f"{self.mask_char * 3}-{self.mask_char * 2}-{digits[-4:]}"
        return self.mask_char * len(ssn)

    def _mask_credit_card(self, card: str) -> str:
        """Mask credit card, showing only last 4 digits."""
        digits = re.sub(r'\D', '', card)
        if len(digits) >= 13:
            return self.mask_char * (len(digits) - 4) + digits[-4:]
        return self.mask_char * len(digits)

    def _mask_bank_account(self, account: str) -> str:
        """Mask bank account number."""
        return self.mask_char * len(account)


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    masker = PIIMasker()

    # Test text with PII
    text = """
    Contact John Doe at john.doe@example.com or call 555-123-4567.
    His SSN is 123-45-6789 and credit card is 4532-1234-5678-9010.
    Bank account: DE89370400440532013000
    """

    result = masker.mask_text(text)

    print("Original text:")
    print(text)
    print("\nMasked text:")
    print(result['masked_text'])
    print(f"\nEntities found: {len(result['entities_found'])}")
    for entity in result['entities_found']:
        print(f"  - {entity['type']}")

    # Test document masking
    document = {
        'content': "Contact vendor at vendor@company.com, phone: 555-987-6543",
        'metadata': {
            'source': 'contract'
        }
    }

    masked_doc = masker.mask_document(document)
    print("\nMasked document content:")
    print(masked_doc['content'])

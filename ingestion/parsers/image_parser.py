"""
Image Parser for extracting information from images using Vision-Language Models.
Handles warehouse photos, damaged cargo images, and IoT sensor displays.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
import io
import base64
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


class ImageParser:
    """Parser for images using Vision-Language Models (VLMs)."""

    def __init__(
        self,
        vlm_provider: str = "openai",  # Options: 'openai', 'anthropic', 'local'
        api_key: Optional[str] = None,
        model: str = "gpt-4-vision-preview"
    ):
        """
        Initialize image parser with VLM.

        Args:
            vlm_provider: Vision-Language Model provider
            api_key: API key for the provider
            model: Specific model to use
        """
        self.vlm_provider = vlm_provider
        self.api_key = api_key
        self.model = model

        if vlm_provider == "openai":
            try:
                import openai
                self.client = openai.OpenAI(api_key=api_key)
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")

        elif vlm_provider == "anthropic":
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")

        logger.info(f"Image parser initialized with {vlm_provider}")

    def parse(
        self,
        content: bytes,
        filename: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> Dict:
        """
        Parse image and extract information using VLM.

        Args:
            content: Image file content as bytes
            filename: Original filename
            prompt: Custom prompt for VLM (uses default if None)

        Returns:
            Parsed image with description and metadata
        """
        # Load image for metadata
        image = Image.open(io.BytesIO(content))

        metadata = {
            'format': image.format,
            'mode': image.mode,
            'size': image.size,
            'width': image.width,
            'height': image.height,
            'filename': filename,
            'file_size': len(content)
        }

        # Generate description using VLM
        if prompt is None:
            prompt = self._get_default_prompt()

        description = self._generate_description(content, prompt)

        # Extract EXIF data if available
        exif_data = self._extract_exif(image)
        if exif_data:
            metadata['exif'] = exif_data

        logger.info(f"Parsed image: {filename} ({image.width}x{image.height})")

        return {
            'description': description,
            'metadata': metadata,
            'image_data': {
                'base64': base64.b64encode(content).decode('utf-8'),
                'mime_type': f"image/{image.format.lower()}"
            }
        }

    def _generate_description(
        self,
        image_content: bytes,
        prompt: str
    ) -> str:
        """
        Generate image description using VLM.

        Args:
            image_content: Image bytes
            prompt: Prompt for VLM

        Returns:
            Generated description
        """
        if self.vlm_provider == "openai":
            return self._generate_openai(image_content, prompt)
        elif self.vlm_provider == "anthropic":
            return self._generate_anthropic(image_content, prompt)
        else:
            return "VLM description not available"

    def _generate_openai(
        self,
        image_content: bytes,
        prompt: str
    ) -> str:
        """Generate description using OpenAI GPT-4 Vision."""
        try:
            # Encode image to base64
            base64_image = base64.b64encode(image_content).decode('utf-8')

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )

            description = response.choices[0].message.content
            logger.debug(f"Generated OpenAI description: {len(description)} chars")
            return description

        except Exception as e:
            logger.error(f"Error generating OpenAI description: {e}")
            return f"Error: {str(e)}"

    def _generate_anthropic(
        self,
        image_content: bytes,
        prompt: str
    ) -> str:
        """Generate description using Anthropic Claude Vision."""
        try:
            # Encode image to base64
            base64_image = base64.b64encode(image_content).decode('utf-8')

            # Detect image format
            image = Image.open(io.BytesIO(image_content))
            media_type = f"image/{image.format.lower()}"

            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": base64_image
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )

            description = response.content[0].text
            logger.debug(f"Generated Anthropic description: {len(description)} chars")
            return description

        except Exception as e:
            logger.error(f"Error generating Anthropic description: {e}")
            return f"Error: {str(e)}"

    def _get_default_prompt(self) -> str:
        """Get default prompt for logistics images."""
        return """
        Analyze this logistics/warehouse image and provide a detailed description including:
        1. What type of cargo or goods are visible
        2. Condition of the cargo (damaged, intact, etc.)
        3. Any visible labels, barcodes, or identification numbers
        4. Environmental conditions (weather, lighting, etc.)
        5. Any safety hazards or notable features
        6. Location indicators (warehouse, port, truck, etc.)

        Be specific and factual in your description.
        """

    def _extract_exif(self, image: Image.Image) -> Optional[Dict]:
        """
        Extract EXIF metadata from image.

        Args:
            image: PIL Image object

        Returns:
            EXIF data dictionary or None
        """
        try:
            from PIL.ExifTags import TAGS

            exif_data = {}
            exif = image._getexif()

            if exif:
                for tag_id, value in exif.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    exif_data[tag_name] = str(value)

                return exif_data

        except Exception as e:
            logger.debug(f"No EXIF data or error extracting: {e}")

        return None

    def parse_cargo_image(
        self,
        content: bytes,
        filename: Optional[str] = None
    ) -> Dict:
        """
        Specialized parser for cargo/warehouse images.

        Args:
            content: Image file content
            filename: Original filename

        Returns:
            Parsed image with cargo-specific analysis
        """
        prompt = """
        This is a cargo or warehouse image. Analyze and extract:
        1. Type of cargo/goods
        2. Quantity (approximate count or volume)
        3. Condition assessment (damaged/intact/weathered)
        4. Packaging type (boxes, pallets, containers, etc.)
        5. Any visible tracking numbers or labels
        6. Storage location indicators
        7. Safety concerns or hazards

        Provide a structured analysis.
        """

        result = self.parse(content, filename, prompt)

        # Add cargo-specific metadata
        result['metadata']['document_type'] = 'cargo_image'
        result['metadata']['parsed_at'] = datetime.utcnow().isoformat()

        return result

    def parse_damage_report_image(
        self,
        content: bytes,
        filename: Optional[str] = None
    ) -> Dict:
        """
        Specialized parser for damage report images.

        Args:
            content: Image file content
            filename: Original filename

        Returns:
            Parsed image with damage assessment
        """
        prompt = """
        This is a damage report image. Analyze and identify:
        1. Type and extent of damage visible
        2. Affected items or cargo
        3. Probable cause of damage (if determinable)
        4. Severity assessment (minor/moderate/severe)
        5. Any visible identifying marks or numbers
        6. Timestamp or date information if visible

        Be detailed and objective in your assessment.
        """

        result = self.parse(content, filename, prompt)

        # Add damage report metadata
        result['metadata']['document_type'] = 'damage_report_image'
        result['metadata']['parsed_at'] = datetime.utcnow().isoformat()

        return result

    def generate_clip_embedding(
        self,
        content: bytes
    ) -> np.ndarray:
        """
        Generate CLIP embedding for cross-modal retrieval.

        Args:
            content: Image file content

        Returns:
            CLIP embedding vector
        """
        try:
            from transformers import CLIPProcessor, CLIPModel
            import torch

            # Load CLIP model (cache it for efficiency)
            if not hasattr(self, 'clip_model'):
                self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
                self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

            # Load image
            image = Image.open(io.BytesIO(content))

            # Generate embedding
            inputs = self.clip_processor(images=image, return_tensors="pt")

            with torch.no_grad():
                image_features = self.clip_model.get_image_features(**inputs)

            embedding = image_features.cpu().numpy()[0]
            logger.debug(f"Generated CLIP embedding: shape {embedding.shape}")

            return embedding

        except ImportError:
            logger.error("transformers not installed. Run: pip install transformers torch")
            return np.array([])
        except Exception as e:
            logger.error(f"Error generating CLIP embedding: {e}")
            return np.array([])


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    parser = ImageParser(
        vlm_provider="openai",
        api_key="your-openai-api-key"
    )

    # Parse cargo image
    with open("warehouse_cargo.jpg", "rb") as f:
        content = f.read()

    result = parser.parse_cargo_image(content, filename="warehouse_cargo.jpg")

    print(f"Description: {result['description']}")
    print(f"Image size: {result['metadata']['width']}x{result['metadata']['height']}")

    # Generate CLIP embedding for multimodal search
    embedding = parser.generate_clip_embedding(content)
    print(f"CLIP embedding shape: {embedding.shape}")

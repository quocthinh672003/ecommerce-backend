import base64
from email.mime import image
import os
import sys
from io import BytesIO
from pathlib import Path

from openai import AzureOpenAI
from PIL import Image


# Fastest test option: put an image inside ./test-images, then run:
# python a.py
TEST_IMAGES_DIR = Path("test-images")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
DEFAULT_AZURE_DEPLOYMENT = "gpt-4o-mini"

# Or put the image path here, for example:
# IMAGE_PATH = r"C:\Users\Admin\Pictures\product.jpg"
IMAGE_PATH = r""

# Or keep IMAGE_PATH empty and run:
# python a.py "C:\path\to\your-image.jpg"

PROMPT = """
Describe this image in detail. Cover all relevant aspects such as subjects,
composition, background, setting, lighting, colors, any visible text (transcribe exactly),
and overall mood or atmosphere. Be specific and observational.
""".strip()


"""
Please provide a detailed, comprehensive description of this image. 
Cover all key aspects including: subjects and their appearance,
spatial composition and layout, background and setting, lighting and color palette,
any visible text, and the overall mood or atmosphere. Be specific and observational.

Make the Summary specific and rich in visible details: describe the main subject,
appearance, colors, clothing or accessories if present, objects, text, logo,
background, setting, lighting, camera angle, composition, image quality, and
any distinctive visual details. Write 8-12 clear sentences in one paragraph.
Only describe what can be seen in the image; if a detail is unclear, say it is unclear.
"""


def load_dotenv(path: str = ".env") -> None:
    """Load simple KEY=VALUE lines from a .env file without extra packages."""
    env_path = Path(path)
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def image_to_data_url(image_path: str) -> str:
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    with Image.open(image_path) as img:
        # JPEG does not support transparency, so place transparent images on white.
        if img.mode in ("RGBA", "LA") or "transparency" in img.info:
            rgba = img.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel("A"))
            rgb_image = background
        else:
            rgb_image = img.convert("RGB")

        buffer = BytesIO()
        rgb_image.save(buffer, format="JPEG", quality=92)
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return f"data:image/jpeg;base64,{encoded}"


def create_azure_client() -> tuple[AzureOpenAI, str]:
    resource_name = os.getenv("AZURE_RESOURCE_NAME", "").strip()
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    if not endpoint and resource_name:
        endpoint = f"https://{resource_name}.openai.azure.com/"

    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    deployment = (
        os.getenv("AZURE_OPENAI_DEPLOYMENT_IMAGE", "").strip()
        or os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip()
        or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "").strip()
        or DEFAULT_AZURE_DEPLOYMENT
    )
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview").strip()

    missing = []
    if not endpoint:
        missing.append("AZURE_OPENAI_ENDPOINT or AZURE_RESOURCE_NAME")
    if not api_key:
        missing.append("AZURE_OPENAI_API_KEY")
    if missing:
        missing_text = ", ".join(missing)
        raise RuntimeError(
            "Missing Azure OpenAI config: "
            f"{missing_text}\n\n"
            "Add these lines to .env, then run again:\n"
            "AZURE_RESOURCE_NAME=<your-resource-name>\n"
            "AZURE_OPENAI_API_KEY=<your-api-key>\n"
            "AZURE_OPENAI_API_VERSION=2024-02-15-preview\n"
            "IMAGE_PATH=C:\\path\\to\\your-image.jpg"
        )

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
    )
    return client, deployment


def describe_image(client: AzureOpenAI, deployment: str, image_path: str) -> str:
    data_url = image_to_data_url(image_path)

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {
                "role": "system",
                "content": (
                    "You provide safe visual descriptions. You must not identify "
                    "people in images or infer sensitive attributes."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url,
                            "detail": "high",
                        },
                    },
                ],
            },
        ],
        max_tokens=2000,
    )

    if not response.choices or not response.choices[0].message.content:
        raise RuntimeError("Empty response from Azure OpenAI")

    return response.choices[0].message.content.strip()


def get_image_path() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1].strip('"')

    configured_path = os.getenv("IMAGE_PATH", "").strip() or IMAGE_PATH.strip()
    if configured_path:
        return configured_path

    if TEST_IMAGES_DIR.exists():
        images = sorted(
            path
            for path in TEST_IMAGES_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        if images:
            return str(images[0])

    return ""


def main() -> int:
    load_dotenv()

    image_path = get_image_path()
    if not image_path:
        print(
            "Missing image path.\n\n"
            "Use one of these options:\n"
            "1. Put an image in the test-images folder, then run: python a.py\n"
            '2. Edit IMAGE_PATH near the top of a.py, for example IMAGE_PATH = r"C:\\path\\image.jpg"\n'
            '3. Add IMAGE_PATH=C:\\path\\image.jpg to .env\n'
            '4. Run: python a.py "C:\\path\\image.jpg"'
        )
        return 1

    if not Path(image_path).exists():
        print(f"Image not found: {image_path}")
        return 1

    try:
        client, deployment = create_azure_client()
        print(f"Using image: {image_path}")
        print(f"Using Azure OpenAI deployment/model: {deployment}")
        description = describe_image(client, deployment, image_path)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    print("\n=== AI IMAGE ANALYSIS ===\n")
    print(description)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

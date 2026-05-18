def describe_image(client, image_path: str) -> str:
    """Use GPT-4o-mini Vision to describe image"""
    try:
        if Image is None:
            return "[Error: Pillow not installed - run: pip install Pillow]"

        with Image.open(image_path) as img:
            rgb_im = img.convert('RGB')
            buf = BytesIO()
            rgb_im.save(buf, format="JPEG", quality=90)
            buf.seek(0)
            base64_image = base64.b64encode(buf.getvalue()).decode('utf-8')

        if not base64_image:
            return "[Error: Failed to encode image to base64]"

        response = client.chat.completions.create(
            model=config.get('openai_model_image', 'gpt-4o-mini'),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please provide a detailed comprehensive description of this image."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "high"
                            }
                        }
                    ],
                }
            ],
            max_tokens=2000,
        )

        if not response.choices or not response.choices[0].message.content:
            return "[Error: Empty response from API]"

        return response.choices[0].message.content

    except Exception as e:
        return f"[Error describing image: {str(e)}]"
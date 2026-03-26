import time
from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
import torch
import os
from PIL import Image
from pathlib import Path
from transformers import LogitsProcessor

class LetterOnlyProcessor(LogitsProcessor):
    def __init__(self, tokenizer, allowed=["A", "B", "C"]):
        self.allowed_ids = [tokenizer.encode(x, add_special_tokens=False)[0] for x in allowed]

    def __call__(self, input_ids, scores):
        mask = torch.full_like(scores, float("-inf"))
        for i in self.allowed_ids:
            mask[:, i] = 0
        return scores + mask
    
class VLM:
    def __init__(self, model_id="Qwen/Qwen3.5-9B", device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # ✅ Initialize processor FIRST
        self.processor = AutoProcessor.from_pretrained(model_id)

        # ✅ Create logits processor separately
        self.letter_processor = LetterOnlyProcessor(self.processor.tokenizer)

        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )

        self.model = AutoModelForImageTextToText.from_pretrained(
            model_id,
            device_map="auto",
            quantization_config=quantization_config,
        )

    def analyze(self, image):
        prompt = """You are tasked with detecting wildfire smoke.

                Determine:
                Is there smoke in the image coming from burning vegetation (trees, forest, grass)?

                Return EXACTLY ONE uppercase letter and nothing else:
                A: yes, Smoke is present and is coming from burning vegetation
                B: no (e.g., there is no smoke, or there is smoke but it's from a non-vegetation source like a chimney or industrial)
                C: it can't be determined whether there is smoke or its source
                """
        messages = [
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": "You are a wildfire smoke detection assistant. You analyze images and determine whether they contain smoke from burning vegetation (trees, forest, grass). You answer with EXACTLY ONE uppercase letter: A, B or C, based on the creiteria provided by the user. You do not provide any explanations or additional text, only the letter."}
                ]
            },
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        inputs = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.model.device)

        with torch.inference_mode():
            outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=1,
                        logits_processor=[self.letter_processor],  # ✅ correct object
                        do_sample=False,
                    )

        answer = self.processor.decode(
            outputs[0][inputs["input_ids"].shape[-1]:],
            skip_special_tokens=True
        )

        return answer.strip()


if __name__ == "__main__":

    vlm = VLM()
    forestfireinsight_folder = r"U:\Fraunhofer Waldbrand\Testbilder\TrainingDataset\forestfire_0326"
    positives = 0
    for image_path in Path(forestfireinsight_folder).iterdir():
        if image_path.is_file() and image_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            image = Image.open(image_path).convert("RGB")
            print(f"Analyzing {image_path.name}...")
            result = vlm.analyze(image)
            if result == "A":
                positives += 1
            print(f"Result: {result}")
    print(f"Total positives: {positives}")
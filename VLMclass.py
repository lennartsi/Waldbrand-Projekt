import time
from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
import torch
import os
from PIL import Image
from pathlib import Path
import json
import re
from pydantic import BaseModel, ValidationError
from typing import Optional

class SmokeAnalysisAnswer(BaseModel):
    """Schema for smoke detection response"""
    reasoning: str
    decision: Optional[bool]

class VLM:
    def __init__(self, model_id="Qwen/Qwen3-VL-8B-Instruct", adapter_path=None, device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = AutoProcessor.from_pretrained(model_id)
        
        # Configure 4-bit quantization with bitsandbytes
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )
        
        self.model = AutoModelForImageTextToText.from_pretrained(
            model_id,
            device_map="auto",
            # quantization_config=quantization_config,
        )
        if adapter_path:
            self.model.load_adapter(adapter_path)
        else:
            adapter_path = r"U:\Fraunhofer Waldbrand\Fine_tuning\Adapters\qwen3-8b-instruct-fine-tune-no-reasoning-V8"
            self.model.load_adapter(adapter_path)
        
        self._sync_lora_to_base_devices()

    def _sync_lora_to_base_devices(self):
        # Ensure LoRA A/B projection weights live on the same device as the wrapped base layer.
        for module in self.model.modules():
            if not hasattr(module, "lora_A") or not hasattr(module, "lora_B"):
                continue

            base_weight = getattr(module, "weight", None)
            if base_weight is None:
                continue

            target_device = base_weight.device
            for adapter_name, lora_a in module.lora_A.items():
                lora_b = module.lora_B[adapter_name] if adapter_name in module.lora_B else None
                if lora_a.weight.device != target_device:
                    lora_a.to(target_device)
                if lora_b is not None and lora_b.weight.device != target_device:
                    lora_b.to(target_device)
                    
    def analyze(self, image):
        # prompt = "Is the smoke in the middle of the image coming from burning vegetation (trees, forest, grass)? Answer ONLY with the letter:\
        #             D: can't be determined with certainty\
        #             B: no (chimney, cloud, fog, industrial)\
        #             C: there is no smoke in the image.\
        #             A: yes (wildfire/vegetation fire)"
        # prompt = "You are tasked with detecting wildfire smoke. Is there smoke in the image? If yes, is it coming from burning vegetation (trees, forest, grass)? Answer ONLY with the letter:\
        #             B: no there is no smoke in the image\
        #             C: there is smoke in the image, but it's not coming from burning vegetation\
        #             A: there is smoke in the image and it's coming from burning vegetation\
        #             D: it can't be determined whether there is smoke or not, or where it's coming from"
        # prompt = """You are tasked with detecting wildfire smoke.

        #         Determine:
        #         1. Is there visible smoke in the image?
        #         2. If yes, is the smoke coming from burning vegetation (trees, forest, grass)?

        #         Answer with ONLY the letter:
        #         A: Smoke is present and is coming from burning vegetation
        #         B: No smoke is present. This includes:
        #         - images with nothing resembling smoke
        #         - images with fog, clouds
        #         C: Smoke is present, but NOT from burning vegetation (e.g., chimney industrial)
        #         D: It cannot be determined whether there is smoke or its source
        #         """
        # prompt = """You are tasked with detecting wildfire smoke.

        #         Determine:
        #         Is there smoke in the image coming from burning vegetation (trees, forest, grass)?

        #         Return EXACTLY ONE uppercase letter and nothing else:
        #         A: yes, Smoke is present and is coming from burning vegetation
        #         B: no (e.g., there is no smoke, or there is smoke but it's from a non-vegetation source like a chimney or industrial)
        #         C: it can't be determined whether there is smoke or its source
        #         """
        prompt ="""You are tasked with detecting wildfire smoke in images.

        Question: Is there smoke in this image coming from burning vegetation (trees, forest, grass)?

        Respond with ONLY valid JSON in this exact format, no markdown, no extra text:
        {
        "reasoning": "Your analysis of why this is true or false (mention presence/absence of smoke, characteristics, confidence). Keep the reasoning brief, ideally one sentence.",
        "decision": true or false
        }

        Return ONLY the JSON object. true = smoke from vegetation, false = no smoke or non-vegetation smoke (chimney, clouds, industrial)."""
        messages = [
            # {
            #     "role": "system",
            #     "content": [
            #         {"type": "text", "text": "You are a wildfire smoke detection assistant. You analyze images and determine whether they contain smoke from burning vegetation (trees, forest, grass). You answer with EXACTLY ONE uppercase letter: A, B or C, based on the creiteria provided by the user. You do not provide any explanations or additional text, only the letter."}
            #     ]
            # },
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
            outputs = self.model.generate(**inputs, max_new_tokens=100, do_sample=False)

        answer = self.processor.decode(
            outputs[0][inputs["input_ids"].shape[-1]:],
            skip_special_tokens=True
        )
        # Parse and validate JSON response
        try:
            json_data = self._parse_json_response(answer)
            validated_response = self._validate_response(json_data)
            return validated_response
        except (ValueError, ValidationError) as e:
            print(f"Warning: Failed to parse/validate response: {e}")
            print(f"Raw response: {answer}")
            # Return a default response on parse failure
            return "unexpected output"
    
    def _parse_json_response(self, text: str) -> dict:
        """Extract and parse JSON from model output, handling various formats"""
        text = text.strip()
        
        # Try direct JSON parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON object in text (handles markdown code blocks, extra text, etc.)
        try:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
        
        raise ValueError(f"Could not extract valid JSON from model output: {text}")
    
    def _validate_response(self, data: dict) -> SmokeAnalysisAnswer:
        """Validate response against schema and return typed object"""
        try:
            return SmokeAnalysisAnswer.model_validate(data)
        except ValidationError as e:
            raise ValueError(f"Response validation failed: {e}")


if __name__ == "__main__":
    # forestfireinsight_folder = r"U:\Fraunhofer Waldbrand\Testbilder\ForestFireInsights-EvalImages\smoke"
    # falsepositives_folder = r"\\netappn1\SCS\50_Abteilungen\54_RSA\Sicherheitsforschung\smart_forrest_fire\Images\Sam_only\Smoke_T=0.5\No_masks"
    # balkon_folder = r"U:\Fraunhofer Waldbrand\Testbilder\Kamera_Balkon\Images_smoke"
    # cropped_folder = r"U:\Fraunhofer Waldbrand\Testbilder\TrainingDataset\combined_cropped"
    # ouptut_folder = r"U:\Fraunhofer Waldbrand\Testbilder\VLMoutput"

    # os.makedirs(ouptut_folder, exist_ok=True)
    # from SAM3class import Sam3
    # sam = Sam3(threshold=0.5)
    # vlm = VLM()
    # fires = 0
    # for image_path in Path(forestfireinsight_folder).iterdir():
    #     if image_path.is_file() and image_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
    #         image = Image.open(image_path).convert("RGB")
    #         print(f"Analyzing {image_path.name}...")
    #         results = sam.segment(image, "smoke")
    #         if len(results["masks"]) > 0:
    #             image = sam.crop_image(image, results["masks"][0], padding=150)
    #             result = vlm.analyze(image)
    #             if result == "A":
    #                 image.save(os.path.join(ouptut_folder, f"fire_{image_path.name}"))
    #                 fires += 1
    #             else:
    #                 image.save(os.path.join(ouptut_folder, f"no_smoke_{image_path.name}"))
    #         #     image.save(os.path.join(ouptut_folder, f"false_positive_{image_path.name}"))
    #         print(f"Result: {result}")
    # print(f"Total fires detected: {fires}")
    vlm = VLM()
    forestfireinsight_folder = r"U:\Fraunhofer Waldbrand\Testbilder\Kamera_Balkon\Images_smoke_cropped"
    positives = 0
    for image_path in Path(forestfireinsight_folder).iterdir():
        if image_path.is_file() and image_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            image = Image.open(image_path).convert("RGB")
            print(f"Analyzing {image_path.name}...")
            result = vlm.analyze(image)[-4]
            if result == "u":
                positives += 1
            print(f"Result: {result}")
    print(f"Total positives: {positives}")
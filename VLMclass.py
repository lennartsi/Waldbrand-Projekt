import time
from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
import torch
import os
from PIL import Image
from pathlib import Path

class VLM:
    def __init__(self, model_id="Qwen/Qwen3-VL-8B-Instruct", device=None):
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
            quantization_config=quantization_config,
        )

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
            outputs = self.model.generate(**inputs, max_new_tokens=1, do_sample=False)

        answer = self.processor.decode(
            outputs[0][inputs["input_ids"].shape[-1]:],
            skip_special_tokens=True
        )

        return answer.strip()


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
            result = vlm.analyze(image)
            if result == "A":
                positives += 1
            print(f"Result: {result}")
    print(f"Total positives: {positives}")
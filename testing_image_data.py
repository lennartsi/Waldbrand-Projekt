from pathlib import Path
import os
import random
import time
import torch

from transformers import Sam3Processor, Sam3Model
from PIL import Image
import numpy as np
import matplotlib
from VAPIXcamera import VAPIXCamera
from SAM3class import Sam3
from VLMclass import VLM

input_folder = Path(r"U:\Fraunhofer Waldbrand\Testbilder\ForestFireInsights-EvalImages\smoke")
input_folder = Path(r"U:\Fraunhofer Waldbrand\Testbilder\Kamera_Balkon\Images_smoke")

input_folder = Path(r"U:\Fraunhofer Waldbrand\Testbilder\T=0.5_VLM_forestfire")
input_folder = Path(r"\\netappn1\SCS\50_Abteilungen\54_RSA\Sicherheitsforschung\smart_forrest_fire\Images\Smoke_T=0.5_VLM\Chimney_cloud_fog_industrial")
output_folder = Path(r"U:\Fraunhofer Waldbrand\Testbilder\VLM_results_new_prompt")
path_A = os.path.join(output_folder, "Forestfire")
path_B = os.path.join(output_folder, "Chimney_cloud_fog_industrial")
path_C = os.path.join(output_folder, "No_smoke")
path_D = os.path.join(output_folder, "Unsure")

# create folders if they don't exist
os.makedirs(output_folder, exist_ok=True)
os.makedirs(path_A, exist_ok=True)
os.makedirs(path_B, exist_ok=True)
os.makedirs(path_C, exist_ok=True)
os.makedirs(path_D, exist_ok=True)
# output_folder_smoke = Path(r"U:\Fraunhofer Waldbrand\Testbilder\Images_smoke")
# output_folder_nosmoke = Path(r"U:\Fraunhofer Waldbrand\Testbilder\Images_nosmoke")


# Uncomment to analyse the rain images
# input_folder = Path(r"U:\Fraunhofer Waldbrand\Testbilder\rain_images")
# output_folder_smoke = Path(r"U:\Fraunhofer Waldbrand\Testbilder\rain_images_smoke")
# output_folder_nosmoke = Path(r"U:\Fraunhofer Waldbrand\Testbilder\rain_images_nosmoke")

# Create output folder if it doesn't exist
# os.makedirs(output_folder_smoke, exist_ok=True)
# os.makedirs(output_folder_nosmoke, exist_ok=True)


prompt = "smoke"

threshold = 0.5
sam3 = Sam3(threshold=threshold)
vlm = VLM()

def segment_and_save_images(threshold):
    sam3=Sam3(threshhold=threshold)
    for image_path in Path(input_folder).iterdir():
        if image_path.is_file() and image_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            image = Image.open(image_path).convert("RGB")
            results = sam3.segment(image, prompt)
            if len(results["masks"]) > 0:
                masks = results["masks"]
                overlay_image = sam3.overlay_masks(image, masks)
                overlay_image.save(output_folder_smoke / f"overlay_{image_path.name}")
                image.save(output_folder_smoke / f"original_{image_path.name}")
            else:
                image.save(output_folder_nosmoke / f"nosmoke_{image_path.name}")
            

def segment_and_crop(image, padding=50):
    results = sam3.segment(image, prompt)
    if len(results["masks"]) > 0:
        masks = results["masks"]
        for mask in masks:
            crop_image = sam3.crop_image(image, mask, padding=padding)
            return crop_image
    else:
        return None

def count_positives(input_folder):
    pos = 0
    neg = 0
    sam3=Sam3(threshold=threshold)
    
    for image_path in Path(input_folder).iterdir():
        filename = os.path.basename(image_path)
        if image_path.is_file() and image_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            image = Image.open(image_path).convert("RGB")
            results = sam3.segment(image, prompt)
            if len(results["masks"]) > 0:
                pos += 1
                # image.show()
            else:
                # image.show()
                neg += 1
    print(f"Threshold: {threshold}, Percentage: {pos/(pos+neg)*100:.2f}%, Positives: {pos}/{pos+neg}, Negatives: {neg}")


for image_path in Path(input_folder).iterdir():
    if "mask" in image_path.name:
        continue
    if image_path.is_file() and image_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
        image = Image.open(image_path).convert("RGB")
        results = sam3.segment(image, prompt)
        for mask in results["masks"]:
            crop_image = sam3.crop_image(image, mask, padding=100)
            result = vlm.analyze(crop_image)
        
            if result == "A":
                image.save(os.path.join(path_A, f"smoke_{image_path.name}"))
                crop_image.save(os.path.join(path_A, f"crop_{image_path.name}"))
            elif result == "B":
                image.save(os.path.join(path_B, f"smoke_{image_path.name}"))
                crop_image.save(os.path.join(path_B, f"crop_{image_path.name}"))
            elif result == "C":
                image.save(os.path.join(path_C, f"smoke_{image_path.name}"))
                crop_image.save(os.path.join(path_C, f"crop_{image_path.name}"))
            elif result == "D":
                image.save(os.path.join(path_D, f"smoke_{image_path.name}"))
                crop_image.save(os.path.join(path_D, f"crop_{image_path.name}"))
            else:
                print(f"Unexpected result '{result}' for image {image_path.name}")




from transformers import Sam3Processor, Sam3Model
import torch
from PIL import Image
import requests
import numpy as np
import matplotlib
import pandas as pd
import io


device = "cuda" if torch.cuda.is_available() else "cpu"
df = pd.read_parquet("hf://datasets/leon-se/ForestFireInsights-Eval/data/train-00000-of-00001.parquet")


def segment(image, text_prompt):
        inputs = processor(images=image, text=text_prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = model(**inputs)
        results = processor.post_process_instance_segmentation(
            outputs,
            threshold=0.5,
            mask_threshold=0.5,
            target_sizes=inputs.get("original_sizes").tolist()
        )[0]
        return results

def overlay_masks(image, masks):
    image = image.convert("RGBA")
    masks = 255 * masks.cpu().numpy().astype(np.uint8)
    
    n_masks = masks.shape[0]
    cmap = matplotlib.colormaps.get_cmap("rainbow").resampled(n_masks)
    colors = [
        tuple(int(c * 255) for c in cmap(i)[:3])
        for i in range(n_masks)
    ]

    for mask, color in zip(masks, colors):
        mask = Image.fromarray(mask)
        overlay = Image.new("RGBA", image.size, color + (0,))
        alpha = mask.point(lambda v: int(v * 0.5))
        overlay.putalpha(alpha)
        image = Image.alpha_composite(image, overlay)
    return image

def get_lowest_point(mask):
    """
    Given a binary mask, returns the coordinates of an arbitrary lowest point in the mask.
    """
    coords = torch.nonzero(mask)
    if len(coords) == 0:
        return None
    lowest_point = coords[torch.argmax(coords[:, 0])]
    return lowest_point



if __name__ == "__main__":
    from Camera_test import VAPIXCamera
    
    # Load model and processor only when script runs
    model = Sam3Model.from_pretrained("facebook/sam3").to(device)
    processor = Sam3Processor.from_pretrained("facebook/sam3")
    # Access one row (example: row index 1)

    row = df.iloc[1]

    # Extract raw bytes
    img_bytes = row["image"]["bytes"]

    # Convert to PIL Image
    image = Image.open(io.BytesIO(img_bytes))

    results = segment(image, "smoke")
    overlay_masks(image, results["masks"]).show()
    # which_cam = "rent"
    # if which_cam == "rent":
    #     ip = '195.60.68.14:11066'
    #     user='VLTuser'
    #     password='SrJWWEhk'
    # else:
    #     ip = '192.44.18.67'
    #     user='lennart'
    #     password='7v1wuUGGsE3W2R3GpGbg'

    # cam=VAPIXCamera(ip, user, password,use_https=False)

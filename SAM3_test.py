from transformers import Sam3Processor, Sam3Model
import torch
from PIL import Image
import requests
import numpy as np
import matplotlib
from Camera_test import VAPIXCamera

device = "cuda" if torch.cuda.is_available() else "cpu"

model = Sam3Model.from_pretrained("facebook/sam3").to(device)
processor = Sam3Processor.from_pretrained("facebook/sam3")

ip='195.60.68.14:11115'
url = f"http://{ip}/axis-cgi/com/ptz.cgi"
user='VLTuser'
password='pMycBxxn'
cam=VAPIXCamera(ip, user, password,use_https=False)

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

for degree in range(225, 360, 45):
    cam.absolute_move(degree, 0, 1, 100)
    cam.wait_until_stopped()
    image=cam.get_current_image()

    # Segment using text prompt
    inputs = processor(images=image, text="a digital clock displaying the time with blue-white numbers", return_tensors="pt").to(device)

    with torch.no_grad():
        outputs = model(**inputs)

    # Post-process results
    results = processor.post_process_instance_segmentation(
        outputs,
        threshold=0.5,
        mask_threshold=0.5,
        target_sizes=inputs.get("original_sizes").tolist()
    )[0]
    print(type(results["masks"]))
    print(results["masks"].shape)
    print(results["masks"].dtype)
    if len(results["masks"]) == 0:
        print("Camera position:", cam.get_ptz_status())
        print("No objects found")  
        image.show()
        continue
    else:
        print("Camera position:", cam.get_ptz_status())
        print(f"Found {len(results['masks'])} objects")
        for i in range(len(results["masks"])):
            lowest_point=get_lowest_point(results["masks"][i])
            print(f"Lowest point of mask {i}: {lowest_point}")
            cam.area_zoom(lowest_point[1].item(), lowest_point[0].item(),1000, 100)
            cam.wait_until_stopped()
            cam.get_current_image().show()
        overlay_masks(image, results["masks"]).show()
        exit(0)

# Results contain:
# - masks: Binary masks resized to original image size
# - boxes: Bounding boxes in absolute pixel coordinates (xyxy format)
# - scores: Confidence scores




#overlay_masks(image, results["masks"]).show()


# import torch
# from PIL import Image
# import requests
# from transformers import SamModel, SamProcessor
# import os

# # Get your token from environment
# token = os.environ.get('HF_TOKEN')
# print("HF token from env:", os.environ.get("HUGGINGFACE_HUB_TOKEN"))
# # Try loading SAM 3 (if you have access)
# try:
#     model_id = "facebook/sam3"
#     processor = SamProcessor.from_pretrained(model_id, token=token)
#     model = SamModel.from_pretrained(model_id, token=token)
#     print("✅ SAM 3 loaded successfully!")
# except Exception as e:
#     print(f"❌ SAM 3 failed: {e}")
from pathlib import Path
import os

from transformers import Sam3Processor, Sam3Model
from PIL import Image
import numpy as np
import matplotlib
from VAPIXcamera import VAPIXCamera
from SAM3class import Sam3

input_folder = Path(r"U:\Fraunhofer Waldbrand\Testbilder\forest_masks\Vorlagen_12Uhr\Vorlagen")
path = Path(r"U:\Fraunhofer Waldbrand\Testbilder\forest_masks\Vorlagen_12Uhr\forest_masks")
# Create output folder if it doesn't exist
os.makedirs(path, exist_ok=True)

ip = '192.44.18.67'
user='lennart'
password='7v1wuUGGsE3W2R3GpGbg'

cam=VAPIXCamera(ip, user, password,use_https=False)
speed = 100

prompt="forest"
time_interval = 1  # seconds between each image capture and analysis
# sam3=Sam3(threshold=0.3)

preset_no = 18

# for i in range(preset_no,45):
#     cam.go_to_server_preset_number(i, speed)
#     cam.wait_until_stopped()
#     image = cam.get_current_image()
#     results = sam3.segment(image, prompt)
#     if results['masks'].shape[0]>0:
#         image_with_mask = sam3.overlay_masks(image, results['masks'])
#         image_with_mask.save(path / f"preset_{i}_forest.jpg")
#     else:
#         image.save(path / f"preset_{i}_noforest.jpg")

# masks_dict = {}
# preset_no = 18
# for image_path in Path(input_folder).iterdir():
    
#     filename = os.path.basename(image_path)
#     image = Image.open(image_path).convert("RGB")
#     results = sam3.segment(image, prompt)
#     if results['masks'].shape[0] > 0:
#         # Convert to numpy array if it's a torch tensor
#         masks_np = results['masks'].cpu().numpy() if hasattr(results['masks'], 'cpu') else np.array(results['masks'])
#         # Merge all masks into one mask (logical OR across axis 0)
#         merged_mask = np.any(masks_np, axis=0).astype(np.uint8)
#         masks_dict["Position"+str(preset_no)] = merged_mask
#     preset_no += 1
# # Save all merged masks in a single .npz file
# np.savez_compressed(path / "merged_forest_masks.npz", **masks_dict)

def load_merged_masks(npz_path):
	return np.load(npz_path)


def get_pixel_distance(npz_data, position_key, row, col):
	"""Return Euclidean distance from (row, col) to nearest mask pixel."""
	if position_key not in npz_data.files:
		raise KeyError(f"Position key '{position_key}' not found in npz file")

	mask = npz_data[position_key].astype(bool)
	h, w = mask.shape

	if row < 0 or row >= h or col < 0 or col >= w:
		raise ValueError(f"Pixel ({row}, {col}) is outside mask bounds {(h, w)}")

	# Find all forest pixels and compute nearest Euclidean distance.
	forest_pixels = np.argwhere(mask)
	if forest_pixels.size == 0:
		return float("inf")

	deltas = forest_pixels - np.array([row, col])
	distances = np.sqrt((deltas ** 2).sum(axis=1))
	return float(distances.min())


npz_data = load_merged_masks(path / "merged_forest_masks.npz")
distance = get_pixel_distance(npz_data, "Position43", 100, 100)
print(f"Distance of pixel (100, 100) to forest mask in Position18: {distance}")

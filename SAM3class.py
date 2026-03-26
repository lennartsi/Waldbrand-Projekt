from pathlib import Path

import torch
from transformers import Sam3Processor, Sam3Model
from PIL import Image
import numpy as np
import matplotlib

class Sam3:
    def __init__(self, model_id="facebook/sam3", device=None, threshold=0.5):

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = Sam3Model.from_pretrained(model_id).to(self.device)
        self.processor = Sam3Processor.from_pretrained(model_id)
        self.threshold = threshold

    def segment(self, image, text_prompt):
        inputs = self.processor(images=image, text=text_prompt, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
        results = self.processor.post_process_instance_segmentation(
            outputs,
            threshold=self.threshold,
            mask_threshold=0.5,
            target_sizes=inputs.get("original_sizes").tolist()
        )[0]
        return results
    
    
    def overlay_masks(self, image, masks):
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
        return image.convert("RGB")
    
    def get_lowest_point_single_mask(self, mask):
        """
        Given a binary mask, returns the coordinates of an arbitrary lowest point in the mask.
        """
        if self.device == "cuda":
            mask = mask.cpu()
        coords = torch.nonzero(mask)
        if len(coords) == 0:
            return None
        lowest_point = coords[torch.argmax(coords[:, 0])]
        return lowest_point
    
    def crop_image(self, image, mask, padding=100):
        '''
        Applies the binary mask to the image, returning a rectangular image of the masked area with some padding.
        '''
        image = image.convert("RGBA")
        if self.device == "cuda":
            mask = mask.cpu()
        coords = torch.nonzero(mask)
        if len(coords) == 0:
            return None
        
        lowest,highest,leftmost,rightmost = coords[torch.argmax(coords[:, 0])], coords[torch.argmin(coords[:, 0])], coords[torch.argmin(coords[:, 1])], coords[torch.argmax(coords[:, 1])]
        bottom = max(lowest[0].item() + padding, 0)
        top = min(highest[0].item() - padding, image.height)
        left = max(leftmost[1].item() - padding, 0)
        right = min(rightmost[1].item() + padding, image.width)
        return image.crop((left, top, right, bottom)).convert("RGB")

    def get_lowest_point(self, masks):
        """
        Given a set of binary masks, returns the coordinates of the lowest point across all masks.
        """
        lowest_points = []
        for i in range(masks.shape[0]):
            lowest_point = self.get_lowest_point_single_mask(masks[i])
            if lowest_point is not None:
                lowest_points.append(lowest_point)
        
        if len(lowest_points) == 0:
            return None
        
        lowest_points = torch.stack(lowest_points)
        overall_lowest = lowest_points[torch.argmax(lowest_points[:, 0])]
        return overall_lowest

if __name__ == "__main__":
    sam3 = Sam3()
    folder_path = r"U:\Fraunhofer Waldbrand\Testbilder\Kamera_Balkon\Images_smoke"
    positives = 0
    negatives = 0
    
    for image_path in Path(folder_path).iterdir():
        if image_path.is_file() and image_path.suffix.lower() in [".png", ".jpg", ".jpeg"] and "mask" not in image_path.name:
            image = Image.open(image_path).convert("RGB")
            results = sam3.segment(image, "smoke")
            if results['masks'].shape[0]>0:
                sam3.crop_image(image, results['masks'][0]).save(image_path.parent / f"cropped_{image_path.name}")
            else:
                negatives += 1
    print(f"Total images: {positives + negatives}, Positives: {positives}, Negatives: {negatives}")
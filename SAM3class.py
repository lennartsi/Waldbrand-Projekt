import torch
from transformers import Sam3Processor, Sam3Model
from PIL import Image
import numpy as np
import matplotlib

class Sam3:
    def __init__(self, model_id="facebook/sam3", device=None):

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = Sam3Model.from_pretrained(model_id).to(self.device)
        self.processor = Sam3Processor.from_pretrained(model_id)

    def segment(self, image, text_prompt):
        inputs = self.processor(images=image, text=text_prompt, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
        results = self.processor.post_process_instance_segmentation(
            outputs,
            threshold=0.5,
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
        return image
    
    def get_lowest_point(self, mask):
        """
        Given a binary mask, returns the coordinates of an arbitrary lowest point in the mask.
        """
        coords = torch.nonzero(mask)
        if len(coords) == 0:
            return None
        lowest_point = coords[torch.argmax(coords[:, 0])]
        return lowest_point
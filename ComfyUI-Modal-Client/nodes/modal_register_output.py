import os
from pathlib import Path

import numpy as np
import torch
from PIL import Image

# Ruta base del ComfyUI local (Ajuste de profundidad: parents[3])
COMFY_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = COMFY_ROOT / "output"


class LoadLocalImageModal:
    """
    Nodo que carga una imagen PNG/JPG desde la carpeta output
    y la convierte a tensor IMAGE de ComfyUI.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "filename": (
                    "STRING",
                    {"default": "z-image_00001_.png"},
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "load_image"
    CATEGORY = "modal"
    OUTPUT_IS_LIST = (False,)

    def load_image(self, filename: str):
        img_path = OUTPUT_DIR / filename
        if not img_path.exists():
            raise FileNotFoundError(f"Imagen no encontrada en output: {img_path}")

        img = Image.open(img_path).convert("RGB")
        arr = np.array(img).astype(np.float32) / 255.0  # [H, W, C], 0–1
        arr = arr[None, ...]  # [1, H, W, C]
        tensor = torch.from_numpy(arr)

        return (tensor,)


# Mapeo requerido por ComfyUI
NODE_CLASS_MAPPINGS = {
    "LoadLocalImageModal": LoadLocalImageModal,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadLocalImageModal": "Load Local Image (Modal)",
}
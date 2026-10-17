"""
ControlNet para Chroma: copia la pose, la profundidad (forma y perspectiva) o los bordes
de una imagen guia. Usa los detectores que ya trae ComfyUI (SDPose, Depth Anything 3, Canny)
y el ControlNet Union Pro 2.0 de Flux, que funciona con Chroma.
"""

import logging

import torch

import comfy.utils
import nodes
from comfy_extras.nodes_canny import Canny
from comfy_extras.nodes_depth_anything_3 import DA3Inference, DA3Render, LoadDA3Model
from comfy_extras.nodes_sdpose import SDPoseDrawKeypoints, SDPoseKeypointExtractor

CONTROLNET = "flux_controlnet_union_pro_2.safetensors"
SDPOSE = "sdpose_wholebody_fp16.safetensors"
DA3 = "depth_anything_3_mono_large.safetensors"

POSE = "Pose (copia la postura, manos y cara)"
PROFUNDIDAD = "Profundidad (copia forma, volumen y angulo de camara)"
BORDES = "Bordes (copia contornos y composicion exacta)"

_cache = {}


def _cargar(clave, fn):
    if clave not in _cache:
        _cache[clave] = fn()
    return _cache[clave]


def _lado_largo(imagen, maximo=1024):
    h, w = imagen.shape[1], imagen.shape[2]
    escala = min(1.0, maximo / float(max(h, w)))
    if escala >= 1.0:
        return imagen
    s = imagen[..., :3].movedim(-1, 1)
    s = comfy.utils.common_upscale(s, round(w * escala), round(h * escala), "area", "disabled")
    return s.movedim(1, -1)


def mapa_pose(imagen):
    model, _, vae = _cargar("sdpose", lambda: nodes.CheckpointLoaderSimple().load_checkpoint(SDPOSE)[:3])
    puntos = SDPoseKeypointExtractor.execute(model, vae, imagen, 16).result[0]
    return SDPoseDrawKeypoints.execute(puntos, True, True, True, True, 4, 2, 0.5, True).result[0]


def mapa_profundidad(imagen):
    modelo = _cargar("da3", lambda: LoadDA3Model.execute(DA3, "default").result[0])
    geo = DA3Inference.execute(modelo, imagen, 504, "upper_bound_resize", {"mode": "mono"}).result[0]
    return DA3Render.execute(geo, {"output": "depth", "normalization": "v2_style", "apply_sky_clip": False}).result[0]


def mapa_bordes(imagen):
    return Canny.execute(imagen, 0.15, 0.45).result[0]


class ChromaControl:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "imagen_guia": ("IMAGE", {"tooltip": "Imagen de la que copiar pose / forma / bordes."}),
                "activar": ("BOOLEAN", {"default": False, "label_on": "ACTIVADO", "label_off": "apagado"}),
                "tipo": ([POSE, PROFUNDIDAD, BORDES], {"default": POSE}),
                "fuerza": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 1.5, "step": 0.05, "display": "slider",
                                     "tooltip": "Cuanto obedece a la guia. 0.5-0.8 recomendado."}),
                "hasta": ("FLOAT", {"default": 0.6, "min": 0.1, "max": 1.0, "step": 0.05, "display": "slider",
                                    "tooltip": "Hasta que parte de los pasos guia (0.6 = el 60%). Menos = mas libertad en los detalles."}),
            }
        }

    RETURN_TYPES = ("CHROMA_CONTROL", "IMAGE")
    RETURN_NAMES = ("control", "mapa")
    FUNCTION = "preparar"
    CATEGORY = "Chroma"
    DESCRIPTION = "ControlNet: copia la pose, la profundidad o los bordes de una imagen guia."

    def preparar(self, imagen_guia, activar, tipo, fuerza, hasta):
        if not activar or fuerza == 0:
            return ({"activo": False}, torch.zeros(1, 64, 64, 3))
        img = _lado_largo(imagen_guia[:1, :, :, :3])
        if tipo == POSE:
            mapa = mapa_pose(img)
        elif tipo == PROFUNDIDAD:
            mapa = mapa_profundidad(img)
        else:
            mapa = mapa_bordes(img)
        logging.info("[Chroma] ControlNet %s: fuerza %.2f hasta %.0f%%", tipo.split(" ")[0], fuerza, hasta * 100)
        return ({"activo": True, "tipo": tipo, "mapa": mapa, "fuerza": fuerza, "hasta": hasta}, mapa)


def aplicar_control(control, positivo, negativo, vae):
    if not control or not control.get("activo"):
        return positivo, negativo
    cn = _cargar("controlnet", lambda: nodes.ControlNetLoader().load_controlnet(CONTROLNET)[0])
    return nodes.ControlNetApplyAdvanced().apply_controlnet(
        positivo, negativo, cn, control["mapa"], control["fuerza"], 0.0, control["hasta"], vae=vae)

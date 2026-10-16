"""
Chroma Panel: nodos para controlar Chroma1-HD desde un solo lugar.

  - Panel Chroma : todos los ajustes (modo, prompts, resolucion, semilla, pasos, escalado...)
  - LoRAs Chroma : hasta 4 LoRAs con fuerza, "Ninguno" para desactivar un hueco
  - Motor Chroma : codifica prompts, genera, decodifica y escala segun el panel

El muestreo usa el KSampler interno de ComfyUI, igual que la plantilla oficial
de Chroma (euler / beta, shift 1.0, T5 min_padding 1).
"""

import math

import torch

import comfy.model_management
import comfy.samplers
import comfy.utils
import folder_paths
import nodes
from comfy_extras.nodes_model_advanced import ModelSamplingAuraFlow
from comfy_extras.nodes_upscale_model import ImageUpscaleWithModel, UpscaleModelLoader

NINGUNO = "Ninguno"

MODO_TEXTO = "Texto a imagen"
MODO_REFERENCIA = "Imagen de referencia (img2img)"

PERSONALIZADO = "Personalizado (usa ancho/alto)"
RESOLUCIONES = {
    "Retrato 2:3  - 832x1216": (832, 1216),
    "Retrato 3:4  - 896x1152": (896, 1152),
    "Vertical 9:16 - 768x1344": (768, 1344),
    "Cuadrado 1:1 - 1024x1024": (1024, 1024),
    "Paisaje 3:2  - 1216x832": (1216, 832),
    "Paisaje 4:3  - 1152x896": (1152, 896),
    "Panoramico 16:9 - 1344x768": (1344, 768),
    "Rapido 2:3 (pruebas) - 640x960": (640, 960),
    "Rapido 1:1 (pruebas) - 768x768": (768, 768),
}

ESCALADO_NO = "No"
ESCALADO_RAPIDO = "Rapido x2 (solo upscaler, segundos)"
ESCALADO_DETALLE = "Detallado x1.5 (upscaler + 2a pasada, +2-3 min)"

NEGATIVO_GENERICO = (
    "This low quality, blurry, out of focus image is a cartoon, anime, illustration, 3D render, CGI, painting, "
    "drawing or sketch. It has a toony aesthetic with bold outlines and flat colors, plastic or waxy airbrushed "
    "skin, doll-like face, uncanny valley look, oversaturated colors, excessive bloom, chromatic aberration, heavy "
    "vignette, jpeg artifacts, noise, overexposed or underexposed lighting. The anatomy is wrong: deformed body, "
    "bad proportions, extra limbs, missing limbs, extra arms, extra legs, fused fingers, too many fingers, missing "
    "fingers, malformed hands, twisted wrists, distorted face, asymmetrical eyes, crossed eyes, deformed genitals, "
    "merged body parts, elongated neck, broken spine. The image contains text, watermark, logo, signature, caption, "
    "frame, border, collage or split screen. Childlike features, child, minor, underage, teen."
)


def _a_multiplo(valor, multiplo=16):
    return max(multiplo, int(round(valor / multiplo)) * multiplo)


class ChromaPanel:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "modo": ([MODO_TEXTO, MODO_REFERENCIA], {"default": MODO_TEXTO}),
                "prompt": ("STRING", {"multiline": True, "default": "",
                                      "tooltip": "En ingles y en frases completas: sujeto, ropa, pose, lugar, luz, tipo de foto."}),
                "negativo": ("STRING", {"multiline": True, "default": NEGATIVO_GENERICO}),
                "resolucion": (list(RESOLUCIONES.keys()) + [PERSONALIZADO], {"default": "Retrato 2:3  - 832x1216"}),
                "ancho": ("INT", {"default": 1024, "min": 256, "max": 2048, "step": 16,
                                  "tooltip": "Solo se usa con 'Personalizado'."}),
                "alto": ("INT", {"default": 1024, "min": 256, "max": 2048, "step": 16,
                                 "tooltip": "Solo se usa con 'Personalizado'."}),
                "semilla": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff, "control_after_generate": True,
                                    "tooltip": "randomize = una distinta en cada imagen. fixed = repetir la misma."}),
                "pasos": ("INT", {"default": 26, "min": 1, "max": 100,
                                  "tooltip": "20 = rapido, 26 = normal, 30-35 = mas detalle."}),
                "cfg": ("FLOAT", {"default": 4.0, "min": 1.0, "max": 10.0, "step": 0.1, "round": 0.01,
                                  "tooltip": "Cuanto obedece al prompt. 3.5-5 recomendado."}),
                "sampler": (comfy.samplers.KSampler.SAMPLERS, {"default": "euler"}),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS, {"default": "beta"}),
                "fuerza_referencia": ("FLOAT", {"default": 0.65, "min": 0.05, "max": 1.0, "step": 0.01,
                                                "tooltip": "Solo en modo referencia. 0.3-0.45 retoque, 0.55-0.7 cambia ropa/estilo, 0.75-0.9 solo guia."}),
                "escalado": ([ESCALADO_NO, ESCALADO_RAPIDO, ESCALADO_DETALLE], {"default": ESCALADO_NO}),
                "fuerza_detalle": ("FLOAT", {"default": 0.35, "min": 0.1, "max": 0.7, "step": 0.01,
                                             "tooltip": "Solo en 'Detallado': cuanto redibuja la 2a pasada. 0.3-0.4 recomendado."}),
            }
        }

    RETURN_TYPES = ("CHROMA_AJUSTES",)
    RETURN_NAMES = ("ajustes",)
    FUNCTION = "armar"
    CATEGORY = "Chroma"
    DESCRIPTION = "Todos los ajustes de Chroma en un solo lugar. Conectalo al Motor Chroma."

    def armar(self, modo, prompt, negativo, resolucion, ancho, alto, semilla, pasos, cfg, sampler, scheduler,
              fuerza_referencia, escalado, fuerza_detalle):
        if resolucion in RESOLUCIONES:
            ancho, alto = RESOLUCIONES[resolucion]
        return ({
            "referencia": modo == MODO_REFERENCIA,
            "prompt": prompt,
            "negativo": negativo,
            "ancho": _a_multiplo(ancho),
            "alto": _a_multiplo(alto),
            "semilla": semilla,
            "pasos": pasos,
            "cfg": cfg,
            "sampler": sampler,
            "scheduler": scheduler,
            "denoise": fuerza_referencia if modo == MODO_REFERENCIA else 1.0,
            "escalado": escalado,
            "fuerza_detalle": fuerza_detalle,
        },)


class ChromaLoras:
    HUECOS = 4

    def __init__(self):
        self.cargador = nodes.LoraLoader()  # reutiliza la cache de LoRA de ComfyUI

    @classmethod
    def INPUT_TYPES(cls):
        loras = [NINGUNO] + folder_paths.get_filename_list("loras")
        req = {"model": ("MODEL",)}
        for i in range(1, cls.HUECOS + 1):
            req[f"lora_{i}"] = (loras, {"default": NINGUNO})
            req[f"fuerza_{i}"] = ("FLOAT", {"default": 0.8, "min": -3.0, "max": 3.0, "step": 0.05})
        return {"required": req}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "aplicar"
    CATEGORY = "Chroma"
    DESCRIPTION = "Hasta 4 LoRAs para Chroma. Pon 'Ninguno' o fuerza 0 para desactivar un hueco. Archivos en ComfyUI/models/loras."

    def aplicar(self, model, **kw):
        for i in range(1, self.HUECOS + 1):
            nombre, fuerza = kw[f"lora_{i}"], kw[f"fuerza_{i}"]
            if nombre == NINGUNO or fuerza == 0:
                continue
            model = self.cargador.load_lora(model, None, nombre, fuerza, 0)[0]
        return (model,)


class ChromaMotor:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "ajustes": ("CHROMA_AJUSTES",),
                "upscaler": ([NINGUNO] + folder_paths.get_filename_list("upscale_models"),
                             {"default": NINGUNO, "tooltip": "Modelo de escalado (carpeta models/upscale_models)."}),
            },
            "optional": {
                "imagen_referencia": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("imagen",)
    FUNCTION = "generar"
    CATEGORY = "Chroma"
    DESCRIPTION = "Genera la imagen con los ajustes del Panel Chroma."

    @staticmethod
    def _codificar(clip, texto):
        clip = clip.clone()
        # forma oficial de Chroma (plantilla de ComfyUI: T5TokenizerOptions min_padding=1)
        clip.set_tokenizer_option("t5xxl_min_padding", 1)
        clip.set_tokenizer_option("t5xxl_min_length", 0)
        return clip.encode_from_tokens_scheduled(clip.tokenize(texto))

    @staticmethod
    def _latente_vacio(ancho, alto):
        dev = comfy.model_management.intermediate_device()
        dtype = comfy.model_management.intermediate_dtype()
        return {"samples": torch.zeros([1, 16, alto // 8, ancho // 8], device=dev, dtype=dtype),
                "downscale_ratio_spacial": 8}

    @staticmethod
    def _redimensionar(imagen, ancho, alto):
        s = imagen[..., :3].movedim(-1, 1)
        s = comfy.utils.common_upscale(s, ancho, alto, "lanczos", "center")
        return s.movedim(1, -1)

    @staticmethod
    def _decodificar(vae, latente):
        img = vae.decode(latente["samples"])
        if len(img.shape) == 5:
            img = img.reshape(-1, img.shape[-3], img.shape[-2], img.shape[-1])
        return img

    def generar(self, model, clip, vae, ajustes, upscaler, imagen_referencia=None):
        a = ajustes
        if not a["prompt"].strip():
            raise ValueError("El prompt del Panel Chroma esta vacio.")
        if a["escalado"] != ESCALADO_NO and upscaler == NINGUNO:
            raise ValueError("Elegiste escalado pero el Motor Chroma no tiene 'upscaler'. Elige uno o pon escalado = No.")

        model = ModelSamplingAuraFlow().patch_aura(model, 1.0)[0]  # shift 1.0 = el del autor de Chroma
        positivo = self._codificar(clip, a["prompt"])
        negativo = self._codificar(clip, a["negativo"])

        if a["referencia"]:
            if imagen_referencia is None:
                raise ValueError("Modo 'Imagen de referencia' pero no hay imagen conectada.")
            pix = self._redimensionar(imagen_referencia[:1], a["ancho"], a["alto"])
            latente = {"samples": vae.encode(pix)}
        else:
            latente = self._latente_vacio(a["ancho"], a["alto"])

        latente = nodes.common_ksampler(model, a["semilla"], a["pasos"], a["cfg"], a["sampler"], a["scheduler"],
                                        positivo, negativo, latente, denoise=a["denoise"])[0]
        imagen = self._decodificar(vae, latente)

        if a["escalado"] == ESCALADO_NO:
            return (imagen,)

        modelo_esc = UpscaleModelLoader.execute(upscaler).result[0]
        grande = ImageUpscaleWithModel.execute(modelo_esc, imagen).result[0]
        factor = 2.0 if a["escalado"] == ESCALADO_RAPIDO else 1.5
        ancho, alto = _a_multiplo(a["ancho"] * factor), _a_multiplo(a["alto"] * factor)
        imagen = self._redimensionar(grande, ancho, alto)

        if a["escalado"] == ESCALADO_DETALLE:
            # 2a pasada: redibuja detalles finos sobre la imagen escalada
            latente = {"samples": vae.encode(imagen)}
            pasos = max(8, math.ceil(a["pasos"] * 0.6))
            latente = nodes.common_ksampler(model, a["semilla"], pasos, a["cfg"], a["sampler"], a["scheduler"],
                                            positivo, negativo, latente, denoise=a["fuerza_detalle"])[0]
            imagen = self._decodificar(vae, latente)
        return (imagen,)


NODE_CLASS_MAPPINGS = {
    "ChromaPanel": ChromaPanel,
    "ChromaLoras": ChromaLoras,
    "ChromaMotor": ChromaMotor,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ChromaPanel": "Panel Chroma",
    "ChromaLoras": "LoRAs Chroma",
    "ChromaMotor": "Motor Chroma",
}

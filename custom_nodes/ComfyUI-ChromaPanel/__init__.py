"""
Chroma Panel: nodos para controlar Chroma1-HD desde un solo lugar.

  - Panel Chroma : todos los ajustes (modo, prompts, resolucion, semilla, pasos, escalado...)
  - LoRAs Chroma : hasta 4 LoRAs con fuerza, "Ninguno" para desactivar un hueco
  - Motor Chroma : codifica prompts, genera, decodifica y escala segun el panel

El muestreo usa el KSampler interno de ComfyUI, igual que la plantilla oficial
de Chroma (euler / beta, shift 1.0, T5 min_padding 1).
"""

import json
import logging
import math
import os

import numpy as np
import torch
from PIL import Image

import comfy.model_management
import comfy.samplers
import comfy.utils
import folder_paths
import nodes
from comfy_extras.nodes_model_advanced import ModelSamplingAuraFlow
from comfy_extras.nodes_upscale_model import ImageUpscaleWithModel, UpscaleModelLoader

from .control import ChromaControl, aplicar_control
from .etiquetas import ChromaEtiquetas
from .herramientas import (YOLO_CARA, YOLO_MANO, ChromaComparador, ChromaDetallador, ChromaRetoque,
                           cuadricula, detallar, detectar)

NINGUNO = "Ninguno"

MODO_TEXTO = "Texto a imagen"
MODO_REFERENCIA = "Imagen de referencia (img2img)"
MODO_ULTIMA = "Editar la ultima imagen generada"
MODO_INPAINT = "Inpaint: redibujar zona pintada"
MODOS_REF = (MODO_REFERENCIA, MODO_ULTIMA, MODO_INPAINT)

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
                "modo": ([MODO_TEXTO, MODO_REFERENCIA, MODO_ULTIMA, MODO_INPAINT], {"default": MODO_TEXTO,
                          "tooltip": "Ultima imagen: usa la ultima de output/Chroma. Inpaint: pinta la zona en Load Image (clic derecho > Open in MaskEditor) y solo esa zona se redibuja."}),
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
                                                "tooltip": "Solo en modos de referencia. 0.3-0.45 retoque, 0.55-0.7 cambia estilo/detalles, 0.75-0.9 cambia ropa o la quita (mantiene pose)."}),
                "escalado": ([ESCALADO_NO, ESCALADO_RAPIDO, ESCALADO_DETALLE], {"default": ESCALADO_NO}),
                "fuerza_detalle": ("FLOAT", {"default": 0.35, "min": 0.1, "max": 0.7, "step": 0.01,
                                             "tooltip": "Solo en 'Detallado': cuanto redibuja la 2a pasada. 0.3-0.4 recomendado."}),
            },
            "optional": {
                "etiquetas": ("CHROMA_ETIQUETAS", {"tooltip": "Conecta aqui los Botones de prompt."}),
            },
        }

    RETURN_TYPES = ("CHROMA_AJUSTES",)
    RETURN_NAMES = ("ajustes",)
    FUNCTION = "armar"
    CATEGORY = "Chroma"
    DESCRIPTION = "Todos los ajustes de Chroma en un solo lugar. Conectalo al Motor Chroma."

    @classmethod
    def IS_CHANGED(cls, modo, **kw):
        # en "ultima imagen" hay que volver a mirar la carpeta en cada ejecucion
        return float("nan") if modo == MODO_ULTIMA else ""

    def armar(self, modo, prompt, negativo, resolucion, ancho, alto, semilla, pasos, cfg, sampler, scheduler,
              fuerza_referencia, escalado, fuerza_detalle, etiquetas=None):
        if resolucion in RESOLUCIONES:
            ancho, alto = RESOLUCIONES[resolucion]
        if etiquetas:
            prompt = " ".join(t for t in (etiquetas["positivo"], prompt.strip()) if t)
            negativo = ", ".join(t for t in (negativo.strip().rstrip("."), etiquetas["negativo"]) if t)
        return ({
            "referencia": modo in MODOS_REF,
            "inpaint": modo == MODO_INPAINT,
            "ultima": modo == MODO_ULTIMA,
            "prompt": prompt,
            "negativo": negativo,
            "ancho": _a_multiplo(ancho),
            "alto": _a_multiplo(alto),
            "semilla": semilla,
            "pasos": pasos,
            "cfg": cfg,
            "sampler": sampler,
            "scheduler": scheduler,
            "denoise": fuerza_referencia if modo in MODOS_REF else 1.0,
            "escalado": escalado,
            "fuerza_detalle": fuerza_detalle,
        },)


def _catalogo():
    ruta = os.path.join(os.path.dirname(__file__), "catalogo.json")
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


class ChromaLoras:
    """LoRAs del pack con interruptor y barra de fuerza + 2 huecos libres."""
    LIBRES = 2

    def __init__(self):
        self.cargador = nodes.LoraLoader()  # reutiliza la cache de LoRA de ComfyUI

    @classmethod
    def INPUT_TYPES(cls):
        req = {"model": ("MODEL",)}
        for e in _catalogo()["loras"]:
            req[e["etiqueta"]] = ("BOOLEAN", {"default": e["activo"], "label_on": "ACTIVADO", "label_off": "apagado",
                                              "tooltip": e["nota"] or e["etiqueta"]})
            req["fuerza " + e["clave"]] = ("FLOAT", {"default": e["fuerza"], "min": e["min"], "max": e["max"],
                                                     "step": 0.05, "display": "slider"})
        loras = [NINGUNO] + folder_paths.get_filename_list("loras")
        for i in range(1, cls.LIBRES + 1):
            req[f"libre {i}"] = ("BOOLEAN", {"default": False, "label_on": "ACTIVADO", "label_off": "apagado"})
            req[f"libre {i} archivo"] = (loras, {"default": NINGUNO})
            req[f"libre {i} fuerza"] = ("FLOAT", {"default": 0.8, "min": -2.0, "max": 2.0, "step": 0.05, "display": "slider"})
            req[f"libre {i} palabras"] = ("STRING", {"default": "", "tooltip": "Palabras clave (trigger) de ese LoRA, si tiene."})
        return {"required": req}

    RETURN_TYPES = ("MODEL", "CHROMA_LORAS")
    RETURN_NAMES = ("model", "info_loras")
    FUNCTION = "aplicar"
    CATEGORY = "Chroma"
    DESCRIPTION = "Pack de LoRAs para Chroma: activa con el interruptor y ajusta la fuerza con la barra."

    def _aplicar_uno(self, model, nombre, fuerza):
        if folder_paths.get_full_path("loras", nombre) is None:
            logging.warning(f"[Chroma] LoRA no encontrado, se omite: {nombre} (vuelve a ejecutar INSTALAR.bat)")
            return model, False
        return self.cargador.load_lora(model, None, nombre, fuerza, 0)[0], True

    def aplicar(self, model, **kw):
        palabras, flash, activos = [], False, []
        for e in _catalogo()["loras"]:
            fuerza = kw["fuerza " + e["clave"]]
            if not kw[e["etiqueta"]] or fuerza == 0:
                continue
            model, ok = self._aplicar_uno(model, e["archivo"], fuerza)
            if not ok:
                continue
            activos.append(f"{e['etiqueta']} ({fuerza})")
            if e["palabras"]:
                palabras.append(e["palabras"])
            if e["clave"] == "velocidad_flash":
                flash = True
        for i in range(1, self.LIBRES + 1):
            nombre, fuerza = kw[f"libre {i} archivo"], kw[f"libre {i} fuerza"]
            if not kw[f"libre {i}"] or nombre == NINGUNO or fuerza == 0:
                continue
            model, ok = self._aplicar_uno(model, nombre, fuerza)
            if ok:
                activos.append(f"{nombre} ({fuerza})")
                if kw[f"libre {i} palabras"].strip():
                    palabras.append(kw[f"libre {i} palabras"].strip())
        logging.info("[Chroma] LoRAs activos: " + (", ".join(activos) or "ninguno"))
        return (model, {"palabras": palabras, "flash": flash})


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
                "info_loras": ("CHROMA_LORAS",),
                "control": ("CHROMA_CONTROL", {"tooltip": "ControlNet (pose / profundidad / bordes)."}),
                "detallador": ("CHROMA_DETALLE", {"tooltip": "Redibuja caras y manos."}),
                "comparador": ("CHROMA_COMPARAR", {"tooltip": "Cuadricula comparando un ajuste."}),
                "mascara": ("MASK", {"tooltip": "Zona pintada para el modo Inpaint (salida MASK de Load Image)."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("imagen", "prompt_final")
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
    def _ultima_imagen():
        carpeta = os.path.join(folder_paths.get_output_directory(), "Chroma")
        archivos = [os.path.join(carpeta, f) for f in os.listdir(carpeta)
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))] if os.path.isdir(carpeta) else []
        if not archivos:
            raise ValueError("Todavia no hay imagenes en output/Chroma. Genera una primero en 'Texto a imagen'.")
        ruta = max(archivos, key=os.path.getmtime)
        logging.info("[Chroma] Referencia = ultima imagen: %s", ruta)
        with Image.open(ruta) as im:
            arr = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
        return torch.from_numpy(arr)[None]

    @staticmethod
    def _decodificar(vae, latente):
        img = vae.decode(latente["samples"])
        if len(img.shape) == 5:
            img = img.reshape(-1, img.shape[-3], img.shape[-2], img.shape[-1])
        return img

    @staticmethod
    def _medidas_referencia(imagen, ancho, alto):
        """Mantiene la proporcion de la referencia con los megapixeles de la resolucion elegida."""
        h, w = imagen.shape[1], imagen.shape[2]
        escala = math.sqrt((ancho * alto) / float(w * h))
        return _a_multiplo(w * escala), _a_multiplo(h * escala)

    @staticmethod
    def _preparar_mascara(mascara, ancho, alto, crecer=24, difuminar=24):
        m = mascara.reshape(-1, 1, mascara.shape[-2], mascara.shape[-1])[:1].float()
        m = torch.nn.functional.interpolate(m, size=(alto, ancho), mode="bilinear")
        m = (m > 0.5).float()
        m = torch.nn.functional.max_pool2d(m, 2 * crecer + 1, stride=1, padding=crecer)  # agranda el borde
        m = torch.nn.functional.avg_pool2d(m, 2 * difuminar + 1, stride=1, padding=difuminar, count_include_pad=False)
        return m.clamp(0, 1)

    def generar(self, model, clip, vae, ajustes, upscaler, imagen_referencia=None, info_loras=None, mascara=None,
                control=None, detallador=None, comparador=None):
        a = dict(ajustes)
        if info_loras:
            if info_loras["palabras"]:
                a["prompt"] = ", ".join(info_loras["palabras"]) + ". " + a["prompt"]
            if info_loras["flash"]:
                # el LoRA Flash esta destilado para CFG 1 y pocos pasos
                a["cfg"], a["pasos"] = 1.0, min(a["pasos"], 12)
                logging.info("[Chroma] Modo rapido Flash: CFG 1, %d pasos", a["pasos"])
        if not a["prompt"].strip():
            raise ValueError("El prompt esta vacio: escribe algo en el Panel o activa Botones de prompt.")
        logging.info("[Chroma] Prompt final: %s", a["prompt"])
        if a["escalado"] != ESCALADO_NO and upscaler == NINGUNO:
            raise ValueError("Elegiste escalado pero el Motor Chroma no tiene 'upscaler'. Elige uno o pon escalado = No.")

        model = ModelSamplingAuraFlow().patch_aura(model, 1.0)[0]  # shift 1.0 = el del autor de Chroma
        pos_base = self._codificar(clip, a["prompt"])
        neg_base = self._codificar(clip, a["negativo"])
        positivo, negativo = aplicar_control(control, pos_base, neg_base, vae)

        if a["referencia"]:
            if a.get("ultima"):
                imagen_referencia = self._ultima_imagen()
            if imagen_referencia is None:
                raise ValueError("Modo 'Imagen de referencia' pero no hay imagen conectada.")
            a["ancho"], a["alto"] = self._medidas_referencia(imagen_referencia, a["ancho"], a["alto"])
            if a.get("inpaint") and (mascara is None or float(mascara.max()) <= 0):
                raise ValueError("Modo Inpaint: pinta la zona a cambiar en Load Image (clic derecho > Open in MaskEditor).")

        ctx = dict(model=model, vae=vae, upscaler=upscaler, positivo=positivo, negativo=negativo,
                   pos_base=pos_base, neg_base=neg_base, referencia=imagen_referencia, mascara=mascara,
                   detallador=detallador)
        if not comparador or not comparador.get("activo"):
            return (self._una_imagen(a, ctx), a["prompt"])

        imagenes, etiquetas = [], []
        for v in comparador["valores"]:
            variante = dict(a, **{comparador["clave"]: v})
            logging.info("[Chroma] Comparador: %s = %s", comparador["parametro"], v)
            imagenes.append(self._una_imagen(variante, ctx))
            etiquetas.append(f"{comparador['parametro']} = {v}")
        return (cuadricula(imagenes, etiquetas), a["prompt"])

    def _una_imagen(self, a, c):
        model, vae = c["model"], c["vae"]

        def muestrear(latente, pasos, denoise, positivo=None, negativo=None):
            return nodes.common_ksampler(model, a["semilla"], pasos, a["cfg"], a["sampler"], a["scheduler"],
                                         positivo or c["positivo"], negativo or c["negativo"], latente,
                                         denoise=denoise)[0]

        if a["referencia"]:
            pix = self._redimensionar(c["referencia"][:1], a["ancho"], a["alto"])
            latente = {"samples": vae.encode(pix)}
            if a.get("inpaint"):
                m = self._preparar_mascara(c["mascara"], a["ancho"], a["alto"])
                latente["noise_mask"] = m
        else:
            latente = self._latente_vacio(a["ancho"], a["alto"])

        imagen = self._decodificar(vae, muestrear(latente, a["pasos"], a["denoise"]))
        if a.get("inpaint"):
            # fuera de la zona pintada se conserva la imagen original exacta
            mm = m.movedim(1, -1).to(imagen)
            imagen = pix.to(imagen) * (1 - mm) + imagen * mm

        if a["escalado"] != ESCALADO_NO:
            modelo_esc = UpscaleModelLoader.execute(c["upscaler"]).result[0]
            grande = ImageUpscaleWithModel.execute(modelo_esc, imagen).result[0]
            factor = 2.0 if a["escalado"] == ESCALADO_RAPIDO else 1.5
            imagen = self._redimensionar(grande, _a_multiplo(a["ancho"] * factor), _a_multiplo(a["alto"] * factor))
            if a["escalado"] == ESCALADO_DETALLE:
                # 2a pasada: redibuja detalles finos sobre la imagen escalada
                latente = muestrear({"samples": vae.encode(imagen)}, max(8, math.ceil(a["pasos"] * 0.6)), a["fuerza_detalle"])
                imagen = self._decodificar(vae, latente)

        d = c["detallador"]
        if d and (d["caras"] or d["manos"]):
            # caras y manos al final, sobre la imagen ya escalada; sin ControlNet (el mapa no corresponde al recorte)
            pasos = max(10, math.ceil(a["pasos"] * 0.6))

            def redibujar(recorte):
                lat = muestrear({"samples": vae.encode(recorte)}, pasos, d["fuerza"], c["pos_base"], c["neg_base"])
                return self._decodificar(vae, lat)

            for activo, archivo, nombre in ((d["caras"], YOLO_CARA, "caras"), (d["manos"], YOLO_MANO, "manos")):
                if activo:
                    cajas = detectar(imagen, archivo, d["confianza"])
                    logging.info("[Chroma] Detallador: %d %s", len(cajas), nombre)
                    imagen = detallar(imagen, cajas, redibujar, d["lado"])
        return imagen

NODE_CLASS_MAPPINGS = {
    "ChromaPanel": ChromaPanel,
    "ChromaEtiquetas": ChromaEtiquetas,
    "ChromaControl": ChromaControl,
    "ChromaDetallador": ChromaDetallador,
    "ChromaComparador": ChromaComparador,
    "ChromaRetoque": ChromaRetoque,
    "ChromaLoras": ChromaLoras,
    "ChromaMotor": ChromaMotor,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ChromaPanel": "Panel Chroma",
    "ChromaEtiquetas": "Botones de prompt Chroma",
    "ChromaControl": "ControlNet Chroma (pose / profundidad / bordes)",
    "ChromaDetallador": "Detallador de caras y manos",
    "ChromaComparador": "Comparador de ajustes (cuadricula)",
    "ChromaRetoque": "Retoque final (nitidez, grano, color)",
    "ChromaLoras": "LoRAs Chroma",
    "ChromaMotor": "Motor Chroma",
}

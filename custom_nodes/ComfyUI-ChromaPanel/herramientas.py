"""
Herramientas de calidad para Chroma:
  - Detallador : detecta caras y manos (YOLO), las redibuja en alta resolucion y las pega.
  - Comparador : misma semilla, varios valores de un ajuste -> cuadricula etiquetada.
  - Retoque    : nitidez, grano de pelicula, vineta, saturacion y temperatura.
"""

import logging
import math
import os

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

import comfy.samplers
import comfy.utils
import folder_paths

YOLO_DIR = os.path.join(folder_paths.models_dir, "ultralytics", "bbox")
YOLO_CARA = "face_yolov8m.pt"
YOLO_MANO = "hand_yolov8s.pt"

_yolo = {}


def _a16(v):
    return max(16, int(round(v / 16.0)) * 16)


def _redim(img, w, h):
    s = img.movedim(-1, 1)
    s = comfy.utils.common_upscale(s, w, h, "lanczos", "disabled")
    return s.movedim(1, -1).clamp(0, 1)


# --------------------------------------------------------------------------- detallador
def detectar(imagen, archivo, confianza):
    ruta = os.path.join(YOLO_DIR, archivo)
    if not os.path.exists(ruta):
        logging.warning("[Chroma] Falta el detector %s (vuelve a ejecutar INSTALAR.bat); se omite.", archivo)
        return []
    os.environ.setdefault("YOLO_OFFLINE", "1")
    from ultralytics import YOLO  # import diferido: si falta, el resto del pack sigue funcionando
    if ruta not in _yolo:
        _yolo[ruta] = YOLO(ruta)
    pil = Image.fromarray((imagen[0, :, :, :3].detach().clamp(0, 1).float().cpu().numpy() * 255).astype(np.uint8))
    res = _yolo[ruta](pil, conf=confianza, verbose=False)[0]
    return [tuple(map(float, b)) for b in res.boxes.xyxy.tolist()]


def _mascara_suave(h, w, borde=0.18):
    """1 en el centro, baja suavemente a 0 en los bordes del recorte."""
    yy = torch.linspace(0, 1, h)[:, None].expand(h, w)
    xx = torch.linspace(0, 1, w)[None, :].expand(h, w)
    d = torch.minimum(torch.minimum(xx, 1 - xx), torch.minimum(yy, 1 - yy))
    return (d / borde).clamp(0, 1)[None, :, :, None]


def detallar(imagen, cajas, redibujar, lado=1024, margen=1.6):
    """redibujar(recorte_ampliado) -> recorte redibujado del mismo tamano."""
    img = imagen.clone()
    H, W = img.shape[1], img.shape[2]
    for (x0, y0, x1, y1) in cajas:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        lado_caja = max(x1 - x0, y1 - y0) * margen
        rx0, ry0 = int(max(0, cx - lado_caja / 2)), int(max(0, cy - lado_caja / 2))
        rx1, ry1 = int(min(W, cx + lado_caja / 2)), int(min(H, cy + lado_caja / 2))
        if rx1 - rx0 < 8 or ry1 - ry0 < 8:
            continue
        recorte = img[:, ry0:ry1, rx0:rx1, :3]
        h, w = recorte.shape[1], recorte.shape[2]
        esc = lado / float(max(h, w))
        grande = _redim(recorte, _a16(w * esc), _a16(h * esc))
        nuevo = _redim(redibujar(grande), w, h).to(img)
        m = _mascara_suave(h, w).to(img)
        img[:, ry0:ry1, rx0:rx1, :3] = recorte * (1 - m) + nuevo * m
    return img


class ChromaDetallador:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "caras": ("BOOLEAN", {"default": True, "label_on": "ACTIVADO", "label_off": "apagado"}),
            "manos": ("BOOLEAN", {"default": False, "label_on": "ACTIVADO", "label_off": "apagado"}),
            "fuerza": ("FLOAT", {"default": 0.4, "min": 0.1, "max": 0.8, "step": 0.05, "display": "slider",
                                 "tooltip": "Cuanto se redibuja. 0.3-0.45: mejora sin cambiar la identidad."}),
            "confianza": ("FLOAT", {"default": 0.35, "min": 0.1, "max": 0.9, "step": 0.05,
                                    "tooltip": "Seguridad minima de la deteccion. Sube si detecta cosas que no son caras."}),
            "resolucion": ([768, 1024], {"default": 1024, "tooltip": "Tamano al que se redibuja cada cara/mano."}),
        }}

    RETURN_TYPES = ("CHROMA_DETALLE",)
    RETURN_NAMES = ("detallador",)
    FUNCTION = "armar"
    CATEGORY = "Chroma"
    DESCRIPTION = "Redibuja caras y manos en alta resolucion (lo que hacen los workflows grandes con FaceDetailer)."

    def armar(self, caras, manos, fuerza, confianza, resolucion):
        return ({"caras": caras, "manos": manos, "fuerza": fuerza, "confianza": confianza, "lado": int(resolucion)},)


# --------------------------------------------------------------------------- comparador
PARAMETROS = ["cfg", "pasos", "sampler", "scheduler", "semilla", "fuerza_referencia"]


class ChromaComparador:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "activar": ("BOOLEAN", {"default": False, "label_on": "ACTIVADO", "label_off": "apagado"}),
            "parametro": (PARAMETROS, {"default": "cfg"}),
            "valores": ("STRING", {"default": "3, 4, 5", "tooltip": "Separados por coma. Ej. cfg: 3, 4, 5 | sampler: euler, res_2s | semilla: 1, 2, 3, 4"}),
        }}

    RETURN_TYPES = ("CHROMA_COMPARAR",)
    RETURN_NAMES = ("comparador",)
    FUNCTION = "armar"
    CATEGORY = "Chroma"
    DESCRIPTION = "Genera la misma imagen variando un ajuste y las pone en una cuadricula con etiquetas."

    def armar(self, activar, parametro, valores):
        if not activar:
            return ({"activo": False},)
        vals = [v.strip() for v in valores.split(",") if v.strip()]
        if not vals:
            raise ValueError("Comparador: escribe al menos un valor.")
        conv = {"cfg": float, "fuerza_referencia": float, "pasos": int, "semilla": int}.get(parametro, str)
        validos = {"sampler": comfy.samplers.KSampler.SAMPLERS, "scheduler": comfy.samplers.KSampler.SCHEDULERS}.get(parametro)
        salida = []
        for v in vals:
            if validos is not None and v not in validos:
                raise ValueError(f"Comparador: '{v}' no es un {parametro} valido.")
            salida.append(conv(v))
        clave = {"fuerza_referencia": "denoise"}.get(parametro, parametro)
        return ({"activo": True, "parametro": parametro, "clave": clave, "valores": salida},)


def cuadricula(imagenes, etiquetas):
    n = len(imagenes)
    cols = min(n, 4 if n > 4 else n)
    filas = math.ceil(n / cols)
    h, w = imagenes[0].shape[1], imagenes[0].shape[2]
    franja = max(28, h // 24)
    lienzo = Image.new("RGB", (cols * w, filas * (h + franja)), (20, 20, 20))
    dibujo = ImageDraw.Draw(lienzo)
    try:
        fuente = ImageFont.load_default(size=int(franja * 0.7))
    except TypeError:
        fuente = ImageFont.load_default()
    for i, (im, et) in enumerate(zip(imagenes, etiquetas)):
        im = _redim(im[:1], w, h) if (im.shape[1], im.shape[2]) != (h, w) else im[:1]
        x, y = (i % cols) * w, (i // cols) * (h + franja)
        lienzo.paste(Image.fromarray((im[0, :, :, :3].detach().clamp(0, 1).float().cpu().numpy() * 255).astype(np.uint8)), (x, y + franja))
        dibujo.text((x + 8, y + 2), et, fill=(255, 220, 120), font=fuente)
    return torch.from_numpy(np.asarray(lienzo, dtype=np.float32) / 255.0)[None]


# --------------------------------------------------------------------------- retoque
class ChromaRetoque:
    @classmethod
    def INPUT_TYPES(cls):
        def barra(d, lo, hi, tip):
            return ("FLOAT", {"default": d, "min": lo, "max": hi, "step": 0.05, "display": "slider", "tooltip": tip})
        return {"required": {
            "imagen": ("IMAGE",),
            "activar": ("BOOLEAN", {"default": True, "label_on": "ACTIVADO", "label_off": "apagado"}),
            "nitidez": barra(0.3, 0.0, 1.0, "Enfoque suave tipo camara."),
            "grano": barra(0.15, 0.0, 1.0, "Grano de pelicula/sensor: quita el aspecto 'plastico' de la IA."),
            "vineta": barra(0.1, 0.0, 1.0, "Oscurece un poco las esquinas."),
            "saturacion": barra(1.0, 0.5, 1.5, "1 = igual."),
            "temperatura": barra(0.0, -1.0, 1.0, "Negativo = mas frio/azul, positivo = mas calido."),
        }}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "retocar"
    CATEGORY = "Chroma"
    DESCRIPTION = "Retoque final para que parezca una foto de camara real."

    def retocar(self, imagen, activar, nitidez, grano, vineta, saturacion, temperatura):
        if not activar:
            return (imagen,)
        x = imagen[..., :3].clone().float()
        if nitidez > 0:
            s = x.movedim(-1, 1)
            k = torch.tensor([1.0, 4.0, 6.0, 4.0, 1.0])
            k = (k[:, None] * k[None, :]) / 256.0
            k = k.to(s)[None, None].repeat(3, 1, 1, 1)
            borrosa = torch.nn.functional.conv2d(torch.nn.functional.pad(s, (2, 2, 2, 2), mode="replicate"), k, groups=3)
            x = (s + nitidez * 1.5 * (s - borrosa)).movedim(1, -1)
        if saturacion != 1.0:
            gris = (x * torch.tensor([0.299, 0.587, 0.114]).to(x)).sum(-1, keepdim=True)
            x = gris + (x - gris) * saturacion
        if temperatura != 0:
            x = x * torch.tensor([1 + 0.08 * temperatura, 1.0, 1 - 0.08 * temperatura]).to(x)
        if vineta > 0:
            h, w = x.shape[1], x.shape[2]
            yy = torch.linspace(-1, 1, h)[:, None]
            xx = torch.linspace(-1, 1, w)[None, :]
            r = torch.sqrt(xx ** 2 + yy ** 2) / math.sqrt(2)
            x = x * (1 - vineta * 0.6 * r ** 2).to(x)[None, :, :, None]
        if grano > 0:
            g = torch.Generator().manual_seed(1234)
            ruido = torch.randn(x.shape[:3] + (1,), generator=g).to(x)
            x = x + ruido * grano * 0.04
        return (x.clamp(0, 1),)

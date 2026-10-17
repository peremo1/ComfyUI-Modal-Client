"""
Informe para copiar: junta TODOS los ajustes del workflow (cada nodo y sus valores) con lo que
hizo el Motor (tamanos, detecciones, tiempos, VRAM, prompt final). El boton 'Copiar informe'
lo deja en el portapapeles para pegarlo en el chat. Tambien se guarda en output/Chroma/informes.
"""

import datetime
import os

import folder_paths

# no aportan nada al informe
OMITIR = {"MarkdownNote", "Note", "PreviewImage", "PreviewAny", "ChromaInforme"}
LARGO_MAX = 600


def _valor(v):
    if isinstance(v, list):  # enlace a otro nodo
        return None
    if isinstance(v, float):
        return f"{v:g}"
    v = str(v)
    return v if len(v) <= LARGO_MAX else v[:LARGO_MAX] + f"... ({len(v)} caracteres)"


def ajustes_del_workflow(prompt):
    lineas = ["== AJUSTES DEL WORKFLOW =="]
    for nid in sorted(prompt or {}, key=lambda k: int(k) if str(k).isdigit() else 0):
        nodo = prompt[nid]
        clase = nodo.get("class_type", "?")
        if clase in OMITIR:
            continue
        titulo = (nodo.get("_meta") or {}).get("title") or clase
        valores = []
        for k, v in (nodo.get("inputs") or {}).items():
            t = _valor(v)
            if t is None:
                continue
            if isinstance(v, bool) and not v and clase in ("ChromaEtiquetas", "ChromaLoras"):
                continue  # en botones y LoRAs solo interesa lo que esta encendido
            if clase == "ChromaLoras" and k.startswith("fuerza ") and not _lora_activo(nodo["inputs"], k):
                continue
            if clase == "ChromaEtiquetas" and t == "-":
                continue
            valores.append(f"{k}={t}")
        lineas.append(f"[{titulo}] " + (" | ".join(valores) if valores else "(sin ajustes)"))
    return lineas


def _lora_activo(inputs, clave_fuerza):
    # 'fuerza realismo_lenovo' -> busca el interruptor con la misma clave en el catalogo
    from . import _catalogo
    clave = clave_fuerza[len("fuerza "):]
    for e in _catalogo()["loras"]:
        if e["clave"] == clave:
            return bool(inputs.get(e["etiqueta"]))
    return True


class ChromaInforme:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"informe": ("STRING", {"forceInput": True})},
            "hidden": {"prompt": "PROMPT"},
        }

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "mostrar"
    CATEGORY = "Chroma"
    DESCRIPTION = "Informe completo de la ultima generacion, con boton para copiarlo y pegarlo en el chat."

    def mostrar(self, informe, prompt=None):
        texto = "\n".join([f"INFORME CHROMA - {datetime.datetime.now():%Y-%m-%d %H:%M:%S}", ""]
                          + ajustes_del_workflow(prompt) + ["", informe])
        carpeta = os.path.join(folder_paths.get_output_directory(), "Chroma", "informes")
        os.makedirs(carpeta, exist_ok=True)
        with open(os.path.join(carpeta, f"informe_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt"), "w", encoding="utf-8") as f:
            f.write(texto)
        return {"ui": {"informe": [texto]}}

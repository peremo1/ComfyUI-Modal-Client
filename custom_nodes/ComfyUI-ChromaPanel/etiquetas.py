"""
Botones de prompt: etiquetas en espanol que escriben el prompt en ingles por ti.
Cada interruptor o menu anade una frase; si lo apagas, la frase desaparece.
"""

NADA = "-"

SUJETOS = {
    "SUJETO mujer desnuda": "a completely naked adult woman with no clothes on",
    "SUJETO hombre desnudo": "a completely naked adult man with no clothes on, bare chest",
    "SUJETO futanari": "a completely naked adult futanari woman with a feminine body and breasts, and a penis with testicles instead of a vagina",
    "SUJETO pareja (hombre y mujer)": "a completely naked adult couple, a man and a woman, together, with no clothes on",
}

EDAD = {NADA: "", "20 a 29": "in their twenties", "30 a 39": "in their thirties",
        "40 a 49": "in their forties", "50 o mas": "in their fifties"}
CUERPO = {NADA: "", "delgado": "a slim build", "atletico": "an athletic, toned build", "curvilineo": "a curvy hourglass figure",
          "rellenito": "a soft, chubby body", "musculoso": "a muscular, fit body"}
PECHOS = {NADA: "", "planos": "a flat chest", "pequenos": "small natural breasts", "medianos": "medium natural breasts",
          "grandes": "large natural breasts", "muy grandes": "very large heavy natural breasts"}
PENE = {NADA: "", "pequeno": "a small penis", "promedio": "an average-sized penis", "grande": "a large penis",
        "muy grande": "a very large, thick penis"}
PIEL = {NADA: "", "clara": "fair pale skin", "bronceada": "tanned skin", "morena": "olive brown skin", "oscura": "dark skin"}
PELO_COLOR = {NADA: "", "rubio": "blonde", "castano": "brown", "negro": "black", "pelirrojo": "red", "rosa/fantasia": "pastel pink"}
PELO_LARGO = {NADA: "", "corto": "short", "media melena": "shoulder-length", "largo": "long", "muy largo": "very long"}
VELLO = {NADA: "", "depilado": "a shaved pubic area", "recortado": "trimmed pubic hair", "natural": "natural pubic hair"}

DETALLES = {
    "DETALLE pene erecto": "the penis is erect",
    "DETALLE pecas": "freckles",
    "DETALLE tatuajes": "a few tasteful tattoos",
    "DETALLE piercings": "nipple and navel piercings",
    "DETALLE piel sudada/brillante": "glistening, slightly sweaty skin",
}

ROPA = {
    "ROPA lenceria": "lace lingerie",
    "ROPA medias": "sheer thigh-high stockings",
    "ROPA ligueros": "a garter belt",
    "ROPA tacones": "high heels",
    "ROPA bikini": "a skimpy bikini",
    "ROPA camisa abierta": "an unbuttoned shirt, open in the front",
    "ROPA toalla": "a towel loosely wrapped around the body",
    "ROPA collar y joyas": "a delicate necklace and earrings",
}

POSES = {
    "POSE de pie": "standing",
    "POSE sentada": "sitting",
    "POSE acostada": "lying on the bed",
    "POSE de espaldas": "seen from behind, looking over the shoulder",
    "POSE en cuatro": "on all fours",
    "POSE piernas abiertas": "with legs spread",
    "POSE mirando a camara": "looking directly at the camera",
    "POSE selfie en espejo": "taking a mirror selfie with a smartphone",
}

LUGAR = {NADA: "", "dormitorio": "in a cozy bedroom", "bano/ducha": "in a steamy bathroom shower",
         "playa": "on a sunny beach", "sofa/salon": "on a couch in a living room", "naturaleza": "outdoors in nature",
         "estudio fotografico": "in a professional photo studio with a plain backdrop", "hotel de lujo": "in a luxury hotel room",
         "piscina": "by a swimming pool", "cocina": "in a modern kitchen"}
LUZ = {NADA: "", "natural de ventana": "soft natural window light", "hora dorada": "warm golden hour sunlight",
       "neon nocturno": "colorful neon lights at night", "estudio suave": "soft diffused studio lighting",
       "velas": "warm candlelight", "flash directo": "direct on-camera flash"}
FOTO = {NADA: "", "amateur/movil": "amateur smartphone photo, unfiltered, real life",
        "profesional": "professional photoshoot, shot on a full-frame camera with an 85mm lens, shallow depth of field",
        "cinematografica": "cinematic film still, 35mm film grain"}
CAMARA = {NADA: "", "frontal a la altura de los ojos": "eye-level shot, facing the camera",
          "desde arriba (picado)": "high-angle shot, camera looking down from above",
          "desde abajo (contrapicado)": "low-angle shot, camera looking up from below",
          "cenital (vista desde el techo)": "overhead top-down shot, bird's-eye view",
          "de perfil (lateral)": "side view, profile shot", "tres cuartos": "three-quarter view",
          "desde atras": "rear view, shot from behind", "POV primera persona": "first-person point of view (POV) shot",
          "angulo holandes (inclinado)": "dutch angle, tilted camera"}
LENTE = {NADA: "", "gran angular": "wide-angle lens, 24mm", "normal 50mm": "50mm lens",
         "retrato 85mm": "85mm portrait lens, shallow depth of field", "teleobjetivo": "telephoto lens, compressed background"}
PLANO = {NADA: "", "cuerpo entero": "full body shot", "medio cuerpo": "medium shot from the thighs up",
         "primer plano": "close-up shot"}

NEGATIVOS = {
    "EVITAR ropa": "clothes, clothing, jacket, coat, shirt, pants, underwear",
    "EVITAR otras personas": "extra people, crowd, other people in the background",
    "EVITAR maquillaje fuerte": "heavy makeup",
    "EVITAR tatuajes": "tattoos",
    "EVITAR vello corporal": "body hair",
}

MENUS = [
    ("edad (adulta)", EDAD, "20 a 29"),
    ("cuerpo", CUERPO, NADA),
    ("pechos", PECHOS, NADA),
    ("pene", PENE, NADA),
    ("piel", PIEL, NADA),
    ("pelo color", PELO_COLOR, NADA),
    ("pelo largo", PELO_LARGO, NADA),
    ("vello pubico", VELLO, NADA),
    ("lugar", LUGAR, NADA),
    ("luz", LUZ, NADA),
    ("tipo de foto", FOTO, "amateur/movil"),
    ("plano", PLANO, NADA),
    ("camara angulo", CAMARA, NADA),
    ("camara lente", LENTE, NADA),
]


def _lista(partes):
    partes = [p for p in partes if p]
    if len(partes) <= 1:
        return "".join(partes)
    return ", ".join(partes[:-1]) + " and " + partes[-1]


class ChromaEtiquetas:
    @classmethod
    def INPUT_TYPES(cls):
        req = {}
        for k in SUJETOS:
            req[k] = ("BOOLEAN", {"default": k == "SUJETO mujer desnuda", "label_on": "SI", "label_off": "no"})
        menus = dict((n, (list(d.keys()), {"default": dflt})) for n, d, dflt in MENUS)
        for n in ["edad (adulta)", "cuerpo", "pechos", "pene", "piel", "pelo color", "pelo largo", "vello pubico"]:
            req[n] = menus[n]
        for grupo in (DETALLES, ROPA, POSES):
            for k in grupo:
                req[k] = ("BOOLEAN", {"default": False, "label_on": "SI", "label_off": "no"})
        for n in ["lugar", "luz", "tipo de foto", "plano", "camara angulo", "camara lente"]:
            req[n] = menus[n]
        for k in NEGATIVOS:
            req[k] = ("BOOLEAN", {"default": False, "label_on": "SI", "label_off": "no"})
        return {"required": req}

    RETURN_TYPES = ("CHROMA_ETIQUETAS", "STRING")
    RETURN_NAMES = ("etiquetas", "prompt_generado")
    FUNCTION = "construir"
    CATEGORY = "Chroma"
    DESCRIPTION = "Botones de prompt en espanol. Se suman al texto libre del Panel Chroma."

    def construir(self, **kw):
        sujetos = [v for k, v in SUJETOS.items() if kw[k]]
        rasgos = [CUERPO[kw["cuerpo"]], PECHOS[kw["pechos"]], PENE[kw["pene"]], PIEL[kw["piel"]], VELLO[kw["vello pubico"]]]
        if kw["pelo color"] != NADA or kw["pelo largo"] != NADA:
            rasgos.append(" ".join(p for p in (PELO_LARGO[kw["pelo largo"]], PELO_COLOR[kw["pelo color"]]) if p) + " hair")
        rasgos += [v for k, v in DETALLES.items() if kw[k]]

        frases = []
        if sujetos:
            s = "A photograph of " + _lista(sujetos)
            if EDAD[kw["edad (adulta)"]]:
                s += ", " + EDAD[kw["edad (adulta)"]]
            if any(rasgos):
                s += ", with " + _lista(rasgos)
            frases.append(s)
        elif any(rasgos):
            frases.append("With " + _lista(rasgos))
        ropa = [v for k, v in ROPA.items() if kw[k]]
        if ropa:
            frases.append("Wearing " + _lista(ropa))
        poses = [v for k, v in POSES.items() if kw[k]]
        if poses:
            frases.append(_lista(poses).capitalize())
        for n, d in (("lugar", LUGAR), ("luz", LUZ), ("plano", PLANO), ("camara angulo", CAMARA), ("camara lente", LENTE), ("tipo de foto", FOTO)):
            if d[kw[n]]:
                frases.append(d[kw[n]][0].upper() + d[kw[n]][1:])
        positivo = ". ".join(frases) + ("." if frases else "")
        negativo = ", ".join(v for k, v in NEGATIVOS.items() if kw[k])
        return ({"positivo": positivo, "negativo": negativo}, positivo)

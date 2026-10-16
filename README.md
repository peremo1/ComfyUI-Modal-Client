# ComfyUI + Chroma1-HD: instalador local para Windows

Instalador de un clic que deja ComfyUI listo para generar imágenes con **Chroma1-HD** en tu propia PC, pensado para una **RTX 3060 de 12 GB** con 32 GB de RAM. No usa la nube, así que no hay arranque en frío: el modelo se carga una sola vez y después cada imagen sale directo.

## Qué instala

| Componente | Versión / archivo | Notas |
|---|---|---|
| ComfyUI portable (NVIDIA) | **v0.41.0** | Incluye Python 3.13 y PyTorch cu130 |
| ComfyUI-Manager | el que fija esa versión (`manager_requirements.txt`) | Se activa con `--enable-manager` |
| Visual C++ Redistributable | 2015-2022 x64 | Solo si te falta o está desactualizado |
| Triton + SageAttention | `triton-windows` según tu PyTorch + `sageattention==1.0.6` | Optimizador **opcional**. El instalador lo prueba en tu GPU y solo lo activa si funciona |
| Modelo | `Chroma1-HD-fp8mixed.safetensors` (8,6 GB) | Versión fp8 oficial de Comfy-Org, cabe en 12 GB |
| Codificador de texto | `t5xxl_fp8_e4m3fn_scaled.safetensors` (4,8 GB) | |
| VAE | `ae.safetensors` (0,3 GB) | |
| Panel Chroma (nodos propios) | `custom_nodes/ComfyUI-ChromaPanel` | Botones de prompt, panel de control, LoRAs con interruptor y barra, y un motor con escalado |
| Upscaler | `4x_foolhardy_Remacri.safetensors` (67 MB) | Para el escalado x2 / x1.5 |
| Pack de LoRAs | 12 LoRAs, unos 3,4 GB (`catalogo.json`) | Verificados con SHA256 |
| Modelos alternativos (opcional) | UnCanny v1.3 fp8, GonzaLomo v3 fp8 | 8,5 GB cada uno |
| Workflows | `Chroma_0_Panel` (recomendado), `Chroma_1_TextoAImagen`, `Chroma_2_ImagenReferencia` | Basados en la plantilla oficial de Chroma de ComfyUI |

Necesitas unos **40 GB libres**. Instálalo en el SSD (C:), no en el disco HDD.

## Requisitos

- Windows 10/11 de 64 bits y una GPU NVIDIA.
- **Driver NVIDIA 580 o superior**, porque el PyTorch del portable usa CUDA 13. Si tu driver es más antiguo, el instalador se detiene y te avisa.

## Instalación

1. Descarga este repo (*Code → Download ZIP*) y descomprímelo.
2. Haz doble clic en **`INSTALAR.bat`**.
   - Por defecto instala en `C:\IA`. Para usar otra carpeta, ejecuta `INSTALAR.bat D:\IA` desde una consola.
   - Windows te pedirá permiso de administrador solo si tiene que instalar Visual C++.
3. Espera a que termine. Se descargan unos 20 GB; si se corta, vuelve a ejecutarlo y continúa donde quedó.
4. Abre **"ComfyUI Chroma"** desde el escritorio. Se abre el navegador en `http://127.0.0.1:8188`.
5. En el panel izquierdo, abre **Workflows** y elige uno de los dos.

Opciones avanzadas (ejecútalas desde PowerShell en la carpeta del repo):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -InstallDir "D:\IA" -SinSage      # sin optimizador
powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -SinModelos                       # si ya tienes los modelos
```

## Workflow recomendado: `Chroma_0_Panel`

Todo está en el bloque **CONTROL**:

### 1. Botones de prompt (azul)
Interruptores y menús en español que escriben el prompt en inglés por ti: sujeto (mujer, hombre, futanari, pareja), edad adulta, cuerpo, pechos, pene, piel, pelo, ropa, poses, lugar, luz, tipo de foto y plano, más casillas para el negativo ("evitar ropa", "evitar otras personas"…). Abajo a la derecha, **"Prompt final"** muestra exactamente el texto en inglés que recibió Chroma.

### 2. Panel de control (amarillo)
| Ajuste | Qué hace |
|---|---|
| **modo** | *Texto a imagen* o *Imagen de referencia (img2img)* |
| **prompt / negativo** | Texto libre que se suma a los botones. El negativo genérico de realismo ya viene escrito |
| **resolucion** | Plantillas: retrato 2:3, 3:4 o 9:16; cuadrado; paisaje 3:2, 4:3 o 16:9; dos tamaños *Rápido* para pruebas; *Personalizado* |
| **semilla** | `randomize` = una distinta cada vez; `fixed` = repetir |
| **escalado** | *No*, *Rápido x2* o *Detallado x1.5* (con una segunda pasada que redibuja detalles) |

**Varias imágenes seguidas:** cambia el número junto al botón **Run** (por ejemplo, 8).

### 3. LoRAs (interruptor + barra)
| LoRA | Para qué | Palabra clave (se añade sola) |
|---|---|---|
| Lenovo UltraReal | Realismo de foto real (activado por defecto) | `l3n0v0` |
| GOONTUNE | Realismo NSFW | |
| Foto profesional | Calidad de sesión de fotos | |
| NSFW Realism | Escenas sexuales concretas | |
| Tamaño de pene | **Slider**: -2 = pequeño, +2 = grande | |
| COCKTASTIC | Detalle de pene (en pruebas, solo Civitai) | |
| Pezones erectos / Areolas grandes | Detalle anatómico | `erect nipples` / `big areolas nipples` |
| Vulva cerrada (innie) | Detalle anatómico | `cleft of venus` |
| Deepthroat | Acto concreto (solo Civitai) | `dprthrt` |
| Futanari (Flux, experimental) | Hecho para Flux; en Chroma funciona a medias (solo Civitai) | `futanari girl got a penis` |
| **MODO RÁPIDO (Flash)** | 2-3 veces más rápido: pone CFG 1 y 12 pasos solo; el negativo deja de funcionar | |

Hay además **2 huecos libres** para cualquier LoRA de Chroma que pongas en `ComfyUI\models\loras` (pulsa **R** en ComfyUI para refrescar la lista).

El instalador descarga el pack (unos 3,4 GB) desde copias en Hugging Face y **verifica cada archivo con su SHA256** del original. Los 3 LoRAs que solo están en Civitai necesitan tu API key de Civitai; el instalador te la pide y la guarda solo en tu PC (`C:\IA\civitai_api_key.txt`). También puedes saltarlos pulsando Enter.

### 4. Modelo
El nodo **MODELO** permite elegir entre:
- **Chroma1-HD**: el modelo oficial.
- **UnCanny v1.3**: más fotorrealista; 30-40 pasos, CFG 3,5.
- **GonzaLomo v3**: rápido; 8-14 pasos, CFG 1-1,3.

Los dos alternativos son opcionales: el instalador pregunta si quieres bajarlos (8,5 GB cada uno).

## Workflows sencillos

### 1. `Chroma_1_TextoAImagen`: texto a imagen
- Escribe el prompt en **inglés y en frases completas**. Chroma entiende descripciones largas: sujeto, ropa, pose, lugar, luz y tipo de foto.
- CFG entre 3,5 y 4,5, unos 26 pasos, sampler `euler` con scheduler `beta`.
- Tamaños: 1024×1024, 832×1216 (vertical) o 1216×832 (horizontal).

### 2. `Chroma_2_ImagenReferencia`: imagen de referencia / img2img
- Sube tu imagen en **Load Image**. Se reescala sola a unos 1 MP.
- El **denoise** del nodo `BasicScheduler` decide cuánto cambia la imagen:
  - **0,30-0,45**: retoque leve, mantiene la pose y la composición.
  - **0,55-0,70**: mantiene la composición y cambia ropa, estilo o detalles. Es el valor recomendado.
  - **0,75-0,90**: la referencia solo sirve como guía de colores y formas.

Las imágenes se guardan en `C:\IA\ComfyUI_windows_portable\ComfyUI\output\Chroma\`.

## Rendimiento esperado (RTX 3060 12 GB)

- La primera imagen tarda más porque carga el modelo desde el disco.
- Después, unos **60-120 s** por imagen a 1024×1024 con 26 pasos.
- Si te quedas sin memoria (OOM), baja la resolución o cierra programas que usen la GPU, como el navegador con vídeos o los juegos.

## Problemas comunes

| Síntoma | Solución |
|---|---|
| `c10.dll` o un error al iniciar | Instala [VC++ Redist](https://aka.ms/vs/17/release/vc_redist.x64.exe) y actualiza el driver NVIDIA |
| "driver NVIDIA ... necesita 580" | Actualiza el driver desde nvidia.com o la app de NVIDIA |
| Se cortó una descarga | Vuelve a ejecutar `INSTALAR.bat`; reanuda la descarga |
| Errores con SageAttention | Edita `C:\IA\INICIAR_ComfyUI_Chroma.bat` y quita `--use-sage-attention` |

## Uso responsable

Usa solo personajes ficticios adultos o personas que te hayan dado su consentimiento. Generar imágenes sexuales de personas reales sin su consentimiento, o cualquier contenido sexual que involucre a menores, es ilegal.

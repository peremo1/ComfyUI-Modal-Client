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
| Panel Chroma (nodos propios) | `custom_nodes/ComfyUI-ChromaPanel` | Panel de control, 4 LoRAs y un motor con escalado |
| Upscaler | `4x_foolhardy_Remacri.safetensors` (67 MB) | Para el escalado x2 / x1.5 |
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

Todo se controla desde un único **PANEL DE CONTROL** (el bloque amarillo):

| Ajuste | Qué hace |
|---|---|
| **modo** | *Texto a imagen* o *Imagen de referencia (img2img)*, que usa la imagen cargada al lado |
| **prompt / negativo** | El negativo ya viene con uno genérico para realismo |
| **resolucion** | Plantillas: retrato 2:3, 3:4, 9:16, cuadrado, paisaje 3:2, 4:3, 16:9, dos tamaños *Rápido* para probar prompts y *Personalizado* (usa ancho y alto) |
| **semilla** | `randomize` da una distinta en cada imagen; `fixed` repite la misma |
| **pasos / cfg / sampler / scheduler** | Vienen con los valores oficiales de Chroma (26, 4, euler, beta) |
| **fuerza_referencia** | Solo en modo referencia: cuánto cambia la imagen (0,3-0,9) |
| **escalado** | *No*, *Rápido x2* (solo el upscaler, tarda segundos) o *Detallado x1.5* (upscaler más una segunda pasada que redibuja detalles, unos 2-3 min más) |

**Varias imágenes seguidas:** cambia el número que está junto al botón **Run** (por ejemplo, 8) y pulsa Run. Las genera una tras otra, cada una con una semilla nueva si tienes `randomize`.

**LoRAs:** el nodo *LoRAs (opcional)* tiene 4 huecos. Copia los `.safetensors` a `ComfyUI\models\loras`, pulsa **R** en ComfyUI para refrescar la lista y elígelos. Una fuerza de 0,6-1,0 es lo normal; con *Ninguno* el hueco queda desactivado. En Civitai, filtra por el modelo base **Chroma**. Los LoRAs de Flux funcionan solo a veces y los de SDXL o Pony no funcionan.

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

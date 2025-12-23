ComfyUI-Modal-Client ☁️🚀
Ejecuta ComfyUI localmente, procesa en la nube.

Este proyecto es un "puente" (bridge) que conecta tu instalación local de ComfyUI con la plataforma de computación en la nube https://modal.com/. Te permite diseñar tus workflows cómodamente en tu PC y enviarlos a ejecutar en GPUs de alto rendimiento (T4, A10G, A100, H100), descargando los resultados automáticamente de vuelta a tu ordenador.

✨ Características Principales
Interfaz Local, Potencia Nube: Usa tu ComfyUI de siempre. No necesitas configurar interfaces web remotas complejas.

Soporte Multi-GPU: Selecciona dinámicamente entre GPUs económicas (T4) o bestias de rendimiento (H100) desde un panel en ComfyUI.

Gestión de Modelos: Descarga modelos desde HuggingFace directamente al almacenamiento persistente de Modal con un solo clic.

Sincronización Automática: Las imágenes generadas se descargan automáticamente a tu carpeta de salida local.

Estimación de Costos: Visualiza el costo aproximado por hora de la GPU seleccionada.

🛠️ Requisitos Previos
Tener ComfyUI instalado localmente.

Una cuenta en Modal.com.

Una cuenta en HuggingFace (para descargar modelos).

Python instalado en tu sistema.

⚙️ Configuración de Secretos (Importante)
Para que el sistema pueda descargar modelos protegidos o públicos desde HuggingFace dentro de los servidores de Modal, necesitas configurar un Token.

Paso 1: Obtener Token de HuggingFace
Ve a HuggingFace Settings > Tokens.

Haz clic en "Create new token".

Tipo: Read.

Nombre: HF_TOKEN.

Copia el token generado (empieza por hf_...).

Paso 2: Configurar Secreto en Modal
Ve a tu panel de Modal: Modal Secrets.

Haz clic en "Create new secret".

Selecciona "Custom".

Configura los siguientes campos:

Key: HF_TOKEN

Value: (Pega aquí tu token de HuggingFace)

Nombra el secreto (Name) también como HF_TOKEN y guarda.

📥 Instalación
Clonar el repositorio: Ve a la carpeta custom_nodes de tu instalación de ComfyUI y clona este repo:

Bash

cd ComfyUI/custom_nodes/
git clone https://github.com/peremo1/ComfyUI-Modal-Client.git
Instalar dependencias de Python (Lado Cliente): Necesitas instalar las librerías para el puente local.

Bash

pip install modal flask flask-cors requests
Autenticar Modal en tu PC: Si es la primera vez que usas Modal:

Bash

modal setup
🚀 Uso
El sistema consta de dos partes: el servidor en la nube (Modal) y el puente local (Flask).

1. Desplegar/Subir el código a Modal
Primero, asegúrate de que el código del servidor (modal_downloader.py) esté disponible en tu cuenta de Modal. Desde la carpeta del nodo:

Bash

modal deploy server/modal_downloader.py
Esto creará la aplicación comfyui-model-downloader en tu cuenta de Modal.

2. Iniciar el Puente Local
Este script conecta tu ComfyUI con Modal. Debe estar corriendo siempre que quieras usar la extensión.

Bash

python server/comfyui_modal_bridge.py
Verás un mensaje indicando que el servidor corre en http://127.0.0.1:5001.

3. Usar en ComfyUI
Abre ComfyUI en tu navegador.

Verás un nuevo botón "GPU" en la barra lateral. Úsalo para seleccionar qué tarjeta gráfica quieres usar (T4, A10G, etc.).

En el botón de "Queue Prompt" (Ejecutar), despliega el menú y selecciona "Ejecutar en Modal".

¡Listo! El botón cambiará a azul. Al hacer clic, el workflow se enviará a la nube, se procesará y la imagen volverá a tu pantalla.

📂 Arquitectura y Explicación del Código
Para los curiosos, aquí explicamos cómo funciona cada componente del proyecto:

☁️ Backend (Modal)
server/modal_downloader.py: Es el corazón del sistema en la nube.

Define la imagen de Docker con todas las dependencias (PyTorch, ComfyUI, Drivers CUDA).

Crea Volúmenes Persistentes: Uno para guardar modelos (/models) y otro para las salidas (/outputs), así no tienes que descargar los modelos cada vez.

Funciones execute_workflow: Existen funciones específicas para cada tipo de GPU (T4, A100, etc.). Reciben el workflow en formato API JSON, levantan una instancia de ComfyUI "headless" (sin interfaz gráfica) dentro de Modal, ejecutan el trabajo y guardan la imagen.

🌉 Bridge (Puente Local)
server/comfyui_modal_bridge.py: Es un servidor Flask que corre en tu PC (puerto 5001).

Actúa como intermediario. El Javascript del navegador no puede hablar directamente con Modal por seguridad/CORS fácilmente, así que este servidor recibe las peticiones del navegador y usa la librería de Python de modal para invocar las funciones en la nube.

Maneja la descarga temporal de imágenes desde el volumen de Modal a tu disco duro local.

💻 Frontend (JavaScript/ComfyUI)
web/js/modal-execution.js:

Intercepta el botón de "Queue Prompt".

Envía el workflow al Bridge local.

Muestra una barra de progreso en tiempo real.

Cuando termina, inyecta las imágenes recibidas en el historial de ComfyUI.

Añade botones en el diálogo de "Missing Models" para descargar modelos faltantes directamente a la nube.

web/js/modal-gpu-selector.js:

Añade el panel UI para elegir la GPU y ver precios estimados.

🧩 Nodos Personalizados
nodes/modal_register_output.py:

Un nodo simple de Python que ayuda a cargar la imagen descargada desde Modal para que ComfyUI la reconozca como una imagen local y pueda ser guardada o previsualizada en el flujo normal.

⚠️ Notas
Asegúrate de vigilar tu consumo en el panel de Modal.

La primera vez que ejecutas un modelo nuevo en la nube, puede tardar un poco más mientras descarga los checkpoints necesarios al volumen persistente.

Desarrollado con ❤️ para la comunidad de ComfyUI.

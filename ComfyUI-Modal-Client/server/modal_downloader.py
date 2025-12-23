import modal
import os
from pathlib import Path
import json

app = modal.App("comfyui-model-downloader")

volume_models = modal.Volume.from_name("comfyui-models", create_if_missing=True)
volume_outputs = modal.Volume.from_name("comfyui-outputs", create_if_missing=True)

MODELS_DIR = "/models"
OUTPUT_DIR = "/outputs"

# Imagen básica para funciones de descarga
image_basic = (
    modal.Image.debian_slim()
    .pip_install("huggingface_hub", "requests", "tqdm")
)

# Imagen con ComfyUI completo - VERSIONES MODERNAS
image_comfyui = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "wget", "libgl1-mesa-glx", "libglib2.0-0", "libsm6", "libxext6", "libxrender-dev")
    .pip_install(
        "torch==2.4.0",
        "torchvision==0.19.0",
        "torchaudio==2.4.0",
        extra_index_url="https://download.pytorch.org/whl/cu121"
    )
    .run_commands(
        "cd /root && git clone https://github.com/comfyanonymous/ComfyUI.git"
    )
    .run_commands(
        "cd /root/ComfyUI && pip install -r requirements.txt"
    )
)

progress_dict = modal.Dict.from_name("download-progress", create_if_missing=True)

@app.function(
    image=image_basic,
    volumes={MODELS_DIR: volume_models},
    secrets=[modal.Secret.from_name("HF_TOKEN")],
    timeout=7200
)
def download_model(url: str, subfolder: str, filename: str, task_id: str = None):
    """Descarga un modelo desde HuggingFace reportando progreso"""
    from huggingface_hub import hf_hub_url
    import shutil
    import requests
    
    if not task_id:
        import uuid
        task_id = str(uuid.uuid4())
    
    def update_progress(percent, message="Descargando"):
        progress_dict[task_id] = {
            "percent": percent,
            "message": message,
            "filename": filename
        }
    
    dest_folder = Path(MODELS_DIR) / subfolder
    dest_folder.mkdir(parents=True, exist_ok=True)
    dest_path = dest_folder / filename
    
    try:
        update_progress(0, "Iniciando")
        
        if dest_path.exists():
            file_size = dest_path.stat().st_size
            if file_size > 1000:
                update_progress(100, "Ya existe")
                return {
                    "status": "already_exists",
                    "message": f"El archivo ya existe en Modal ({file_size / (1024**3):.2f} GB)",
                    "path": str(dest_path),
                    "task_id": task_id
                }
            else:
                dest_path.unlink()
        
        parts = url.replace("https://huggingface.co/", "").split("/")
        if "resolve" in parts:
            resolve_idx = parts.index("resolve")
            repo_id = "/".join(parts[:resolve_idx])
            revision = parts[resolve_idx + 1]
            file_path = "/".join(parts[resolve_idx + 2:])
            
            update_progress(5, "Conectando a HuggingFace")
            
            hf_token = os.environ.get("HF_TOKEN")
            if not hf_token:
                update_progress(0, "Error: Token no configurado")
                return {
                    "status": "error",
                    "message": "Token de HuggingFace no configurado",
                    "task_id": task_id
                }
            
            print(f"📥 Descargando: {repo_id}/{file_path}")
            update_progress(10, "Descargando desde HuggingFace")
            
            download_url = hf_hub_url(repo_id=repo_id, filename=file_path, revision=revision)
            headers = {"Authorization": f"Bearer {hf_token}"}
            response = requests.get(download_url, headers=headers, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            print(f"  Tamaño total: {total_size / (1024**3):.2f} GB")
            
            downloaded = 0
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        percent = int((downloaded / total_size) * 85) + 10
                        if downloaded % (50 * 1024 * 1024) == 0:
                            update_progress(
                                percent,
                                f"Descargando: {downloaded / (1024**3):.1f}/{total_size / (1024**3):.1f} GB"
                            )
            
            update_progress(95, "Guardando en volumen")
        else:
            import requests
            update_progress(10, "Descargando desde URL")
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    percent = int((downloaded / total_size) * 85) + 10
                    if downloaded % (50 * 1024 * 1024) == 0:
                        update_progress(percent, "Descargando")
        
        update_progress(98, "Confirmando guardado")
        
        if not dest_path.exists():
            update_progress(0, "Error: Archivo no guardado")
            return {
                "status": "error",
                "message": "El archivo no se guardó correctamente",
                "task_id": task_id
            }
        
        volume_models.commit()
        file_size = dest_path.stat().st_size
        update_progress(100, "Completado")
        
        import time
        time.sleep(10)
        if task_id in progress_dict:
            del progress_dict[task_id]
        
        return {
            "status": "success",
            "message": f"Descarga completada ({file_size / (1024**3):.2f} GB)",
            "path": str(dest_path),
            "size_gb": f"{file_size / (1024**3):.2f} GB",
            "task_id": task_id
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        update_progress(0, f"Error: {str(e)[:50]}")
        print(f"Error: {error_details}")
        return {
            "status": "error",
            "message": str(e),
            "path": str(dest_path),
            "task_id": task_id
        }


# NUEVO ENFOQUE: Crear múltiples funciones con diferentes GPUs
@app.function(
    image=image_comfyui,
    gpu="T4",
    volumes={
        MODELS_DIR: volume_models,
        OUTPUT_DIR: volume_outputs
    },
    timeout=1800,
    secrets=[modal.Secret.from_name("HF_TOKEN")]
)
def execute_workflow_t4(workflow_api: dict, task_id: str = None):
    """Ejecuta workflow con GPU T4"""
    return _execute_workflow_internal(workflow_api, task_id, "T4")


@app.function(
    image=image_comfyui,
    gpu="A10G",
    volumes={
        MODELS_DIR: volume_models,
        OUTPUT_DIR: volume_outputs
    },
    timeout=1800,
    secrets=[modal.Secret.from_name("HF_TOKEN")]
)
def execute_workflow_a10g(workflow_api: dict, task_id: str = None):
    """Ejecuta workflow con GPU A10G"""
    return _execute_workflow_internal(workflow_api, task_id, "A10G")


@app.function(
    image=image_comfyui,
    gpu="A100",
    volumes={
        MODELS_DIR: volume_models,
        OUTPUT_DIR: volume_outputs
    },
    timeout=1800,
    secrets=[modal.Secret.from_name("HF_TOKEN")]
)
def execute_workflow_a100(workflow_api: dict, task_id: str = None):
    """Ejecuta workflow con GPU A100"""
    return _execute_workflow_internal(workflow_api, task_id, "A100")


@app.function(
    image=image_comfyui,
    gpu="H100",
    volumes={
        MODELS_DIR: volume_models,
        OUTPUT_DIR: volume_outputs
    },
    timeout=1800,
    secrets=[modal.Secret.from_name("HF_TOKEN")]
)
def execute_workflow_h100(workflow_api: dict, task_id: str = None):
    """Ejecuta workflow con GPU H100"""
    return _execute_workflow_internal(workflow_api, task_id, "H100")


# Función interna compartida por todas las funciones de ejecución
def _execute_workflow_internal(workflow_api: dict, task_id: str, gpu_type: str):
    """
    Lógica interna de ejecución de workflow
    """
    import sys
    import subprocess
    import uuid
    import time
    import requests
    import json
    import shutil
    
    if not task_id:
        task_id = str(uuid.uuid4())
    
    def update_progress(percent, message="Procesando", generated_images=None):
        progress_data = {
            "percent": percent,
            "message": message,
            "filename": "workflow"
        }
        if generated_images is not None:
            progress_data["generated_images"] = generated_images
        progress_dict[task_id] = progress_data
        print(f"📊 Progreso: {percent}% - {message}")
    
    try:
        update_progress(5, "Iniciando ComfyUI")
        print(f"🎨 Ejecutando workflow REAL en Modal")
        print(f"  Task ID: {task_id}")
        print(f"  GPU: {gpu_type}")
        print(f"  Nodos: {len(workflow_api)}")
        
        comfyui_path = Path("/root/ComfyUI")
        if not comfyui_path.exists():
            raise Exception("ComfyUI no encontrado")
        print(f"✓ ComfyUI encontrado en {comfyui_path}")
        
        # Manejo de directorios
        models_link = comfyui_path / "models"
        import os
        import shutil as _sh
        
        if models_link.exists() or models_link.is_symlink():
            if models_link.is_symlink():
                models_link.unlink()
            else:
                _sh.rmtree(models_link)
        models_link.symlink_to(MODELS_DIR)
        print(f"✓ Models symlink: {models_link} -> {MODELS_DIR}")
        
        print(f"\n📦 Modelos disponibles:")
        for subfolder in Path(MODELS_DIR).iterdir():
            if subfolder.is_dir():
                files = list(subfolder.iterdir())
                print(f"  {subfolder.name}: {len(files)} archivos")
                for f in files[:2]:
                    print(f"    - {f.name}")
        print()
        
        output_link = comfyui_path / "output"
        output_path = Path(OUTPUT_DIR)
        output_path.mkdir(parents=True, exist_ok=True)
        
        if output_link.exists() or output_link.is_symlink():
            if output_link.is_symlink():
                output_link.unlink()
            else:
                _sh.rmtree(output_link)
        output_link.symlink_to(output_path)
        print(f"✓ Output symlink: {output_link} -> {output_path}")
        
        update_progress(10, "ComfyUI configurado")
        
        print("\n🚀 Iniciando servidor ComfyUI...\n")
        server_process = subprocess.Popen(
            [sys.executable, "main.py", "--listen", "127.0.0.1", "--port", "8188", "--disable-auto-launch"],
            cwd=str(comfyui_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        max_wait = 180
        start = time.time()
        server_ready = False
        last_progress = time.time()
        
        while time.time() - start < max_wait:
            if server_process.poll() is not None:
                print(f"\n❌ ComfyUI se cerró con código: {server_process.poll()}")
                remaining = server_process.stdout.read()
                if remaining:
                    print(remaining)
                raise Exception(f"ComfyUI se cerró con código {server_process.poll()}")
            
            line = server_process.stdout.readline()
            if line:
                line = line.strip()
                if line:
                    print(f"  {line}")
            
            try:
                response = requests.get("http://127.0.0.1:8188/system_stats", timeout=1)
                if response.status_code == 200:
                    server_ready = True
                    print("\n✓ Servidor ComfyUI LISTO\n")
                    break
            except:
                pass
            
            elapsed = int(time.time() - start)
            if time.time() - last_progress >= 10:
                update_progress(10 + int((elapsed / max_wait) * 10), f"Iniciando ({elapsed}s)")
                last_progress = time.time()
            
            time.sleep(0.5)
        
        if not server_ready:
            server_process.terminate()
            raise Exception(f"Timeout esperando servidor ({int(time.time() - start)}s)")
        
        update_progress(20, "Servidor iniciado")
        
        print("📤 Enviando workflow...")
        response = requests.post(
            "http://127.0.0.1:8188/prompt",
            json={"prompt": workflow_api, "client_id": task_id},
            timeout=10
        )
        
        if response.status_code != 200:
            raise Exception(f"Error enviando workflow: {response.text}")
        
        result_data = response.json()
        prompt_id = result_data.get("prompt_id")
        if not prompt_id:
            raise Exception(f"No se recibió prompt_id: {result_data}")
        
        print(f"✓ Prompt ID: {prompt_id}\n")
        update_progress(30, "Generando")
        
        max_exec = 600
        start_exec = time.time()
        
        while time.time() - start_exec < max_exec:
            try:
                hist_resp = requests.get(f"http://127.0.0.1:8188/history/{prompt_id}", timeout=5)
                if hist_resp.status_code == 200:
                    hist_data = hist_resp.json()
                    if prompt_id in hist_data:
                        prompt_info = hist_data[prompt_id]
                        if prompt_info.get("status", {}).get("completed", False):
                            print("✓ Workflow completado!")
                            update_progress(90, "Recogiendo imágenes")
                            
                            outputs = prompt_info.get("outputs", {})
                            image_paths = []
                            
                            for node_id, node_output in outputs.items():
                                if "images" in node_output:
                                    for img_info in node_output["images"]:
                                        filename = img_info.get("filename")
                                        if filename:
                                            img_path = output_path / filename
                                            if img_path.exists():
                                                image_paths.append(str(img_path))
                                                print(f"  ✓ Imagen: {filename}")
                            
                            volume_outputs.commit()
                            print(f"\n✓ {len(image_paths)} imagen(es) guardadas\n")
                            
                            server_process.terminate()
                            
                            generated_filenames = [Path(p).name for p in image_paths]
                            update_progress(100, "Completado", generated_images=generated_filenames)
                            
                            print(f"⏱️ Manteniendo progreso disponible por 60 segundos...")
                            time.sleep(60)
                            
                            if task_id in progress_dict:
                                del progress_dict[task_id]
                                print(f"🗑️ Progreso limpiado para task_id: {task_id}")
                            
                            return {
                                "status": "success",
                                "message": f"Generadas {len(image_paths)} imágenes",
                                "images": image_paths,
                                "task_id": task_id,
                                "output_dir": str(output_path),
                                "gpu_type": gpu_type
                            }
            except:
                pass
            
            elapsed = int(time.time() - start_exec)
            if elapsed % 5 == 0:
                progress = min(30 + int((elapsed / max_exec) * 60), 89)
                update_progress(progress, f"Generando ({elapsed}s)")
            
            time.sleep(2)
        
        server_process.terminate()
        raise Exception("Timeout ejecutando workflow")
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        update_progress(0, f"Error: {str(e)[:50]}")
        print(f"\n❌ Error:\n{error_details}")
        
        try:
            server_process.terminate()
        except:
            pass
        
        return {
            "status": "error",
            "message": str(e),
            "task_id": task_id,
            "details": error_details
        }


@app.function(
    image=image_basic,
    volumes={OUTPUT_DIR: volume_outputs}
)
def get_output_image(filename: str):
    """Descarga una imagen generada desde Modal"""
    image_path = Path(OUTPUT_DIR) / filename
    if image_path.exists():
        return image_path.read_bytes()
    else:
        raise FileNotFoundError(f"Imagen no encontrada: {filename}")


@app.function(
    image=image_basic,
    volumes={OUTPUT_DIR: volume_outputs}
)
def list_output_images():
    """Lista todas las imágenes en el output"""
    output_path = Path(OUTPUT_DIR)
    images = []
    if output_path.exists():
        for file in output_path.iterdir():
            if file.is_file() and file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
                images.append({
                    "filename": file.name,
                    "size": file.stat().st_size,
                    "modified": file.stat().st_mtime
                })
    return {"images": images, "count": len(images)}


@app.function()
def get_download_progress(task_id: str):
    """Obtiene el progreso de una descarga o ejecución"""
    if task_id in progress_dict:
        return progress_dict[task_id]
    else:
        return {"percent": 0, "message": "No encontrado", "filename": ""}


@app.function(
    image=image_basic,
    volumes={MODELS_DIR: volume_models}
)
def check_model_exists(subfolder: str, filename: str):
    """Verifica si un modelo existe en Modal Volume"""
    dest_path = Path(MODELS_DIR) / subfolder / filename
    if dest_path.exists():
        file_size = dest_path.stat().st_size
        if file_size > 1000:
            return {
                "exists": True,
                "size": file_size,
                "size_gb": f"{file_size / (1024**3):.2f} GB",
                "path": str(dest_path)
            }
    return {
        "exists": False,
        "size": 0,
        "size_gb": "0 GB",
        "path": str(dest_path)
    }


@app.function(
    image=image_basic,
    volumes={MODELS_DIR: volume_models}
)
def list_all_models():
    """Lista todos los modelos en Modal Volume"""
    models = {}
    models_path = Path(MODELS_DIR)
    if not models_path.exists():
        return {"message": "No hay modelos aún", "models": {}}
    
    for subfolder in models_path.iterdir():
        if subfolder.is_dir():
            models[subfolder.name] = []
            for file in subfolder.iterdir():
                if file.is_file():
                    file_size = file.stat().st_size
                    if file_size > 1000:
                        models[subfolder.name].append({
                            "name": file.name,
                            "size": file_size,
                            "size_gb": f"{file_size / (1024**3):.2f} GB"
                        })
    return {"models": models}


@app.function(image=image_basic)
def get_billing_info():
    """
    Devuelve información de saldo/uso aproximada.
    Se leen variables de entorno que puedes configurar en Modal:
    - MODAL_BALANCE_USD
    - MODAL_USAGE_TODAY_USD
    """
    balance = os.environ.get("MODAL_BALANCE_USD")
    usage_today = os.environ.get("MODAL_USAGE_TODAY_USD")
    
    try:
        balance_val = float(balance) if balance is not None else None
    except:
        balance_val = None
    
    try:
        usage_val = float(usage_today) if usage_today is not None else None
    except:
        usage_val = None
    
    return {
        "balance_usd": balance_val,
        "usage_today_usd": usage_val
    }


@app.function(image=image_basic)
def get_available_gpus():
    """Devuelve lista de GPUs disponibles en Modal"""
    return {
        "gpus": [
            {"name": "T4", "vram": "16 GB", "cost_per_hour": 0.50},
            {"name": "A10G", "vram": "24 GB", "cost_per_hour": 1.10},
            {"name": "A100", "vram": "40 GB", "cost_per_hour": 3.00},
            {"name": "H100", "vram": "80 GB", "cost_per_hour": 8.00}
        ]
    }

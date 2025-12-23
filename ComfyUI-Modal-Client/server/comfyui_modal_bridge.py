from flask import Flask, jsonify, request
from flask_cors import CORS
import modal
import uuid
from pathlib import Path
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Ruta de ComfyUI
COMFYUI_ROOT = Path(__file__).resolve().parents[3]
COMFYUI_OUTPUT_DIR = (COMFYUI_ROOT / "output").resolve()
COMFYUI_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODAL_META_FILE = COMFYUI_OUTPUT_DIR / "_modal_last_outputs.json"

# Archivos de historial y estado
HISTORY_FILE = COMFYUI_OUTPUT_DIR / "_modal_gpu_history.json"
QUEUE_FILE = COMFYUI_OUTPUT_DIR / "_modal_queue.json"

# Mapeo de GPUs a funciones
GPU_FUNCTION_MAP = {
    "T4": "execute_workflow_t4",
    "A10G": "execute_workflow_a10g",
    "A100": "execute_workflow_a100",
    "H100": "execute_workflow_h100"
}

try:
    check_model_fn = modal.Function.from_name("comfyui-model-downloader", "check_model_exists")
    download_model_fn = modal.Function.from_name("comfyui-model-downloader", "download_model")
    
    # Cargar todas las funciones de GPU
    execute_workflow_fns = {}
    for gpu_name, fn_name in GPU_FUNCTION_MAP.items():
        try:
            execute_workflow_fns[gpu_name] = modal.Function.from_name("comfyui-model-downloader", fn_name)
            print(f"✓ Función {fn_name} cargada")
        except Exception as e:
            print(f"⚠️ No se pudo cargar {fn_name}: {e}")
    
    get_progress_fn = modal.Function.from_name("comfyui-model-downloader", "get_download_progress")
    list_models_fn = modal.Function.from_name("comfyui-model-downloader", "list_all_models")
    get_output_image_fn = modal.Function.from_name("comfyui-model-downloader", "get_output_image")
    list_output_images_fn = modal.Function.from_name("comfyui-model-downloader", "list_output_images")
    get_billing_fn = modal.Function.from_name("comfyui-model-downloader", "get_billing_info")
    get_available_gpus_fn = modal.Function.from_name("comfyui-model-downloader", "get_available_gpus")
    print("✓ Funciones de Modal conectadas correctamente")
except Exception as e:
    print(f"⚠️ Error conectando con Modal: {e}")
    check_model_fn = None
    download_model_fn = None
    execute_workflow_fns = {}
    get_progress_fn = None
    list_models_fn = None
    get_output_image_fn = None
    list_output_images_fn = None
    get_billing_fn = None
    get_available_gpus_fn = None


def load_history():
    """Carga historial de GPU desde archivo"""
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except:
            return []
    return []


def save_history(entry):
    """Guarda entrada en el historial"""
    history = load_history()
    history.insert(0, entry)
    history = history[:50]  # Mantener solo últimas 50
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


def load_queue():
    """Carga cola actual"""
    if QUEUE_FILE.exists():
        try:
            return json.loads(QUEUE_FILE.read_text())
        except:
            return []
    return []


def save_queue(queue):
    """Guarda cola actual"""
    QUEUE_FILE.write_text(json.dumps(queue, indent=2))


@app.route('/check_model', methods=['POST'])
def check_model():
    if not check_model_fn:
        return jsonify({"error": "Modal no está conectado", "exists": False}), 503
    
    data = request.json
    subfolder = data.get('subfolder')
    filename = data.get('filename')
    
    print(f"🔍 Verificando: {subfolder}/{filename}")
    
    try:
        result = check_model_fn.remote(subfolder=subfolder, filename=filename)
        print(f"  Resultado: {'✓ Existe' if result.get('exists') else '✗ No existe'}")
        return jsonify(result)
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return jsonify({"error": str(e), "exists": False}), 500


@app.route('/download_model', methods=['POST'])
def download_model():
    if not download_model_fn:
        return jsonify({"error": "Modal no está conectado", "status": "error"}), 503
    
    data = request.json
    url = data.get('url')
    subfolder = data.get('subfolder')
    filename = data.get('filename')
    task_id = str(uuid.uuid4())
    
    print(f"⬇️ Descargando: {subfolder}/{filename} [task_id: {task_id}]")
    print(f"  URL: {url[:80]}...")
    
    try:
        call = download_model_fn.spawn(
            url=url,
            subfolder=subfolder,
            filename=filename,
            task_id=task_id
        )
        
        return jsonify({
            "status": "started",
            "message": "Descarga iniciada",
            "task_id": task_id,
            "call_id": call.object_id
        })
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/execute_workflow', methods=['POST'])
def execute_workflow():
    data = request.json
    workflow_api = data.get('workflow')
    gpu_type = data.get('gpu_type', 'T4').upper()
    
    if not workflow_api:
        return jsonify({"error": "No se proporcionó workflow", "status": "error"}), 400
    
    # Validar GPU
    if gpu_type not in execute_workflow_fns:
        return jsonify({
            "error": f"GPU '{gpu_type}' no válida. Opciones: {', '.join(execute_workflow_fns.keys())}",
            "status": "error"
        }), 400
    
    execute_fn = execute_workflow_fns[gpu_type]
    
    task_id = str(uuid.uuid4())
    print(f"🎨 Ejecutando workflow en Modal con GPU: {gpu_type} [task_id: {task_id}]")
    print(f"  Nodos: {len(workflow_api)}")
    
    try:
        # Agregar a la cola
        queue = load_queue()
        queue_entry = {
            "task_id": task_id,
            "gpu_type": gpu_type,
            "status": "running",
            "timestamp": datetime.now().isoformat(),
            "nodes": len(workflow_api)
        }
        queue.append(queue_entry)
        save_queue(queue)
        
        call = execute_fn.spawn(
            workflow_api=workflow_api,
            task_id=task_id
        )
        
        return jsonify({
            "status": "started",
            "message": f"Ejecución iniciada en Modal con GPU {gpu_type}",
            "task_id": task_id,
            "call_id": call.object_id,
            "gpu_type": gpu_type
        })
    except Exception as e:
        print(f"  ✗ Error: {e}")
        
        # Actualizar cola como error
        queue = load_queue()
        for item in queue:
            if item['task_id'] == task_id:
                item['status'] = 'error'
                item['error'] = str(e)
        save_queue(queue)
        
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/progress/<task_id>', methods=['GET'])
def get_progress(task_id):
    if not get_progress_fn:
        return jsonify({"error": "Modal no está conectado"}), 503
    
    try:
        result = get_progress_fn.remote(task_id=task_id)
        
        # Si completado, actualizar historial y cola
        if result.get('percent') == 100:
            # Actualizar cola
            queue = load_queue()
            for item in queue:
                if item['task_id'] == task_id:
                    item['status'] = 'completed'
                    # Mover a historial
                    save_history({
                        "task_id": task_id,
                        "gpu_type": item.get('gpu_type', 'T4'),
                        "status": "completed",
                        "timestamp": item.get('timestamp'),
                        "completed_at": datetime.now().isoformat(),
                        "images": result.get('generated_images', [])
                    })
                    queue.remove(item)
                    break
            save_queue(queue)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"percent": 0, "message": "Error", "error": str(e)}), 500


@app.route('/list_output_images', methods=['GET'])
def list_output_images_endpoint():
    """Lista las imágenes generadas en Modal (sin descargar)"""
    if not list_output_images_fn:
        return jsonify({"error": "Modal no está conectado", "images": []}), 503
    
    print("📋 Listando imágenes en Modal (sin descargar)...")
    
    try:
        result = list_output_images_fn.remote()
        images = result.get("images", [])
        print(f"✓ {len(images)} imágenes encontradas en Modal")
        for img in images:
            print(f"  - {img.get('filename', 'unknown')}")
        return jsonify(result)
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return jsonify({"error": str(e), "images": []}), 500


@app.route('/get_image/<filename>', methods=['GET'])
def get_single_image(filename):
    """Descarga UNA imagen desde Modal y la guarda temporalmente"""
    if not get_output_image_fn:
        return jsonify({"error": "Modal no está conectado"}), 503
    
    print(f"⬇ Descargando imagen temporal: {filename}")
    
    try:
        image_data = get_output_image_fn.remote(filename=filename)
        temp_path = COMFYUI_OUTPUT_DIR / filename
        
        with open(temp_path, 'wb') as f:
            f.write(image_data)
        
        print(f"✓ Imagen guardada temporalmente: {temp_path}")
        
        return jsonify({
            'status': 'success',
            'filename': filename,
            'path': str(temp_path)
        })
    except Exception as e:
        print(f"❌ Error descargando {filename}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/delete_temp/<filename>', methods=['DELETE'])
def delete_temp_image(filename):
    """Borra una imagen temporal después de procesarla"""
    try:
        temp_path = COMFYUI_OUTPUT_DIR / filename
        if temp_path.exists():
            temp_path.unlink()
            print(f"🗑 Imagen temporal borrada: {filename}")
            return jsonify({'status': 'success', 'message': f'Borrada: {filename}'})
        else:
            return jsonify({'status': 'not_found', 'message': f'No existe: {filename}'}), 404
    except Exception as e:
        print(f"❌ Error borrando {filename}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/download_images', methods=['GET'])
def download_all_images():
    """SOLO lista imágenes, NO las descarga. El mini-workflow las descargará individualmente."""
    if not list_output_images_fn:
        return jsonify({"error": "Modal no está conectado"}), 503
    
    print("📋 Obteniendo lista de imágenes desde Modal...")
    
    try:
        result = list_output_images_fn.remote()
        images = result.get("images", [])
        filenames = [img['filename'] for img in images]
        
        print(f"✓ {len(filenames)} imágenes disponibles para procesar")
        
        try:
            MODAL_META_FILE.write_text(
                json.dumps(
                    {
                        "files": filenames,
                        "local_dir": str(COMFYUI_OUTPUT_DIR)
                    },
                    ensure_ascii=False,
                    indent=2
                ),
                "utf-8"
            )
            print(f"✓ Metadatos actualizados en {MODAL_META_FILE}")
        except Exception as e:
            print(f"⚠️ No se pudieron escribir metadatos: {e}")
        
        return jsonify({
            "status": "success",
            "message": f"{len(filenames)} imágenes listas",
            "downloaded": filenames,
            "local_dir": str(COMFYUI_OUTPUT_DIR)
        })
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/list_models', methods=['GET'])
def list_models():
    if not list_models_fn:
        return jsonify({"error": "Modal no está conectado"}), 503
    
    print("📋 Listando modelos en Modal...")
    
    try:
        result = list_models_fn.remote()
        return jsonify(result)
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return jsonify({"error": str(e)}), 500


# NUEVO: Endpoint para información de cuenta/billing
@app.route('/modal_account', methods=['GET'])
def get_modal_account():
    """Obtiene información de cuenta y billing desde Modal"""
    if not get_billing_fn:
        return jsonify({"error": "Modal no está conectado"}), 503
    
    print("💰 Obteniendo información de cuenta Modal...")
    
    try:
        billing_info = get_billing_fn.remote()
        
        # Datos simulados si no hay variables de entorno configuradas
        account_data = {
            "balance": billing_info.get("balance_usd", 50.00),
            "usage_today": billing_info.get("usage_today_usd", 2.35),
            "currency": "USD"
        }
        
        return jsonify(account_data)
    except Exception as e:
        print(f"  ✗ Error: {e}")
        # Retornar datos por defecto si falla
        return jsonify({
            "balance": 50.00,
            "usage_today": 0.00,
            "currency": "USD"
        })


# NUEVO: Endpoint para cola actual
@app.route('/modal_queue', methods=['GET'])
def get_modal_queue():
    """Obtiene la cola actual de trabajos"""
    print("📋 Obteniendo cola actual...")
    
    try:
        queue = load_queue()
        return jsonify({
            "queue": queue,
            "count": len(queue)
        })
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return jsonify({"queue": [], "count": 0})


# NUEVO: Endpoint para historial de GPU
@app.route('/gpu_history', methods=['GET'])
def get_gpu_history():
    """Obtiene historial de ejecuciones"""
    print("📜 Obteniendo historial de GPU...")
    
    try:
        history = load_history()
        return jsonify({
            "history": history,
            "count": len(history)
        })
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return jsonify({"history": [], "count": 0})


@app.route('/gpu_info', methods=['GET'])
def get_gpu_info():
    """Obtiene información de GPUs disponibles y billing desde Modal"""
    if not get_billing_fn or not get_available_gpus_fn:
        return jsonify({"error": "Modal no está conectado"}), 503
    
    print("📊 Obteniendo información de GPUs y billing...")
    
    try:
        billing_info = get_billing_fn.remote()
        gpus_info = get_available_gpus_fn.remote()
        
        return jsonify({
            "status": "ok",
            "gpus": gpus_info.get("gpus", []),
            "billing": billing_info
        })
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    modal_status = "connected" if check_model_fn else "disconnected"
    available_gpus = list(execute_workflow_fns.keys())
    return jsonify({
        "status": "ok",
        "message": "Modal Bridge está activo",
        "modal_status": modal_status,
        "available_gpus": available_gpus,
        "local_output_dir": str(COMFYUI_OUTPUT_DIR)
    })


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Servidor Modal Bridge")
    print("📍 URL: http://127.0.0.1:5001")
    print("📦 Modal App: comfyui-model-downloader")
    print(f"💾 Output local: {COMFYUI_OUTPUT_DIR}")
    print(f"🎮 GPUs disponibles: {', '.join(execute_workflow_fns.keys())}")
    print("=" * 60)
    app.run(host='127.0.0.1', port=5001, debug=False)

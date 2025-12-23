import { app } from '/scripts/app.js';

app.registerExtension({
    name: "modal.buttons.extension",
    async setup() {
        const API_BASE = 'http://127.0.0.1:5001';
        
        // Estado global para modo de ejecución
        let modoEjecucion = 'local'; // 'local' o 'modal'
        
        // NUEVO: Variable global para GPU seleccionada
        let selectedGPU = 'T4'; // Por defecto T4
        
        // NUEVO: Función global para que modal-gpu-selector.js pueda cambiar la GPU
        window.setSelectedGPU = function(gpuName) {
            selectedGPU = gpuName;
            console.log(`🔧 GPU seleccionada: ${gpuName}`);
        };

        const parseModelInfo = (titleText) => {
            const parts = titleText.trim().split(' / ');
            if (parts.length === 2) {
                return { subfolder: parts[0].trim(), filename: parts[1].trim() };
            }
            return null;
        };

        const pollProgress = async (taskId, labelSpan, onComplete) => {
            const interval = setInterval(async () => {
                try {
                    const response = await fetch(`${API_BASE}/progress/${taskId}`);
                    const progress = await response.json();
                    
                    if (progress.percent !== undefined) {
                        labelSpan.textContent = `Descargando... ${progress.percent}%`;
                        
                        if (progress.percent >= 100) {
                            clearInterval(interval);
                            labelSpan.textContent = progress.message || 'Completado ✓';
                            setTimeout(() => {
                                if (onComplete) onComplete();
                            }, 1000);
                        }
                    }
                } catch (error) {
                    console.error('Error obteniendo progreso:', error);
                }
            }, 1000);
            
            return interval;
        };

        // ========== REGISTRAR IMÁGENES EN COMFYUI LOCAL (descarga + mini-workflow + limpieza) ==========
        async function registrarImagenesEnComfyUI(filenames) {
            if (!filenames || !filenames.length) return;
            
            console.log("📥 Registrando imágenes en ComfyUI:", filenames);
            
            for (const filename of filenames) {
                try {
                    // 1. Descargar imagen desde Modal
                    console.log(`⬇ Descargando ${filename} desde Modal...`);
                    const downloadRes = await fetch(`${API_BASE}/get_image/${filename}`);
                    const downloadData = await downloadRes.json();
                    
                    if (downloadData.status !== 'success') {
                        console.error(`❌ Error descargando ${filename}:`, downloadData.error);
                        continue;
                    }
                    
                    console.log(`✓ Descargada temporalmente: ${filename}`);
                    
                    // 2. Pequeño prompt local: LoadLocalImageModal -> SaveImage
                    const workflow = {
                        "0": {
                            "class_type": "LoadLocalImageModal",
                            "inputs": { "filename": filename }
                        },
                        "1": {
                            "class_type": "SaveImage",
                            "inputs": {
                                "images": ["0", 0],
                                "filename_prefix": "modal_registered_"
                            }
                        }
                    };
                    
                    const payload = {
                        prompt: workflow,
                        client_id: `modal-register-${Date.now()}`
                    };
                    
                    const res = await fetch("/prompt", {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify(payload)
                    });
                    
                    if (!res.ok) {
                        const txt = await res.text();
                        console.error(`❌ Error registrando ${filename}:`, txt);
                        continue;
                    }
                    
                    const data = await res.json();
                    console.log(`✓ Lanzado mini-workflow local para ${filename}`, data);
                    
                    // 3. Esperar un momento para que se procese
                    await new Promise(resolve => setTimeout(resolve, 500));
                    
                    // 4. Borrar imagen temporal
                    console.log(`🗑 Borrando temporal: ${filename}`);
                    const deleteRes = await fetch(`${API_BASE}/delete_temp/${filename}`, { method: 'DELETE' });
                    const deleteData = await deleteRes.json();
                    console.log(`✓ ${deleteData.message}`);
                    
                } catch (err) {
                    console.error(`❌ Error lanzando mini-workflow para ${filename}:`, err);
                }
            }
        }

        // ========== Refrescar resultados en ComfyUI ==========
        const refrescarResultados = async () => {
            console.log("🔄 Refrescando resultados en ComfyUI...");
            
            try {
                if (app.ui && app.ui.loadHistory) {
                    await app.ui.loadHistory();
                    console.log("✓ Historial refrescado");
                }
                
                try {
                    await fetch("/api/media_assets?type=image&subfolder=&page=0&per_page=50");
                    console.log("✓ Media assets refrescados");
                } catch (e) {
                    console.warn("No se pudo llamar a /api/media_assets (no crítico):", e);
                }
                
                const graph = app.graph;
                if (graph && graph._nodes) {
                    const outputNodes = graph._nodes.filter(node => 
                        node.type === "SaveImage" || 
                        node.type === "PreviewImage" ||
                        node.type === "VHS_VideoCombine" ||
                        node.type === "SaveAnimatedWEBP" ||
                        node.type === "SaveAnimatedPNG" ||
                        (node.constructor?.name || "").includes("Save") ||
                        (node.constructor?.name || "").includes("Preview") ||
                        (node.constructor?.name || "").includes("Output")
                    );
                    
                    console.log(`📋 Encontrados ${outputNodes.length} nodos de output`);
                    
                    for (const node of outputNodes) {
                        if (node.onExecuted) {
                            try {
                                node.onExecuted({ images: [{ filename: "dummy", type: "output" }] });
                            } catch (e) {
                                console.warn("onExecuted lanzó error (no grave):", e);
                            }
                        }
                        
                        if (node.setDirtyCanvas) {
                            node.setDirtyCanvas(true, true);
                        }
                    }
                    
                    if (graph.setDirtyCanvas) {
                        graph.setDirtyCanvas(true, true);
                    }
                }
                
                if (app.canvas) {
                    app.canvas.setDirty(true, true);
                    app.canvas.draw(true, true);
                }
                
                console.log("✓ Resultados refrescados");
            } catch (error) {
                console.error("⚠️ Error refrescando resultados:", error);
            }
        };

        // ========== UI: Botón principal / modo ejecución ==========
        const actualizarBotonPrincipal = () => {
            const botonPrincipal = document.querySelector('.comfyui-queue-button .p-splitbutton-button .p-button-label');
            if (botonPrincipal) {
                const btn = botonPrincipal.closest('button');
                
                if (modoEjecucion === 'modal') {
                    botonPrincipal.textContent = 'Ejecutar en Modal';
                    if (btn && !btn.classList.contains('p-button-primary')) {
                        btn.classList.add('p-button-primary', 'p-button-sm');
                        btn.classList.remove('p-button-secondary');
                    }
                } else {
                    botonPrincipal.textContent = 'Ejecutar';
                    if (btn) {
                        btn.classList.remove('p-button-primary');
                        btn.classList.add('p-button-secondary', 'p-button-sm');
                        btn.style.background = '';
                        btn.style.borderColor = '';
                        btn.style.color = '';
                    }
                }
            }
        };

        // Intercepta el botón "Ejecutar" cuando está en modo Modal
        const interceptarEjecucion = () => {
            const botonEjecutar = document.querySelector('.comfyui-queue-button .p-splitbutton-button');
            
            if (botonEjecutar && !botonEjecutar.dataset.modalIntercepted) {
                botonEjecutar.dataset.modalIntercepted = 'true';
                
                botonEjecutar.addEventListener('click', async (e) => {
                    if (modoEjecucion === 'modal') {
                        e.preventDefault();
                        e.stopPropagation();
                        e.stopImmediatePropagation();
                        
                        console.log('🚀 Ejecutando en Modal...');
                        console.log(`🔧 GPU seleccionada: ${selectedGPU}`); // NUEVO: Log de GPU
                        
                        try {
                            const prompt = await app.graphToPrompt();
                            console.log('📋 Workflow capturado');
                            console.log('   Nodos:', Object.keys(prompt.workflow).length);
                            
                            // MODIFICADO: Incluir gpu_type en el request
                            const response = await fetch(`${API_BASE}/execute_workflow`, {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({
                                    workflow: prompt.output,
                                    gpu_type: selectedGPU  // ← NUEVO: Enviar GPU seleccionada
                                })
                            });
                            
                            const result = await response.json();
                            
                            if (result.status === 'started' && result.task_id) {
                                console.log('✓ Ejecución iniciada en Modal');
                                console.log('   Task ID:', result.task_id);
                                console.log('   GPU:', result.gpu_type || selectedGPU); // NUEVO: Log de GPU confirmada
                                
                                // Crear indicador de progreso
                                const actionbarContainer = document.querySelector('.actionbar-container');
                                const progressIndicator = document.createElement('div');
                                progressIndicator.className = 'flex items-center gap-2 px-3 py-1 border-l border-interface-stroke';
                                progressIndicator.style.cssText = `
                                    height: 100%;
                                    min-width: 200px;
                                `;
                                
                                progressIndicator.innerHTML = `
                                    <div class="flex flex-col gap-1 flex-1">
                                        <div class="flex items-center justify-between">
                                            <span class="text-xs font-medium" style="color: var(--fg-color)">Ejecutando en Modal (${selectedGPU})</span>
                                            <span id="modal-progress-percent" class="text-xs font-mono" style="color: var(--fg-color); opacity: 0.7">0%</span>
                                        </div>
                                        <div class="flex items-center gap-2">
                                            <div class="flex-1 h-1.5 rounded-full overflow-hidden" style="background: var(--border-color)">
                                                <div id="modal-progress-bar" class="h-full rounded-full transition-all duration-300" style="width: 0%; background: var(--primary-bg, #667eea)"></div>
                                            </div>
                                        </div>
                                        <div id="modal-progress-text" class="text-xs" style="color: var(--fg-color); opacity: 0.7">Iniciando...</div>
                                    </div>
                                `;
                                
                                if (actionbarContainer) {
                                    actionbarContainer.appendChild(progressIndicator);
                                } else {
                                    progressIndicator.className = 'pointer-events-auto flex flex-col overflow-hidden rounded-lg border font-inter transition-colors duration-200 ease-in-out border-interface-stroke bg-comfy-menu-bg shadow-interface';
                                    progressIndicator.style.cssText = `
                                        position: fixed !important;
                                        top: 60px !important;
                                        right: 20px !important;
                                        min-width: 280px;
                                        max-width: 320px;
                                        z-index: 13000 !important;
                                        padding: 12px !important;
                                    `;
                                    document.body.appendChild(progressIndicator);
                                }
                                
                                const progressText = document.getElementById('modal-progress-text');
                                const progressBar = document.getElementById('modal-progress-bar');
                                const progressPercent = document.getElementById('modal-progress-percent');
                                
                                // Polling de progreso que obtiene generated_images
                                const progressInterval = setInterval(async () => {
                                    try {
                                        const progressResponse = await fetch(`${API_BASE}/progress/${result.task_id}`);
                                        const progress = await progressResponse.json();
                                        
                                        if (progress.percent !== undefined) {
                                            progressText.textContent = progress.message || 'Procesando...';
                                            progressBar.style.width = `${progress.percent}%`;
                                            progressPercent.textContent = `${progress.percent}%`;
                                            
                                            if (progress.percent >= 100) {
                                                console.log('✅ Progreso 100% alcanzado!');
                                                clearInterval(progressInterval);
                                                
                                                progressText.textContent = 'Completado. Obteniendo imágenes...';
                                                progressBar.style.backgroundColor = '#4caf50';
                                                
                                                setTimeout(async () => {
                                                    try {
                                                        // Obtener imágenes generadas del progreso
                                                        const generatedImages = progress.generated_images || [];
                                                        
                                                        if (generatedImages.length > 0) {
                                                            console.log(`📥 Imágenes generadas en este workflow: ${generatedImages.join(', ')}`);
                                                            
                                                            // Notificar al panel Modal solo con las nuevas
                                                            const imageObjects = generatedImages.map(filename => ({
                                                                filename: filename,
                                                                size: 0,
                                                                modified: Date.now()
                                                            }));
                                                            
                                                            console.log('📢 Disparando evento modal-images-ready');
                                                            window.dispatchEvent(new CustomEvent('modal-images-ready', {
                                                                detail: { images: imageObjects }
                                                            }));
                                                            
                                                            console.log(`⬇ Descargando solo: ${generatedImages.join(', ')}`);
                                                            
                                                            // Descargar, procesar y limpiar SOLO las nuevas
                                                            await registrarImagenesEnComfyUI(generatedImages);
                                                            await refrescarResultados();
                                                            
                                                            progressText.textContent = `✓ ${generatedImages.length} imagen(es) registradas`;
                                                        } else {
                                                            console.warn('⚠️ No se encontraron imágenes generadas en el progreso');
                                                            progressText.textContent = 'Sin imágenes nuevas';
                                                        }
                                                        
                                                        setTimeout(() => progressIndicator.remove(), 2500);
                                                        
                                                    } catch (error) {
                                                        console.error('Error obteniendo imágenes:', error);
                                                        progressText.textContent = 'Error obteniendo imágenes';
                                                        setTimeout(() => progressIndicator.remove(), 3000);
                                                    }
                                                }, 1000);
                                                
                                            } else if (progress.percent === 0 && progress.message && progress.message.includes('Error')) {
                                                clearInterval(progressInterval);
                                                progressText.textContent = `Error: ${progress.message}`;
                                                progressBar.style.backgroundColor = '#f44336';
                                                setTimeout(() => progressIndicator.remove(), 5000);
                                            }
                                        }
                                    } catch (error) {
                                        console.error('Error obteniendo progreso de ejecución:', error);
                                    }
                                }, 2000);
                                
                            } else {
                                console.error('Error:', result.message);
                                alert(`Error iniciando ejecución en Modal: ${result.message}`);
                            }
                            
                        } catch (error) {
                            console.error('Error ejecutando en Modal:', error);
                            alert(`Error: ${error.message}\n\nAsegúrate de que comfyui_modal_bridge.py está corriendo.`);
                        }
                        
                        return false;
                    }
                }, true);
            }
        };
        
        setInterval(interceptarEjecucion, 1000);

        // ========== Menú "Ejecutar" con opción Modal ==========
        const observadorMenuEjecutar = new MutationObserver(() => {
            const menuList = document.querySelector('.p-tieredmenu-root-list');
            
            if (menuList && !menuList.querySelector('.ejecutar-modal-item')) {
                const menuItem = document.createElement('li');
                menuItem.className = 'p-tieredmenu-item ejecutar-modal-item';
                menuItem.setAttribute('role', 'menuitem');
                menuItem.setAttribute('aria-label', 'Ejecutar en modal');
                menuItem.setAttribute('aria-level', '1');
                menuItem.setAttribute('data-pc-section', 'item');
                menuItem.setAttribute('data-p-active', 'false');
                menuItem.setAttribute('data-p-focused', 'false');
                
                const isActive = modoEjecucion === 'modal';
                const buttonClass = isActive ? 'p-button-primary' : 'p-button-secondary';
                
                menuItem.innerHTML = `
                    <div class="p-tieredmenu-item-content" data-pc-section="itemcontent">
                        <button class="p-button p-component ${buttonClass} p-button-text p-button-sm" type="button" aria-label="Ejecutar en modal" data-pc-name="button">
                            <span class="p-button-label">Ejecutar en modal</span>
                        </button>
                    </div>
                `;
                
                const button = menuItem.querySelector('button');
                
                menuItem.addEventListener('mouseenter', () => {
                    menuList.querySelectorAll('.p-tieredmenu-item').forEach(item => {
                        item.setAttribute('data-p-focused', 'false');
                    });
                    menuItem.setAttribute('data-p-focused', 'true');
                });
                
                menuItem.addEventListener('mouseleave', () => {
                    menuItem.setAttribute('data-p-focused', 'false');
                });
                
                button.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    modoEjecucion = 'modal';
                    
                    menuList.querySelectorAll('.p-tieredmenu-item button').forEach(btn => {
                        btn.classList.remove('p-button-primary');
                        btn.classList.add('p-button-secondary');
                    });
                    
                    button.classList.remove('p-button-secondary');
                    button.classList.add('p-button-primary');
                    
                    actualizarBotonPrincipal();
                    
                    const overlay = document.querySelector('[id*="pv_id_"][id*="_overlay"]');
                    if (overlay) {
                        overlay.style.display = 'none';
                    }
                    
                    console.log('✓ Modo de ejecución cambiado a: MODAL');
                });
                
                menuList.appendChild(menuItem);
                console.log('✓ Item "Ejecutar en modal" agregado al menú');
            }
        });
        
        observadorMenuEjecutar.observe(document.body, { childList: true, subtree: true });

        // Detectar cambio a modo LOCAL
        document.addEventListener('click', (e) => {
            const menuButton = e.target.closest('.p-tieredmenu-item button');
            if (menuButton && !menuButton.closest('.ejecutar-modal-item')) {
                const labelText = menuButton.querySelector('.p-button-label')?.textContent;
                if (labelText && (labelText.includes('Ejecutar') || labelText.includes('Queue'))) {
                    if (modoEjecucion !== 'local') {
                        modoEjecucion = 'local';
                        actualizarBotonPrincipal();
                        console.log('✓ Modo de ejecución cambiado a: LOCAL');
                    }
                }
            }
        }, true);

        // ========== Descargar modelos en Modal con progreso ==========
        let processingItems = new Set();
        
        const observadorDialogoModelos = new MutationObserver(async () => {
            const listaItems = document.querySelectorAll('.comfy-missing-models .p-listbox-option');
            
            for (const item of listaItems) {
                const itemId = item.id;
                if (processingItems.has(itemId)) continue;
                if (item.querySelector('.descargar-modal-btn')) continue;
                
                processingItems.add(itemId);
                
                const contenedorBotones = item.querySelector('.flex.flex-row.items-center.gap-2');
                if (!contenedorBotones) {
                    processingItems.delete(itemId);
                    continue;
                }
                
                const spanTitulo = item.querySelector('span[title^="https"]');
                if (!spanTitulo) {
                    processingItems.delete(itemId);
                    continue;
                }
                
                const urlModelo = spanTitulo.getAttribute('title');
                const modeloTexto = spanTitulo.textContent;
                const modelInfo = parseModelInfo(modeloTexto);
                
                if (!modelInfo) {
                    processingItems.delete(itemId);
                    continue;
                }
                
                try {
                    const response = await fetch(`${API_BASE}/check_model`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(modelInfo)
                    });
                    
                    const result = await response.json();
                    
                    if (result.exists) {
                        console.log(`✓ Modelo ya existe en Modal: ${modelInfo.filename} (${result.size_gb})`);
                        item.remove();
                        processingItems.delete(itemId);
                        continue;
                    }
                } catch (error) {
                    console.warn('No se pudo verificar modelo en Modal:', error);
                }
                
                const nuevoBotonDiv = document.createElement('div');
                nuevoBotonDiv.innerHTML = `
                    <button class="p-button p-component p-button-outlined p-button-sm descargar-modal-btn" type="button" aria-label="Descargar en modal" data-pc-name="button" data-p-disabled="false" data-pc-section="root">
                        <span class="p-button-label" data-pc-section="label">Modal</span>
                    </button>
                `;
                
                const botonModal = nuevoBotonDiv.querySelector('button');
                
                botonModal.addEventListener('click', async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    const labelSpan = botonModal.querySelector('.p-button-label');
                    const originalText = labelSpan.textContent;
                    labelSpan.textContent = '0%';
                    botonModal.disabled = true;
                    
                    try {
                        const response = await fetch(`${API_BASE}/download_model`, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                url: urlModelo,
                                subfolder: modelInfo.subfolder,
                                filename: modelInfo.filename
                            })
                        });
                        
                        const result = await response.json();
                        
                        if (result.status === 'started' && result.task_id) {
                            pollProgress(result.task_id, labelSpan, () => {
                                console.log(`✓ Descarga completada: ${modelInfo.filename}`);
                                item.remove();
                                processingItems.delete(itemId);
                            });
                        } else if (result.status === 'already_exists') {
                            console.log(result.message);
                            item.remove();
                            processingItems.delete(itemId);
                        } else {
                            alert(`Error: ${result.message}`);
                            labelSpan.textContent = originalText;
                            botonModal.disabled = false;
                        }
                        
                        console.log('Resultado:', result);
                    } catch (error) {
                        alert(`Error de conexión: ${error.message}\n\nAsegúrate de que comfyui_modal_bridge.py está corriendo.`);
                        labelSpan.textContent = originalText;
                        botonModal.disabled = false;
                        console.error('Error:', error);
                    }
                });
                
                contenedorBotones.appendChild(nuevoBotonDiv);
            }
        });
        
        observadorDialogoModelos.observe(document.body, { childList: true, subtree: true });

        console.log('✓ Extensión Modal iniciada correctamente');
        console.log('   Modo inicial: LOCAL');
        console.log('   Cambia a Modal desde el menú desplegable del botón Ejecutar');
    }
});

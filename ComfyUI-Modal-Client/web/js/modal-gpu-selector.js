// modal-gpu-selector.js COMPLETO - SIN HISTORIAL + FIX 404s
import { app } from "/scripts/app.js"

app.registerExtension({
    name: 'modal.gpu.selector',
    async setup() {
        console.log('✅ Modal GPU Selector cargado')
        
        const API_BASE = 'http://127.0.0.1:5001'
        
        // Lista completa de GPUs de Modal
        const GPU_OPTIONS = [
            { name: 'Nvidia B200', price: 0.001736, value: 'B200', max: 8 },
            { name: 'Nvidia H200', price: 0.001261, value: 'H200', max: 8 },
            { name: 'Nvidia H100', price: 0.001097, value: 'H100', max: 8 },
            { name: 'Nvidia A100, 80 GB', price: 0.000694, value: 'A100-80GB', max: 8 },
            { name: 'Nvidia A100, 40 GB', price: 0.000583, value: 'A100', max: 8 },
            { name: 'Nvidia L40S', price: 0.000542, value: 'L40S', max: 8 },
            { name: 'Nvidia A10G', price: 0.000306, value: 'A10G', max: 4 },
            { name: 'Nvidia L4', price: 0.000222, value: 'L4', max: 8 },
            { name: 'Nvidia T4', price: 0.000164, value: 'T4', max: 8 }
        ]

        let activeGPU = localStorage.getItem('modalactivegpu') || 'T4'
        let gpuCounts = JSON.parse(localStorage.getItem('modalgpucounts') || '{}')
        if (!gpuCounts[activeGPU]) gpuCounts[activeGPU] = 1

        // Inicializar GPU global
        if (window.setSelectedGPU) window.setSelectedGPU(activeGPU)

        const formatPrice = (value) => '$' + value.toFixed(6)

        const saveState = () => {
            localStorage.setItem('modalactivegpu', activeGPU)
            localStorage.setItem('modalgpucounts', JSON.stringify(gpuCounts))
            if (window.setSelectedGPU) window.setSelectedGPU(activeGPU)
            console.log('💾 GPU actualizada:', activeGPU)
        }

        // ---------- UI helpers ----------
        const updateFooter = (panelElement) => {
            const footer = panelElement.querySelector('#modal-gpu-footer')
            if (!footer) return

            const data = GPU_OPTIONS.find(g => g.value === activeGPU)
            const count = gpuCounts[activeGPU] || 1
            const base = data ? data.price : 0
            const total = base * count

            footer.innerHTML = `
                <div class="text-xs opacity-70 mb-1">Configuración actual</div>
                <div class="font-semibold text-sm">${data ? data.name : 'Nvidia T4'} × ${count}</div>
                <div class="text-xs opacity-70 mt-1">
                    Precio base: ${formatPrice(base)}<br>
                    Total: ${formatPrice(total)}
                </div>
            `
        }

        const createGPUButton = () => {
            const sidebar = document.querySelector('.sidebar-item-group.flex.flex-col.items-center')
            if (!sidebar || document.querySelector('.modal-gpu-button')) {
                return
            }

            const gpuButton = document.createElement('button')
            gpuButton.className = 'p-button p-component p-button-icon-only p-button-text modal-gpu-button side-bar-button p-button-secondary'
            gpuButton.type = 'button'
            gpuButton.setAttribute('aria-label', 'GPU Selector (G)')
            gpuButton.setAttribute('data-pc-name', 'button')
            gpuButton.setAttribute('data-p-disabled', 'false')
            gpuButton.setAttribute('data-pc-section', 'root')
            gpuButton.setAttribute('data-pd-tooltip', 'true')
            gpuButton.title = 'GPU Selector (G)'
            
            gpuButton.innerHTML = `
                <div class="side-bar-button-content">
                    <svg class="side-bar-button-icon" xmlns="http://www.w3.org/2000/svg" width="1.2em" height="1.2em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M2 21V3"></path>
                        <path d="M2 5h18a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H2.26"></path>
                        <path d="M7 17v3a1 1 0 0 0 1 1h5a1 1 0 0 0 1-1v-3"></path>
                        <circle cx="16" cy="11" r="2"></circle>
                        <circle cx="8" cy="11" r="2"></circle>
                    </svg>
                    <span class="side-bar-button-label">GPU</span>
                </div>
                <span class="p-button-label" data-pc-section="label">&nbsp;</span>
            `

            const templatesButton = sidebar.querySelector('.templates-tab-button')
            if (templatesButton && templatesButton.parentNode) {
                templatesButton.parentNode.insertBefore(gpuButton, templatesButton.nextSibling)
            } else {
                sidebar.appendChild(gpuButton)
            }

            gpuButton.addEventListener('click', (e) => {
                e.preventDefault()
                e.stopPropagation()
                toggleGPUPanel()
            })
            
            console.log('✅ Botón GPU creado en sidebar')
        }

        const toggleGPUPanel = async () => {
            let panel = document.getElementById('modal-gpu-panel')
            if (panel) {
                panel.style.display = panel.style.display === 'none' ? 'flex' : 'none'
                return
            }

            // ✅ ELIMINADO: fetchQueue() y fetchHistory() - Sin llamadas 404

            panel = document.createElement('div')
            panel.id = 'modal-gpu-panel'
            panel.className = 'pointer-events-auto flex flex-col overflow-hidden rounded-lg border font-inter transition-colors duration-200 ease-in-out border-interface-stroke bg-comfy-menu-bg shadow-interface z-50'
            panel.style.cssText = `
                position: fixed;
                left: 60px;
                top: 50%;
                transform: translateY(-50%);
                width: 380px;
                max-height: 700px;
                z-index: 10000;
                display: flex;
                color: var(--fg-color);
            `

            const header = document.createElement('div')
            header.className = 'flex items-center justify-between p-4 border-b border-interface-stroke'
            header.style.cssText = 'background: var(--comfy-menu-bg); color: var(--fg-color)'
            header.innerHTML = `
                <div class="flex items-center gap-2">
                    <svg width="20" height="20" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M2 21V3"></path>
                        <path d="M2 5h18a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H2.26"></path>
                        <path d="M7 17v3a1 1 0 0 0 1 1h5a1 1 0 0 0 1-1v-3"></path>
                        <circle cx="16" cy="11" r="2"></circle>
                        <circle cx="8" cy="11" r="2"></circle>
                    </svg>
                    <span class="font-semibold text-sm">GPU Selector</span>
                </div>
                <button class="p-1 rounded hover:bg-interface-hover transition-colors" title="Cerrar">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            `

            const content = document.createElement('div')
            content.className = 'flex-1 overflow-y-auto p-4'
            content.style.cssText = 'background: var(--comfy-menu-bg); color: var(--fg-color)'
            content.gpuRows = []

            // ✅ ELIMINADO COMPLETAMENTE: historyPanel

            GPU_OPTIONS.forEach((gpu, index) => {
                const row = document.createElement('div')
                row.className = 'gpu-row mb-4 p-4 rounded-lg transition-all duration-200 cursor-pointer hover:bg-interface-hover'
                row.style.cssText = 'color: var(--fg-color); border: 2px solid transparent'
                row.dataset.gpuValue = gpu.value

                const count = gpuCounts[gpu.value] ?? (gpu.value === activeGPU ? 1 : 0)
                const totalPrice = gpu.price * count

                row.innerHTML = `
                    <div class="flex items-center justify-between mb-3 gpu-header">
                        <span class="font-semibold text-sm">${gpu.name}</span>
                        <div class="flex flex-col items-end text-right gpu-price-container">
                            <span class="text-xs opacity-70 base-price">Base: ${formatPrice(gpu.price)}</span>
                            <span class="text-sm font-bold total-price" style="color: var(--primary-color, #667eea)">Total: ${formatPrice(totalPrice)}</span>
                        </div>
                    </div>
                    <div class="flex items-center gap-3">
                        <label class="text-xs opacity-70 w-12 font-medium">Cant:</label>
                        <input type="range" class="gpu-slider flex-1 h-2 bg-interface-hover rounded-lg appearance-none cursor-pointer" min="0" max="${gpu.max}" value="${count}" step="1">
                        <span class="gpu-count text-sm font-bold font-mono w-10 text-center">${count}</span>
                    </div>
                    <div class="text-xs opacity-50 mt-2">Máx ${gpu.max} GPUs</div>
                `
                content.appendChild(row)
                content.gpuRows[index] = row

                const slider = row.querySelector('.gpu-slider')
                slider.addEventListener('input', (e) => {
                    const newCount = parseInt(e.target.value)
                    gpuCounts[gpu.value] = newCount
                    if (newCount > 0) {
                        activeGPU = gpu.value
                        GPU_OPTIONS.forEach(other => {
                            if (other.value !== gpu.value) gpuCounts[other.value] = 0
                        })
                    }
                    saveState()
                    refreshAllRows(content)
                    updateFooter(panel)
                })
            })

            const refreshAllRows = (contentEl) => {
                contentEl.gpuRows.forEach((row, idx) => {
                    const gpu = GPU_OPTIONS[idx]
                    const count = gpuCounts[gpu.value] ?? 0
                    const slider = row.querySelector('.gpu-slider')
                    const countSpan = row.querySelector('.gpu-count')
                    const priceBox = row.querySelector('.gpu-price-container .total-price')
                    const totalPrice = gpu.price * count

                    priceBox.textContent = `Total: ${formatPrice(totalPrice)}`

                    if (gpu.value === activeGPU && count > 0) {
                        row.style.border = '2px solid var(--primary-bg, #667eea)'
                        row.style.background = 'rgba(102, 126, 234, 0.1)'
                        row.style.opacity = '1'
                    } else {
                        row.style.border = '2px solid transparent'
                        row.style.background = 'transparent'
                        row.style.opacity = '0.7'
                    }

                    slider.value = count
                    countSpan.textContent = count
                })
            }

            const footer = document.createElement('div')
            footer.id = 'modal-gpu-footer'
            footer.className = 'p-4 border-t border-interface-stroke'
            footer.style.cssText = 'background: var(--comfy-menu-bg); color: var(--fg-color)'

            panel.appendChild(header)
            panel.appendChild(content)
            panel.appendChild(footer)

            document.body.appendChild(panel)
            refreshAllRows(content)
            updateFooter(panel)

            // Botón cerrar
            header.querySelector('button[title="Cerrar"]').addEventListener('click', () => {
                panel.style.display = 'none'
            })

            // ✅ ELIMINADO: refreshInterval con llamadas 404

            const closePanel = (e) => {
                if (!panel.contains(e.target) && !e.target.closest('.modal-gpu-button')) {
                    panel.style.display = 'none'
                    document.removeEventListener('click', closePanel)
                }
            }
            setTimeout(() => document.addEventListener('click', closePanel), 100)
        }

        const observer = new MutationObserver(() => {
            if (!document.querySelector('.modal-gpu-button')) {
                createGPUButton()
            }
        })
        observer.observe(document.body, { childList: true, subtree: true })

        const initButton = () => {
            createGPUButton()
        }
        initButton()
        setTimeout(initButton, 1000)
        setTimeout(initButton, 3000)
        setTimeout(initButton, 5000)

        // Tecla G
        document.addEventListener('keydown', (e) => {
            if (e.key.toLowerCase() === 'g' && !e.ctrlKey && !e.altKey && !e.shiftKey) {
                const activeEl = document.activeElement
                if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA')) return
                e.preventDefault()
                toggleGPUPanel()
            }
        })

        console.log('🚀 GPU Selector listo - Presiona G')
    }
})

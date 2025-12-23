import { app } from '/scripts/app.js';

app.registerExtension({
    name: "modal.media.panel",
    async setup() {
        const MODAL_VOLUME_URL = 'https://modal.com/api/volumes/camilafutanari/main/comfyui-outputs/files/content?path=';
        
        // Estado para tracking de imágenes
        let modalImages = [];

        // ✅ Hook para recibir imágenes desde modal-execution.js
        window.addEventListener('modal-images-ready', async (e) => {
            const images = e.detail?.images || [];
            console.log(`🎯 Imágenes recibidas desde Modal:`, images);
            
            // Agregar nuevas imágenes con sus URLs
            for (const imgInfo of images) {
                const imageUrl = `${MODAL_VOLUME_URL}${imgInfo.filename}`;
                
                // Evitar duplicados
                if (!modalImages.find(img => img.filename === imgInfo.filename)) {
                    modalImages.push({
                        filename: imgInfo.filename,
                        url: imageUrl,
                        timestamp: Date.now()
                    });
                }
            }
            
            console.log('✓ Imágenes agregadas. Total en memoria:', modalImages.length);
        });

        console.log('✓ Panel Modal cargado (modo directo desde Modal)');
    }
});

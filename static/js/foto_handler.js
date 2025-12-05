// foto_handler.js - Manejo de fotos para auto-save
(function () {
    // Esperar a que el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    function init() {
        // Interceptar la función global previewPhoto
        const originalPreviewPhoto = window.previewPhoto;

        window.previewPhoto = function (input, index) {
            // Llamar a la función original si existe
            if (originalPreviewPhoto) {
                originalPreviewPhoto(input, index);
            }

            // Agregar nuestra lógica para guardar Base64
            if (input.files && input.files[0]) {
                const reader = new FileReader();
                reader.onload = function (e) {
                    const hiddenData = document.getElementById(`foto${index}_data`);
                    if (hiddenData) {
                        hiddenData.value = e.target.result;
                        // Disparar evento change para que auto-save lo capture
                        const event = new Event('change', { bubbles: true });
                        hiddenData.dispatchEvent(event);
                    }
                };
                reader.readAsDataURL(input.files[0]);
            }
        };

        // Interceptar la función global removePhoto
        const originalRemovePhoto = window.removePhoto;

        window.removePhoto = function (index) {
            // Llamar a la función original si existe
            if (originalRemovePhoto) {
                originalRemovePhoto(index);
            }

            // Agregar nuestra lógica para limpiar Base64
            const hiddenData = document.getElementById(`foto${index}_data`);
            if (hiddenData) {
                hiddenData.value = '';
                // Disparar evento change para que auto-save lo capture
                const event = new Event('change', { bubbles: true });
                hiddenData.dispatchEvent(event);
            }
        };

        // Función para restaurar imágenes desde draft
        window.restorePhotosFromDraft = function (draft) {
            for (let i = 1; i <= 4; i++) {
                const fotoDataKey = `foto${i}_data`;
                const fotoData = draft[fotoDataKey];

                if (fotoData) {
                    // Restaurar preview
                    const previewContainer = document.getElementById(`foto${i}_preview_container`);
                    const previewImg = document.getElementById(`foto${i}_preview`);
                    const fotoInput = document.getElementById(`foto${i}_input`);
                    const hiddenData = document.getElementById(`foto${i}_data`);

                    if (previewImg && previewContainer) {
                        previewImg.src = fotoData;
                        previewContainer.style.display = 'block';
                        if (fotoInput) {
                            fotoInput.style.display = 'none';
                        }
                    }

                    if (hiddenData) {
                        hiddenData.value = fotoData;
                    }
                }
            }
        };

        console.log('foto_handler.js initialized - Photo auto-save enabled');
    }
})();

// ======== GLOBAL TOGGLE FUNCTION FOR READ-ONLY FIELDS ========
// This function is called from HTML onclick attributes
function toggleReadOnly(fieldId) {
    const field = document.getElementById(fieldId);
    const button = document.getElementById(`toggle_${fieldId}`);

    if (field && button) {
        if (field.readOnly) {
            // Unlock for editing
            field.readOnly = false;
            field.focus();
            button.textContent = '✏️';
            button.title = 'Bloquear';
        } else {
            // Lock again
            field.readOnly = true;
            button.textContent = '🔒';
            button.title = 'Editar';
        }
    }
}

// Enhanced client auto-fill with cascading selectors and multiple series handling
document.addEventListener('DOMContentLoaded', function () {
    loadClients();

    const clienteSelect = document.getElementById('cliente_select');
    const clienteInput = document.getElementById('cliente_input');
    const clienteToggle = document.getElementById('toggle_manual_client');

    // NEW: Updated references for tipo_equipo and modelo
    const tipoEquipoSelect = document.getElementById('tipo_equipo_select');
    const tipoEquipoInput = document.getElementById('tipo_equipo_input');
    const tipoEquipoToggle = document.getElementById('toggle_tipo_equipo');

    const modeloSelect = document.getElementById('modelo_select');
    const modeloInput = document.getElementById('modelo_input');
    const modeloToggle = document.getElementById('toggle_modelo');

    // Series elements
    const serieInput = document.getElementById('serie_input');
    const serieSelect = document.getElementById('serie_select');
    const serieToggle = document.getElementById('toggle_serie_manual');

    let clienteEquipos = [];  // Store client equipment data

    // NEW: Track toggle states
    let isClienteManual = false;
    let isTipoManual = false;
    let isModeloManual = false;
    let isSerieManual = true; // Default state tracking

    // ======== CLIENTE TOGGLE BUTTON ========
    if (clienteToggle) {
        clienteToggle.addEventListener('click', function () {
            if (isClienteManual) {
                // Switch to list mode
                clienteSelect.style.display = 'block';
                clienteSelect.disabled = false;
                clienteInput.style.display = 'none';
                clienteInput.disabled = true;
                clienteToggle.textContent = '✏️';
                clienteToggle.title = 'Entrada Manual';
                isClienteManual = false;
            } else {
                // Switch to manual mode
                clienteSelect.style.display = 'none';
                clienteSelect.disabled = true;
                clienteInput.style.display = 'block';
                clienteInput.disabled = false;
                clienteInput.classList.remove('mt-2');
                clienteToggle.textContent = '📋';
                clienteToggle.title = 'Seleccionar de Lista';
                isClienteManual = true;
            }
        });
    }

    // Client selection handler
    if (clienteSelect) {
        clienteSelect.addEventListener('change', async function () {
            const clienteId = this.value;
            const clienteText = this.options[this.selectedIndex].text;

            document.getElementById('cliente_id').value = clienteId;

            if (clienteInput) {
                clienteInput.value = clienteText !== 'Seleccione un cliente...' ? clienteText : '';
            }

            if (clienteId) {
                await loadClientData(clienteId);
            } else {
                clearClientData();
                clearEquipmentMarks();
            }
        });
    }

    // NEW: Tipo equipo selection handler (select)
    if (tipoEquipoSelect) {
        tipoEquipoSelect.addEventListener('change', function () {
            if (!isTipoManual) {
                tipoEquipoInput.value = this.value; // Sync to input
            }
            const selectedTipo = this.value;
            populateModelos(selectedTipo);
        });
    }

    // NEW: Tipo equipo toggle button
    if (tipoEquipoToggle) {
        tipoEquipoToggle.addEventListener('click', function () {
            if (isTipoManual) {
                // Switch to list mode
                tipoEquipoSelect.style.display = 'block';
                tipoEquipoSelect.disabled = false;
                tipoEquipoInput.style.display = 'none';
                tipoEquipoInput.disabled = true;
                tipoEquipoToggle.textContent = '✏️';
                tipoEquipoToggle.title = 'Entrada Manual';
                isTipoManual = false;
                // Sync value
                tipoEquipoInput.value = tipoEquipoSelect.value;
            } else {
                // Switch to manual mode
                tipoEquipoSelect.style.display = 'none';
                tipoEquipoSelect.disabled = true;
                tipoEquipoInput.style.display = 'block';
                tipoEquipoInput.disabled = false;
                tipoEquipoToggle.textContent = '📋';
                tipoEquipoToggle.title = 'Seleccionar de Lista';
                isTipoManual = true;
                // Sync value
                tipoEquipoInput.value = tipoEquipoSelect.value;
            }
        });
    }

    // NEW: Modelo selection handler (select)
    if (modeloSelect) {
        modeloSelect.addEventListener('change', function () {
            if (!isModeloManual) {
                modeloInput.value = this.value; // Sync to input
            }
            const selectedModelo = this.value;
            const selectedTipo = isTipoManual ? tipoEquipoInput.value : tipoEquipoSelect.value;
            handleModeloSelection(selectedTipo, selectedModelo);
        });
    }

    // NEW: Modelo toggle button
    if (modeloToggle) {
        modeloToggle.addEventListener('click', function () {
            if (isModeloManual) {
                // Switch to list mode
                modeloSelect.style.display = 'block';
                modeloSelect.disabled = false;
                modeloInput.style.display = 'none';
                modeloInput.disabled = true;
                modeloToggle.textContent = '✏️';
                modeloToggle.title = 'Entrada Manual';
                isModeloManual = false;
                // Sync value
                modeloInput.value = modeloSelect.value;
            } else {
                // Switch to manual mode
                modeloSelect.style.display = 'none';
                modeloSelect.disabled = true;
                modeloInput.style.display = 'block';
                modeloInput.disabled = false;
                modeloToggle.textContent = '📋';
                modeloToggle.title = 'Seleccionar de Lista';
                isModeloManual = true;
                // Sync value
                modeloInput.value = modeloSelect.value;
            }
        });
    }

    // Serie selection handler (Dropdown)
    if (serieSelect) {
        serieSelect.addEventListener('change', function () {
            const selectedSerie = this.value;
            const selectedModelo = isModeloManual ? modeloInput.value : modeloSelect.value;
            const selectedTipo = isTipoManual ? tipoEquipoInput.value : tipoEquipoSelect.value;

            if (selectedSerie) {
                // Sync input just in case
                if (serieInput) serieInput.value = selectedSerie;
                autoFillFromSerie(selectedTipo, selectedModelo, selectedSerie);
            } else {
                if (serieInput) serieInput.value = '';
            }
        });
    }

    // Serie Toggle Button
    if (serieToggle) {
        serieToggle.addEventListener('click', function () {
            if (serieInput.style.display === 'none') {
                switchToManualSerie();
            } else {
                const selectedModelo = isModeloManual ? modeloInput.value : modeloSelect.value;
                const selectedTipo = isTipoManual ? tipoEquipoInput.value : tipoEquipoSelect.value;
                const equipos = clienteEquipos.filter(e =>
                    e.tipo_equipo === selectedTipo && e.modelo === selectedModelo
                );

                if (equipos.length > 0) {
                    switchToListSerie(equipos);
                } else {
                    console.log("No series available for list mode");
                }
            }
        });
    }

    function switchToManualSerie() {
        if (serieInput) {
            serieInput.style.display = 'block';
            serieInput.disabled = false;
        }
        if (serieSelect) {
            serieSelect.style.display = 'none';
            serieSelect.disabled = true;
        }
        if (serieToggle) {
            serieToggle.textContent = '📋';
            serieToggle.title = 'Seleccionar de Lista';
        }
        isSerieManual = true;
    }

    function switchToListSerie(equipos) {
        if (serieInput) {
            serieInput.style.display = 'none';
            serieInput.disabled = true;
        }
        if (serieSelect) {
            serieSelect.style.display = 'block';
            serieSelect.disabled = false;

            // Populate
            serieSelect.innerHTML = '<option value="">Seleccione serie...</option>';
            equipos.forEach(eq => {
                const option = document.createElement('option');
                option.value = eq.serie;
                option.textContent = eq.serie;
                serieSelect.appendChild(option);
            });
        }
        if (serieToggle) {
            serieToggle.textContent = '✏️';
            serieToggle.title = 'Entrada Manual';
        }
        isSerieManual = false;
    }

    async function loadClients() {
        try {
            const response = await fetch('/api/clientes');
            const clientes = await response.json();

            const select = document.getElementById('cliente_select');
            if (!select) return;

            select.innerHTML = '<option value="">Seleccione un cliente...</option>';

            clientes.forEach(cliente => {
                const option = document.createElement('option');
                option.value = cliente.id;
                option.textContent = cliente.nombre;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('Error cargando clientes:', error);
        }
    }
    // Expose globally
    window.loadClients = loadClients;
    window.populateModelos = populateModelos;
    window.handleModeloSelection = handleModeloSelection;
    window.switchToListSerie = switchToListSerie; // Also useful
    window.switchToManualSerie = switchToManualSerie; // Also useful

    async function loadClientData(clienteId) {
        try {
            const response = await fetch(`/api/clientes/${clienteId}/equipos`);
            const data = await response.json();

            // Fill client contact info (will be read-only by default)
            if (data.cliente) {
                document.getElementById('contacto').value = data.cliente.contacto || '';
                document.getElementById('telefono').value = data.cliente.telefono || '';
                document.getElementById('email').value = data.cliente.email || '';
                document.getElementById('direccion').value = data.cliente.direccion || '';
            }

            // Store equipment data
            clienteEquipos = data.equipos || [];

            // Mark equipment types with stars
            markEquipmentTypes();

            // Clear modelo dropdown
            if (modeloSelect) {
                modeloSelect.innerHTML = '<option value="">Seleccione modelo...</option>';
            }

            // Reset series fields
            resetSerieFields();

        } catch (error) {
            console.error('Error cargando datos del cliente:', error);
        }
    }
    // Expose globally
    window.loadClientData = loadClientData;

    function markEquipmentTypes() {
        if (!tipoEquipoSelect) return;

        // Get unique equipment types for this client
        const clienteTipos = [...new Set(clienteEquipos.map(e => e.tipo_equipo))];

        // Add stars to options that match client equipment
        Array.from(tipoEquipoSelect.options).forEach(option => {
            if (option.value && clienteTipos.includes(option.value)) {
                if (!option.textContent.startsWith('★ ')) {
                    option.textContent = '★ ' + option.textContent;
                }
                // Style: Blue and Bold
                option.style.color = '#0d6efd';
                option.style.fontWeight = 'bold';
                option.style.backgroundColor = '#e7f1ff';
            } else {
                option.textContent = option.textContent.replace('★ ', '');
                option.style.color = '';
                option.style.fontWeight = '';
                option.style.backgroundColor = '';
            }
        });
    }

    function populateModelos(tipoEquipo) {
        if (!modeloSelect || !tipoEquipo) {
            if (modeloSelect) {
                modeloSelect.innerHTML = '<option value="">Seleccione modelo...</option>';
            }
            resetSerieFields();
            return;
        }

        // Filter equipment by selected type
        const equiposDelTipo = clienteEquipos.filter(e => e.tipo_equipo === tipoEquipo);

        // Get unique modelos
        const modelos = [...new Set(equiposDelTipo.map(e => e.modelo).filter(Boolean))];

        // Populate modelo dropdown
        modeloSelect.innerHTML = '<option value="">Seleccione modelo...</option>';
        modelos.forEach(modelo => {
            const option = document.createElement('option');
            option.value = modelo;
            option.textContent = modelo;
            modeloSelect.appendChild(option);
        });

        resetSerieFields();
    }

    function handleModeloSelection(tipoEquipo, modelo) {
        if (!tipoEquipo || !modelo) {
            resetSerieFields();
            return;
        }

        // Find matching equipment(s)
        const equipos = clienteEquipos.filter(e =>
            e.tipo_equipo === tipoEquipo && e.modelo === modelo
        );

        if (equipos.length === 0) {
            // No known series -> Manual mode
            switchToManualSerie();
            if (serieInput) serieInput.value = '';
            return;
        }

        if (equipos.length === 1) {
            // SINGLE SERIES -> Auto-fill in Manual Mode (Input)
            switchToManualSerie();

            const equipo = equipos[0];
            if (serieInput) serieInput.value = equipo.serie || '';

            autoFillDetails(equipo);

        } else {
            // MULTIPLE SERIES -> Show Dropdown
            switchToListSerie(equipos);
        }
    }

    function autoFillFromSerie(tipoEquipo, modelo, serie) {
        const equipo = clienteEquipos.find(e =>
            e.tipo_equipo === tipoEquipo && e.modelo === modelo && e.serie === serie
        );

        if (equipo) {
            autoFillDetails(equipo);
        }
    }

    function autoFillDetails(equipo) {
        // Fill marca
        const marcaSelect = document.getElementById('marca_select');
        if (marcaSelect && equipo.marca) {
            let matched = false;
            Array.from(marcaSelect.options).forEach(option => {
                if (option.value.toUpperCase() === equipo.marca.toUpperCase()) {
                    marcaSelect.value = option.value;
                    matched = true;
                }
            });

            if (!matched) {
                marcaSelect.value = 'OTROS';
                const otraMarcaInput = document.querySelector('input[name="otra_marca"]');
                if (otraMarcaInput) {
                    otraMarcaInput.value = equipo.marca;
                    document.getElementById('otra_marca_wrap').style.display = 'block';
                }
            }
            marcaSelect.dispatchEvent(new Event('change'));
        }

        // Fill potencia
        const potenciaInput = document.querySelector('input[name="potencia"]');
        if (potenciaInput) {
            potenciaInput.value = equipo.potencia || '';
        }
    }

    function resetSerieFields() {
        // Default to manual mode, empty
        switchToManualSerie();
        if (serieInput) serieInput.value = '';
        if (serieSelect) serieSelect.innerHTML = '<option value="">Seleccione serie...</option>';

        // Also clear other fields
        const marcaSelect = document.getElementById('marca_select');
        if (marcaSelect) marcaSelect.value = marcaSelect.options[0].value;

        const potenciaInput = document.querySelector('input[name="potencia"]');
        if (potenciaInput) potenciaInput.value = '';
    }

    function clearClientData() {
        document.getElementById('contacto').value = '';
        document.getElementById('telefono').value = '';
        document.getElementById('email').value = '';
        document.getElementById('direccion').value = '';
        clienteEquipos = [];
    }

    function clearEquipmentMarks() {
        if (!tipoEquipoSelect) return;

        Array.from(tipoEquipoSelect.options).forEach(option => {
            option.textContent = option.textContent.replace('★ ', '');
            option.style.color = '';
            option.style.fontWeight = '';
            option.style.backgroundColor = '';
        });
    }
});

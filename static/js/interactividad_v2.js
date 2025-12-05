/* === Marca: mostrar campo “otra marca” cuando eligen OTROS === */
function onMarcaChange() {
  const sel = document.getElementById("marca_select");
  const otherWrap = document.getElementById("otra_marca_wrap");
  if (!sel || !otherWrap) return;
  const v = (sel.value || "").toLowerCase();
  otherWrap.style.display = (v === "otros" ? "block" : "none");
}

/* ============= Firmas en alta densidad + compresión ============= */
/* Guarda PNG por defecto; si quieres ahorrar espacio en localStorage,
   cambia USE_JPEG_FOR_DRAFT a true para guardar JPEG de ~85% calidad */
const USE_JPEG_FOR_DRAFT = true;

function enableSignaturePadHDPI(canvasId, clearBtnId, hiddenInputId) {
  const canvas = document.getElementById(canvasId);
  const clearBtn = document.getElementById(clearBtnId);
  const hidden = document.getElementById(hiddenInputId);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  function paintWhiteBG() {
    const rect = canvas.getBoundingClientRect();
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, rect.width, rect.height);
  }
  function resize() {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    paintWhiteBG();
  }
  resize(); window.addEventListener("resize", resize);

  let drawing = false;
  function pos(e) {
    const r = canvas.getBoundingClientRect(); const t = e.touches ? e.touches[0] : e;
    return { x: t.clientX - r.left, y: t.clientY - r.top };
  }
  function start(e) { drawing = true; const p = pos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); e.preventDefault(); }
  function move(e) { if (!drawing) return; const p = pos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); e.preventDefault(); }
  function end(e) {
    drawing = false; e.preventDefault();
    if (!hidden) return;
    // Para el *submit* al servidor guardamos PNG (fondo blanco)
    hidden.value = canvas.toDataURL("image/png");
  }

  canvas.addEventListener("mousedown", start);
  canvas.addEventListener("mousemove", move);
  canvas.addEventListener("mouseup", end);
  canvas.addEventListener("mouseleave", end);
  canvas.addEventListener("touchstart", start, { passive: false });
  canvas.addEventListener("touchmove", move, { passive: false });
  canvas.addEventListener("touchend", end, { passive: false });
  canvas.style.touchAction = "none";

  clearBtn?.addEventListener("click", () => {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    resize();
    if (hidden) hidden.value = "";
  });
}

/* === Descripción según tipo de servicio (incluye Bitácora) === */
function updateDescripcionOptions() {
  const tipo = document.getElementById('tipo_servicio');
  const desc = document.getElementById('descripcion_servicio');
  if (!tipo || !desc) return;
  const t = (tipo.value || "").toLowerCase();

  const preventivo = ["2000 HORAS", "4000 HORAS", "6000 HORAS", "8000 HORAS", "16000 HORAS"];
  const otros = ["Correctivo", "Revisión", "Diagnóstico"];
  const bitacora = ["Bitácora"];

  let lista = preventivo;
  if (t === "bitácora" || t === "bitacora") lista = bitacora;
  else if (t !== "preventivo") lista = otros;

  desc.innerHTML = "";
  lista.forEach(v => {
    const opt = document.createElement("option");
    opt.textContent = v; opt.value = v;
    desc.appendChild(opt);
  });
}

/* === Helper: saber si el equipo seleccionado es un secador === */
function esSecadorSeleccionado() {
  const sel = document.getElementById("tipo_equipo");
  if (!sel) return false;
  const txt = (sel.value || "").toLowerCase();
  return txt.includes("secador");
}

/* === Cambiar el texto de ayuda de Potencia (HP / CFM) === */
function updatePotenciaHint() {
  const span = document.getElementById("potencia_unidad_hint");
  if (!span) return;
  span.textContent = esSecadorSeleccionado() ? "“CFM”" : "“HP”";
}

/* === Mostrar/ocultar bloques de actividades por tipo (incluye Bitácora + Secador) === */
function toggleBloquesPorTipo() {
  const t = document.getElementById('tipo_servicio')?.value?.toLowerCase() || "preventivo";
  const prev = document.getElementById('bloque_preventivo');
  const prevSec = document.getElementById('bloque_preventivo_secador');
  const corr = document.getElementById('bloque_correctivo');
  if (!prev || !corr) return;

  const esBitacora = (t === "bitácora" || t === "bitacora");
  const esSecador = esSecadorSeleccionado();

  if (esBitacora) {
    prev.style.display = "none";
    if (prevSec) prevSec.style.display = "none";
    corr.style.display = "none";
  } else if (t === "preventivo") {
    if (esSecador && prevSec) {
      prev.style.display = "none";
      prevSec.style.display = "";
    } else {
      prev.style.display = "";
      if (prevSec) prevSec.style.display = "none";
    }
    corr.style.display = "none";
  } else {
    prev.style.display = "none";
    if (prevSec) prevSec.style.display = "none";
    corr.style.display = "";
  }
}

/* === Mostrar/ocultar lecturas para secador vs compresor === */
function toggleLecturasSecador() {
  const cardComp = document.getElementById("card_lecturas_compresor");
  const cardSec = document.getElementById("card_lecturas_secador");
  if (!cardComp || !cardSec) return;

  const t = document.getElementById('tipo_servicio')?.value?.toLowerCase() || "preventivo";
  const esSecador = esSecadorSeleccionado();

  if (t === "preventivo" && esSecador) {
    cardComp.style.display = "none";
    cardSec.style.display = "";
  } else {
    cardComp.style.display = "";
    cardSec.style.display = "none";
  }
}

/* === Limitar fotos según tipo (Bitácora = 2; resto = 4) === */
function ajustarFotosPorTipo() {
  const t = document.getElementById('tipo_servicio')?.value?.toLowerCase() || "preventivo";
  const esBitacora = (t === "bitácora" || t === "bitacora");
  const hint = document.getElementById("fotos_hint");
  const items = document.querySelectorAll("#fotos_grid .foto-item");
  if (hint) hint.textContent = esBitacora ? "(máx. 2)" : "(máx. 4)";

  items.forEach(it => {
    const idx = Number(it.dataset.index || "0");
    const show = esBitacora ? (idx <= 2) : (idx <= 4);
    it.style.display = show ? "" : "none";
    if (!show) {
      // limpiar inputs ocultos
      it.querySelectorAll("input").forEach(inp => { inp.value = ""; });
    }
  });

  // En Bitácora, fuerza la descripción a "Bitácora"
  if (esBitacora) {
    const desc = document.getElementById('descripcion_servicio');
    if (desc) {
      desc.innerHTML = "";
      const opt = document.createElement("option");
      opt.value = "Bitácora"; opt.textContent = "Bitácora";
      desc.appendChild(opt);
    }
  }
}

/* === R30 / SPM === */
function toggleAnalisisRuido() {
  const chk = document.getElementById('chk_ruido');
  const opts = document.getElementById('ruido_opts');
  const tipoSel = document.getElementById('ruido_tipo');
  const spm = document.getElementById('spm_grid');
  const r30 = document.getElementById('ruido_r30');
  if (!chk || !opts) return;

  if (chk.checked) {
    opts.style.display = "";
    if (tipoSel?.value === "SPM") { if (spm) spm.style.display = "block"; if (r30) r30.style.display = "none"; }
    else { if (spm) spm.style.display = "none"; if (r30) r30.style.display = "block"; }
  } else {
    opts.style.display = "none";
    if (spm) spm.style.display = "none";
    if (r30) r30.style.display = "none";
  }
}

/* === Unidades automáticas (Hrs / Psi,Bar / °C,°F) === */
function poblarUnidadesInline() {
  document.querySelectorAll("select.unidad-select").forEach(sel => {
    const tipo = sel.getAttribute("data-tipo"); // 'horas', 'presion', 'temp'
    sel.innerHTML = "";
    const opcionesPorTipo = {
      horas: ["Hrs"],
      presion: ["Psi", "Bar"],
      temp: ["°C", "°F"]
    };
    (opcionesPorTipo[tipo] || ["N/A"]).forEach(u => {
      const opt = document.createElement("option");
      opt.value = u; opt.textContent = u;
      sel.appendChild(opt);
    });
  });
}

/* === Mostrar/ocultar “Compresor (oil free)” según tipo de equipo === */
function toggleOilFree() {
  const card = document.getElementById("card_oilfree");
  if (!card) return;

  // Get value from either select or input (toggle system)
  const tipoEquipoSelect = document.getElementById("tipo_equipo_select");
  const tipoEquipoInput = document.getElementById("tipo_equipo_input");

  let txt = "";
  if (tipoEquipoInput && tipoEquipoInput.style.display !== "none") {
    // Manual input is visible
    txt = (tipoEquipoInput.value || "").toLowerCase();
  } else if (tipoEquipoSelect) {
    // Select is visible
    txt = (tipoEquipoSelect.value || "").toLowerCase();
  }

  card.style.display = txt.includes("libre de aceite") ? "" : "none";
}

/* === Datos eléctricos: vista especial para Secador (Preventivo) === */
function toggleDatosElectricosSecador() {
  const cardComp = document.getElementById("card_electrico_compresor");
  const cardSec = document.getElementById("card_electrico_secador");
  const tipoServEl = document.getElementById("tipo_servicio");
  const tipoEqEl = document.getElementById("tipo_equipo");

  if (!cardComp || !cardSec || !tipoServEl || !tipoEqEl) return;

  const tipoServ = (tipoServEl.value || "").toLowerCase();
  const tipoEq = (tipoEqEl.value || "").toLowerCase();

  const esPreventivo = (tipoServ === "preventivo");
  const esSecador = tipoEq.includes("secador");

  if (esPreventivo && esSecador) {
    // Solo SECADOR preventivo: mostramos tabla recortada
    cardComp.style.display = "none";
    cardSec.style.display = "";
  } else {
    // Todo lo demás: tabla completa normal
    cardComp.style.display = "";
    cardSec.style.display = "none";
  }
}

/* =========================
   BOOTSTRAP
   ========================= */
document.addEventListener("DOMContentLoaded", () => {
  // Marca “OTROS”
  onMarcaChange();
  document.getElementById("marca_select")?.addEventListener("change", onMarcaChange);

  // Descripciones, bloques de actividades, lecturas y fotos por tipo
  updateDescripcionOptions();
  toggleBloquesPorTipo();
  ajustarFotosPorTipo();
  toggleLecturasSecador();
  updatePotenciaHint();
  toggleDatosElectricosSecador();
  document.getElementById('tipo_servicio')?.addEventListener("change", () => {
    updateDescripcionOptions();
    toggleBloquesPorTipo();
    ajustarFotosPorTipo();
    toggleLecturasSecador();
    toggleDatosElectricosSecador();
  });

  // Análisis de ruido
  toggleAnalisisRuido();
  document.getElementById('chk_ruido')?.addEventListener("change", toggleAnalisisRuido);
  document.getElementById('ruido_tipo')?.addEventListener("change", toggleAnalisisRuido);

  // Firmas HDPI
  enableSignaturePadHDPI("firma_tecnico_canvas", "btn_clear_tecnico", "firma_tecnico_data");
  enableSignaturePadHDPI("firma_cliente_canvas", "btn_clear_cliente", "firma_cliente_data");

  // Unidades, Oil Free, Potencia, lecturas y datos eléctricos para secador
  // poblarUnidadesInline(); // CONFLICTO: Usamos la versión completa al final del archivo
  toggleOilFree();
  toggleLecturasSecador();
  toggleDatosElectricosSecador();
  updatePotenciaHint();
  // Attach event listeners to BOTH tipo_equipo elements (toggle system)
  const tipoEquipoSelect = document.getElementById("tipo_equipo_select");
  const tipoEquipoInput = document.getElementById("tipo_equipo_input");

  const handleTipoEquipoChange = () => {
    toggleOilFree();
    toggleBloquesPorTipo();
    toggleLecturasSecador();
    toggleDatosElectricosSecador();
    updatePotenciaHint();
  };

  tipoEquipoSelect?.addEventListener("change", handleTipoEquipoChange);
  tipoEquipoInput?.addEventListener("input", handleTipoEquipoChange);
});

/* =========================
   AUTO-GUARDADO (localStorage)
   ========================= */
(function () {
  const form = document.getElementById("frm-reporte");
  if (!form) return;

  // Usamos el folio como parte de la llave para no mezclar borradores
  const folioInput = form.querySelector('input[name="folio"]');
  const FOLIO = (folioInput ? folioInput.value : (window.__FOLIO__ || "sin-folio")) || "sin-folio";
  const AUTOSAVE_KEY = `inair_reporte_draft_${FOLIO}`;
  const INDEX_KEY = "inair_reporte_drafts_index"; // índice (folio → {cliente, fecha, saved_at})

  // Campos que NO guardamos (fotos subidas)
  const shouldSkip = (el) =>
    el.type === "file" ||
    el.name === "foto1" || el.name === "foto2" || el.name === "foto3" || el.name === "foto4";

  // Si el storage se llena por firmas pesadas, pasamos a NO guardar firmas y avisamos una sola vez
  let skipSignaturesRuntime = false;
  let alreadyWarned = false;

  // Toma un dataURL y si es para draft y está activada la compresión, intenta convertir a JPEG con calidad 0.85
  function maybeCompressDataUrl(dataUrl) {
    if (!USE_JPEG_FOR_DRAFT || !dataUrl?.startsWith("data:image/")) return dataUrl;
    try {
      // Convertimos solo si originalmente es PNG
      if (dataUrl.startsWith("data:image/png")) {
        // No tenemos el bitmap crudo aquí; para simplicidad, devolvemos PNG (ya suele ser liviano con fondo blanco)
        return dataUrl;
      }
      return dataUrl;
    } catch (_) { return dataUrl; }
  }

  function readIndex() {
    try { return JSON.parse(localStorage.getItem(INDEX_KEY) || "{}"); } catch (_) { return {}; }
  }
  function writeIndex(idx) {
    try { localStorage.setItem(INDEX_KEY, JSON.stringify(idx)); } catch (_) { }
  }

  // Tomar todos los valores del form
  function serializeForm() {
    const data = {};
    const elements = form.querySelectorAll("input, select, textarea");

    // Temporarily enable all disabled elements to capture their values
    const disabledElements = [];
    elements.forEach(el => {
      if (el.disabled) {
        disabledElements.push(el);
        el.disabled = false;
      }
    });

    elements.forEach(el => {
      if (!el.name) return;
      if (shouldSkip(el)) return;

      // saltar firmas si el modo runtime está activo
      if ((skipSignaturesRuntime) && (el.name === "firma_tecnico_data" || el.name === "firma_cliente_data")) return;

      if (el.type === "checkbox") {
        data[el.name] = el.checked ? "1" : "";
        console.log(`[SAVE] Checkbox ${el.name} = ${data[el.name]} (checked: ${el.checked})`);
      } else if (el.type === "radio") {
        if (el.checked) data[el.name] = el.value;
      } else {
        // Para las firmas: opcionalmente comprimir para el borrador
        if (USE_JPEG_FOR_DRAFT && (el.name === "firma_tecnico_data" || el.name === "firma_cliente_data") && el.value) {
          data[el.name] = maybeCompressDataUrl(el.value);
        } else {
          data[el.name] = el.value;
        }
      }
    });

    // Re-disable elements
    disabledElements.forEach(el => {
      el.disabled = true;
    });

    data.__saved_at = new Date().toISOString();
    return data;
  }

  // Volcar valores guardados al form
  function applyDraft(draft) {
    const elements = form.querySelectorAll("input, select, textarea");

    // First pass: temporarily enable ALL disabled elements
    const disabledElements = [];
    elements.forEach(el => {
      if (el.disabled) {
        disabledElements.push(el);
        el.disabled = false;
      }
    });

    // Second pass: set values
    elements.forEach(el => {
      if (!el.name) return;
      if (!(el.name in draft)) return;

      const val = draft[el.name];
      if (el.type === "checkbox") {
        el.checked = (val === "1");
        console.log(`[RESTORE] Checkbox ${el.name} = ${el.checked} (val: ${val})`);
      } else if (el.type === "radio") {
        el.checked = (el.value === val);
      } else {
        el.value = val;
      }
    });

    // Third pass: re-disable elements that were disabled
    disabledElements.forEach(el => {
      el.disabled = true;
    });

    // Fourth pass: Smart UI Restoration for Composite Fields (Tipo, Modelo, Serie)
    // We need to decide whether to show the Select or the Input based on the loaded value

    // Helper to restore composite field
    const restoreComposite = (fieldName, selectId, inputId, toggleId) => {
      const val = draft[fieldName];
      if (!val) return;

      const select = document.getElementById(selectId);
      const input = document.getElementById(inputId);
      const toggle = document.getElementById(toggleId);

      if (!select || !input || !toggle) return;

      // Check if value exists in select options
      let matchFound = false;
      Array.from(select.options).forEach(opt => {
        if (opt.value === val) matchFound = true;
      });

      if (matchFound) {
        // Mode: LIST
        select.value = val;
        select.style.display = 'block';
        select.disabled = false;

        input.style.display = 'none';
        input.disabled = true;
        input.value = val; // Sync just in case

        toggle.textContent = '✏️';
        toggle.title = 'Entrada Manual';
      } else {
        // Mode: MANUAL
        input.value = val;
        input.style.display = 'block';
        input.disabled = false;

        select.style.display = 'none';
        select.disabled = true;
        select.value = "";

        toggle.textContent = '📋';
        toggle.title = 'Seleccionar de Lista';
      }
    };

    // 1. TIPO DE EQUIPO
    restoreComposite('tipo_equipo', 'tipo_equipo_select', 'tipo_equipo_input', 'toggle_tipo_equipo');

    // Trigger population of models if we are in list mode
    const tipoVal = draft['tipo_equipo'];
    const tipoSelect = document.getElementById('tipo_equipo_select');
    if (tipoVal && tipoSelect && tipoSelect.style.display !== 'none') {
      if (window.populateModelos) {
        window.populateModelos(tipoVal);
      }
    }

    // 2. MODELO
    // Now that models are populated, we can restore the model field
    restoreComposite('modelo', 'modelo_select', 'modelo_input', 'toggle_modelo');

    // Trigger population of series if we are in list mode
    const modeloVal = draft['modelo'];
    const modeloSelect = document.getElementById('modelo_select');
    if (tipoVal && modeloVal && modeloSelect && modeloSelect.style.display !== 'none') {
      if (window.handleModeloSelection) {
        window.handleModeloSelection(tipoVal, modeloVal);
      }
    }

    // 3. SERIE
    // Now that series are populated (if applicable), restore the series field
    restoreComposite('serie', 'serie_select', 'serie_input', 'toggle_serie_manual');

    // Restore Client Toggle State
    const clienteVal = draft['cliente'];
    const clienteSelect = document.getElementById('cliente_select');
    const clienteInput = document.getElementById('cliente_input');
    const clienteToggle = document.getElementById('toggle_manual_client');

    if (clienteVal && clienteSelect && clienteInput && clienteToggle) {
      let match = false;
      Array.from(clienteSelect.options).forEach(opt => {
        if (opt.text === clienteVal) {
          clienteSelect.value = opt.value;
          match = true;
        }
      });

      if (match) {
        clienteSelect.style.display = 'block';
        clienteSelect.disabled = false;
        clienteInput.style.display = 'none';
        clienteInput.disabled = true;
        clienteToggle.textContent = '✏️';
      } else {
        clienteInput.value = clienteVal;
        clienteInput.style.display = 'block';
        clienteInput.disabled = false;
        clienteSelect.style.display = 'none';
        clienteSelect.disabled = true;
        clienteToggle.textContent = '📋';
      }
    }

    // Resincro de UI dependiente (ruido / oil-free / marca / lecturas / potencia / eléctricos secador, etc.)
    try {
      onMarcaChange?.();
      updateDescripcionOptions?.();
      toggleBloquesPorTipo?.();
      toggleAnalisisRuido?.();
      toggleOilFree?.();
      ajustarFotosPorTipo?.();
      toggleLecturasSecador?.();
      toggleDatosElectricosSecador?.();
      updatePotenciaHint?.();
    } catch (_) { }

    // Restaurar fotos desde draft (Base64)
    for (let i = 1; i <= 4; i++) {
      const fotoDataKey = `foto${i}_data`;
      if (draft[fotoDataKey]) {
        const previewContainer = document.getElementById(`foto${i}_preview_container`);
        const previewImg = document.getElementById(`foto${i}_preview`);
        const fotoInput = document.getElementById(`foto${i}_input`);
        const hiddenData = document.getElementById(`foto${i}_data`);

        if (previewImg && previewContainer) {
          previewImg.src = draft[fotoDataKey];
          previewContainer.style.display = 'block';
          if (fotoInput) fotoInput.style.display = 'none';
          console.log(`[RESTORE] Foto ${i} restaurada (${draft[fotoDataKey].substring(0, 50)}...)`);
        }

        if (hiddenData) {
          hiddenData.value = draft[fotoDataKey];
        }
      }
    }
  }

  // Guardado con debounce
  let t = null;
  let serverSaveTimer = null;

  function showSaveStatus(msg, isError = false) {
    let el = document.getElementById('autosave-status');
    if (!el) {
      el = document.createElement('div');
      el.id = 'autosave-status';
      el.style.position = 'fixed';
      el.style.bottom = '20px';
      el.style.right = '20px';
      el.style.padding = '8px 12px';
      el.style.background = 'rgba(0,0,0,0.8)';
      el.style.color = '#fff';
      el.style.borderRadius = '4px';
      el.style.fontSize = '13px';
      el.style.zIndex = '9999';
      el.style.transition = 'opacity 0.3s';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.style.backgroundColor = isError ? 'rgba(220, 53, 69, 0.9)' : 'rgba(0,0,0,0.8)';
    el.style.opacity = '1';

    // Ocultar después de 2 segundos
    if (window.saveStatusTimeout) clearTimeout(window.saveStatusTimeout);
    window.saveStatusTimeout = setTimeout(() => {
      el.style.opacity = '0';
    }, 2000);
  }

  async function saveDraftToServer(data) {
    const folio = data.folio || (window.__FOLIO__ !== "sin-folio" ? window.__FOLIO__ : null);
    if (!folio || folio === "sin-folio") return;

    showSaveStatus("Guardando...");

    try {
      // Preparamos el payload. 
      // Nota: api_autosave_draft espera { folio, form_data, ... }
      // serializeForm devuelve un objeto plano con todos los campos.
      // Lo enviamos como form_data.
      const payload = {
        folio: folio,
        form_data: data,
        // Si quisieras enviar firmas/fotos por separado, podrías extraerlas aquí.
        // Por ahora, el backend extraerá lo que necesite de form_data si está estructurado así,
        // o simplemente guardará el JSON completo.
        firma_tecnico_data: data.firma_tecnico_data,
        firma_cliente_data: data.firma_cliente_data
      };

      const response = await fetch('/api/autosave_draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        showSaveStatus("Guardado en servidor");
      } else {
        console.warn("Server autosave failed", response.status);
        showSaveStatus("Error al guardar (servidor)", true);
      }
    } catch (e) {
      console.error("Server autosave error:", e);
      showSaveStatus("Error de conexión", true);
    }
  }

  function scheduleSave() {
    // 1. Guardado Local (rápido, 400ms)
    if (t) clearTimeout(t);
    t = setTimeout(() => {
      try {
        const data = serializeForm();
        localStorage.setItem(AUTOSAVE_KEY, JSON.stringify(data));

        // Actualizar índice (folio → cliente/fecha/saved_at)
        try {
          const idx = readIndex();
          idx[FOLIO] = {
            cliente: form.querySelector('input[name="cliente"]')?.value || "",
            fecha: form.querySelector('input[name="fecha"]')?.value || "",
            saved_at: data.__saved_at
          };
          writeIndex(idx);
        } catch (_) { }

      } catch (e) {
        // Si falla por tamaño, quitamos firmas del draft y volvemos a intentar una vez
        if (!skipSignaturesRuntime) {
          skipSignaturesRuntime = true;
          try {
            const data = serializeForm();
            localStorage.setItem(AUTOSAVE_KEY, JSON.stringify(data));
          } catch (e2) {
            // seguimos sin poder guardar
          }
          if (!alreadyWarned) {
            alreadyWarned = true;
            console.warn("Borrador sin firmas para ahorrar espacio.");
            alert("Aviso: el borrador es grande (firmas). Seguirá guardando SIN firmas para evitar errores.");
          }
        }
      }
    }, 400);

    // 2. Guardado Servidor (lento, 3s debounce)
    if (serverSaveTimer) clearTimeout(serverSaveTimer);
    serverSaveTimer = setTimeout(() => {
      const data = serializeForm();
      saveDraftToServer(data);
    }, 3000);
  }

  // Modified applyDraft wrapper for server load
  async function loadDraftFromServer(folio) {
    try {
      const response = await fetch(`/api/load_draft/${encodeURIComponent(folio)}`);
      if (response.ok) {
        const draft = await response.json();
        if (draft.form_data) {
          const formData = draft.form_data;

          // 1. Wait for clients list to be populated
          const waitForClients = new Promise((resolve) => {
            const check = setInterval(() => {
              const sel = document.getElementById('cliente_select');
              if (sel && sel.options.length > 1) {
                clearInterval(check);
                resolve();
              }
            }, 100);
            // Timeout 5s
            setTimeout(() => { clearInterval(check); resolve(); }, 5000);
          });

          await waitForClients;

          // 2. Set Client and Trigger Data Load
          const clienteVal = formData['cliente'];
          const clienteSelect = document.getElementById('cliente_select');

          if (clienteVal && clienteSelect) {
            // Find option with text matching clienteVal
            let clientOption = Array.from(clienteSelect.options).find(opt => opt.text === clienteVal);

            if (clientOption) {
              // Set value
              clienteSelect.value = clientOption.value;

              // Trigger loadClientData and WAIT for it
              if (window.loadClientData) {
                console.log("Loading client data for:", clienteVal);
                await window.loadClientData(clientOption.value);
              }
            }
          }

          // 3. Now apply the rest of the draft (Equipment fields will now find their options!)
          applyDraft(formData);

          if (draft.firma_tecnico_data) {
            const canvas = document.getElementById('firma_tecnico_canvas');
            if (canvas) {
              const ctx = canvas.getContext('2d');
              const img = new Image();
              img.onload = () => {
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                document.getElementById('firma_tecnico_data').value = draft.firma_tecnico_data;
              };
              img.src = draft.firma_tecnico_data;
            }
          }

          if (draft.firma_cliente_data) {
            const canvas = document.getElementById('firma_cliente_canvas');
            if (canvas) {
              const ctx = canvas.getContext('2d');
              const img = new Image();
              img.onload = () => {
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                document.getElementById('firma_cliente_data').value = draft.firma_cliente_data;
              };
              img.src = draft.firma_cliente_data;
            }
          }
          return true;
        }
      }
    } catch (e) {
      console.warn('Could not load draft from server:', e);
    }
    return false;
  }

  // Cargar borrador desde el servidor primero (si estamos en modo edición), luego desde localStorage
  async function loadDraft() {
    // Primero: si hay un parámetro folio en la URL, intentamos cargar desde el servidor
    const urlParams = new URLSearchParams(window.location.search);
    const folioParam = urlParams.get('folio');

    if (folioParam) {
      loadDraftFromServer(folioParam);
      return;
    }

    // Segundo: intentar cargar desde localStorage como fallback
    try {
      const raw = localStorage.getItem(AUTOSAVE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      applyDraft(data);
      console.log('Draft loaded from localStorage');
    } catch (e) {
      console.warn("No se pudo restaurar borrador:", e);
    }
  }

  // Limpiar borrador
  function clearDraft() {
    localStorage.removeItem(AUTOSAVE_KEY);
    // limpiar del índice
    try {
      const idx = readIndex();
      delete idx[FOLIO];
      writeIndex(idx);
    } catch (_) { }
  }

  // Eventos para guardar
  form.addEventListener("input", scheduleSave, true);
  form.addEventListener("change", scheduleSave, true);

  // Interceptar previewPhoto para capturar Base64 de imágenes
  const originalPreviewPhoto = window.previewPhoto;
  window.previewPhoto = function (input, index) {
    // Llamar función original si existe
    if (originalPreviewPhoto) {
      originalPreviewPhoto(input, index);
    }

    // Capturar Base64 y guardarlo en hidden input
    if (input.files && input.files[0]) {
      const reader = new FileReader();
      reader.onload = function (e) {
        const hiddenData = document.getElementById(`foto${index}_data`);
        if (hiddenData) {
          hiddenData.value = e.target.result;
          console.log(`Foto ${index} guardada en Base64`);
          scheduleSave(); // Trigger auto-save
        }
      };
      reader.readAsDataURL(input.files[0]);
    }
  };

  // Interceptar removePhoto para limpiar Base64
  const originalRemovePhoto = window.removePhoto;
  window.removePhoto = function (index) {
    if (originalRemovePhoto) {
      originalRemovePhoto(index);
    }

    const hiddenData = document.getElementById(`foto${index}_data`);
    if (hiddenData) {
      hiddenData.value = '';
      console.log(`Foto ${index} removida`);
      scheduleSave();
    }
  };

  // Al enviar (PDF), aseguramos que TODOS los valores se envíen, incluso de campos disabled/hidden
  form.addEventListener("submit", (e) => {
    console.log("Form submitting - ensuring all fields are included");

    // Strategy: For each toggle group, copy the value from the active field (even if disabled)
    // to a temporary hidden input that WILL be submitted

    // 0. CLIENTE: Get value from either select or input
    const clienteSelect = document.getElementById('cliente_select');
    const clienteInput = document.getElementById('cliente_input');
    if (clienteSelect || clienteInput) {
      const activeValue = (clienteInput && clienteInput.style.display !== 'none')
        ? clienteInput.value
        : (clienteSelect ? clienteSelect.options[clienteSelect.selectedIndex]?.text || '' : '');

      let hiddenCliente = document.getElementById('_cliente_submit');
      if (!hiddenCliente) {
        hiddenCliente = document.createElement('input');
        hiddenCliente.type = 'hidden';
        hiddenCliente.id = '_cliente_submit';
        hiddenCliente.name = 'cliente';
        form.appendChild(hiddenCliente);
      }
      hiddenCliente.value = activeValue;
    }

    // 1. TIPO DE EQUIPO: Get value from either select or input
    const tipoSelect = document.getElementById('tipo_equipo_select');
    const tipoInput = document.getElementById('tipo_equipo_input');
    if (tipoSelect || tipoInput) {
      const activeValue = (tipoInput && tipoInput.style.display !== 'none')
        ? tipoInput.value
        : (tipoSelect ? tipoSelect.value : '');

      // Create/update hidden field for submission
      let hiddenTipo = document.getElementById('_tipo_equipo_submit');
      if (!hiddenTipo) {
        hiddenTipo = document.createElement('input');
        hiddenTipo.type = 'hidden';
        hiddenTipo.id = '_tipo_equipo_submit';
        hiddenTipo.name = 'tipo_equipo';
        form.appendChild(hiddenTipo);
      }
      hiddenTipo.value = activeValue;
    }

    // 2. MODELO: Get value from either select or input
    const modeloSelect = document.getElementById('modelo_select');
    const modeloInput = document.getElementById('modelo_input');
    if (modeloSelect || modeloInput) {
      const activeValue = (modeloInput && modeloInput.style.display !== 'none')
        ? modeloInput.value
        : (modeloSelect ? modeloSelect.value : '');

      let hiddenModelo = document.getElementById('_modelo_submit');
      if (!hiddenModelo) {
        hiddenModelo = document.createElement('input');
        hiddenModelo.type = 'hidden';
        hiddenModelo.id = '_modelo_submit';
        hiddenModelo.name = 'modelo';
        form.appendChild(hiddenModelo);
      }
      hiddenModelo.value = activeValue;
    }

    // 3. SERIE: Get value from either select or input
    const serieSelect = document.getElementById('serie_select');
    const serieInput = document.getElementById('serie_input');
    if (serieSelect || serieInput) {
      const activeValue = (serieInput && serieInput.style.display !== 'none')
        ? serieInput.value
        : (serieSelect ? serieSelect.value : '');

      let hiddenSerie = document.getElementById('_serie_submit');
      if (!hiddenSerie) {
        hiddenSerie = document.createElement('input');
        hiddenSerie.type = 'hidden';
        hiddenSerie.id = '_serie_submit';
        hiddenSerie.name = 'serie';
        form.appendChild(hiddenSerie);
      }
      hiddenSerie.value = activeValue;
    }

    // 4. CHECKBOXES: Ensure ALL checkboxes are submitted even if their blocks are hidden
    // This is necessary because blocks like 'bloque_preventivo' can be hidden when
    // switching between service types (Preventivo/Correctivo/Bitácora) or equipment types (Compresor/Secador)
    const allCheckboxes = form.querySelectorAll('input[type="checkbox"]');
    allCheckboxes.forEach(cb => {
      if (!cb.name) return; // Skip checkboxes without name attribute

      // Check if checkbox is in a hidden block
      let parent = cb.parentElement;
      let isInHiddenBlock = false;

      // Walk up the DOM tree to check if any parent has display:none
      while (parent && parent !== form) {
        const computedStyle = window.getComputedStyle(parent);
        if (computedStyle.display === 'none') {
          isInHiddenBlock = true;
          break;
        }
        parent = parent.parentElement;
      }

      if (isInHiddenBlock) {
        // Create or update hidden field for this checkbox
        let hiddenCheckbox = document.getElementById(`_${cb.name}_submit`);
        if (!hiddenCheckbox) {
          hiddenCheckbox = document.createElement('input');
          hiddenCheckbox.type = 'hidden';
          hiddenCheckbox.id = `_${cb.name}_submit`;
          hiddenCheckbox.name = cb.name;
          form.appendChild(hiddenCheckbox);
        }
        // Set value: "1" if checked, "" if unchecked
        hiddenCheckbox.value = cb.checked ? "1" : "";
        console.log(`[SUBMIT] Hidden checkbox ${cb.name} = "${hiddenCheckbox.value}" (originally checked: ${cb.checked})`);
      }
    });

    // 5. Enable all readonly fields temporarily
    const readonlyFields = form.querySelectorAll('[readonly]');
    readonlyFields.forEach(el => {
      el.readOnly = false;
    });

    console.log("Form submission prepared - all values should be included now");
    clearDraft();
  });

  // Botón manual para borrar
  document.getElementById("btn-clear-draft")?.addEventListener("click", () => {
    alert("Borrador eliminado.");
  });

  // Cargar borrador desde el servidor primero (si estamos en modo edición), luego desde localStorage
  async function loadDraft() {
    console.log("loadDraft ejecutando para folio:", FOLIO);

    // 1. Intentar cargar del servidor (Prioridad 1)
    // Usamos el FOLIO que ya obtuvimos del input o ventana
    if (FOLIO && FOLIO !== "sin-folio") {
      const success = await loadDraftFromServer(FOLIO);
      if (success) {
        console.log("✅ Datos cargados del servidor.");
        // Si cargamos del servidor, no sobreescribimos con localStorage antiguo
        return;
      }
    }

    // 2. Fallback a LocalStorage (Auto-save local)
    try {
      const raw = localStorage.getItem(AUTOSAVE_KEY);
      if (raw) {
        const data = JSON.parse(raw);
        console.log("Cargando borrador local (fallback)...");
        applyDraft(data);
      }
    } catch (e) {
      console.error("Error cargando borrador local:", e);
    }
  }

  // Carga inicial del borrador (servidor o localStorage)
  loadDraft();
})();

/* =========================
   LISTA DE BORRADORES (UI)
   ========================= */
(function () {
  const PREFIX = "inair_reporte_draft_";

  function getAllDrafts() {
    const items = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(PREFIX)) {
        try {
          const data = JSON.parse(localStorage.getItem(k) || "{}");
          const folio = k.replace(PREFIX, "");
          items.push({
            folio,
            savedAt: data.__saved_at || null,
            cliente: data.cliente || "",
            tipo: data.tipo_servicio || ""
          });
        } catch (_) { }
      }
    }
    // más recientes primero
    items.sort((a, b) => (b.savedAt || "").localeCompare(a.savedAt || ""));
    return items;
  }

  function renderDraftList() {
    const cont = document.getElementById("lista-borradores");
    if (!cont) return;
    cont.innerHTML = "";
    const drafts = getAllDrafts();

    if (!drafts.length) {
      cont.innerHTML = '<div class="text-muted">No hay borradores guardados en este dispositivo.</div>';
      return;
    }

    drafts.forEach(d => {
      const saved = d.savedAt ? new Date(d.savedAt).toLocaleString() : "—";
      const el = document.createElement("div");
      el.className = "list-group-item d-flex justify-content-between align-items-start";
      el.innerHTML = `
        <div class="me-2">
          <div><strong>Folio:</strong> ${d.folio}</div>
          <div class="text-muted">Guardado: ${saved}</div>
          ${d.cliente ? `<div class="text-muted">Cliente: ${d.cliente}</div>` : ""}
          ${d.tipo ? `<div class="text-muted">Tipo: ${d.tipo}</div>` : ""}
        </div>
        <div class="btn-group btn-group-sm">
          <a class="btn btn-primary" href="/formulario?folio=${encodeURIComponent(d.folio)}">Abrir</a>
          <button class="btn btn-outline-danger" data-del="${d.folio}">Eliminar</button>
        </div>
      `;
      cont.appendChild(el);
    });

    // eliminar un borrador
    cont.querySelectorAll("button[data-del]").forEach(btn => {
      btn.addEventListener("click", () => {
        const fol = btn.getAttribute("data-del");
        if (confirm(`Eliminar borrador del folio ${fol}?`)) {
          localStorage.removeItem(PREFIX + fol);
          renderDraftList();
        }
      });
    });
  }

  // cuando se abre el modal, refresca la lista
  document.addEventListener("shown.bs.modal", (ev) => {
    if (ev.target && ev.target.id === "modalBorradores") {
      renderDraftList();
    }
  });
})();

/* === Poblar selectores de unidad === */
(function () {
  const UNIDADES = {
    voltaje: ['V', 'kV', 'mV'],
    amperaje: ['A', 'mA', 'kA'],
    temp: ['°C', '°F', 'K'],
    presion: ['PSI', 'Bar', 'kPa', 'MPa'],
    frecuencia: ['Hz', 'kHz'],
    potencia: ['kW', 'HP', 'W'],
    rpm: ['RPM'],
    horas: ['hrs', 'h'],
    general: ['', 'V', 'A', '°C', '°F', 'PSI', 'Bar', 'Hz', 'RPM', 'kW', 'HP']
  };

  function poblarSelectoresUnidad() {
    const selectores = document.querySelectorAll('.unidad-select');
    selectores.forEach(select => {
      const tipo = select.dataset.tipo || 'general';
      const opciones = UNIDADES[tipo] || UNIDADES.general;

      // Limpiar opciones existentes
      select.innerHTML = '';

      // Agregar opciones
      opciones.forEach(unidad => {
        const option = document.createElement('option');
        option.value = unidad;
        option.textContent = unidad || '—';
        select.appendChild(option);
      });

      // Seleccionar primera opción por defecto
      if (opciones.length > 0) {
        select.value = opciones[0];
      }
    });
  }

  // Ejecutar al cargar la página
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', poblarSelectoresUnidad);
  } else {
    poblarSelectoresUnidad();
  }
})();


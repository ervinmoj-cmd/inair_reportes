/* === Marca: mostrar campo “otra marca” cuando eligen OTROS === */
function onMarcaChange(){
  const sel = document.getElementById("marca_select");
  const otherWrap = document.getElementById("otra_marca_wrap");
  if(!sel || !otherWrap) return;
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
  function pos(e){ const r = canvas.getBoundingClientRect(); const t = e.touches?e.touches[0]:e;
    return {x:t.clientX-r.left, y:t.clientY-r.top}; }
  function start(e){ drawing = true; const p=pos(e); ctx.beginPath(); ctx.moveTo(p.x,p.y); e.preventDefault(); }
  function move(e){ if(!drawing) return; const p=pos(e); ctx.lineTo(p.x,p.y); ctx.stroke(); e.preventDefault(); }
  function end(e){ drawing = false; e.preventDefault();
    if(!hidden) return;
    // Para el *submit* al servidor guardamos PNG (fondo blanco)
    hidden.value = canvas.toDataURL("image/png");
  }

  canvas.addEventListener("mousedown", start);
  canvas.addEventListener("mousemove", move);
  canvas.addEventListener("mouseup", end);
  canvas.addEventListener("mouseleave", end);
  canvas.addEventListener("touchstart", start, {passive:false});
  canvas.addEventListener("touchmove", move, {passive:false});
  canvas.addEventListener("touchend", end, {passive:false});
  canvas.style.touchAction = "none";

  clearBtn?.addEventListener("click", () => {
    ctx.setTransform(1,0,0,1,0,0);
    ctx.clearRect(0,0,canvas.width,canvas.height);
    resize();
    if(hidden) hidden.value="";
  });
}

/* === Descripción según tipo de servicio (incluye Bitácora) === */
function updateDescripcionOptions(){
  const tipo = document.getElementById('tipo_servicio');
  const desc = document.getElementById('descripcion_servicio');
  if (!tipo || !desc) return;
  const t = (tipo.value || "").toLowerCase();

  const preventivo = ["2000 HORAS","4000 HORAS","6000 HORAS","8000 HORAS","16000 HORAS"];
  const otros = ["Correctivo","Revisión","Diagnóstico"];
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
function esSecadorSeleccionado(){
  const sel = document.getElementById("tipo_equipo");
  if (!sel) return false;
  const txt = (sel.value || "").toLowerCase();
  return txt.includes("secador");
}

/* === Cambiar el texto de ayuda de Potencia (HP / CFM) === */
function updatePotenciaHint(){
  const span = document.getElementById("potencia_unidad_hint");
  if (!span) return;
  span.textContent = esSecadorSeleccionado() ? "“CFM”" : "“HP”";
}

/* === Mostrar/ocultar bloques de actividades por tipo (incluye Bitácora + Secador) === */
function toggleBloquesPorTipo(){
  const t = document.getElementById('tipo_servicio')?.value?.toLowerCase() || "preventivo";
  const prev = document.getElementById('bloque_preventivo');
  const prevSec = document.getElementById('bloque_preventivo_secador');
  const corr = document.getElementById('bloque_correctivo');
  if (!prev || !corr) return;

  const esBitacora = (t === "bitácora" || t === "bitacora");
  const esSecador = esSecadorSeleccionado();

  if (esBitacora){
    prev.style.display = "none";
    if (prevSec) prevSec.style.display = "none";
    corr.style.display = "none";
  } else if (t === "preventivo") {
    if (esSecador && prevSec){
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
function toggleLecturasSecador(){
  const cardComp = document.getElementById("card_lecturas_compresor");
  const cardSec = document.getElementById("card_lecturas_secador");
  if (!cardComp || !cardSec) return;

  const t = document.getElementById('tipo_servicio')?.value?.toLowerCase() || "preventivo";
  const esSecador = esSecadorSeleccionado();

  if (t === "preventivo" && esSecador){
    cardComp.style.display = "none";
    cardSec.style.display = "";
  } else {
    cardComp.style.display = "";
    cardSec.style.display = "none";
  }
}

/* === Limitar fotos según tipo (Bitácora = 2; resto = 4) === */
function ajustarFotosPorTipo(){
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
function toggleAnalisisRuido(){
  const chk = document.getElementById('chk_ruido');
  const opts = document.getElementById('ruido_opts');
  const tipoSel = document.getElementById('ruido_tipo');
  const spm = document.getElementById('spm_grid');
  const r30 = document.getElementById('ruido_r30');
  if (!chk || !opts) return;

  if (chk.checked){
    opts.style.display = "";
    if (tipoSel?.value === "SPM"){ if(spm) spm.style.display = "block"; if(r30) r30.style.display = "none"; }
    else { if(spm) spm.style.display = "none"; if(r30) r30.style.display = "block"; }
  } else {
    opts.style.display = "none";
    if(spm) spm.style.display = "none";
    if(r30) r30.style.display = "none";
  }
}

/* === Unidades automáticas (Hrs / Psi,Bar / °C,°F) === */
function poblarUnidadesInline(){
  document.querySelectorAll("select.unidad-select").forEach(sel=>{
    const tipo = sel.getAttribute("data-tipo"); // 'horas', 'presion', 'temp'
    sel.innerHTML = "";
    const opcionesPorTipo = {
      horas: ["Hrs"],
      presion: ["Psi","Bar"],
      temp: ["°C","°F"]
    };
    (opcionesPorTipo[tipo] || ["N/A"]).forEach(u=>{
      const opt = document.createElement("option");
      opt.value = u; opt.textContent = u;
      sel.appendChild(opt);
    });
  });
}

/* === Mostrar/ocultar “Compresor (oil free)” según tipo de equipo === */
function toggleOilFree(){
  const equipoSel = document.getElementById("tipo_equipo");
  const card = document.getElementById("card_oilfree");
  if(!equipoSel || !card) return;
  const txt = (equipoSel.value || "").toLowerCase();
  card.style.display = txt.includes("libre de aceite") ? "" : "none";
}

/* === Datos eléctricos: vista especial para Secador (Preventivo) === */
function toggleDatosElectricosSecador(){
  const cardComp = document.getElementById("card_electrico_compresor");
  const cardSec  = document.getElementById("card_electrico_secador");
  const tipoServEl = document.getElementById("tipo_servicio");
  const tipoEqEl   = document.getElementById("tipo_equipo");

  if (!cardComp || !cardSec || !tipoServEl || !tipoEqEl) return;

  const tipoServ = (tipoServEl.value || "").toLowerCase();
  const tipoEq   = (tipoEqEl.value   || "").toLowerCase();

  const esPreventivo = (tipoServ === "preventivo");
  const esSecador    = tipoEq.includes("secador");

  if (esPreventivo && esSecador){
    // Solo SECADOR preventivo: mostramos tabla recortada
    cardComp.style.display = "none";
    cardSec.style.display  = "";
  } else {
    // Todo lo demás: tabla completa normal
    cardComp.style.display = "";
    cardSec.style.display  = "none";
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
  enableSignaturePadHDPI("firma_tecnico_canvas","btn_clear_tecnico","firma_tecnico_data");
  enableSignaturePadHDPI("firma_cliente_canvas","btn_clear_cliente","firma_cliente_data");

  // Unidades, Oil Free, Potencia, lecturas y datos eléctricos para secador
  poblarUnidadesInline();
  toggleOilFree();
  toggleLecturasSecador();
  toggleDatosElectricosSecador();
  updatePotenciaHint();
  document.getElementById("tipo_equipo")?.addEventListener("change", () => {
    toggleOilFree();
    toggleBloquesPorTipo();
    toggleLecturasSecador();
    toggleDatosElectricosSecador();
    updatePotenciaHint();
  });
});

/* =========================
   AUTO-GUARDADO (localStorage)
   ========================= */
(function(){
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
  function maybeCompressDataUrl(dataUrl){
    if (!USE_JPEG_FOR_DRAFT || !dataUrl?.startsWith("data:image/")) return dataUrl;
    try{
      // Convertimos solo si originalmente es PNG
      if (dataUrl.startsWith("data:image/png")) {
        // No tenemos el bitmap crudo aquí; para simplicidad, devolvemos PNG (ya suele ser liviano con fondo blanco)
        return dataUrl;
      }
      return dataUrl;
    }catch(_){ return dataUrl; }
  }

  function readIndex(){
    try{ return JSON.parse(localStorage.getItem(INDEX_KEY)||"{}"); }catch(_){ return {}; }
  }
  function writeIndex(idx){
    try{ localStorage.setItem(INDEX_KEY, JSON.stringify(idx)); }catch(_){}
  }

  // Tomar todos los valores del form
  function serializeForm(){
    const data = {};
    const elements = form.querySelectorAll("input, select, textarea");
    elements.forEach(el => {
      if (!el.name) return;
      if (shouldSkip(el)) return;

      // saltar firmas si el modo runtime está activo
      if ((skipSignaturesRuntime) && (el.name === "firma_tecnico_data" || el.name === "firma_cliente_data")) return;

      if (el.type === "checkbox"){
        data[el.name] = el.checked ? "1" : "";
      } else if (el.type === "radio"){
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
    data.__saved_at = new Date().toISOString();
    return data;
  }

  // Volcar valores guardados al form
  function applyDraft(draft){
    const elements = form.querySelectorAll("input, select, textarea");
    elements.forEach(el => {
      if (!el.name) return;
      if (!(el.name in draft)) return;

      const val = draft[el.name];
      if (el.type === "checkbox"){
        el.checked = (val === "1");
      } else if (el.type === "radio"){
        el.checked = (el.value === val);
      } else {
        el.value = val;
      }
    });

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
    } catch(_) {}
  }

  // Guardado con debounce
  let t=null;
  function scheduleSave(){
    if (t) clearTimeout(t);
    t = setTimeout(() => {
      try{
        const data = serializeForm();
        localStorage.setItem(AUTOSAVE_KEY, JSON.stringify(data));

        // Actualizar índice (folio → cliente/fecha/saved_at)
        try{
          const idx = readIndex();
          idx[FOLIO] = {
            cliente: form.querySelector('input[name="cliente"]')?.value || "",
            fecha: form.querySelector('input[name="fecha"]')?.value || "",
            saved_at: data.__saved_at
          };
          writeIndex(idx);
        }catch(_){}

      }catch(e){
        // Si falla por tamaño, quitamos firmas del draft y volvemos a intentar una vez
        if (!skipSignaturesRuntime) {
          skipSignaturesRuntime = true;
          try {
            const data = serializeForm();
            localStorage.setItem(AUTOSAVE_KEY, JSON.stringify(data));
          } catch(e2){
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
  }

  // Cargar borrador si existe
  function loadDraft(){
    try{
      const raw = localStorage.getItem(AUTOSAVE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      applyDraft(data);
    } catch(e){
      console.warn("No se pudo restaurar borrador:", e);
    }
  }

  // Limpiar borrador
  function clearDraft(){
    localStorage.removeItem(AUTOSAVE_KEY);
    // limpiar del índice
    try{
      const idx = readIndex();
      delete idx[FOLIO];
      writeIndex(idx);
    }catch(_){}
  }

  // Eventos para guardar
  form.addEventListener("input", scheduleSave, true);
  form.addEventListener("change", scheduleSave, true);

  // Al enviar (PDF), limpiamos el borrador de ese folio
  form.addEventListener("submit", () => {
    clearDraft();
  });

  // Botón manual para borrar
  document.getElementById("btn-clear-draft")?.addEventListener("click", () => {
    clearDraft();
    alert("Borrador eliminado.");
  });

  // Carga inicial
  loadDraft();
})();

/* =========================
   LISTA DE BORRADORES (UI)
   ========================= */
(function(){
  const PREFIX = "inair_reporte_draft_";

  function getAllDrafts(){
    const items = [];
    for (let i=0; i<localStorage.length; i++){
      const k = localStorage.key(i);
      if (k && k.startsWith(PREFIX)){
        try{
          const data = JSON.parse(localStorage.getItem(k) || "{}");
          const folio = k.replace(PREFIX, "");
          items.push({
            folio,
            savedAt: data.__saved_at || null,
            cliente: data.cliente || "",
            tipo: data.tipo_servicio || ""
          });
        }catch(_){}
      }
    }
    // más recientes primero
    items.sort((a,b)=> (b.savedAt||"").localeCompare(a.savedAt||""));
    return items;
  }

  function renderDraftList(){
    const cont = document.getElementById("lista-borradores");
    if (!cont) return;
    cont.innerHTML = "";
    const drafts = getAllDrafts();

    if (!drafts.length){
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
    cont.querySelectorAll("button[data-del]").forEach(btn=>{
      btn.addEventListener("click", ()=>{
        const fol = btn.getAttribute("data-del");
        if (confirm(`Eliminar borrador del folio ${fol}?`)){
          localStorage.removeItem(PREFIX + fol);
          renderDraftList();
        }
      });
    });
  }

  // cuando se abre el modal, refresca la lista
  document.addEventListener("shown.bs.modal", (ev)=>{
    if (ev.target && ev.target.id === "modalBorradores"){
      renderDraftList();
    }
  });
})();

/**
 * bind_tour.js — Onboarding interactivo para Bind
 * Usa Driver.js v1 con popover completamente personalizado en Tailwind.
 * Se activa solo si SHOW_TOUR=true (backend) y localStorage no tiene la clave.
 */

(function () {
  'use strict';

  const LS_KEY = 'bind_tour_done';
  // TOUR_COMPLETE_URL se inyecta desde el template Django
  const _completeUrl = (typeof TOUR_COMPLETE_URL !== 'undefined')
    ? TOUR_COMPLETE_URL
    : '/accounts/tour/complete/';

  // Doble check: backend + localStorage
  if (typeof SHOW_TOUR === 'undefined' || !SHOW_TOUR) return;
  if (localStorage.getItem(LS_KEY)) return;

  // ── Obtener CSRF token del DOM ──────────────────────────────────────────────
  function getCsrf() {
    const el = document.querySelector('[name=csrfmiddlewaretoken]');
    if (el) return el.value;
    const cookie = document.cookie.split('; ').find(r => r.startsWith('csrftoken='));
    return cookie ? cookie.split('=')[1] : '';
  }

  // ── Marcar tour como completado (local + backend, fire-and-forget) ──────────
  function markDone() {
    localStorage.setItem(LS_KEY, '1');
    fetch(_completeUrl, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
      credentials: 'same-origin',
    }).catch(() => {});
  }

  // ── Construir el popover personalizado ─────────────────────────────────────
  // Driver.js v1 permite reemplazar el HTML del popover completo.
  function buildPopoverHTML({ title, description, totalCount, currentIndex, state }) {
    const current = currentIndex + 1;
    const isFirst = currentIndex === 0;
    const isLast  = currentIndex === totalCount - 1;

    const btnBack = isFirst
      ? ''
      : `<button id="bind-tour-prev"
           class="px-4 py-2 rounded-xl border border-white/15 text-sm text-gray-300 hover:bg-white/8 transition-colors font-medium">
           ← Atrás
         </button>`;

    const btnNext = isLast
      ? `<button id="bind-tour-done"
           class="px-4 py-2 rounded-xl bg-teal-500 hover:bg-teal-600 text-white text-sm font-semibold transition-colors shadow-lg shadow-teal-500/20">
           ¡Listo!
         </button>`
      : `<button id="bind-tour-next"
           class="px-4 py-2 rounded-xl bg-teal-500 hover:bg-teal-600 text-white text-sm font-semibold transition-colors shadow-lg shadow-teal-500/20">
           Siguiente →
         </button>`;

    return `
      <div class="bind-tour-popover" style="
        background: rgba(13, 17, 27, 0.93);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        box-shadow: 0 25px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(94,207,190,0.08);
        width: 320px;
        font-family: inherit;
        overflow: hidden;
      ">
        <!-- Header -->
        <div style="padding: 16px 18px 0;">
          <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:10px;">
            <!-- Step dots -->
            <div style="display:flex; gap:5px; align-items:center;">
              ${Array.from({ length: totalCount }, (_, i) => `
                <span style="
                  width: ${i === currentIndex ? '18px' : '6px'};
                  height: 6px;
                  border-radius: 999px;
                  background: ${i === currentIndex ? '#14b8a6' : 'rgba(255,255,255,0.15)'};
                  transition: all 0.3s ease;
                  display:inline-block;
                "></span>`).join('')}
              <span style="font-size:10px; color:rgba(255,255,255,0.35); margin-left:4px; font-weight:600; letter-spacing:0.05em;">${current}/${totalCount}</span>
            </div>
            <!-- Skip button -->
            <button id="bind-tour-skip" style="
              background: none; border: none; cursor: pointer;
              font-size: 11px; color: rgba(255,255,255,0.3);
              padding: 2px 6px; border-radius: 6px;
              transition: color 0.2s;
              font-family: inherit;
              font-weight: 500;
              letter-spacing: 0.02em;
            " onmouseover="this.style.color='rgba(255,255,255,0.6)'"
               onmouseout="this.style.color='rgba(255,255,255,0.3)'">
              Saltar ×
            </button>
          </div>

          <!-- Title -->
          <p style="
            font-size: 15px;
            font-weight: 700;
            color: #fff;
            margin: 0 0 6px;
            line-height: 1.3;
          ">${title}</p>

          <!-- Description -->
          <p style="
            font-size: 12.5px;
            color: rgba(255,255,255,0.55);
            margin: 0;
            line-height: 1.55;
          ">${description}</p>
        </div>

        <!-- Footer -->
        <div style="
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 14px 18px;
          margin-top: 14px;
          border-top: 1px solid rgba(255,255,255,0.06);
        ">
          <div>${btnBack}</div>
          <div>${btnNext}</div>
        </div>
      </div>`;
  }

  // ── Definición de pasos ─────────────────────────────────────────────────────
  const STEPS = [
    {
      element: null,
      title: 'Bienvenido a Bind',
      description: 'Este tour de 4 pasos te muestra las partes esenciales de la plataforma. Puedes saltarlo en cualquier momento si ya conoces Bind.',
    },
    {
      element: '#dashboard-metrics',
      title: 'Tu estado en un vistazo',
      description: 'Pendientes, tareas de hoy y proyectos activos. Estos tres números te dicen dónde enfocar tu energía cada mañana.',
      side: 'bottom',
      align: 'end',
    },
    {
      element: '#btn-new-event',
      title: 'Tu punto de partida',
      description: 'Desde aquí creas un nuevo evento. Elige una plantilla y Bind configura los módulos, tareas y fechas automáticamente.',
      side: 'bottom',
      align: 'end',
    },
    {
      element: '#project-status-panel',
      title: 'Salud de cada proyecto',
      description: 'El health score resume progreso, tareas pendientes y riesgo. Verde = en control, rojo = requiere atención inmediata.',
      side: 'top',
      align: 'start',
    },
    {
      element: null,
      title: 'Bynix, tu asistente IA',
      description: 'Dentro de cada evento encontrarás a Bynix — impulsado por Gemini. Úsalo para generar narrativas, hacer preguntas sobre el estado del proyecto y capturar ideas rápidas.',
    },
  ];

  // ── Motor del tour (sin depender de Driver.js API) ──────────────────────────
  let currentStep = 0;
  let overlayEl   = null;
  let popoverEl   = null;
  let highlightEl = null;
  let originalBoxShadow = '';

  function createOverlay() {
    overlayEl = document.createElement('div');
    overlayEl.id = 'bind-tour-overlay';
    overlayEl.style.cssText = `
      position: fixed; inset: 0; z-index: 9998;
      pointer-events: none;
    `;
    document.body.appendChild(overlayEl);
  }

  function positionPopover(targetEl, side, align) {
    if (!popoverEl) return;
    popoverEl.style.position = 'fixed';
    popoverEl.style.zIndex   = '9999';

    if (!targetEl) {
      // Centrado
      popoverEl.style.top       = '50%';
      popoverEl.style.left      = '50%';
      popoverEl.style.transform = 'translate(-50%, -50%)';
      return;
    }

    popoverEl.style.transform = '';
    const rect    = targetEl.getBoundingClientRect();
    const pw      = 320;
    const ph      = popoverEl.offsetHeight || 200;
    const gap     = 14;
    const vw      = window.innerWidth;
    const vh      = window.innerHeight;

    let top, left;

    if (side === 'bottom') {
      top  = rect.bottom + gap;
      left = align === 'end' ? rect.right - pw : rect.left;
    } else if (side === 'top') {
      top  = rect.top - ph - gap;
      left = align === 'start' ? rect.left : rect.right - pw;
    } else if (side === 'left') {
      top  = rect.top;
      left = rect.left - pw - gap;
    } else {
      top  = rect.top;
      left = rect.right + gap;
    }

    // Clamp dentro del viewport
    left = Math.max(12, Math.min(left, vw - pw - 12));
    top  = Math.max(12, Math.min(top,  vh - ph - 12));

    popoverEl.style.top  = top  + 'px';
    popoverEl.style.left = left + 'px';
  }

  function highlightTarget(el) {
    // Quitar highlight anterior
    if (highlightEl) {
      highlightEl.style.boxShadow = originalBoxShadow;
      highlightEl.style.position  = '';
      highlightEl.style.zIndex    = '';
      highlightEl = null;
    }
    if (!el) return;

    originalBoxShadow = el.style.boxShadow || '';
    el.style.position = el.style.position || 'relative';
    el.style.zIndex   = '9999';
    el.style.boxShadow = `
      0 0 0 4px rgba(20,184,166,0.45),
      0 0 0 9999px rgba(0,0,0,0.55)
    `;
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    highlightEl = el;
  }

  function renderStep(index) {
    const step = STEPS[index];
    const targetEl = step.element ? document.querySelector(step.element) : null;

    // Construir o actualizar popover
    const html = buildPopoverHTML({
      title:        step.title,
      description:  step.description,
      totalCount:   STEPS.length,
      currentIndex: index,
    });

    if (!popoverEl) {
      popoverEl = document.createElement('div');
      document.body.appendChild(popoverEl);
    }
    popoverEl.innerHTML = html;

    // Highlight + posición
    highlightTarget(targetEl);
    // Esperar un frame para que el popover tenga dimensiones
    requestAnimationFrame(() => positionPopover(targetEl, step.side, step.align));

    // Bind botones
    popoverEl.querySelector('#bind-tour-skip')?.addEventListener('click', destroyTour);
    popoverEl.querySelector('#bind-tour-prev')?.addEventListener('click', () => goTo(index - 1));
    popoverEl.querySelector('#bind-tour-next')?.addEventListener('click', () => goTo(index + 1));
    popoverEl.querySelector('#bind-tour-done')?.addEventListener('click', finishTour);
  }

  function goTo(index) {
    if (index < 0 || index >= STEPS.length) return;
    currentStep = index;
    renderStep(currentStep);
  }

  function destroyTour() {
    if (highlightEl) {
      highlightEl.style.boxShadow = originalBoxShadow;
      highlightEl.style.position  = '';
      highlightEl.style.zIndex    = '';
    }
    popoverEl?.remove();
    overlayEl?.remove();
    document.body.style.overflow = '';
    popoverEl   = null;
    overlayEl   = null;
    highlightEl = null;
  }

  function finishTour() {
    destroyTour();
    markDone();
  }

  // Saltar con Escape
  document.addEventListener('keydown', function onEsc(e) {
    if (e.key === 'Escape') {
      destroyTour();
      document.removeEventListener('keydown', onEsc);
    }
  });

  // ── Iniciar con un pequeño delay para que el DOM esté pintado ───────────────
  function startTour() {
    createOverlay();
    renderStep(0);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(startTour, 600));
  } else {
    setTimeout(startTour, 600);
  }

})();

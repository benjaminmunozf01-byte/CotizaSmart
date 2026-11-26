/**
 * Utilidades globales de interfaz SaaS para CotizaSmart.
 * Trabajo 3 - Tecnología de la Información II, Universidad de Concepción (Campus Los Ángeles).
 * Autores: Jorge Campos, Benjamin Muñoz y Raul Vergara.
 */

window.CotizaSmart = {
  /**
   * Formatea un monto en pesos chilenos con punto como separador de miles, sin decimales ($1.250.000).
   */
  formatoCLP(valor) {
    const num = Math.round(Number(valor) || 0);
    const signo = num < 0 ? "-" : "";
    const absStr = Math.abs(num)
      .toString()
      .replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return `${signo}$${absStr}`;
  },

  /**
   * Formatea un porcentaje con un decimal y coma chilena (14,5%).
   */
  formatoPct(valor) {
    const num = Number(valor) || 0;
    return `${num.toFixed(1).replace(".", ",")}%`;
  },

  /**
   * Formatea un número decimal con coma chilena.
   */
  formatoDecimal(valor, dec = 1) {
    const num = Number(valor) || 0;
    return num.toFixed(dec).replace(".", ",");
  },

  /**
   * Muestra una notificación flotante tipo SaaS en la esquina superior derecha.
   */
  mostrarToast(mensaje, tipo = "exito") {
    const contenedor = document.getElementById("toast-container");
    if (!contenedor) return;

    const colores = {
      exito: "bg-brand-dark border-emerald-500 text-white",
      error: "bg-red-950 border-red-500 text-red-50",
      alerta: "bg-amber-950 border-amber-500 text-amber-50",
      info: "bg-brand-dark border-brand-accent text-white",
    };

    const el = document.createElement("div");
    el.className = `flex items-center gap-3 px-4 py-3 rounded-xl border-l-4 shadow-xl text-sm font-medium transition-all duration-300 transform translate-y-0 opacity-100 max-w-md ${
      colores[tipo] || colores.exito
    }`;
    el.innerHTML = `
      <span class="flex-1 leading-snug">${mensaje}</span>
      <button type="button" class="text-slate-400 hover:text-white ml-2 text-base leading-none" aria-label="Cerrar">&times;</button>
    `;
    el.querySelector("button").addEventListener("click", () => el.remove());
    contenedor.appendChild(el);

    setTimeout(() => {
      el.classList.add("opacity-0", "translate-y-2");
      setTimeout(() => el.remove(), 300);
    }, 4500);
  },

  /**
   * Muestra u oculta el overlay de carga durante la simulación Montecarlo.
   */
  mostrarSpinner(texto = "Simulando 10.000 escenarios Montecarlo...") {
    const overlay = document.getElementById("loading-overlay");
    const label = document.getElementById("loading-overlay-text");
    if (label) label.textContent = texto;
    if (overlay) overlay.classList.remove("hidden");
  },

  ocultarSpinner() {
    const overlay = document.getElementById("loading-overlay");
    if (overlay) overlay.classList.add("hidden");
  },

  /**
   * Abre el modal de demostración del Plan Pro ($49.000 CLP/mes).
   */
  abrirModalPlanPro(mensajeExtra = "") {
    const modal = document.getElementById("modal-plan-pro");
    const boxExtra = document.getElementById("modal-plan-pro-motivo");
    if (boxExtra) {
      if (mensajeExtra) {
        boxExtra.textContent = mensajeExtra;
        boxExtra.classList.remove("hidden");
      } else {
        boxExtra.classList.add("hidden");
      }
    }
    if (modal) modal.classList.remove("hidden");
  },

  cerrarModalPlanPro() {
    const modal = document.getElementById("modal-plan-pro");
    if (modal) modal.classList.add("hidden");
  },

  /**
   * Restablece la base de datos al estado inicial de demostración ("2 de 3 cotizaciones usadas este mes").
   */
  async restablecerDatosDemo() {
    try {
      this.mostrarSpinner("Restableciendo datos de demostración (2 de 3 cotizaciones)...");
      const resp = await fetch("/api/reset-demo", { method: "POST" });
      const data = await resp.json();
      this.ocultarSpinner();
      if (data.ok) {
        this.mostrarToast(data.mensaje, "exito");
        setTimeout(() => {
          window.location.href = "/";
        }, 500);
      } else {
        this.mostrarToast(data.error || "No se pudo restablecer la demo.", "error");
      }
    } catch (err) {
      this.ocultarSpinner();
      this.mostrarToast("Error de red al restablecer datos de demostración.", "error");
    }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) {
    window.lucide.createIcons();
  }
});

const state = {
  lastMessage: "",
};

const todayLabel = document.querySelector("#todayLabel");
const historyList = document.querySelector("#historyList");
const historySearch = document.querySelector("#historySearch");
const historyPeriod = document.querySelector("#historyPeriod");
const historyStatus = document.querySelector("#historyStatus");
const dateFrom = document.querySelector("#dateFrom");
const dateTo = document.querySelector("#dateTo");
const movementTotals = document.querySelector("#movementTotals");
const ticketDetail = document.querySelector("#ticketDetail");
const refreshHistory = document.querySelector("#refreshHistory");
const lowStockGrid = document.querySelector("#lowStockGrid");
const refreshLowStock = document.querySelector("#refreshLowStock");
const closureGrid = document.querySelector("#closureGrid");
const closureAlert = document.querySelector("#closureAlert");
const refreshClosures = document.querySelector("#refreshClosures");
const backupButton = document.querySelector("#backupButton");
const toast = document.querySelector("#toast");

const formatter = new Intl.NumberFormat("es-AR", {
  style: "currency",
  currency: "ARS",
});

todayLabel.textContent = new Intl.DateTimeFormat("es-AR", {
  dateStyle: "medium",
  timeStyle: "short",
}).format(new Date());

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  window.setTimeout(() => toast.classList.remove("visible"), 2600);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function unitLabel(unit) {
  return unit === "metro" ? "m" : "u";
}

function formatQuantity(value, unit) {
  return `${Number(value).toLocaleString("es-AR", { maximumFractionDigits: 2 })} ${unitLabel(unit)}`;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Error inesperado");
  }
  return data;
}

async function loadHistory() {
  const params = new URLSearchParams();
  if (historySearch.value.trim()) params.set("q", historySearch.value.trim());
  if (historyPeriod.value) params.set("periodo", historyPeriod.value);
  if (historyStatus.value) params.set("estado", historyStatus.value);
  if (dateFrom.value) params.set("desde", dateFrom.value);
  if (dateTo.value) params.set("hasta", dateTo.value);
  const data = await fetchJson(`/api/budgets?${params.toString()}`);
  renderTotals(data.totals);
  if (!data.budgets.length) {
    historyList.innerHTML = `<p class="subline">Todavia no hay movimientos guardados.</p>`;
    ticketDetail.classList.add("hidden");
    return;
  }

  historyList.innerHTML = data.budgets
    .map(
      (item) => `
        <button type="button" class="history-row" data-ticket="${item.numero}">
          <strong>${item.numero}</strong>
          <span>${escapeHtml(item.cliente)} · ${escapeHtml(item.estado)} · ${item.items_count} item(s)</span>
          <span>${formatter.format(item.total)}</span>
        </button>
      `,
    )
    .join("");
}

function renderTotals(totals) {
  movementTotals.innerHTML = `
    <article><span>Ventas</span><strong>${totals.ventas}</strong></article>
    <article><span>Total vendido</span><strong>${formatter.format(totals.vendido)}</strong></article>
    <article><span>Presupuestos</span><strong>${totals.presupuestos}</strong></article>
    <article><span>Total presupuestado</span><strong>${formatter.format(totals.pendiente)}</strong></article>
    <article><span>Anulados</span><strong>${totals.anulados}</strong></article>
    <article><span>Mostrados</span><strong>${totals.mostrados}/${totals.coincidencias}</strong></article>
  `;
}

async function loadTicketDetail(number) {
  const data = await fetchJson(`/api/budgets/${encodeURIComponent(number)}`);
  const document = data.document;
  const billing = document.facturacion || {};
  const isSale = document.estado === "vendido";
  ticketDetail.classList.remove("hidden");
  ticketDetail.innerHTML = `
    <div class="ticket-brand">
      <img src="/assets/logo-hidrogas.svg" alt="Hidrogas" />
      <div>
        <strong>Hidrogas</strong>
        <span>Gestion local de mostrador</span>
      </div>
    </div>
    <div class="ticket-ribbon ${isSale ? "sale" : "budget"}">
      <div>
        <span>${isSale ? "Venta" : "Presupuesto"}</span>
        <strong>${document.numero}</strong>
      </div>
      <span>${escapeHtml(document.estado)}</span>
    </div>
    <div class="ticket-header">
      <button type="button" data-copy-ticket>Copiar</button>
      <button type="button" data-print-ticket>Imprimir</button>
      ${document.estado === "pendiente" ? `<button type="button" data-sell-ticket="${document.numero}">Vender</button>` : ""}
      ${document.estado !== "anulado" ? `<button type="button" data-void-ticket="${document.numero}">Anular</button>` : ""}
    </div>
    <div class="ticket-info-grid">
      <article>
        <span>Fecha</span>
        <strong>${escapeHtml(document.fecha)}</strong>
      </article>
      <article>
        <span>Cliente</span>
        <strong>${escapeHtml(document.cliente)}</strong>
      </article>
      <article>
        <span>Condicion</span>
        <strong>${escapeHtml(billing.tax_condition || "Consumidor final")}</strong>
      </article>
      <article>
        <span>Pago</span>
        <strong>${escapeHtml(document.medio_pago || "Sin definir")}</strong>
      </article>
      ${document.vendedor ? `<article><span>Vendedor</span><strong>${escapeHtml(document.vendedor)}</strong></article>` : ""}
      ${billing.tax_id ? `<article><span>CUIT/DNI</span><strong>${escapeHtml(billing.tax_id)}</strong></article>` : ""}
    </div>
    <table class="ticket-table">
      <thead>
        <tr><th>Producto</th><th>Cant.</th><th>Unitario</th><th>Subtotal</th></tr>
      </thead>
      <tbody>
        ${document.items.map((item) => `
          <tr>
            <td>${escapeHtml(item.codigo)} - ${escapeHtml(item.nombre)}</td>
            <td>${formatQuantity(item.cantidad, item.unidad_venta)}</td>
            <td>${formatter.format(item.precio_unitario)}</td>
            <td>${formatter.format(item.subtotal)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
    ${Number(document.descuento || 0) > 0 ? `
      <div class="ticket-discount">
        <span>Subtotal</span><strong>${formatter.format(document.subtotal_bruto || document.total)}</strong>
        <span>Descuento</span><strong>-${formatter.format(document.descuento)}</strong>
      </div>
    ` : ""}
    <div class="ticket-total"><span>Total</span><strong>${formatter.format(document.total)}</strong></div>
    ${document.observaciones ? `<p class="ticket-notes">${escapeHtml(document.observaciones)}</p>` : ""}
    <div class="ticket-terms">
      <strong>${isSale ? "Comprobante interno de venta" : "Presupuesto valido por 7 dias"}</strong>
      <span>Precios sujetos a modificacion segun lista vigente. La disponibilidad queda sujeta al stock al momento de confirmar la operacion.</span>
    </div>
    <div class="ticket-footer">
      <span>Hidrogas</span>
      <strong>Gracias por su consulta</strong>
    </div>
  `;
  state.lastMessage = data.message;
}

async function sellTicket(number) {
  const medioPago = window.prompt("Medio de pago:", "Efectivo") || "";
  const vendedor = window.prompt("Vendedor:", "") || "";
  const data = await fetchJson(`/api/budgets/${encodeURIComponent(number)}/sell`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ medio_pago: medioPago, vendedor }),
  });
  await loadHistory();
  await loadClosures();
  await loadTicketDetail(data.document.numero);
  showToast(`Venta generada: ${data.document.numero}`);
}

async function voidTicket(number) {
  const motivo = window.prompt("Motivo de anulacion:", "");
  if (motivo === null) return;
  await fetchJson(`/api/budgets/${encodeURIComponent(number)}/void`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ motivo }),
  });
  await loadHistory();
  await loadClosures();
  await loadTicketDetail(number);
  showToast("Movimiento anulado.");
}

function printTicket() {
  window.print();
}

async function loadClosures() {
  const data = await fetchJson("/api/closures");
  closureAlert.textContent = data.pending.length
    ? `Hay ${data.pending.length} mes(es) con ventas sin cierre.`
    : "No hay cierres vencidos.";
  closureAlert.classList.add("visible");

  if (!data.months.length) {
    closureGrid.innerHTML = `<p class="subline">Todavia no hay movimientos para cerrar.</p>`;
    return;
  }

  closureGrid.innerHTML = data.months
    .map((month) => `
      <article>
        <div>
          <strong>${month.periodo}</strong>
          <span>${month.ventas} ventas · ${month.presupuestos} presupuestos</span>
          <span>${formatter.format(month.total_vendido)}</span>
        </div>
        <button type="button" data-close-month="${month.periodo}" ${month.cerrado ? "disabled" : ""}>
          ${month.cerrado ? "Cerrado" : "Generar cierre"}
        </button>
      </article>
    `)
    .join("");
}

async function loadLowStock() {
  const data = await fetchJson("/api/low-stock");
  if (!data.products.length) {
    lowStockGrid.innerHTML = `<p class="subline">No hay productos por debajo del stock minimo.</p>`;
    return;
  }
  lowStockGrid.innerHTML = data.products
    .slice(0, 20)
    .map((product) => `
      <article>
        <strong>${escapeHtml(product.codigo)} - ${escapeHtml(product.nombre)}</strong>
        <span>Stock: ${formatQuantity(product.stock, product.unidad_venta)} · Minimo: ${formatQuantity(product.stock_minimo, product.unidad_venta)}</span>
        <span>${escapeHtml(product.ubicacion || "A definir")}</span>
      </article>
    `)
    .join("");
}

refreshHistory.addEventListener("click", () => loadHistory());
let searchTimer = null;
historySearch.addEventListener("input", () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => loadHistory(), 180);
});
historyPeriod.addEventListener("change", () => loadHistory());
historyStatus.addEventListener("change", () => loadHistory());
dateFrom.addEventListener("change", () => loadHistory());
dateTo.addEventListener("change", () => loadHistory());
historyList.addEventListener("click", (event) => {
  const row = event.target.closest("[data-ticket]");
  if (!row) return;
  loadTicketDetail(row.dataset.ticket).catch((error) => showToast(error.message));
});
ticketDetail.addEventListener("click", async (event) => {
  if (event.target.closest("[data-copy-ticket]")) {
    await navigator.clipboard.writeText(state.lastMessage);
    showToast("Ticket copiado.");
    return;
  }
  if (event.target.closest("[data-print-ticket]")) {
    printTicket();
    return;
  }
  const sellButton = event.target.closest("[data-sell-ticket]");
  if (sellButton) {
    sellTicket(sellButton.dataset.sellTicket).catch((error) => showToast(error.message));
    return;
  }
  const voidButton = event.target.closest("[data-void-ticket]");
  if (voidButton) {
    voidTicket(voidButton.dataset.voidTicket).catch((error) => showToast(error.message));
  }
});
refreshClosures.addEventListener("click", () => loadClosures());
refreshLowStock.addEventListener("click", () => loadLowStock());
backupButton.addEventListener("click", async () => {
  try {
    const data = await fetchJson("/api/backups", { method: "POST" });
    showToast(`Backup generado: ${data.archivo}`);
  } catch (error) {
    showToast(error.message);
  }
});
closureGrid.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-close-month]");
  if (!button) return;
  try {
    const data = await fetchJson("/api/closures", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ periodo: button.dataset.closeMonth }),
    });
    await loadClosures();
    showToast(`Cierre generado: ${data.archivo}`);
  } catch (error) {
    showToast(error.message);
  }
});

loadHistory().catch((error) => showToast(error.message));
loadClosures().catch((error) => showToast(error.message));
loadLowStock().catch((error) => showToast(error.message));

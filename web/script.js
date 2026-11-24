const state = {
  products: [],
  totalProducts: 0,
  cart: new Map(),
  mode: "budget",
  selectedProduct: null,
  lastMessage: "",
};

const searchInput = document.querySelector("#searchInput");
const clearSearch = document.querySelector("#clearSearch");
const productsBody = document.querySelector("#productsBody");
const productCount = document.querySelector("#productCount");
const todayLabel = document.querySelector("#todayLabel");
const emptyState = document.querySelector("#emptyState");
const cartItems = document.querySelector("#cartItems");
const cartTotal = document.querySelector("#cartTotal");
const customerInput = document.querySelector("#customerInput");
const taxIdInput = document.querySelector("#taxIdInput");
const taxConditionInput = document.querySelector("#taxConditionInput");
const invoiceTypeInput = document.querySelector("#invoiceTypeInput");
const emailInput = document.querySelector("#emailInput");
const phoneInput = document.querySelector("#phoneInput");
const addressInput = document.querySelector("#addressInput");
const paymentMethodInput = document.querySelector("#paymentMethodInput");
const sellerInput = document.querySelector("#sellerInput");
const discountInput = document.querySelector("#discountInput");
const billingNote = document.querySelector("#billingNote");
const notesInput = document.querySelector("#notesInput");
const saveButton = document.querySelector("#saveButton");
const copyButton = document.querySelector("#copyButton");
const editHint = document.querySelector("#editHint");
const editForm = document.querySelector("#editForm");
const editTitle = document.querySelector("#editTitle");
const editName = document.querySelector("#editName");
const editCategory = document.querySelector("#editCategory");
const editBrand = document.querySelector("#editBrand");
const editProviderCode = document.querySelector("#editProviderCode");
const editMeasure = document.querySelector("#editMeasure");
const editPrice = document.querySelector("#editPrice");
const editStock = document.querySelector("#editStock");
const editMinStock = document.querySelector("#editMinStock");
const editUnit = document.querySelector("#editUnit");
const editLocation = document.querySelector("#editLocation");
const editSynonyms = document.querySelector("#editSynonyms");
const editNotes = document.querySelector("#editNotes");
const newProductButton = document.querySelector("#newProductButton");
const salesToday = document.querySelector("#salesToday");
const salesMonth = document.querySelector("#salesMonth");
const pendingBudgets = document.querySelector("#pendingBudgets");
const orderedItems = document.querySelector("#orderedItems");
const updateGrid = document.querySelector("#updateGrid");
const refreshUpdate = document.querySelector("#refreshUpdate");
const priceListInput = document.querySelector("#priceListInput");
const previewPriceUpdate = document.querySelector("#previewPriceUpdate");
const applyPriceUpdate = document.querySelector("#applyPriceUpdate");
const priceUpdateDetail = document.querySelector("#priceUpdateDetail");
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

function requiresBillingData() {
  return taxConditionInput.value !== "Consumidor final";
}

function updateBillingRequirements() {
  const required = requiresBillingData();
  taxIdInput.required = required;
  invoiceTypeInput.required = required;
  emailInput.required = required;
  phoneInput.required = required;
  addressInput.required = required;
  customerInput.required = required;

  if (required) {
    billingNote.textContent =
      "Para esta condicion fiscal, completar cliente, CUIT/DNI, factura, email, telefono y direccion.";
    invoiceTypeInput.closest("label").classList.add("required-field");
    taxIdInput.closest("label").classList.add("required-field");
    emailInput.closest("label").classList.add("required-field");
    phoneInput.closest("label").classList.add("required-field");
    addressInput.closest("label").classList.add("required-field");
    customerInput.closest("label").classList.add("required-field");
  } else {
    billingNote.textContent = "Para consumidor final no hace falta completar datos fiscales.";
    invoiceTypeInput.value = "";
    [
      invoiceTypeInput,
      taxIdInput,
      emailInput,
      phoneInput,
      addressInput,
      customerInput,
    ].forEach((input) => input.closest("label").classList.remove("required-field"));
  }
}

function validateBilling() {
  if (!requiresBillingData()) return true;

  const missing = [];
  if (!customerInput.value.trim()) missing.push("cliente");
  if (!taxIdInput.value.trim()) missing.push("CUIT/DNI");
  if (!invoiceTypeInput.value) missing.push("tipo de factura");
  if (!emailInput.value.trim()) missing.push("email");
  if (!phoneInput.value.trim()) missing.push("telefono");
  if (!addressInput.value.trim()) missing.push("direccion");

  if (missing.length) {
    showToast(`Faltan datos: ${missing.join(", ")}.`);
    return false;
  }
  return true;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Error inesperado");
  }
  return data;
}

async function loadProducts(query = "") {
  const data = await fetchJson(`/api/products?q=${encodeURIComponent(query)}`);
  state.products = data.products;
  state.totalProducts = data.total ?? state.products.length;
  renderProducts();
}

function stockClass(product) {
  if (product.stock <= 0) return "zero";
  if (product.stock <= product.stock_minimo) return "low";
  return "";
}

function renderProducts() {
  const shown = state.products.length;
  const total = state.totalProducts;
  productCount.textContent =
    shown < total ? `${total} productos cargados · mostrando ${shown}` : `${total} productos`;
  emptyState.classList.toggle("visible", state.products.length === 0);
  productsBody.innerHTML = state.products
    .map(
      (product) => `
        <tr>
          <td class="code">${product.codigo}</td>
          <td>
            <span class="product-name">${product.nombre}</span>
            <span class="subline">Proveedor: ${product.codigo_proveedor || "-"} | ${product.marca}</span>
          </td>
          <td>${product.rubro}</td>
          <td class="price">${formatter.format(product.precio)}</td>
          <td class="stock ${stockClass(product)}">${formatQuantity(product.stock, product.unidad_venta)}</td>
          <td>${product.unidad_venta === "metro" ? "Por metro" : "Por unidad"}</td>
          <td>${product.ubicacion || "A definir"}</td>
          <td>
            <div class="row-actions">
              <button type="button" data-add="${product.codigo}">Agregar</button>
              <button type="button" class="ghost" data-edit="${product.codigo}">Editar</button>
            </div>
          </td>
        </tr>
      `,
    )
    .join("");
}

function addToCart(code) {
  const product = state.products.find((item) => item.codigo === code);
  if (!product) return;

  const existing = state.cart.get(code);
  if (existing) {
    existing.cantidad += 1;
  } else {
    state.cart.set(code, { ...product, cantidad: 1, encargue: product.stock <= 0 });
  }
  renderCart();
  showToast(`Agregado ${product.codigo}`);
}

function renderCart() {
  const items = [...state.cart.values()];
  if (!items.length) {
    cartItems.innerHTML = `<p class="subline">Todavia no hay productos agregados.</p>`;
    cartTotal.textContent = formatter.format(0);
    return;
  }

  cartItems.innerHTML = items
    .map(
      (item) => `
        <article class="cart-item">
          <strong>${item.codigo} - ${item.nombre}</strong>
          <span class="subline">${formatter.format(item.precio)} por ${unitLabel(item.unidad_venta)} | Stock: ${formatQuantity(item.stock, item.unidad_venta)}</span>
          <div class="cart-controls">
            <input type="number" min="${item.unidad_venta === "metro" ? "0.01" : "1"}" step="${item.unidad_venta === "metro" ? "0.01" : "1"}" value="${item.cantidad}" data-qty="${item.codigo}" />
            <label>
              <input type="checkbox" ${item.encargue ? "checked" : ""} data-order="${item.codigo}" />
              Encargue
            </label>
            <button type="button" data-remove="${item.codigo}">X</button>
          </div>
        </article>
      `,
    )
    .join("");

  const total = items.reduce((sum, item) => sum + item.precio * item.cantidad, 0);
  cartTotal.textContent = formatter.format(total);
}

function selectProduct(code) {
  const product = state.products.find((item) => item.codigo === code);
  if (!product) return;

  state.selectedProduct = product;
  editHint.classList.add("hidden");
  editForm.classList.remove("hidden");
  editTitle.textContent = `${product.codigo} - ${product.nombre}`;
  editName.value = product.nombre;
  editCategory.value = product.rubro;
  editBrand.value = product.marca;
  editProviderCode.value = product.codigo_proveedor || "";
  editMeasure.value = product.medida || "";
  editPrice.value = product.precio;
  editStock.value = product.stock;
  editMinStock.value = product.stock_minimo;
  editUnit.value = product.unidad_venta || "unidad";
  editLocation.value = product.ubicacion || "";
  editSynonyms.value = product.sinonimos || "";
  editNotes.value = product.observaciones || "";
}

function newProduct() {
  state.selectedProduct = null;
  editHint.classList.add("hidden");
  editForm.classList.remove("hidden");
  editTitle.textContent = "Nuevo producto";
  editName.value = "";
  editCategory.value = "";
  editBrand.value = "Generica";
  editProviderCode.value = "";
  editMeasure.value = "";
  editPrice.value = "";
  editStock.value = "0";
  editMinStock.value = "0";
  editUnit.value = "unidad";
  editLocation.value = "A definir";
  editSynonyms.value = "";
  editNotes.value = "";
  editName.focus();
}

async function checkout() {
  if (!validateBilling()) return;

  const items = [...state.cart.values()].map((item) => ({
    codigo: item.codigo,
    cantidad: item.cantidad,
    encargue: item.encargue,
  }));

  if (!items.length) {
    showToast("Agrega productos antes de guardar.");
    return;
  }

  const data = await fetchJson("/api/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: state.mode,
      customer: customerInput.value.trim(),
      billing: {
        tax_id: taxIdInput.value.trim(),
        tax_condition: taxConditionInput.value,
        invoice_type: invoiceTypeInput.value,
        email: emailInput.value.trim(),
        phone: phoneInput.value.trim(),
        address: addressInput.value.trim(),
      },
      payment_method: paymentMethodInput.value,
      seller: sellerInput.value.trim(),
      discount_value: discountInput.value,
      notes: notesInput.value.trim(),
      items,
    }),
  });

  state.lastMessage = data.message;
  state.cart.clear();
  renderCart();
  await loadProducts(searchInput.value.trim());
  await loadSummary();
  showToast(`${data.document.numero} guardado.`);
}

async function loadSummary() {
  const data = await fetchJson("/api/summary");
  salesToday.textContent = formatter.format(data.sales_today);
  salesMonth.textContent = formatter.format(data.sales_month);
  pendingBudgets.textContent = data.pending_budgets;
  orderedItems.textContent = data.ordered_items;
}

async function loadLatestUpdate() {
  const data = await fetchJson("/api/latest-update");
  if (!data.exists) {
    updateGrid.innerHTML = `<p class="subline">Todavia no hay reportes de actualizacion.</p>`;
    return;
  }

  updateGrid.innerHTML = `
    <article><span>Estado</span><strong>${data.aplicado ? "Aplicado" : "Solo revision"}</strong></article>
    <article><span>Precios modificados</span><strong>${data.cambios}</strong></article>
    <article><span>Productos nuevos</span><strong>${data.nuevos}</strong></article>
    <article><span>Precios en USD</span><strong>${data.precios_usd}</strong></article>
    <article><span>Catalogo actual</span><strong>${data.total_actual}</strong></article>
    <article><span>Lista nueva</span><strong>${data.total_lista_nueva}</strong></article>
    <article><span>No vinieron</span><strong>${data.no_vinieron}</strong></article>
    <article><span>Sin cambios</span><strong>${data.sin_cambios}</strong></article>
  `;
}

function renderPriceUpdateResult(data) {
  const changedRows = (data.muestra_cambios || [])
    .map((item) => `
      <tr>
        <td>${escapeHtml(item.codigo || "")}</td>
        <td>${escapeHtml(item.nombre || "")}</td>
        <td>${formatter.format(item.precio_anterior || 0)}</td>
        <td>${formatter.format(item.precio_nuevo || 0)}</td>
      </tr>
    `)
    .join("");
  const newRows = (data.muestra_nuevos || [])
    .map((item) => `
      <tr>
        <td>${escapeHtml(item.codigo_proveedor || "")}</td>
        <td>${escapeHtml(item.nombre || "")}</td>
        <td>${formatter.format(item.precio || 0)}</td>
      </tr>
    `)
    .join("");
  updateGrid.innerHTML = `
    <article><span>Estado</span><strong>${data.aplicado ? "Aplicado" : "Pendiente"}</strong></article>
    <article><span>Precios modificados</span><strong>${data.cambios}</strong></article>
    <article><span>Productos nuevos</span><strong>${data.nuevos}</strong></article>
    <article><span>Precios en USD</span><strong>${data.precios_usd}</strong></article>
    <article><span>Catalogo actual</span><strong>${data.total_actual}</strong></article>
    <article><span>Lista nueva</span><strong>${data.total_lista_nueva}</strong></article>
    <article><span>No vinieron</span><strong>${data.no_vinieron}</strong></article>
    <article><span>Sin cambios</span><strong>${data.sin_cambios}</strong></article>
  `;
  priceUpdateDetail.innerHTML = `
    <strong>${data.aplicado ? "Lista aplicada" : "Revision lista para aplicar"}</strong>
    <span>Reporte: ${escapeHtml(data.report_path)}</span>
    ${changedRows ? `
      <div class="price-preview">
        <span>Primeros precios modificados</span>
        <table>
          <thead><tr><th>Cod.</th><th>Producto</th><th>Antes</th><th>Nuevo</th></tr></thead>
          <tbody>${changedRows}</tbody>
        </table>
      </div>
    ` : ""}
    ${newRows ? `
      <div class="price-preview">
        <span>Primeros productos nuevos</span>
        <table>
          <thead><tr><th>Proveedor</th><th>Producto</th><th>Precio</th></tr></thead>
          <tbody>${newRows}</tbody>
        </table>
      </div>
    ` : ""}
  `;
  applyPriceUpdate.disabled = data.aplicado;
  applyPriceUpdate.dataset.reportPath = data.report_path;
}

async function previewSelectedPriceList() {
  const file = priceListInput.files[0];
  if (!file) {
    showToast("Elegí una lista .xlsx primero.");
    return;
  }
  const response = await fetch("/api/price-update/preview", {
    method: "POST",
    headers: { "X-Filename": file.name },
    body: await file.arrayBuffer(),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "No se pudo revisar la lista");
  renderPriceUpdateResult(data);
  showToast("Lista revisada.");
}

async function applySelectedPriceList() {
  const reportPath = applyPriceUpdate.dataset.reportPath;
  if (!reportPath) {
    showToast("Primero revisá una lista.");
    return;
  }
  const data = await fetchJson("/api/price-update/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ report_path: reportPath }),
  });
  renderPriceUpdateResult(data);
  await loadProducts(searchInput.value.trim());
  showToast("Lista aplicada.");
}

let searchTimer = null;
searchInput.addEventListener("input", () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => loadProducts(searchInput.value.trim()), 180);
});

searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && state.products[0]) {
    event.preventDefault();
    addToCart(state.products[0].codigo);
  }
});

clearSearch.addEventListener("click", () => {
  searchInput.value = "";
  loadProducts();
  searchInput.focus();
});

productsBody.addEventListener("click", (event) => {
  const action = event.target.closest("[data-add], [data-edit]");
  if (!action) return;
  const addCode = action.dataset.add;
  const editCode = action.dataset.edit;
  if (addCode) addToCart(addCode);
  if (editCode) selectProduct(editCode);
});

cartItems.addEventListener("input", (event) => {
  const qtyCode = event.target.dataset ? event.target.dataset.qty : null;
  if (!qtyCode) return;
  const item = state.cart.get(qtyCode);
  if (!item) return;
  item.cantidad = Number(event.target.value || 0);
  renderCart();
});

cartItems.addEventListener("change", (event) => {
  const orderCode = event.target.dataset ? event.target.dataset.order : null;
  if (!orderCode) return;
  const item = state.cart.get(orderCode);
  if (!item) return;
  item.encargue = event.target.checked;
});

cartItems.addEventListener("click", (event) => {
  const action = event.target.closest("[data-remove]");
  if (!action) return;
  const removeCode = action.dataset.remove;
  state.cart.delete(removeCode);
  renderCart();
});

document.querySelectorAll("[data-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    state.mode = button.dataset.mode;
    document.querySelectorAll("[data-mode]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
  });
});

taxConditionInput.addEventListener("change", updateBillingRequirements);
newProductButton.addEventListener("click", newProduct);

saveButton.addEventListener("click", () => {
  checkout().catch((error) => showToast(error.message));
});

copyButton.addEventListener("click", async () => {
  if (!state.lastMessage) {
    showToast("Primero guarda un presupuesto o venta.");
    return;
  }
  await navigator.clipboard.writeText(state.lastMessage);
  showToast("Texto copiado.");
});

editForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  try {
    const creating = !state.selectedProduct;
    const payload = {
      codigo: state.selectedProduct?.codigo,
      nombre: editName.value,
      rubro: editCategory.value,
      marca: editBrand.value,
      codigo_proveedor: editProviderCode.value,
      medida: editMeasure.value,
      precio: editPrice.value,
      stock: editStock.value,
      stock_minimo: editMinStock.value,
      unidad_venta: editUnit.value,
      ubicacion: editLocation.value,
      sinonimos: editSynonyms.value,
      observaciones: editNotes.value,
    };
    const url = state.selectedProduct ? "/api/update-product" : "/api/products";
    const data = await fetchJson(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await loadProducts(searchInput.value.trim());
    state.selectedProduct = data.product;
    editTitle.textContent = `${data.product.codigo} - ${data.product.nombre}`;
    showToast(creating ? "Producto creado." : "Producto guardado.");
  } catch (error) {
    showToast(error.message);
  }
});

refreshUpdate.addEventListener("click", () => loadLatestUpdate());
previewPriceUpdate.addEventListener("click", () => {
  previewSelectedPriceList().catch((error) => showToast(error.message));
});
applyPriceUpdate.addEventListener("click", () => {
  applySelectedPriceList().catch((error) => showToast(error.message));
});

loadProducts().catch((error) => showToast(error.message));
loadSummary().catch((error) => showToast(error.message));
loadLatestUpdate().catch((error) => showToast(error.message));
updateBillingRequirements();
renderCart();

from __future__ import annotations

import json
import mimetypes
import sys
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import app


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
ASSETS_DIR = BASE_DIR / "assets"
UPDATES_DIR = BASE_DIR / "actualizaciones"
CLOSURES_DIR = BASE_DIR / "cierres"
BACKUPS_DIR = BASE_DIR / "backups"
PRICE_UPLOADS_DIR = UPDATES_DIR / "listas"
TOOLS_DIR = BASE_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import import_tigre
import update_prices


def product_to_dict(product: app.Product) -> dict[str, object]:
    return {
        "codigo": product.codigo,
        "codigo_proveedor": product.codigo_proveedor,
        "nombre": product.nombre,
        "rubro": product.rubro,
        "medida": product.medida,
        "marca": product.marca,
        "precio": product.precio,
        "stock": product.stock,
        "stock_minimo": product.stock_minimo,
        "unidad_venta": product.unidad_venta,
        "ubicacion": product.ubicacion,
        "sinonimos": product.sinonimos,
        "observaciones": product.observaciones,
    }


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, object]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        return {}
    body = handler.rfile.read(length).decode("utf-8")
    return json.loads(body)


def movement_summary() -> dict[str, object]:
    today = app.datetime.now().date()
    month_key = app.datetime.now().strftime("%Y-%m")
    sales_today = 0.0
    sales_month = 0.0
    pending_budgets = 0
    ordered_items = 0

    app.BUDGETS_DIR.mkdir(parents=True, exist_ok=True)
    for path in app.BUDGETS_DIR.glob("*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        date_text = str(document.get("fecha", ""))
        status = document.get("estado")
        total = float(document.get("total", 0))

        if status == "vendido":
            if date_text.startswith(str(today)):
                sales_today += total
            if date_text.startswith(month_key):
                sales_month += total
        elif status == "pendiente":
            pending_budgets += 1

        for item in document.get("items", []):
            if isinstance(item, dict) and item.get("encargue"):
                ordered_items += 1

    return {
        "sales_today": sales_today,
        "sales_month": sales_month,
        "pending_budgets": pending_budgets,
        "ordered_items": ordered_items,
    }


def read_document(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def movement_row(path: Path) -> dict[str, object]:
    document = read_document(path)
    items = document.get("items", [])
    return {
        "numero": document["numero"],
        "fecha": document["fecha"],
        "cliente": document["cliente"],
        "total": document["total"],
        "estado": document["estado"],
        "medio_pago": document.get("medio_pago", ""),
        "vendedor": document.get("vendedor", ""),
        "items_count": len(items) if isinstance(items, list) else 0,
    }


def document_path(number: str) -> Path:
    clean = "".join(char for char in number if char.isalnum() or char in "-_")
    path = app.BUDGETS_DIR / f"{clean}.json"
    if not path.exists() or not path.is_file():
        raise ValueError("Movimiento no encontrado")
    return path


def parse_document_date(document: dict[str, object]) -> app.datetime | None:
    try:
        return app.datetime.fromisoformat(str(document.get("fecha", "")))
    except ValueError:
        return None


def documents_for_month(month_key: str) -> list[tuple[Path, dict[str, object]]]:
    app.BUDGETS_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in app.BUDGETS_DIR.glob("*.json"):
        document = read_document(path)
        if str(document.get("fecha", "")).startswith(month_key):
            rows.append((path, document))
    rows.sort(key=lambda row: str(row[1].get("fecha", "")))
    return rows


def document_matches_filters(
    document: dict[str, object],
    status_filter: str,
    period: str,
    date_from: str,
    date_to: str,
    text_query: str,
) -> bool:
    if status_filter and document.get("estado") != status_filter:
        return False

    date_text = str(document.get("fecha", ""))
    document_date = date_text[:10]
    if period == "today" and not date_text.startswith(str(app.datetime.now().date())):
        return False
    if period == "month" and not date_text.startswith(app.datetime.now().strftime("%Y-%m")):
        return False
    if date_from and document_date < date_from:
        return False
    if date_to and document_date > date_to:
        return False

    query = app.normalize_text(text_query)
    if query:
        haystack = app.normalize_text(
            " ".join(
                [
                    str(document.get("numero", "")),
                    str(document.get("cliente", "")),
                    str(document.get("estado", "")),
                    str(document.get("medio_pago", "")),
                    str(document.get("vendedor", "")),
                    " ".join(str(item.get("nombre", "")) for item in document.get("items", []) if isinstance(item, dict)),
                ]
            )
        )
        if query not in haystack:
            return False
    return True


def movements_payload(query: dict[str, list[str]]) -> dict[str, object]:
    status_filter = query.get("estado", [""])[0]
    period = query.get("periodo", [""])[0]
    date_from = query.get("desde", [""])[0]
    date_to = query.get("hasta", [""])[0]
    text_query = query.get("q", [""])[0]
    app.BUDGETS_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    total_sold = 0.0
    total_pending = 0.0
    count_sold = 0
    count_pending = 0
    count_void = 0
    for path in sorted(app.BUDGETS_DIR.glob("*.json"), reverse=True):
        document = read_document(path)
        if not document_matches_filters(document, status_filter, period, date_from, date_to, text_query):
            continue
        rows.append(movement_row(path))
        if document.get("estado") == "vendido":
            count_sold += 1
            total_sold += float(document.get("total", 0))
        elif document.get("estado") == "pendiente":
            count_pending += 1
            total_pending += float(document.get("total", 0))
        elif document.get("estado") == "anulado":
            count_void += 1

    return {
        "budgets": rows[:200],
        "totals": {
            "vendido": total_sold,
            "pendiente": total_pending,
            "ventas": count_sold,
            "presupuestos": count_pending,
            "anulados": count_void,
            "mostrados": min(len(rows), 200),
            "coincidencias": len(rows),
        },
    }


def monthly_closures() -> dict[str, object]:
    CLOSURES_DIR.mkdir(parents=True, exist_ok=True)
    months: dict[str, dict[str, object]] = {}
    for path in app.BUDGETS_DIR.glob("*.json"):
        document = read_document(path)
        date_text = str(document.get("fecha", ""))
        month = date_text[:7]
        if len(month) != 7:
            continue
        row = months.setdefault(
            month,
            {"periodo": month, "ventas": 0, "presupuestos": 0, "total_vendido": 0.0, "cerrado": False},
        )
        if document.get("estado") == "vendido":
            row["ventas"] = int(row["ventas"]) + 1
            row["total_vendido"] = float(row["total_vendido"]) + float(document.get("total", 0))
        elif document.get("estado") == "pendiente":
            row["presupuestos"] = int(row["presupuestos"]) + 1

    for zip_path in CLOSURES_DIR.glob("cierre-*.zip"):
        month = zip_path.stem.removeprefix("cierre-")
        if month in months:
            months[month]["cerrado"] = True
            months[month]["archivo"] = zip_path.name

    current_month = app.datetime.now().strftime("%Y-%m")
    rows = sorted(months.values(), key=lambda row: str(row["periodo"]), reverse=True)
    pending = [
        row for row in rows
        if str(row["periodo"]) < current_month and int(row["ventas"]) > 0 and not row["cerrado"]
    ]
    return {"months": rows[:12], "pending": pending}


def create_monthly_closure(month_key: str) -> dict[str, object]:
    if not re_month(month_key):
        raise ValueError("Periodo invalido. Usa AAAA-MM")

    rows = documents_for_month(month_key)
    if not rows:
        raise ValueError("No hay movimientos para ese periodo")

    CLOSURES_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = CLOSURES_DIR / f"cierre-{month_key}.zip"
    summary = {
        "periodo": month_key,
        "fecha_cierre": app.datetime.now().isoformat(timespec="seconds"),
        "ventas": 0,
        "presupuestos": 0,
        "total_vendido": 0.0,
        "movimientos": [],
    }
    for _, document in rows:
        if document.get("estado") == "vendido":
            summary["ventas"] = int(summary["ventas"]) + 1
            summary["total_vendido"] = float(summary["total_vendido"]) + float(document.get("total", 0))
        elif document.get("estado") == "pendiente":
            summary["presupuestos"] = int(summary["presupuestos"]) + 1
        summary["movimientos"].append(movement_row_from_document(document))

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("resumen.json", json.dumps(summary, ensure_ascii=False, indent=2))
        csv_lines = ["numero,fecha,cliente,estado,total"]
        for row in summary["movimientos"]:
            csv_lines.append(
                f"{row['numero']},{row['fecha']},{row['cliente']},{row['estado']},{row['total']}"
            )
        archive.writestr("resumen.csv", "\n".join(csv_lines) + "\n")
        for path, _ in rows:
            archive.write(path, f"movimientos/{path.name}")

    return {"ok": True, "archivo": zip_path.name, "path": str(zip_path), "summary": summary}


def movement_row_from_document(document: dict[str, object]) -> dict[str, object]:
    return {
        "numero": document.get("numero", ""),
        "fecha": document.get("fecha", ""),
        "cliente": document.get("cliente", ""),
        "estado": document.get("estado", ""),
        "total": document.get("total", 0),
    }


def re_month(value: str) -> bool:
    return len(value) == 7 and value[4] == "-" and value[:4].isdigit() and value[5:].isdigit()


def latest_update_report() -> dict[str, object]:
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    reports = sorted(UPDATES_DIR.glob("actualizacion_tigre_*.json"), reverse=True)
    if not reports:
        return {"exists": False}

    report = json.loads(reports[0].read_text(encoding="utf-8"))
    return {
        "exists": True,
        "fecha": report.get("fecha"),
        "aplicado": report.get("aplicado", False),
        "total_actual": report.get("total_actual", 0),
        "total_lista_nueva": report.get("total_lista_nueva", 0),
        "cambios": len(report.get("cambios", [])),
        "nuevos": len(report.get("nuevos", [])),
        "sin_cambios": report.get("sin_cambios", 0),
        "no_vinieron": len(report.get("no_vinieron", [])),
        "precios_usd": len(report.get("precios_usd", [])),
    }


def save_uploaded_price_list(handler: BaseHTTPRequestHandler) -> Path:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        raise ValueError("No se recibio archivo")
    filename = handler.headers.get("X-Filename", "lista.xlsx")
    extension = Path(filename).suffix.lower()
    if extension != ".xlsx":
        raise ValueError("La lista tiene que ser un archivo .xlsx")
    PRICE_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    path = PRICE_UPLOADS_DIR / f"lista_{app.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    path.write_bytes(handler.rfile.read(length))
    return path


def price_update_preview(path: Path) -> dict[str, object]:
    new_products = import_tigre.import_products(path, start_code=1)
    report = update_prices.compare_prices(new_products)
    report["aplicado"] = False
    report["archivo_lista"] = str(path)
    report_path = update_prices.write_report(report)
    return price_update_response(report, report_path)


def price_update_apply(report_path: Path) -> dict[str, object]:
    report = read_document(report_path)
    source = Path(str(report.get("archivo_lista") or ""))
    if not source.exists():
        raise ValueError("No encuentro la lista original para aplicar")
    new_products = import_tigre.import_products(source, start_code=1)
    report["aplicado"] = True
    update_prices.apply_update(new_products, report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return price_update_response(report, report_path)


def price_update_response(report: dict[str, object], report_path: Path) -> dict[str, object]:
    return {
        "ok": True,
        "report_path": str(report_path),
        "fecha": report.get("fecha"),
        "aplicado": report.get("aplicado", False),
        "total_actual": report.get("total_actual", 0),
        "total_lista_nueva": report.get("total_lista_nueva", 0),
        "cambios": len(report.get("cambios", [])),
        "nuevos": len(report.get("nuevos", [])),
        "sin_cambios": report.get("sin_cambios", 0),
        "no_vinieron": len(report.get("no_vinieron", [])),
        "precios_usd": len(report.get("precios_usd", [])),
        "muestra_cambios": report.get("cambios", [])[:12],
        "muestra_nuevos": report.get("nuevos", [])[:12],
    }


def format_document_message(document: dict[str, object]) -> str:
    lines = [
        f"{'Venta' if document.get('estado') == 'vendido' else 'Presupuesto'} Hidrogas {document['numero']}",
        f"Cliente: {document['cliente']}",
    ]

    billing = document.get("facturacion")
    if isinstance(billing, dict):
        tax_id = str(billing.get("tax_id") or "").strip()
        tax_condition = str(billing.get("tax_condition") or "").strip()
        invoice_type = str(billing.get("invoice_type") or "").strip()
        email = str(billing.get("email") or "").strip()
        phone = str(billing.get("phone") or "").strip()
        address = str(billing.get("address") or "").strip()
        if tax_id:
            lines.append(f"CUIT/DNI: {tax_id}")
        if tax_condition:
            lines.append(f"Condicion: {tax_condition}")
        if invoice_type:
            lines.append(f"Factura: {invoice_type}")
        if email:
            lines.append(f"Email: {email}")
        if phone:
            lines.append(f"Telefono: {phone}")
        if address:
            lines.append(f"Direccion: {address}")

    lines.append("")
    for item in document["items"]:  # type: ignore[index]
        unit = str(item.get("unidad_venta") or "unidad")
        label = "m" if unit == "metro" else "u"
        line = f"- {float(item['cantidad']):g} {label} x {item['nombre']} = {app.money(float(item['subtotal']))}"
        if item.get("encargue"):
            line += " (por encargue)"
        lines.append(line)

    if float(document.get("descuento", 0) or 0) > 0:
        lines.append(f"Subtotal: {app.money(float(document.get('subtotal_bruto', document['total'])))}")
        lines.append(f"Descuento: -{app.money(float(document.get('descuento', 0)))}")
    lines.extend(["", f"Total: {app.money(float(document['total']))}"])
    if document.get("observaciones"):
        lines.append(f"Obs: {document['observaciones']}")
    if document.get("medio_pago"):
        lines.append(f"Pago: {document['medio_pago']}")
    return "\n".join(lines)


def apply_stock_for_sale(document: dict[str, object], restore: bool = False) -> None:
    products = app.read_products()
    for item in document.get("items", []):
        if not isinstance(item, dict) or item.get("encargue"):
            continue
        product = app.find_product_by_code(products, str(item.get("codigo", "")))
        if product is None:
            raise ValueError(f"Producto inexistente: {item.get('codigo')}")
        quantity = parse_quantity(item.get("cantidad"), product)
        if restore:
            product.stock += quantity
        else:
            if quantity > product.stock:
                raise ValueError(f"Stock insuficiente para {product.codigo} - {product.nombre}")
            product.stock -= quantity
    app.write_products(products)


def convert_budget_to_sale(number: str, payload: dict[str, object]) -> dict[str, object]:
    path = document_path(number)
    budget = read_document(path)
    if budget.get("estado") != "pendiente":
        raise ValueError("Solo se puede vender un presupuesto pendiente")

    sale = dict(budget)
    sale["numero"] = app.next_sale_number()
    sale["estado"] = "vendido"
    sale["fecha"] = app.datetime.now().isoformat(timespec="seconds")
    sale["origen_presupuesto"] = budget.get("numero")
    sale["medio_pago"] = str(payload.get("medio_pago") or "")
    sale["vendedor"] = str(payload.get("vendedor") or "")
    apply_stock_for_sale(sale, restore=False)

    sale_path = app.BUDGETS_DIR / f"{sale['numero']}.json"
    sale_path.write_text(json.dumps(sale, ensure_ascii=False, indent=2), encoding="utf-8")

    budget["estado"] = "convertido"
    budget["venta_numero"] = sale["numero"]
    budget["fecha_conversion"] = sale["fecha"]
    path.write_text(json.dumps(budget, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"document": sale, "message": format_document_message(sale)}


def void_document(number: str, payload: dict[str, object]) -> dict[str, object]:
    path = document_path(number)
    document = read_document(path)
    if document.get("estado") == "anulado":
        raise ValueError("El movimiento ya esta anulado")
    if document.get("estado") == "vendido":
        apply_stock_for_sale(document, restore=True)
    document["estado_anterior"] = document.get("estado")
    document["estado"] = "anulado"
    document["motivo_anulacion"] = str(payload.get("motivo") or "").strip() or "Sin motivo"
    document["fecha_anulacion"] = app.datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"document": document}


def create_backup() -> dict[str, object]:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = app.datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_path = BACKUPS_DIR / f"backup-hidrogas-{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
      for folder_name in ["data", "presupuestos", "cierres", "actualizaciones"]:
          folder = BASE_DIR / folder_name
          if not folder.exists():
              continue
          for path in folder.rglob("*"):
              if path.is_file():
                  archive.write(path, path.relative_to(BASE_DIR))
    return {"ok": True, "archivo": zip_path.name, "path": str(zip_path)}


class Handler(BaseHTTPRequestHandler):
    server_version = "HidrogasLocal/0.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, data: object, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return

        content = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/assets/"):
            path = ASSETS_DIR / parsed.path.removeprefix("/assets/")
        else:
            relative = parsed.path.lstrip("/") or "index.html"
            path = WEB_DIR / relative

        if not path.exists() or not path.is_file():
            self.send_error(404)
            return

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/products":
            query = parse_qs(parsed.query).get("q", [""])[0].strip()
            products = app.read_products()
            if query:
                by_code = app.find_product_by_code(products, query)
                results = [by_code] if by_code else app.search_products(products, query, limit=80)
            else:
                results = products[:80]
            self.send_json({
                "products": [product_to_dict(product) for product in results],
                "total": len(products),
            })
            return

        if parsed.path == "/api/budgets":
            self.send_json(movements_payload(parse_qs(parsed.query)))
            return

        if parsed.path.startswith("/api/budgets/"):
            number = parsed.path.removeprefix("/api/budgets/")
            document = read_document(document_path(number))
            self.send_json({"document": document, "message": format_document_message(document)})
            return

        if parsed.path == "/api/summary":
            self.send_json(movement_summary())
            return

        if parsed.path == "/api/closures":
            self.send_json(monthly_closures())
            return

        if parsed.path == "/api/low-stock":
            products = [
                product_to_dict(product)
                for product in app.read_products()
                if product.stock_minimo > 0 and product.stock <= product.stock_minimo
            ]
            self.send_json({"products": products[:200], "total": len(products)})
            return

        if parsed.path == "/api/latest-update":
            self.send_json(latest_update_report())
            return

        if parsed.path.startswith("/assets/"):
            self.send_file(ASSETS_DIR / parsed.path.removeprefix("/assets/"))
            return

        relative = parsed.path.lstrip("/") or "index.html"
        self.send_file(WEB_DIR / relative)

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            if self.path == "/api/checkout":
                self.handle_checkout()
                return
            if self.path == "/api/price-update/preview":
                path = save_uploaded_price_list(self)
                self.send_json(price_update_preview(path))
                return
            if self.path == "/api/price-update/apply":
                payload = read_json(self)
                report_path = Path(str(payload.get("report_path") or ""))
                self.send_json(price_update_apply(report_path))
                return
            if self.path == "/api/products":
                self.handle_create_product()
                return
            if self.path == "/api/update-product":
                self.handle_update_product()
                return
            if self.path == "/api/closures":
                self.handle_create_closure()
                return
            if self.path == "/api/backups":
                self.send_json(create_backup())
                return
            if parsed.path.startswith("/api/budgets/") and parsed.path.endswith("/sell"):
                number = parsed.path.removeprefix("/api/budgets/").removesuffix("/sell")
                self.send_json(convert_budget_to_sale(number, read_json(self)))
                return
            if parsed.path.startswith("/api/budgets/") and parsed.path.endswith("/void"):
                number = parsed.path.removeprefix("/api/budgets/").removesuffix("/void")
                self.send_json(void_document(number, read_json(self)))
                return
            self.send_error(404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=400)

    def handle_checkout(self) -> None:
        payload = read_json(self)
        mode = str(payload.get("mode", "budget"))
        customer = str(payload.get("customer") or "Consumidor final")
        billing = payload.get("billing") if isinstance(payload.get("billing"), dict) else {}
        payment_method = str(payload.get("payment_method") or "")
        seller = str(payload.get("seller") or "")
        discount_value = parse_discount(payload.get("discount_value"))
        notes = str(payload.get("notes") or "")
        cart = payload.get("items")
        if mode not in {"budget", "sale"}:
            raise ValueError("Modo invalido")
        if not isinstance(cart, list) or not cart:
            raise ValueError("No hay productos")

        tax_condition = str(billing.get("tax_condition") or "Consumidor final").strip()
        requires_billing = tax_condition != "Consumidor final"
        required_fields = {
            "cliente": customer.strip() if customer != "Consumidor final" else "",
            "CUIT/DNI": str(billing.get("tax_id") or "").strip(),
            "tipo de factura": str(billing.get("invoice_type") or "").strip(),
            "email": str(billing.get("email") or "").strip(),
            "telefono": str(billing.get("phone") or "").strip(),
            "direccion": str(billing.get("address") or "").strip(),
        }
        if requires_billing:
            missing = [label for label, value in required_fields.items() if not value]
            if missing:
                raise ValueError(f"Faltan datos de facturacion: {', '.join(missing)}")

        products = app.read_products()
        items: list[dict[str, object]] = []
        warnings: list[str] = []

        for raw_item in cart:
            if not isinstance(raw_item, dict):
                continue
            code = str(raw_item.get("codigo") or "")
            is_order = bool(raw_item.get("encargue"))
            product = app.find_product_by_code(products, code)
            if product is None:
                raise ValueError(f"Producto inexistente: {code}")
            quantity = parse_quantity(raw_item.get("cantidad"), product)
            if quantity <= 0:
                raise ValueError(f"Cantidad invalida para {product.nombre}")

            if mode == "sale" and quantity > product.stock and not is_order:
                raise ValueError(f"Stock insuficiente para {product.codigo} - {product.nombre}")

            if mode == "sale" and is_order:
                warnings.append(f"{product.codigo} queda por encargue")
            elif mode == "sale":
                product.stock -= quantity

            subtotal = product.precio * quantity
            items.append(
                {
                    "codigo": product.codigo,
                    "codigo_proveedor": product.codigo_proveedor,
                    "nombre": product.nombre,
                    "cantidad": quantity,
                    "unidad_venta": product.unidad_venta,
                    "precio_unitario": product.precio,
                    "subtotal": subtotal,
                    "ubicacion": product.ubicacion,
                    "encargue": is_order,
                }
            )

        subtotal = sum(float(item["subtotal"]) for item in items)
        discount = min(discount_value, subtotal)
        total = subtotal - discount
        document = {
            "numero": app.next_sale_number() if mode == "sale" else app.next_budget_number(),
            "fecha": app.datetime.now().isoformat(timespec="seconds"),
            "cliente": customer,
            "facturacion": {
                "tax_id": str(billing.get("tax_id") or "").strip(),
                "tax_condition": tax_condition,
                "invoice_type": str(billing.get("invoice_type") or "").strip(),
                "email": str(billing.get("email") or "").strip(),
                "phone": str(billing.get("phone") or "").strip(),
                "address": str(billing.get("address") or "").strip(),
            },
            "observaciones": notes,
            "medio_pago": payment_method,
            "vendedor": seller,
            "subtotal_bruto": subtotal,
            "descuento": discount,
            "items": items,
            "total": total,
            "estado": "vendido" if mode == "sale" else "pendiente",
        }
        app.BUDGETS_DIR.mkdir(parents=True, exist_ok=True)
        path = app.BUDGETS_DIR / f"{document['numero']}.json"
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")

        if mode == "sale":
            app.write_products(products)

        self.send_json(
            {
                "document": document,
                "message": format_document_message(document),
                "warnings": warnings,
            }
        )

    def handle_create_product(self) -> None:
        payload = read_json(self)
        products = app.read_products()
        name = str(payload.get("nombre") or "").strip()
        if not name:
            raise ValueError("Falta nombre")
        unit = str(payload.get("unidad_venta") or app.infer_unit(name, str(payload.get("rubro") or "")))
        if unit not in {"unidad", "metro"}:
            raise ValueError("Unidad de venta invalida")
        product = app.Product(
            codigo=app.next_product_code(products),
            codigo_proveedor=str(payload.get("codigo_proveedor") or "").strip(),
            nombre=name,
            rubro=str(payload.get("rubro") or "").strip() or "General",
            medida=str(payload.get("medida") or "").strip(),
            marca=str(payload.get("marca") or "").strip() or "Generica",
            precio=parse_price(payload.get("precio")),
            stock=parse_stock_quantity(payload.get("stock") or 0, "stock", type("P", (), {"unidad_venta": unit})()),
            stock_minimo=parse_stock_quantity(payload.get("stock_minimo") or 0, "stock_minimo", type("P", (), {"unidad_venta": unit})()),
            unidad_venta=unit,
            ubicacion=str(payload.get("ubicacion") or "").strip() or "A definir",
            sinonimos=str(payload.get("sinonimos") or "").strip(),
            observaciones=str(payload.get("observaciones") or "").strip(),
        )
        products.append(product)
        app.write_products(products)
        self.send_json({"product": product_to_dict(product)})

    def handle_update_product(self) -> None:
        payload = read_json(self)
        code = str(payload.get("codigo") or "")
        products = app.read_products()
        product = app.find_product_by_code(products, code)
        if product is None:
            raise ValueError("Producto no encontrado")

        text_fields = ["codigo_proveedor", "nombre", "rubro", "medida", "marca"]
        for field in text_fields:
            if field in payload:
                setattr(product, field, str(payload[field]).strip())
        if "precio" in payload:
            product.precio = parse_price(payload["precio"])
        if "unidad_venta" in payload:
            unit = str(payload["unidad_venta"])
            if unit not in {"unidad", "metro"}:
                raise ValueError("Unidad de venta invalida")
            product.unidad_venta = unit
        for field in ["stock", "stock_minimo"]:
            if field in payload:
                setattr(product, field, parse_stock_quantity(payload[field], field, product))
        for field in ["ubicacion", "sinonimos", "observaciones"]:
            if field in payload:
                setattr(product, field, str(payload[field]))

        app.write_products(products)
        self.send_json({"product": product_to_dict(product)})

    def handle_create_closure(self) -> None:
        payload = read_json(self)
        period = str(payload.get("periodo") or "")
        self.send_json(create_monthly_closure(period))


def parse_integer(value: object, field_name: str) -> int:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name.capitalize()} invalido") from None
    if not number.is_integer() or number < 0:
        raise ValueError(f"{field_name.capitalize()} debe ser un numero entero")
    return int(number)


def parse_price(value: object) -> float:
    text = str(value or "").strip().replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        raise ValueError("Precio invalido") from None
    if number < 0:
        raise ValueError("Precio debe ser mayor o igual a cero")
    return number


def parse_discount(value: object) -> float:
    text = str(value or "0").strip().replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        raise ValueError("Descuento invalido") from None
    if number < 0:
        raise ValueError("Descuento debe ser mayor o igual a cero")
    return number


def parse_quantity(value: object, product: app.Product) -> float:
    text = str(value or "").strip().replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        raise ValueError("Cantidad invalida") from None
    if number <= 0:
        raise ValueError("Cantidad debe ser mayor a cero")
    if product.unidad_venta == "unidad" and not number.is_integer():
        raise ValueError(f"{product.codigo} se vende por unidad; usa cantidad entera")
    return number


def parse_stock_quantity(value: object, field_name: str, product: app.Product) -> float:
    text = str(value or "").strip().replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        raise ValueError(f"{field_name.capitalize()} invalido") from None
    if number < 0:
        raise ValueError(f"{field_name.capitalize()} debe ser mayor o igual a cero")
    if product.unidad_venta == "unidad" and not number.is_integer():
        raise ValueError(f"{field_name.capitalize()} debe ser entero para productos por unidad")
    return number


def main() -> None:
    port = 4180
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Hidrogas Gestion Local: http://127.0.0.1:{port}")
    print("Cerrar con Ctrl+C")
    server.serve_forever()


if __name__ == "__main__":
    main()

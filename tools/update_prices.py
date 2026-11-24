from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import import_tigre


BASE_DIR = Path(__file__).resolve().parents[1]
PRODUCTS_FILE = BASE_DIR / "data" / "productos.csv"
REPORTS_DIR = BASE_DIR / "actualizaciones"
BACKUPS_DIR = BASE_DIR / "backups"


FIELDNAMES = [
    "codigo",
    "codigo_proveedor",
    "nombre",
    "rubro",
    "medida",
    "marca",
    "precio",
    "stock",
    "stock_minimo",
    "unidad_venta",
    "ubicacion",
    "sinonimos",
    "observaciones",
]


def read_products(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def write_products(path: Path, products: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(products)


def as_price(value: str) -> float:
    return round(float(value or 0), 2)


def next_internal_code(products: list[dict[str, str]]) -> int:
    numeric_codes = [int(row["codigo"]) for row in products if row.get("codigo", "").isdigit()]
    return max(numeric_codes, default=0) + 1


def compare_prices(new_products: list[dict[str, str]]) -> dict[str, object]:
    current_products = read_products(PRODUCTS_FILE)
    current_by_provider = {
        row["codigo_proveedor"]: row
        for row in current_products
        if row.get("codigo_proveedor")
    }
    new_by_provider = {
        row["codigo_proveedor"]: row
        for row in new_products
        if row.get("codigo_proveedor")
    }

    changed = []
    unchanged = []
    added = []
    missing = []
    usd_marked = []

    for provider_code, new_row in new_by_provider.items():
        current = current_by_provider.get(provider_code)
        if current is None:
            added.append(new_row)
            continue

        old_price = as_price(current["precio"])
        new_price = as_price(new_row["precio"])
        if "USD" in new_row.get("observaciones", ""):
            usd_marked.append(new_row)

        if old_price != new_price:
            diff = round(new_price - old_price, 2)
            pct = round((diff / old_price * 100), 2) if old_price else None
            changed.append(
                {
                    "codigo": current["codigo"],
                    "codigo_proveedor": provider_code,
                    "nombre": current["nombre"],
                    "precio_anterior": old_price,
                    "precio_nuevo": new_price,
                    "diferencia": diff,
                    "porcentaje": pct,
                    "rubro": new_row["rubro"],
                    "observaciones": new_row["observaciones"],
                }
            )
        else:
            unchanged.append(current)

    for provider_code, current in current_by_provider.items():
        if provider_code not in new_by_provider:
            missing.append(current)

    return {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "total_actual": len(current_products),
        "total_lista_nueva": len(new_products),
        "cambios": changed,
        "sin_cambios": len(unchanged),
        "nuevos": added,
        "no_vinieron": missing,
        "precios_usd": usd_marked,
    }


def apply_update(new_products: list[dict[str, str]], report: dict[str, object]) -> None:
    current_products = read_products(PRODUCTS_FILE)
    current_by_provider = {
        row["codigo_proveedor"]: row
        for row in current_products
        if row.get("codigo_proveedor")
    }
    new_by_provider = {
        row["codigo_proveedor"]: row
        for row in new_products
        if row.get("codigo_proveedor")
    }

    for provider_code, current in current_by_provider.items():
        new_row = new_by_provider.get(provider_code)
        if new_row is None:
            continue

        current["nombre"] = new_row["nombre"]
        current["rubro"] = new_row["rubro"]
        current["marca"] = new_row["marca"]
        current["precio"] = new_row["precio"]
        current["unidad_venta"] = current.get("unidad_venta") or new_row.get("unidad_venta", "unidad")
        current["observaciones"] = new_row["observaciones"]
        current["sinonimos"] = " ".join(
            value
            for value in [current.get("sinonimos", ""), new_row.get("sinonimos", "")]
            if value
        )

    next_code = next_internal_code(current_products)
    for new_row in report["nuevos"]:  # type: ignore[index]
        new_product = dict(new_row)
        new_product["codigo"] = f"{next_code:02d}"
        new_product["unidad_venta"] = new_product.get("unidad_venta") or "unidad"
        current_products.append(new_product)
        next_code += 1

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUPS_DIR / f"productos_antes_actualizacion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    backup_path.write_text(PRODUCTS_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    write_products(PRODUCTS_FILE, current_products)


def write_report(report: dict[str, object]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"actualizacion_tigre_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def print_summary(report: dict[str, object], applied: bool) -> None:
    print("Actualizacion Tigre")
    print(f"Productos actuales: {report['total_actual']}")
    print(f"Productos lista nueva: {report['total_lista_nueva']}")
    print(f"Precios modificados: {len(report['cambios'])}")  # type: ignore[arg-type]
    print(f"Productos nuevos: {len(report['nuevos'])}")  # type: ignore[arg-type]
    print(f"Sin cambios: {report['sin_cambios']}")
    print(f"No vinieron en lista nueva: {len(report['no_vinieron'])}")  # type: ignore[arg-type]
    print(f"Precios en USD: {len(report['precios_usd'])}")  # type: ignore[arg-type]
    print(f"Aplicado: {'si' if applied else 'no'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara y aplica una nueva lista Tigre.")
    parser.add_argument("xlsx", type=Path, help="Ruta a la nueva lista .xlsx de Tigre")
    parser.add_argument("--apply", action="store_true", help="Aplicar cambios al catalogo principal")
    args = parser.parse_args()

    new_products = import_tigre.import_products(args.xlsx, start_code=1)
    report = compare_prices(new_products)
    report["aplicado"] = bool(args.apply)

    if args.apply:
        apply_update(new_products, report)

    report_path = write_report(report)
    print_summary(report, applied=args.apply)
    print(f"Reporte: {report_path}")


if __name__ == "__main__":
    main()

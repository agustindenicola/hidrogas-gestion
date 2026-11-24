from __future__ import annotations

import argparse
import csv
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


BASE_DIR = Path(__file__).resolve().parents[1]
PRODUCTS_FILE = BASE_DIR / "data" / "productos.csv"
OUTPUT_FILE = BASE_DIR / "data" / "productos_tigre_importados.csv"
NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def col_index(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    number = 0
    for letter in letters:
        number = number * 26 + ord(letter.upper()) - 64
    return number - 1


def read_shared_strings(zipped: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zipped.namelist():
        return []

    root = ET.fromstring(zipped.read("xl/sharedStrings.xml"))
    strings = []
    for item in root.findall("a:si", NS):
        texts = [text.text or "" for text in item.findall(".//a:t", NS)]
        strings.append("".join(texts))
    return strings


def workbook_sheets(zipped: ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(zipped.read("xl/workbook.xml"))
    rels = ET.fromstring(zipped.read("xl/_rels/workbook.xml.rels"))
    relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    sheets = []

    for sheet in workbook.find("a:sheets", NS):
        relation_id = sheet.attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        target = relmap[relation_id]
        if not target.startswith("xl/"):
            target = "xl/" + target
        sheets.append((sheet.attrib["name"], target))

    return sheets


def cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    value_node = cell.find("a:v", NS)
    if value_node is None:
        return ""

    raw_value = value_node.text or ""
    if cell.attrib.get("t") == "s":
        return shared_strings[int(raw_value)]
    return raw_value


def sheet_rows(zipped: ZipFile, sheet_path: str, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(zipped.read(sheet_path))
    rows = []

    for row in root.findall(".//a:sheetData/a:row", NS):
        values: list[str] = []
        for cell in row.findall("a:c", NS):
            index = col_index(cell.attrib.get("r", "A1"))
            while len(values) <= index:
                values.append("")
            values[index] = cell_value(cell, shared_strings).strip()

        if any(values):
            rows.append(values)

    return rows


def normalize_header(value: str) -> str:
    normalized = value.upper().replace("Í", "I").replace("Ó", "O")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def parse_price(value: str) -> float | None:
    if not value or value.upper() in {"#N/A", "N/A"}:
        return None
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def next_code_start() -> int:
    if not PRODUCTS_FILE.exists():
        return 1

    max_code = 0
    with PRODUCTS_FILE.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            code = row.get("codigo", "")
            if code.isdigit():
                max_code = max(max_code, int(code))
    return max_code + 1


def detect_columns(row: list[str]) -> dict[str, int] | None:
    headers = [normalize_header(value) for value in row]
    if "CODIGO" not in headers or "DESCRIPCION" not in headers:
        return None

    price_ars_index = None
    price_usd_index = None
    for index, header in enumerate(headers):
        if header in {"PRECIO", "PRECIO AR$"}:
            price_ars_index = index
        if header in {"PRECIO UD$", "PRECIO U$D"}:
            price_usd_index = index

    if price_ars_index is None and price_usd_index is None:
        return None

    result = {
        "codigo": headers.index("CODIGO"),
        "descripcion": headers.index("DESCRIPCION"),
    }
    if price_ars_index is not None:
        result["precio_ars"] = price_ars_index
    if price_usd_index is not None:
        result["precio_usd"] = price_usd_index
    if "EMBALAJE" in headers:
        result["embalaje"] = headers.index("EMBALAJE")
    return result


def import_products(
    xlsx_path: Path,
    limit: int | None = None,
    start_code: int | None = None,
) -> list[dict[str, str]]:
    imported: list[dict[str, str]] = []
    seen_provider_codes: set[str] = set()
    next_code = start_code if start_code is not None else next_code_start()

    with ZipFile(xlsx_path) as zipped:
        shared_strings = read_shared_strings(zipped)
        for sheet_name, sheet_path in workbook_sheets(zipped):
            if sheet_name.upper() in {"RESUMEN", "XBULTO", "FUERA DE STOCK"}:
                continue

            current_section = sheet_name
            columns: dict[str, int] | None = None
            for row in sheet_rows(zipped, sheet_path, shared_strings):
                detected = detect_columns(row)
                if detected:
                    columns = detected
                    continue

                if columns is None:
                    text_values = [value for value in row if value]
                    if len(text_values) == 1 and not text_values[0].lower().startswith("vigencia"):
                        current_section = text_values[0]
                    continue

                provider_code = row[columns["codigo"]] if len(row) > columns["codigo"] else ""
                description = row[columns["descripcion"]] if len(row) > columns["descripcion"] else ""
                price = None
                currency = "ARS"

                if "precio_ars" in columns and len(row) > columns["precio_ars"]:
                    price = parse_price(row[columns["precio_ars"]])

                if (price is None or price == 0) and "precio_usd" in columns and len(row) > columns["precio_usd"]:
                    usd_price = parse_price(row[columns["precio_usd"]])
                    if usd_price is not None and usd_price > 0:
                        price = usd_price
                        currency = "USD"

                if not provider_code.isdigit() or not description or price is None:
                    continue
                if provider_code in seen_provider_codes:
                    continue

                seen_provider_codes.add(provider_code)
                if currency == "USD":
                    observations = "Importado desde lista Tigre. Precio en USD, revisar cotizacion."
                else:
                    observations = "Importado desde lista Tigre."

                packaging = ""
                if "embalaje" in columns and len(row) > columns["embalaje"]:
                    packaging = row[columns["embalaje"]]

                imported.append(
                    {
                        "codigo": f"{next_code:02d}",
                        "codigo_proveedor": provider_code,
                        "nombre": description,
                        "rubro": sheet_name,
                        "medida": "",
                        "marca": "Tigre",
                        "precio": f"{price:.2f}",
                        "stock": "0",
                        "stock_minimo": "0",
                        "unidad_venta": "metro" if any(word in description.upper() for word in ["TUBO", "CAÑO", "CANO", "MANGUERA", "CABLE"]) else "unidad",
                        "ubicacion": "A definir",
                        "sinonimos": f"{sheet_name} {current_section} {description} {provider_code}",
                        "observaciones": f"{observations} Embalaje: {packaging}".strip(),
                    }
                )
                next_code += 1

                if limit and len(imported) >= limit:
                    return imported

    return imported


def write_imported(products: list[dict[str, str]], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "codigo",
        "codigo_proveedor",
        "nombre",
        "rubro",
        "medida",
        "marca",
        "precio",
        "stock",
        "stock_minimo",
        "ubicacion",
        "sinonimos",
        "observaciones",
    ]
    with output_file.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa productos Tigre desde Excel a CSV Hidrogas.")
    parser.add_argument("xlsx", type=Path, help="Ruta al archivo .xlsx de Tigre")
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE, help="CSV de salida")
    parser.add_argument("--limit", type=int, default=None, help="Limitar cantidad de productos")
    parser.add_argument(
        "--start-code",
        type=int,
        default=None,
        help="Codigo interno inicial. Ejemplo: 1 para generar desde 01.",
    )
    args = parser.parse_args()

    products = import_products(args.xlsx, limit=args.limit, start_code=args.start_code)
    write_imported(products, args.output)
    print(f"Productos importados: {len(products)}")
    print(f"Salida: {args.output}")


if __name__ == "__main__":
    main()

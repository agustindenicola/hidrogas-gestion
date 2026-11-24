from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PRODUCTS_FILE = BASE_DIR / "data" / "productos.csv"
BUDGETS_DIR = BASE_DIR / "presupuestos"

SEARCH_SYNONYMS = {
    "cano": ["tubo", "caño"],
    "canio": ["tubo", "caño"],
    "caño": ["tubo", "cano"],
    "tubo": ["caño", "cano"],
    "llave": ["valvula", "válvula", "grifo"],
    "valvula": ["llave", "válvula"],
    "válvula": ["llave", "valvula"],
    "cinta": ["teflon", "sellador"],
    "teflon": ["cinta", "sellador"],
    "pegamento": ["adhesivo", "cemento"],
    "adhesivo": ["pegamento", "cemento"],
    "pileta": ["bacha", "lavatorio"],
    "bacha": ["pileta", "lavatorio"],
    "desague": ["cloaca", "cloacal"],
    "cloaca": ["desague", "cloacal"],
    "boya": ["flotante", "tanque"],
    "flotante": ["boya", "tanque"],
    "termofusion": ["fusion", "termofusora", "ppr"],
    "fusion": ["termofusion", "termofusora", "ppr"],
}


@dataclass
class Product:
    codigo: str
    codigo_proveedor: str
    nombre: str
    rubro: str
    medida: str
    marca: str
    precio: float
    stock: float
    stock_minimo: float
    unidad_venta: str
    ubicacion: str
    sinonimos: str
    observaciones: str

    @property
    def searchable_text(self) -> str:
        return normalize_text(
            " ".join(
                [
                    self.codigo,
                    self.codigo_proveedor,
                    self.nombre,
                    self.rubro,
                    self.medida,
                    self.marca,
                    str(self.stock),
                    self.unidad_venta,
                    self.ubicacion,
                    self.sinonimos,
                    self.observaciones,
                ]
            )
        )

    @property
    def normalized_name(self) -> str:
        return normalize_text(self.nombre)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower()
    value = value.replace('"', " pulgadas ")
    value = re.sub(r"[^a-z0-9/.,]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def singularize(term: str) -> str:
    if len(term) > 4 and term.endswith("es"):
        return term[:-2]
    if len(term) > 3 and term.endswith("s"):
        return term[:-1]
    return term


def query_terms(query: str) -> list[str]:
    normalized = normalize_text(query)
    base_terms = [term for term in normalized.split() if term]
    expanded = []
    for term in base_terms:
        variants = {term, singularize(term)}
        variants.update(normalize_text(value) for value in SEARCH_SYNONYMS.get(term, []))
        expanded.extend(value for value in variants if value)

    deduped = []
    for term in expanded:
        if term not in deduped:
            deduped.append(term)
    return deduped


def compact_code(value: str) -> str:
    return re.sub(r"\D+", "", value)


def term_matches_text(term: str, text: str) -> bool:
    if term.isdigit():
        return f" {term} " in f" {text} "
    return term in text


def product_score(product: Product, terms: list[str], original_query: str) -> int:
    score = 0
    searchable = product.searchable_text
    name = product.normalized_name
    query = normalize_text(original_query)
    raw_query = original_query.strip()
    code_only = raw_query.isdigit()
    query_code = compact_code(original_query) if code_only else ""

    if query_code:
        if product.codigo == query_code.zfill(len(product.codigo)):
            score += 1000
        if product.codigo_proveedor == query_code:
            score += 900

    if query and query in name:
        score += 180
    if query and query in searchable:
        score += 90

    for term in terms:
        padded_name = f" {name} "
        padded_searchable = f" {searchable} "
        if code_only and (term == product.codigo or term == product.codigo_proveedor):
            score += 220
        elif name.startswith(term):
            score += 90
        elif f" {term} " in padded_name:
            score += 55
        elif term in name:
            score += 35
        elif term.isdigit() and f" {term} " in padded_searchable:
            score += 28
        elif not term.isdigit() and term in searchable:
            score += 18

    # Small boost when all original words appear somewhere, regardless of order.
    original_terms = [term for term in normalize_text(original_query).split() if term]
    if original_terms and all(term_matches_text(term, searchable) for term in original_terms):
        score += 120

    return score


def money(value: float) -> str:
    return f"$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def infer_unit(product_name: str, rubro: str = "") -> str:
    text = normalize_text(f"{product_name} {rubro}")
    unit_markers = [
        "tubo macho",
        "tubo hembra",
        "corta tubo",
        "media union",
        "adaptador",
        "codo",
        "tee",
        "cupla",
        "tapon",
        "valvula",
        "llave",
    ]
    if any(marker in text for marker in unit_markers):
        return "unidad"
    meter_markers = [
        "tf tubo ppr",
        "br tubo pvc",
        "je tubo cloacal",
        "tubo irriga",
        "tubo irrigacion",
        "cano",
        "caño",
        "manguera",
        "cable",
    ]
    if any(marker in text for marker in meter_markers):
        return "metro"
    return "unidad"


def pause() -> None:
    input("\nEnter para continuar...")


def read_products() -> list[Product]:
    if not PRODUCTS_FILE.exists():
        return []

    with PRODUCTS_FILE.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return [
            Product(
                codigo=row["codigo"],
                codigo_proveedor=row.get("codigo_proveedor", ""),
                nombre=row["nombre"],
                rubro=row["rubro"],
                medida=row["medida"],
                marca=row["marca"],
                precio=float(row["precio"]),
                stock=float(row.get("stock", 0)),
                stock_minimo=float(row.get("stock_minimo", 0)),
                unidad_venta=row.get("unidad_venta") or infer_unit(row["nombre"], row["rubro"]),
                ubicacion=row["ubicacion"],
                sinonimos=row["sinonimos"],
                observaciones=row["observaciones"],
            )
            for row in reader
        ]


def write_products(products: list[Product]) -> None:
    PRODUCTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PRODUCTS_FILE.open("w", encoding="utf-8", newline="") as file:
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
            "unidad_venta",
            "ubicacion",
            "sinonimos",
            "observaciones",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for product in products:
            writer.writerow(asdict(product))


def search_products(products: list[Product], query: str, limit: int = 12) -> list[Product]:
    terms = query_terms(query)
    if not terms:
        return []

    scored: list[tuple[int, Product]] = []
    for product in products:
        score = product_score(product, terms, query)
        if score:
            scored.append((score, product))

    scored.sort(key=lambda item: (-item[0], item[1].codigo))
    return [product for _, product in scored[:limit]]


def next_product_code(products: list[Product]) -> str:
    numeric_codes = []
    for product in products:
        if product.codigo.isdigit():
            numeric_codes.append(int(product.codigo))

    next_number = max(numeric_codes, default=0) + 1
    return f"{next_number:02d}"


def find_product_by_code(products: list[Product], code: str) -> Product | None:
    raw_code = code.strip()
    if not raw_code.isdigit():
        return None

    normalized = raw_code.zfill(2)
    for product in products:
        if product.codigo == normalized:
            return product
    return None


def print_product(product: Product, index: int | None = None) -> None:
    prefix = f"{index}. " if index is not None else ""
    print(f"{prefix}{product.codigo} - {product.nombre}")
    if product.codigo_proveedor:
        print(f"   Codigo proveedor: {product.codigo_proveedor}")
    print(f"   Rubro: {product.rubro} | Medida: {product.medida} | Marca: {product.marca}")
    print(f"   Precio: {money(product.precio)}")
    print(f"   Stock: {product.stock:g} | Minimo: {product.stock_minimo:g}")
    print(f"   Ubicacion: {product.ubicacion}")
    if product.observaciones:
        print(f"   Obs: {product.observaciones}")


def option_search_products(products: list[Product]) -> None:
    query = input("\nBuscar producto por codigo, nombre o palabra comun: ").strip()
    by_code = find_product_by_code(products, query)
    if by_code:
        print("\nProducto encontrado por codigo:")
        print_product(by_code)
        pause()
        return

    results = search_products(products, query)

    if not results:
        print("\nNo encontre productos. Proba con rubro, medida, uso o palabra comun.")
        pause()
        return

    print("\nResultados:")
    for index, product in enumerate(results, start=1):
        print_product(product, index)
    pause()


def next_budget_number() -> str:
    BUDGETS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    count = len(list(BUDGETS_DIR.glob(f"PRES-{today}-*.json"))) + 1
    return f"PRES-{today}-{count:03d}"


def next_sale_number() -> str:
    BUDGETS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    count = len(list(BUDGETS_DIR.glob(f"VENTA-{today}-*.json"))) + 1
    return f"VENTA-{today}-{count:03d}"


def choose_product(products: list[Product]) -> Product | None:
    query = input("\nCodigo o busqueda para agregar: ").strip()
    by_code = find_product_by_code(products, query)
    if by_code:
        print_product(by_code)
        return by_code

    results = search_products(products, query)
    if not results:
        print("No encontre productos con esa busqueda.")
        return None

    for index, product in enumerate(results, start=1):
        print_product(product, index)

    choice = input("\nNumero de producto, o Enter para cancelar: ").strip()
    if not choice:
        return None

    try:
        position = int(choice)
    except ValueError:
        print("Opcion invalida.")
        return None

    if position < 1 or position > len(results):
        print("Opcion fuera de rango.")
        return None

    return results[position - 1]


def collect_items(products: list[Product], discount_stock: bool) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []

    while True:
        product = choose_product(products)
        if product:
            quantity_text = input("Cantidad: ").strip()
            try:
                quantity = int(quantity_text)
            except ValueError:
                print("Cantidad invalida. Usa un numero entero, por ejemplo 1 o 2.")
                continue

            if quantity <= 0:
                print("La cantidad tiene que ser mayor a cero.")
                continue

            is_order = False
            if discount_stock and quantity > product.stock:
                print(f"Stock insuficiente. Disponible: {product.stock:g}")
                answer = input("Registrar como producto por encargue? [s/N]: ").strip().lower()
                if answer != "s":
                    continue
                is_order = True

            subtotal = product.precio * quantity
            items.append(
                {
                    "codigo": product.codigo,
                    "codigo_proveedor": product.codigo_proveedor,
                    "nombre": product.nombre,
                    "cantidad": quantity,
                    "precio_unitario": product.precio,
                    "subtotal": subtotal,
                    "ubicacion": product.ubicacion,
                    "encargue": is_order,
                }
            )

            if discount_stock and not is_order:
                product.stock -= quantity
                stock_label = f" | Stock nuevo: {product.stock:g}"
            elif is_order:
                stock_label = " | Por encargue"
            else:
                stock_label = ""

            print(f"Agregado: {product.nombre} x {quantity:g} = {money(subtotal)}{stock_label}")

        another = input("\nAgregar otro producto? [s/N]: ").strip().lower()
        if another != "s":
            break

    return items


def option_new_budget(products: list[Product]) -> None:
    if not products:
        print("\nNo hay productos cargados.")
        pause()
        return

    customer = input("\nCliente: ").strip() or "Consumidor final"
    notes = input("Observaciones del presupuesto: ").strip()
    items = collect_items(products, discount_stock=False)

    if not items:
        print("\nPresupuesto cancelado sin productos.")
        pause()
        return

    total = sum(float(item["subtotal"]) for item in items)
    budget = {
        "numero": next_budget_number(),
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "cliente": customer,
        "observaciones": notes,
        "items": items,
        "total": total,
        "estado": "pendiente",
    }

    path = BUDGETS_DIR / f"{budget['numero']}.json"
    path.write_text(json.dumps(budget, ensure_ascii=False, indent=2), encoding="utf-8")

    print_budget(budget)
    print(f"\nGuardado en: {path}")
    print("\nMensaje para WhatsApp:")
    print(format_budget_message(budget))
    pause()


def option_new_sale(products: list[Product]) -> None:
    if not products:
        print("\nNo hay productos cargados.")
        pause()
        return

    customer = input("\nCliente: ").strip() or "Consumidor final"
    notes = input("Observaciones de la venta: ").strip()
    items = collect_items(products, discount_stock=True)

    if not items:
        print("\nVenta cancelada sin productos.")
        pause()
        return

    write_products(products)
    total = sum(float(item["subtotal"]) for item in items)
    sale = {
        "numero": next_sale_number(),
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "cliente": customer,
        "observaciones": notes,
        "items": items,
        "total": total,
        "estado": "vendido",
    }

    path = BUDGETS_DIR / f"{sale['numero']}.json"
    path.write_text(json.dumps(sale, ensure_ascii=False, indent=2), encoding="utf-8")

    print_budget(sale)
    print(f"\nVenta guardada en: {path}")
    print("Stock actualizado en data/productos.csv")
    pause()


def print_budget(budget: dict[str, object]) -> None:
    print("\n" + "=" * 54)
    print(f"Presupuesto {budget['numero']}")
    print(f"Cliente: {budget['cliente']}")
    if budget.get("observaciones"):
        print(f"Obs: {budget['observaciones']}")
    print("-" * 54)

    for item in budget["items"]:  # type: ignore[index]
        print(
            f"{item['cantidad']:g} x {item['nombre']} "
            f"({money(float(item['precio_unitario']))}) = {money(float(item['subtotal']))}"
        )
        if item.get("encargue"):
            print("   Estado: por encargue")
        print(f"   Ubicacion: {item['ubicacion']}")

    print("-" * 54)
    print(f"TOTAL: {money(float(budget['total']))}")
    print("=" * 54)


def format_budget_message(budget: dict[str, object]) -> str:
    lines = [
        f"Presupuesto Hidrogas {budget['numero']}",
        f"Cliente: {budget['cliente']}",
        "",
    ]

    for item in budget["items"]:  # type: ignore[index]
        lines.append(
            f"- {item['cantidad']:g} x {item['nombre']} = {money(float(item['subtotal']))}"
        )
        if item.get("encargue"):
            lines[-1] += " (por encargue)"

    lines.extend(["", f"Total: {money(float(budget['total']))}"])
    if budget.get("observaciones"):
        lines.append(f"Obs: {budget['observaciones']}")

    return "\n".join(lines)


def option_list_budgets() -> None:
    BUDGETS_DIR.mkdir(parents=True, exist_ok=True)
    paths = sorted(BUDGETS_DIR.glob("*.json"), reverse=True)

    if not paths:
        print("\nNo hay presupuestos guardados.")
        pause()
        return

    print("\nPresupuestos guardados:")
    for index, path in enumerate(paths, start=1):
        budget = json.loads(path.read_text(encoding="utf-8"))
        print(f"{index}. {budget['numero']} | {budget['cliente']} | {money(float(budget['total']))}")

    choice = input("\nNumero para ver detalle, o Enter para volver: ").strip()
    if not choice:
        return

    try:
        position = int(choice)
    except ValueError:
        print("Opcion invalida.")
        pause()
        return

    if position < 1 or position > len(paths):
        print("Opcion fuera de rango.")
        pause()
        return

    budget = json.loads(paths[position - 1].read_text(encoding="utf-8"))
    print_budget(budget)
    print("\nMensaje para WhatsApp:")
    print(format_budget_message(budget))
    pause()


def option_add_product(products: list[Product]) -> list[Product]:
    print("\nAgregar producto")
    codigo = next_product_code(products)
    print(f"Codigo asignado automaticamente: {codigo}")

    nombre = input("Nombre: ").strip()
    rubro = input("Rubro: ").strip()
    medida = input("Medida: ").strip()
    marca = input("Marca: ").strip() or "Generica"
    precio_text = input("Precio: ").strip().replace(",", ".")
    stock_text = input("Stock inicial: ").strip()
    stock_minimo_text = input("Stock minimo: ").strip()
    ubicacion = input("Ubicacion: ").strip()
    sinonimos = input("Sinonimos / palabras comunes: ").strip()
    observaciones = input("Observaciones: ").strip()

    try:
        precio = float(precio_text)
        stock = int(stock_text)
        stock_minimo = int(stock_minimo_text or 0)
    except ValueError:
        print("Precio invalido o stock no entero.")
        pause()
        return products

    products.append(
        Product(
            codigo=codigo,
            codigo_proveedor=input("Codigo proveedor, si tiene: ").strip(),
            nombre=nombre,
            rubro=rubro,
            medida=medida,
            marca=marca,
            precio=precio,
            stock=stock,
            stock_minimo=stock_minimo,
            unidad_venta=infer_unit(nombre, rubro),
            ubicacion=ubicacion,
            sinonimos=sinonimos,
            observaciones=observaciones,
        )
    )
    write_products(products)
    print("Producto guardado.")
    pause()
    return products


def option_update_price(products: list[Product]) -> None:
    product = choose_product(products)
    if not product:
        pause()
        return

    print(f"\nPrecio actual de {product.nombre}: {money(product.precio)}")
    price_text = input("Nuevo precio: ").strip().replace(",", ".")
    try:
        product.precio = float(price_text)
    except ValueError:
        print("Precio invalido.")
        pause()
        return

    write_products(products)
    print("Precio actualizado.")
    pause()


def option_price_list(products: list[Product]) -> None:
    print("\nLista de precios")
    print("-" * 78)
    print(f"{'Cod':<5} {'Producto':<30} {'Rubro':<15} {'Precio':>14} {'Stock':>8}")
    print("-" * 78)
    for product in sorted(products, key=lambda item: int(item.codigo) if item.codigo.isdigit() else 999999):
        print(
            f"{product.codigo:<5} {product.nombre[:30]:<30} {product.rubro[:15]:<15} "
            f"{money(product.precio):>14} {product.stock:>8g}"
        )
    pause()


def option_low_stock(products: list[Product]) -> None:
    low = [product for product in products if product.stock <= product.stock_minimo]
    if not low:
        print("\nNo hay productos por debajo del stock minimo.")
        pause()
        return

    print("\nProductos con stock bajo")
    for index, product in enumerate(low, start=1):
        print_product(product, index)
    pause()


def print_menu() -> None:
    print("\n" + "=" * 42)
    print("HIDROGAS - Gestion local")
    print("=" * 42)
    print("1. Buscar producto")
    print("2. Nuevo presupuesto")
    print("3. Registrar venta y descontar stock")
    print("4. Ver presupuestos / ventas")
    print("5. Lista de precios")
    print("6. Agregar producto")
    print("7. Actualizar precio")
    print("8. Ver stock bajo")
    print("9. Salir")


def main() -> None:
    BUDGETS_DIR.mkdir(parents=True, exist_ok=True)
    products = read_products()

    while True:
        print_menu()
        option = input("Opcion: ").strip()

        if option == "1":
            option_search_products(products)
        elif option == "2":
            option_new_budget(products)
        elif option == "3":
            option_new_sale(products)
        elif option == "4":
            option_list_budgets()
        elif option == "5":
            option_price_list(products)
        elif option == "6":
            products = option_add_product(products)
        elif option == "7":
            option_update_price(products)
        elif option == "8":
            option_low_stock(products)
        elif option == "9":
            print("Listo.")
            break
        else:
            print("Opcion invalida.")


if __name__ == "__main__":
    main()

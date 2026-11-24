# Hidrogas Gestion Local

## Idea

Herramienta local para ordenar el trabajo diario de Hidrogas sin arrancar con una tienda online ni un sistema grande.

El objetivo inicial es ahorrar tiempo en:

- lista de precios centralizada;
- busqueda por codigo unico;
- codigos propios desde `01` en adelante;
- control y descuento de stock;
- busqueda de productos;
- armado de presupuestos;
- calculo de totales;
- orden de productos por ubicacion;
- historial de presupuestos;
- consultas con nombres poco claros, como "el cosito del coso".

## Identidad visual

Logo de referencia guardado en:

```text
assets/logo-hidrogas.jpeg
```

Logo adaptado para la app:

```text
assets/logo-hidrogas.svg
```

Estetica general segun logo real:

- interfaz clara para uso diario de mostrador;
- fondos blancos o gris claro para no cansar la vista;
- `Hidro` en verde;
- `Gas` en amarillo;
- recursos visuales de agua/canerias;
- verde para botones y estados positivos;
- amarillo para gas, avisos y llamados de atencion;
- estilo simple, industrial y directo;
- tipografia gruesa, clara y facil de leer;
- evitar una estetica demasiado oscura, delicada o muy corporativa: tiene que sentirse como herramienta de mostrador.

Paleta aproximada:

```text
Texto oscuro: #18231d
Verde principal: #009245
Verde oscuro: #006b35
Amarillo llama: #ffc928
Fondo claro: #f5f7f1
Blanco panel: #ffffff
```

La foto/captura queda solo como referencia en `assets/logo-hidrogas.jpeg`. La app usa `assets/logo-hidrogas.svg`, que es una adaptacion limpia sin la captura, sin circulos dibujados y sin fondo de foto.

La version visual local debe ser de alto contraste, rapida para usar y pensada para buscar por codigo sin perder tiempo.

## Problemas detectados

### 1. El cliente no sabe el nombre tecnico

Muchos clientes piden productos con descripciones vagas. Esto no se puede solucionar del todo, pero se puede mejorar cargando sinonimos, usos, medidas y rubros.

Ejemplo:

```text
Busqueda: cosito tanque
Resultados posibles:
- Flotante para tanque
- Valvula de entrada
- Boya para tanque
- Conexion tanque 1/2
```

La busqueda ahora intenta adaptarse a la forma real de escribir:

- ignora mayusculas y minusculas;
- ignora acentos;
- tolera plurales simples;
- busca sin importar el orden de palabras;
- reconoce sinonimos basicos del rubro, por ejemplo `cano` / `tubo`, `llave` / `valvula`, `pegamento` / `adhesivo`;
- prioriza coincidencia exacta de codigo interno o codigo de proveedor.

### 2. Presupuestos hechos a mano

Al hacer presupuestos a mano pueden aparecer errores de:

- precio;
- producto;
- suma;
- cantidad;
- lectura;
- perdida del papel;
- falta de historial.

La solucion inicial es armar presupuestos desde productos cargados, calcular totales y guardar el resultado.

### 3. Desorden para encontrar productos

Cada producto puede tener una ubicacion interna:

```text
Pasillo 1 / Estante bajo / Caja conexiones
Deposito fondo / Sector tanques
Mostrador / Cajon bronce
```

Asi el sistema no solo muestra precio, tambien ayuda a encontrar fisicamente el producto.

## Primera version

Menu en terminal:

```text
1. Buscar producto
2. Nuevo presupuesto
3. Registrar venta y descontar stock
4. Ver presupuestos / ventas
5. Lista de precios
6. Agregar producto
7. Actualizar precio
8. Ver stock bajo
9. Salir
```

## Datos de producto

Cada producto tiene:

- codigo unico propio, por ejemplo `01`, `02`, `03`;
- nombre;
- rubro;
- medida;
- marca;
- precio;
- stock;
- stock minimo;
- ubicacion;
- sinonimos;
- observaciones.

Cuando se agrega un producto nuevo, el sistema asigna automaticamente el proximo codigo disponible.

Ejemplo:

```text
Ultimo codigo: 10
Nuevo producto: 11
```

## Datos de presupuesto

Cada presupuesto guarda:

- numero;
- fecha;
- cliente;
- datos de facturacion, si se cargan;
- productos;
- cantidades;
- precios;
- subtotal;
- total;
- observaciones.

Importante: un presupuesto no descuenta stock. Solo una venta confirmada descuenta stock.

## Venta y stock

La opcion "Registrar venta y descontar stock" sirve para:

- buscar producto por codigo;
- cargar cantidad;
- calcular total;
- guardar la venta;
- descontar stock automaticamente.

Ejemplo:

```text
Codigo: 01
Producto: Flotante para tanque
Stock actual: 12
Cantidad vendida: 2
Stock nuevo: 10
```

## Como usar la app visual

La forma recomendada para usarlo en el negocio es abrir la interfaz local en navegador.

Desde esta carpeta:

```bash
./iniciar_web.sh
```

Luego abrir:

```text
http://127.0.0.1:4180
```

La app visual permite:

- buscar por codigo, nombre, rubro o palabra comun;
- ver precio, stock y ubicacion;
- agregar productos a un presupuesto o venta;
- cargar datos para factura: CUIT/DNI, condicion, tipo de factura, email, telefono y direccion;
- marcar productos por encargue;
- guardar presupuesto;
- guardar venta y descontar stock;
- editar precio, stock minimo, stock actual y ubicacion;
- ver ultimos movimientos;
- ver resumen de ventas del dia, ventas del mes, presupuestos pendientes y productos por encargue.

Regla de facturacion:

- si es `Consumidor final`, los datos fiscales son opcionales;
- si es `Responsable inscripto`, `Monotributo` o `Exento`, son obligatorios:
  - cliente;
  - CUIT/DNI;
  - tipo de factura;
  - email;
  - telefono;
  - direccion.

## Como usar la demo de terminal

Desde esta carpeta:

```bash
python3 app.py
```

Los productos de ejemplo estan en:

```text
data/productos.csv
```

Actualmente `data/productos.csv` fue generado desde la lista Tigre recibida. El inventario demo anterior quedo respaldado en:

```text
data/productos_demo_backup.csv
```

Los presupuestos generados se guardan en:

```text
presupuestos/
```

## Proximas mejoras posibles

- Importar lista de precios desde Excel o CSV.
- Exportar presupuesto a PDF.
- Imprimir presupuesto.
- Guardar clientes frecuentes.
- Marcar presupuesto como pendiente, vendido o rechazado.
- Agregar proveedores.
- Agregar backup automatico.
- Mejorar busqueda por palabras parecidas.
- Crear una version visual local mas adelante.

## Lista Tigre

Archivo recibido:

```text
/home/agustin/Downloads/Tigre - 20-05-26.xlsx
```

La lista de Tigre trae codigo de proveedor, descripcion, embalaje y precios en pesos o dolares segun la hoja.

Decision importante:

- el codigo interno de Hidrogas sigue siendo propio: `01`, `02`, `03`;
- el codigo Tigre se guarda aparte como `codigo_proveedor`;
- la lista Tigre se puede usar como catalogo principal porque si no esta en stock, se trae por encargue;
- el stock inicial queda en `0` hasta cargar cantidades reales del local.

Importar lista Tigre:

```bash
python3 tools/import_tigre.py "/home/agustin/Downloads/Tigre - 20-05-26.xlsx"
```

Salida:

```text
data/productos_tigre_importados.csv
```

Regenerar catalogo principal desde Tigre empezando por codigo `01`:

```bash
python3 tools/import_tigre.py "/home/agustin/Downloads/Tigre - 20-05-26.xlsx" --start-code 1 --output data/productos.csv
```

Para probar con pocos productos:

```bash
python3 tools/import_tigre.py "/home/agustin/Downloads/Tigre - 20-05-26.xlsx" --limit 20
```

Luego hay que revisar:

- precios en dolares que necesiten conversion;
- ubicacion fisica;
- stock inicial;
- stock minimo;
- sinonimos utiles para mostrador.

## Actualizacion mensual de precios

Este flujo es importante porque los proveedores suelen mandar listas nuevas a principio o fin de mes.

La regla principal:

- se compara por `codigo_proveedor`;
- se actualiza el precio;
- se mantiene el codigo interno de Hidrogas;
- se mantiene stock;
- se mantiene ubicacion;
- se mantiene stock minimo;
- se guarda un backup antes de aplicar cambios.

Paso 1: revisar cambios sin aplicar:

```bash
python3 tools/update_prices.py "/ruta/a/nueva-lista-tigre.xlsx"
```

Esto genera un reporte en:

```text
actualizaciones/
```

El reporte muestra:

- productos actuales;
- productos de la lista nueva;
- precios modificados;
- productos nuevos;
- productos que no vinieron;
- precios en USD;
- si fue aplicado o solo revisado.

Paso 2: aplicar cambios, si esta todo bien:

```bash
python3 tools/update_prices.py "/ruta/a/nueva-lista-tigre.xlsx" --apply
```

Antes de aplicar, se guarda backup del catalogo actual en:

```text
backups/
```

La app visual muestra el ultimo reporte en el panel "Actualizacion de precios".

## Productos por encargue

Si al registrar una venta no hay stock suficiente, el sistema pregunta si se quiere registrar como producto por encargue.

En ese caso:

- guarda el producto en la venta;
- no descuenta stock;
- lo marca como `por encargue`;
- permite seguir usando la lista Tigre como catalogo de referencia.

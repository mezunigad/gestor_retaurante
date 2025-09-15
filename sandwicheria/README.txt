
Sandwichería - App con categorías y soporte para impresión térmica USB
---------------------------------------------------------------------
Contenido:
  - app.py
  - templates/*.html
  - static/style.css
  - sandwich.db (se crea al ejecutar por primera vez)

Requisitos:
  - Python 3.8+
  - Flask
  - (Opcional para impresión) python-escpos

Instalación de dependencias:
  pip install flask
  # Si deseas impresión térmica automática:
  pip install python-escpos

Configurar la impresora térmica (si la tienes):
  - Detecta tus ids USB con `lsusb` en Linux/Mac o en el administrador de dispositivos en Windows.
  - Edita app.py y cambia VENDOR_ID, PRODUCT_ID y USB_INTERFACE.
  - Habilita ENABLE_PRINTER = True en la parte superior de app.py para que intente imprimir cuando se cree una comanda.

Nota sobre python-escpos:
  - En algunas impresoras y sistemas operativos puede ser necesario instalar drivers y dar permisos USB.
  - Si la librería o la impresora no están disponibles, la app seguirá funcionando sin imprimir (la comanda se muestra en la web para imprimir con Ctrl+P).

Uso:
  1. Ejecutar:
     python app.py
  2. Abrir en tu navegador:
     http://127.0.0.1:5000
  3. Ir a /products para agregar o editar productos (elige categoria SANDWICH o BEBESTIBLE)
  4. Crear comandas en /orders (puedes seleccionar varios items en las dos secciones)
  5. Ver e imprimir comandas en /comanda/<id> o activando impresión térmica en la configuración.

Ejemplo de impresión manual con python-escpos (si prefieres probar desde consola):
  from escpos.printer import Usb
  p = Usb(0x04b8, 0x0202, 0)
  p.text("Prueba\\n")
  p.cut()

Observaciones:
  - Los productos iniciales que cargué incluyen tu lista de sándwiches y tres bebestibles de ejemplo.
  - Ajusta precios/costos desde /products.

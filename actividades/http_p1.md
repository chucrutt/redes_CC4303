# Actividad: construir un proxy

## Parte 1: fundamentos del servidor HTTP y proxy

- escuchar conexiones con sockets;
- recibir y parsear mensajes HTTP;
- responder con mensajes HTTP válidos;
- agregar headers personalizados;
- leer configuración desde un archivo JSON.

> Nota: A priori usaremos `localhost` o `127.0.0.1` como sustituto temporal de `IP_VM`.

---

## Paso 1: preparar el entorno y la base del servidor

Como primer paso, debemos ejecutar el desarrollo en una máquina virtual y asociar los sockets a la IP de esa máquina `IP_VM`.

```python
IP_VM = "127.0.0.1"
HOST = IP_VM
PORT = 8000
```

### Ejemplo mínimo de servidor que escucha

```python
import socket

HOST = "127.0.0.1"
PORT = 8000

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(5)

print(f"Servidor escuchando en {HOST}:{PORT}")

while True:
    conn, addr = server.accept()
    print(f"Conexión recibida desde {addr}")
    raw = conn.recv(4096)
    print(raw.decode("latin-1"))
    conn.close()
```

### Objetivo del paso 1

1. Crear la máquina virtual, si aún no existe.
2. Identificar su IP (`IP_VM`).
3. Probar la escucha en esa dirección.
4. En caso de no poder usar la VM, usar `localhost` como alternativa temporal.

---

## Paso 2: parsear mensajes HTTP

En esta etapa no necesitamos responder al cliente todavía. Lo importante es leer un mensaje HTTP recibido por un socket y convertirlo en una estructura más fácil de manipular.

### Objetivo

Crear la función:

```python
parse_HTTP_message(http_message: bytes)
```

que reciba un mensaje HTTP en bytes, lo divida en `start line`, `headers` y `body`, y devuelva una estructura de Python con la información relevante.

### Implementación sugerida

```python
def parse_HTTP_message(http_message: bytes):
    """
    Recibe un mensaje HTTP completo en bytes y devuelve un diccionario con:
      - type: 'request' o 'response'
      - start_line: primera linea del mensaje
      - headers: dict con los headers
      - body: contenido del body en bytes
      - method, path, version, status, reason
    """
    if not isinstance(http_message, (bytes, bytearray)):
        raise TypeError("http_message debe ser bytes")

    raw = bytes(http_message)

    # Separar HEAD y BODY usando \r\n\r\n
    if b"\r\n\r\n" in raw:
        head, body = raw.split(b"\r\n\r\n", 1)
    elif b"\n\n" in raw:
        head, body = raw.split(b"\n\n", 1)
    else:
        head, body = raw, b""

    head_text = head.decode("latin-1")
    lines = head_text.split("\r\n") if "\r\n" in head_text else head_text.split("\n")

    if not lines or not lines[0].strip():
        raise ValueError("Mensaje HTTP vacío o sin start line")

    start_line = lines[0]
    headers = {}

    for line in lines[1:]:
        if not line.strip():
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()

    if start_line.startswith("HTTP/"):
        message_type = "response"
        parts = start_line.split()
        version = parts[0] if len(parts) > 0 else ""
        status = parts[1] if len(parts) > 1 else ""
        reason = " ".join(parts[2:]) if len(parts) > 2 else ""

        return {
            "type": message_type,
            "start_line": start_line,
            "version": version,
            "status": status,
            "reason": reason,
            "headers": headers,
            "body": body,
        }

    message_type = "request"
    parts = start_line.split()
    if len(parts) >= 3:
        method, path, version = parts[0], parts[1], parts[2]
    else:
        method, path, version = "", "", ""

    return {
        "type": message_type,
        "start_line": start_line,
        "method": method,
        "path": path,
        "version": version,
        "headers": headers,
        "body": body,
    }
```

### Función auxiliar para reconstruir mensajes

También es útil definir una función que convierta la estructura devuelta por `parse_HTTP_message` de vuelta a bytes, para comprobar que el parseo funciona correctamente.

```python
def create_HTTP_message(parsed_message):
    if not isinstance(parsed_message, dict):
        raise TypeError("parsed_message debe ser un diccionario")

    headers = parsed_message.get("headers", {})
    body = parsed_message.get("body", b"")

    if parsed_message.get("type") == "request":
        start_line = (
            f"{parsed_message.get('method', '')} "
            f"{parsed_message.get('path', '')} "
            f"{parsed_message.get('version', '')}"
        ).strip()
    else:
        start_line = (
            f"{parsed_message.get('version', '')} "
            f"{parsed_message.get('status', '')} "
            f"{parsed_message.get('reason', '')}"
        ).strip()

    header_lines = [f"{key}: {value}" for key, value in headers.items()]
    http_message = start_line + "\r\n" + "\r\n".join(header_lines)

    if body:
        if isinstance(body, str):
            http_message += "\r\n\r\n" + body
        else:
            http_message += "\r\n\r\n" + body.decode("latin-1")
    else:
        http_message += "\r\n\r\n"

    return http_message.encode("latin-1")
```

### Qué hace esta función

La función hace lo siguiente:

1. recibe un mensaje HTTP completo en bytes;
2. separa el `HEAD` y el `BODY` usando `\r\n\r\n`;
3. toma la primera línea como `start line`;
4. separa los headers en un diccionario;
5. identifica si es una `request` o una `response`;
6. entrega la información estructurada para su procesamiento posterior.

### Ejemplo mínimo de socket para recibir la request

```python
import socket

HOST = "127.0.0.1"
PORT = 8000

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(5)

print(f"Escuchando en {HOST}:{PORT}")

while True:
    conn, addr = server.accept()
    raw = conn.recv(4096)
    print(raw.decode("latin-1"))
    print("\n--- parsed ---")
    print(parse_HTTP_message(raw))
    conn.close()
```

---

## Paso 3: responder con un mensaje HTTP válido

Ahora que ya sabemos cómo leer y interpretar una `request`, el siguiente paso es crear una `response` HTTP y enviarla al cliente.

### Requisitos de una response válida

Una response HTTP debe incluir:

- una `start line` válida;
- headers HTTP correctos;
- `Content-Type` indicando el tipo de contenido;
- `Content-Length` indicando la longitud del body;
- un cuerpo HTML.

### Ejemplo de response HTTP

```bash
curl -i cc4303.bachmann.cl
```
``` text
HTTP/1.1 200 OK
Server: nginx/1.17.0
Date: Sat, 29 Aug 2026 23:42:42 GMT
Content-Type: text/html; charset=utf-8
Content-Length: 237
Connection: keep-alive
Access-Control-Allow-Origin: *

<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>CC4303</title>
</head>
<body>
    <h1>Bienvenide ... oh? no puedo ver tu nombre :c!</h1>
    <h3><a href="replace">¿Qué es un proxy?</a></h3>
</body>
</html>
```

### Construir la response en Python

```python
response_body = "<html><body><h1>Hola desde mi servidor HTTP</h1></body></html>"
response_body_bytes = response_body.encode()

status_line = "HTTP/1.1 200 OK\r\n"
headers = (
    "Content-Type: text/html\r\n"
    f"Content-Length: {len(response_body_bytes)}\r\n"
    "\r\n"
)
response = (status_line + headers).encode() + response_body_bytes
```

### Importante

El header `Content-Length` debe coincidir exactamente con la cantidad de bytes del body. Si esto no ocurre, el cliente podría no procesar bien la respuesta.

### Prueba con el navegador

Se puede abrir el navegador en:

```text
http://localhost:8000
```

Si el servidor responde correctamente, el navegador debería mostrar el HTML entregado.

### Prueba con curl

```bash
curl -i http://localhost:8000
```

Esto debe mostrar tanto los headers como el contenido del HTML en el body.

---

## Paso 4: agregar el header `X-ElQuePregunta`

Una vez que ya sabemos responder correctamente, debemos modificar la respuesta agregando el header:

```text
X-ElQuePregunta: <nombre>
```

### Ejemplo de respuesta con el header

```text
HTTP/1.1 200 OK
Content-Type: text/html
Content-Length: 58
X-ElQuePregunta: Juan Perez

<html><body><h1>Hola desde mi servidor HTTP</h1></body></html>
```

### Código de ejemplo

```python
nombre = "Juan Perez"
response_body = "<html><body><h1>Hola</h1></body></html>"
response_body_bytes = response_body.encode()

status_line = "HTTP/1.1 200 OK\r\n"
headers = (
    "Content-Type: text/html\r\n"
    f"Content-Length: {len(response_body_bytes)}\r\n"
    f"X-ElQuePregunta: {nombre}\r\n"
    "\r\n"
)
response = (status_line + headers).encode() + response_body_bytes
```

### Prueba con curl

```bash
curl -i http://localhost:8000
```

Debe aparecer al menos la siguiente línea:

```text
X-ElQuePregunta: Juan Perez
```

---

## Paso 5: usar un archivo JSON como configuración

La siguiente mejora consiste en leer un archivo `.json` para obtener datos de configuración en vez de dejarlos fijos dentro del código.

Esto será útil más adelante, porque el proxy tendrá reglas como:

- sitios prohibidos,
- palabras a reemplazar,
- nombre del usuario,
- o instrucciones de filtrado.
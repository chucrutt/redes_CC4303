import json
import socket

IP_VM = "127.0.0.1" # Localhost temporalmente, cambiar a la IP de la VM si es necesario
PORT = 8000
# El mensaje puede ser mayor que este valor: recv_http_message lo acumula.
BUFFER_SIZE = 64

"""
Formato de petición HTTP:

GET / HTTP/1.1
Host: www.example.com
Content-Type: text/html; charset=utf-8
User-Agent: Mosaic/1.0
Cookie: name=value; name2=value2

Formato de respuesta HTTP:

HTTP/1.1 200 OK
Server: nginx/1.17.0
Date: Mon, 31 Aug 2026 17:02:41 GMT
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
"""


def parse_HTTP_message(http_message: bytes):
    """Parseamos el mensaje HTTP recibido y lo retornamos en un diccionario para acceder facilmente a sus headers y el contenido del body"""
    # HTTP usa \r\n para separar lineas y \r\n\r\n para separar el header del body.
    head_separator = b"\r\n\r\n"
    header_separator = b"\r\n"

    # Dividimos el mensaje en cabecera y contenido.
    if head_separator in http_message:
        head, body = http_message.split(head_separator, 1)
    elif b"\n\n" in http_message:
        head, body = http_message.split(b"\n\n", 1)
    else:
        head, body = http_message, b""

    # Convertimos la cabecera a texto para poder procesarla facilmente.
    head_text = head.decode()
    lines = head_text.split(header_separator.decode()) if header_separator.decode() in head_text else head_text.split("\n")

    # La primera linea es el start line (GET / HTTP/1.1 o HTTP/1.1 200 OK).
    if not lines or not lines[0].strip():
        raise ValueError("Mensaje HTTP vacío o sin start line")

    start_line = lines[0].strip()
    headers = {}

    # Leemos los headers uno por uno: "Clave: valor".
    for line in lines[1:]:
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()

    # Si la primera linea empieza con HTTP/ significa que es una respuesta.
    if start_line.startswith("HTTP/"):
        parts = start_line.split()
        version = parts[0] if len(parts) > 0 else ""
        status = parts[1] if len(parts) > 1 else ""
        reason = " ".join(parts[2:]) if len(parts) > 2 else ""

        return {
            "type": "response",
            "start_line": start_line,
            "version": version,
            "status": status,
            "reason": reason,
            "headers": headers,
            "body": body,
        }

    # Si no, es un request y la linea tiene formato: METHOD PATH VERSION.
    parts = start_line.split()
    method = parts[0] if len(parts) > 0 else ""
    path = parts[1] if len(parts) > 1 else ""
    version = parts[2] if len(parts) > 2 else ""

    return {
        "type": "request",
        "start_line": start_line,
        "method": method,
        "path": path,
        "version": version,
        "headers": headers,
        "body": body,
    }


def create_HTTP_message(parsed_message):
    """Recibe el diccionario entregado por parse_HTTP_message y lo convierte en un mensaje HTTP en bytes"""
    # Aceptamos tanto peticiones HTTP como respuestas HTTP.
    # La diferencia esta en el start line:
    #   request  -> METHOD PATH VERSION
    #   response -> VERSION STATUS REASON
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
        # Si no viene 'type', asumimos que es una respuesta por compatibilidad.
        start_line = (
            f"{parsed_message.get('version', '')} "
            f"{parsed_message.get('status', '')} "
            f"{parsed_message.get('reason', '')}"
        ).strip()

    # Armamos la cabecera con cada header en formato "Clave: Valor".
    header_lines = []
    for key, value in headers.items():
        header_lines.append(f"{key}: {value}")

    # Primero va el start line, luego los headers y luego una linea en blanco.
    http_message = start_line + "\r\n" + "\r\n".join(header_lines) + "\r\n\r\n"

    # Si el body existe, se agrega al final del mensaje.
    if body:
        if isinstance(body, bytes):
            http_message += body.decode()
        else:
            http_message += str(body)

    return http_message.encode()


def recv_http_message(conn, buff_size=BUFFER_SIZE):
    """Verifica que se haya recibido el mensaje HTTP completo"""
    # 1) Leemos fragmentos hasta encontrar el fin del HEAD.
    #    El HEAD termina con la secuencia HTTP \r\n\r\n.
    is_head_complete = False
    recv_message = b""
    full_message = b""
    head_separator = b"\r\n\r\n"

    while not is_head_complete:
        recv_message = conn.recv(buff_size)
        if not recv_message:
            return b""

        full_message += recv_message
        if head_separator in full_message:
            is_head_complete = True

    # 2) Parseamos la cabecera para obtener los headers.
    head_dictionary = parse_HTTP_message(full_message)

    # 3) Content-Length indica cuantos bytes tiene el BODY.
    #    El body puede haber comenzado en el mismo fragmento que cerro el HEAD.
    content_length = 0
    if "Content-Length" in head_dictionary["headers"]:
        try:
            content_length = int(head_dictionary["headers"]["Content-Length"])
        except ValueError:
            content_length = 0

    # Calculamos cuánto del body ya llego.
    header_end = full_message.find(head_separator) + len(head_separator)
    body_received = len(full_message) - header_end

    # 4) Seguimos leyendo hasta completar el BODY indicado por Content-Length.
    while body_received < content_length:
        recv_message = conn.recv(buff_size)
        if not recv_message:
            break

        full_message += recv_message
        body_received = len(full_message) - header_end

    # 5) Retornamos el mensaje completo, con HEAD + BODY.
    return full_message


def is_domain_blocked(host, path, blocked):
    """Indica si el host o la combinacion host/path esta bloqueada."""
    host = host.lower().split(":", 1)[0]
    path = path.lower()

    # curl envia al proxy una URL absoluta; extraemos solo su path.
    if path.startswith("http://") or path.startswith("https://"):
        path_start = path.find("/", path.find("://") + 3)
        path = path[path_start:] if path_start != -1 else "/"

    requested_resource = host + path

    for blocked_resource in blocked:
        blocked_resource = str(blocked_resource).lower()
        if "/" in blocked_resource:
            if requested_resource == blocked_resource:
                return True
        elif host == blocked_resource or host.endswith("." + blocked_resource):
            return True

    return False


def add_user_header(request, user_name):
    """Agrega el header del usuario antes de reenviar una request permitida."""
    head_separator = b"\r\n\r\n"
    user_header = f"X-ElQuePregunta: {user_name}".encode()

    # Insertamos el nuevo header antes de la linea en blanco que termina la cabecera.
    head_end = request.find(head_separator)
    if head_end == -1:
        return request

    return request[:head_end] + b"\r\n" + user_header + request[head_end:]


def replace_forbidden_words(response, forbidden_words):
    """Reemplaza palabras del body y actualiza Content-Length."""
    parsed_response = parse_HTTP_message(response)

    try:
        body = parsed_response["body"].decode()
    except UnicodeDecodeError:
        return response

    for replacement in forbidden_words:
        if not isinstance(replacement, dict):
            continue
        for original, new_value in replacement.items():
            body = body.replace(str(original), str(new_value))

    parsed_response["body"] = body.encode()
    parsed_response["headers"]["Content-Length"] = str(len(parsed_response["body"]))
    return create_HTTP_message(parsed_response)


def build_blocked_response():
    """Construye la respuesta 403 que muestra una imagen local."""
    body = (
        "<!DOCTYPE html>\n"
        "<html lang='es'>\n"
        "<head><meta charset='UTF-8'><title>Acceso bloqueado</title></head>\n"
        "<body>\n"
        "<h1>Acceso bloqueado</h1>\n"
        "<p>Este dominio no esta permitido.</p>\n"
        "<img src='/blocked_image.svg' alt='Acceso bloqueado'>\n"
        "</body>\n"
        "</html>\n"
    ).encode()

    response = {
        "type": "response",
        "version": "HTTP/1.1",
        "status": "403",
        "reason": "Forbidden",
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Length": str(len(body)),
            "Connection": "close",
        },
        "body": body,
    }

    return create_HTTP_message(response)


def build_image_response():
    """Lee y entrega la imagen local solicitada por el navegador."""
    body = b""
    image_paths = ["blocked_image.svg", "actividades/blocked_image.svg"]

    for image_path in image_paths:
        try:
            with open(image_path, "rb") as image_file:
                body = image_file.read()
            break
        except FileNotFoundError:
            continue

    response = {
        "type": "response",
        "version": "HTTP/1.1",
        "status": "200" if body else "404",
        "reason": "OK" if body else "Not Found",
        "headers": {
            "Content-Type": "image/svg+xml",
            "Content-Length": str(len(body)),
            "Connection": "close",
        },
        "body": body,
    }

    return create_HTTP_message(response)


def get_target_server(request):
    """Extrae el host y el puerto al que debe ir el proxy."""
    parsed_request = parse_HTTP_message(request)
    host_header = parsed_request.get("headers", {}).get("Host", "localhost")

    if ":" in host_header:
        host, port = host_header.rsplit(":", 1)
        return host, int(port)

    return host_header, 80


def forward_http_message(request, host, port=80):
    """Reenvia el request tal como llega al servidor upstream y devuelve la respuesta sin modificar."""
    upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    upstream.connect((host, port))
    upstream.sendall(request)

    response = b""
    head_separator = b"\r\n\r\n"
    header_end = -1
    content_length = None

    while True:
        message = upstream.recv(BUFFER_SIZE)
        if not message:
            break
        response += message

        # Si conocemos Content-Length, no esperamos a que el servidor cierre
        # una conexión keep-alive: basta con recibir todo el body.
        if header_end == -1 and head_separator in response:
            header_end = response.find(head_separator) + len(head_separator)
            parsed_response = parse_HTTP_message(response)
            content_length_header = parsed_response["headers"].get("Content-Length")
            if content_length_header is not None:
                try:
                    content_length = int(content_length_header)
                except ValueError:
                    content_length = None

        if content_length is not None and header_end != -1:
            body_received = len(response) - header_end
            if body_received >= content_length:
                break

    upstream.close()
    return response


def build_response(name):
    """Crea una respuesta HTTP válida para enviar al cliente."""
    if not name:
        name = "desconocid@"

    body = (
        "<!DOCTYPE html>\n"
        "<html lang='es'>\n"
        "<head>\n"
        "    <meta charset='UTF-8'>\n"
        "    <title>CC4303</title>\n"
        "</head>\n"
        "<body>\n"
        f"    <h1>Hola {name}</h1>\n"
        "</body>\n"
        "</html>\n"
    )
    body_bytes = body.encode()

    response = {
        "type": "response",
        "version": "HTTP/1.1",
        "status": "200",
        "reason": "OK",
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Length": str(len(body_bytes)),
            "Connection": "close",
            "X-ElQuePregunta": name,
        },
        "body": body_bytes,
    }

    return create_HTTP_message(response)


def main():
    # Cargamos la configuración desde config.json.
    with open("config.json", "r") as file:
        config = json.load(file)

    user_name = config["user"]
    blocked = config["blocked"]
    forbidden_words = config["forbidden_words"]

    # Creamos socket orientado a conexión (TCP)
    print(f"Nombre del usuario: {user_name}")
    print("Creando socket TCP - Servidor")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket_address = (IP_VM, PORT)
    server.bind(server_socket_address)
    server.listen(5)
    print(f"Servidor escuchando en {IP_VM}:{PORT}")

    # Espramos y aceptamos conexion
    while True:
        # Creamos un nuevo socket de conexion para el cliente
        conn, addr = server.accept()
        print(f"Conexión recibida desde {addr}")

        # Recibimos el mensaje HTTP del cliente
        message = recv_http_message(conn)

        # Si el mensaje es vacío lo ignoramos
        if not message:
            conn.close()
            continue

        # El navegador solicita esta imagen después de recibir el HTML 403.
        parsed_message = parse_HTTP_message(message)
        if parsed_message.get("path") == "/blocked_image.svg":
            conn.sendall(build_image_response())
            conn.close()
            continue

        # Primero revisamos el dominio antes de abrir el socket hacia el servidor real.
        target_host, target_port = get_target_server(message)
        if is_domain_blocked(target_host, parsed_message.get("path", ""), blocked):
            print(f"Dominio bloqueado: {target_host}")
            conn.sendall(build_blocked_response())
            conn.close()
            continue

        # Si el dominio esta permitido, agregamos el header antes de reenviar.
        message = add_user_header(message, user_name)
        print(f"Proxy reenvia la request a {target_host}:{target_port}")
        upstream_response = forward_http_message(message, target_host, target_port)
        upstream_response = replace_forbidden_words(upstream_response, forbidden_words)
        conn.sendall(upstream_response)
        conn.close()


if __name__ == "__main__":
    main()

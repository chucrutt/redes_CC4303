import socket
import struct
from collections import Counter, deque


IP_VM = "127.0.0.1"
PORT = 8000
DNS_PORT = 53
root_ip = "198.41.0.4"
BUFFER_SIZE = 65535
SOCKET_TIMEOUT = 5
DEBUG = True
CACHE_WINDOW_SIZE = 20
CACHE_SIZE = 3
query_history = deque(maxlen=CACHE_WINDOW_SIZE)
dns_cache = {}
TYPE_NAMES = {
    1: "A",
    2: "NS",
    5: "CNAME",
    6: "SOA",
    12: "PTR",
    15: "MX",
    28: "AAAA",
}

# _read_name(message: bytes, offset: int) -> tuple[str, int]
def _read_name(message, offset):
    """Lee un nombre DNS y devuelve el nombre y el offset siguiente."""
    labels = []
    next_offset = offset
    jumped = False
    visited_offsets = set()

    while True:
        if offset >= len(message):
            raise ValueError("El nombre DNS termina fuera del mensaje")

        length = message[offset]
        if length == 0:
            if not jumped:
                next_offset = offset + 1
            break

        # Los dos bits superiores indican un puntero a otro nombre del mensaje.
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(message):
                raise ValueError("Puntero DNS incompleto")
            pointer = ((length & 0x3F) << 8) | message[offset + 1]
            if pointer in visited_offsets:
                raise ValueError("Punteros DNS circulares")
            visited_offsets.add(pointer)
            if not jumped:
                next_offset = offset + 2
                jumped = True
            offset = pointer
            continue

        if length & 0xC0:
            raise ValueError("Etiqueta DNS inválida")
        start = offset + 1
        end = start + length
        if end > len(message):
            raise ValueError("La etiqueta DNS termina fuera del mensaje")
        labels.append(message[start:end].decode("ascii"))
        offset = end

    return ".".join(labels) + ".", next_offset

# _parse_record_data(message: bytes, data_offset: int, data_length: int, record_type: int) -> str | dict
def _parse_record_data(message, data_offset, data_length, record_type):
    """Interpreta el RDATA de un registro DNS segun su tipo."""
    data_end = data_offset + data_length
    if data_end > len(message):
        raise ValueError("Los datos del RR terminan fuera del mensaje")

    if record_type in (2, 5, 12):
        data, _ = _read_name(message, data_offset)
        return data
    if record_type == 1 and data_length == 4:
        return socket.inet_ntoa(message[data_offset:data_end])
    if record_type == 28 and data_length == 16:
        return socket.inet_ntop(socket.AF_INET6, message[data_offset:data_end])
    if record_type == 15 and data_length >= 3:
        preference = struct.unpack("!H", message[data_offset:data_offset + 2])[0]
        exchange, _ = _read_name(message, data_offset + 2)
        return {"preference": preference, "exchange": exchange}
    return message[data_offset:data_end].hex()

# _parse_records(message: bytes, offset: int, count: int) -> tuple[list[dict], int]
def _parse_records(message, offset, count):
    """Parsea una cantidad de registros DNS consecutivos."""
    records = []
    for _ in range(count):
        name, offset = _read_name(message, offset)
        if offset + 10 > len(message):
            raise ValueError("Header de RR incompleto")
        record_type, record_class, ttl, data_length = struct.unpack(
            "!HHIH", message[offset:offset + 10]
        )
        offset += 10
        data = _parse_record_data(message, offset, data_length, record_type)
        offset += data_length
        records.append(
            {
                "name": name,
                "type": TYPE_NAMES.get(record_type, record_type),
                "class": record_class,
                "ttl": ttl,
                "data": data,
            }
        )
    return records, offset

# parse_dns_message(message: bytes) -> dict
def parse_dns_message(message):
    """Parsea un mensaje DNS y devuelve sus campos relevantes."""
    if len(message) < 12:
        raise ValueError("El mensaje DNS debe contener al menos 12 bytes")

    _, _, qdcount, ancount, nscount, arcount = struct.unpack(
        "!6H", message[:12]
    )
    offset = 12
    qname = None
    for question_index in range(qdcount):
        current_qname, offset = _read_name(message, offset)
        if offset + 4 > len(message):
            raise ValueError("Question incompleta")
        offset += 4
        if question_index == 0:
            qname = current_qname

    answer, offset = _parse_records(message, offset, ancount)
    authority, offset = _parse_records(message, offset, nscount)
    additional, _ = _parse_records(message, offset, arcount)

    return {
        "qname": qname,
        "ancount": ancount,
        "nscount": nscount,
        "arcount": arcount,
        "answer": answer,
        "authority": authority,
        "additional": additional,
    }

# _encode_qname(domain: str) -> bytes
def _encode_qname(domain):
    """Codifica un dominio usando el formato QNAME de DNS."""
    labels = domain.rstrip(".").split(".")
    encoded = bytearray()
    for label in labels:
        label_bytes = label.encode("ascii")
        if not 0 < len(label_bytes) <= 63:
            raise ValueError("Etiqueta DNS inválida")
        encoded.append(len(label_bytes))
        encoded.extend(label_bytes)
    encoded.append(0)
    return bytes(encoded)

# _make_a_query(domain: str) -> bytes
def _make_a_query(domain):
    """Construye una consulta DNS para obtener el registro A."""
    header = struct.pack("!6H", 0, 0, 1, 0, 0, 0)
    question = _encode_qname(domain) + struct.pack("!HH", 1, 1)
    return header + question

# _send_dns_query(message: bytes, ip_addr: str) -> bytes
def _send_dns_query(message, ip_addr):
    """Envia una consulta DNS por UDP y espera su respuesta."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as dns_socket:
        dns_socket.settimeout(SOCKET_TIMEOUT)
        dns_socket.sendto(message, (ip_addr, DNS_PORT))
        response, _ = dns_socket.recvfrom(BUFFER_SIZE)
    return response

# _first_record(records: list[dict], record_type: str) -> dict | None
def _first_record(records, record_type):
    """Busca el primer registro de un tipo dentro de una lista."""
    return next(
        (record for record in records if record["type"] == record_type),
        None,
    )

# _update_cache_domains(domain: str) -> None
def _update_cache_domains(domain):
    """Actualiza la ventana de consultas y conserva el top tres del cache."""
    query_history.append(domain)
    domain_counts = Counter(query_history)
    most_frequent = {
        domain_name
        for domain_name, _ in sorted(
            domain_counts.items(), key=lambda item: (-item[1], item[0])
        )[:CACHE_SIZE]
    }
    # El caché solo conserva dominios que siguen entre los tres más frecuentes.
    for cached_domain in list(dns_cache):
        if cached_domain not in most_frequent:
            del dns_cache[cached_domain]

# _make_cached_response(query_message: bytes, domain: str, ip_addr: str) -> bytes
def _make_cached_response(query_message, domain, ip_addr):
    """Construye una respuesta DNS con la direccion IPv4 del cache."""
    try:
        answer_data = socket.inet_aton(ip_addr)
    except OSError:
        return b""

    query_flags = struct.unpack("!H", query_message[2:4])[0]
    response_flags = 0x8400 | (query_flags & 0x0100)
    header = struct.pack("!6H", query_message[0] << 8 | query_message[1], response_flags, 1, 1, 0, 0)
    question = _encode_qname(domain) + struct.pack("!HH", 1, 1)
    answer = b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 300, 4) + answer_data
    return header + question + answer

# _resolver(mensaje_consulta: bytes, ip_addr: str, name_server_name: str) -> bytes
def _resolver(mensaje_consulta, ip_addr, name_server_name):
    """Resuelve una consulta siguiendo la delegacion DNS actual."""
    try:
        query = parse_dns_message(mensaje_consulta)
    except ValueError:
        return b""

    if DEBUG:
        print(
            f"(debug) Consultando '{query['qname']}' a "
            f"'{name_server_name}' con dirección IP '{ip_addr}'"
        )

    try:
        mensaje_respuesta = _send_dns_query(mensaje_consulta, ip_addr)
        parsed_response = parse_dns_message(mensaje_respuesta)
    except (OSError, ValueError):
        return b""

    # Una respuesta A termina este salto y se devuelve completa al cliente.
    if _first_record(parsed_response["answer"], "A") is not None:
        return mensaje_respuesta

    name_server = _first_record(parsed_response["authority"], "NS")
    if name_server is None:
        return b""

    # El glue A permite saltar directamente al NS sin resolver su nombre.
    address_record = _first_record(parsed_response["additional"], "A")
    if address_record is None:
        try:
            # Sin glue, se resuelve la IP del NS comenzando nuevamente en la raíz.
            name_server_query = _make_a_query(name_server["data"])
            name_server_response = _resolver(name_server_query, root_ip, ".")
            parsed_name_server = parse_dns_message(name_server_response)
            address_record = _first_record(parsed_name_server["answer"], "A")
        except (OSError, ValueError):
            return b""

    if address_record is None:
        return b""
    return _resolver(mensaje_consulta, address_record["data"], name_server["data"])

# resolver(mensaje_consulta: bytes, ip_addr: str = root_ip) -> bytes
def resolver(mensaje_consulta: bytes, ip_addr=root_ip) -> bytes:
    """Inicia la resolucion iterativa desde el servidor DNS indicado."""
    name_server_name = "." if ip_addr == root_ip else "desconocido"
    return _resolver(mensaje_consulta, ip_addr, name_server_name)

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((IP_VM, PORT))

    print(f"Resolver escuchando en {IP_VM}:{PORT}")
    while True:
        message, client_address = server_socket.recvfrom(BUFFER_SIZE)
        try:
            query = parse_dns_message(message)
        except ValueError:
            continue

        domain = query["qname"]
        # Cada consulta afecta la ventana de frecuencia antes de buscar el caché.
        _update_cache_domains(domain)
        cached_ip = dns_cache.get(domain)
        if cached_ip is not None:
            if DEBUG:
                print(
                    f"(debug) Caché hit para '{domain}': "
                    f"usando IP '{cached_ip}'"
                )
            response = _make_cached_response(message, domain, cached_ip)
        else:
            if DEBUG:
                print(f"(debug) Caché miss para '{domain}'")
            response = resolver(message)
            if response:
                try:
                    parsed_response = parse_dns_message(response)
                    address_record = _first_record(
                        parsed_response["answer"], "A"
                    )
                except ValueError:
                    address_record = None
                if address_record is not None:
                    # Solo se cachea la primera IPv4 de una respuesta válida.
                    dns_cache[domain] = address_record["data"]
                    _update_cache_domains(domain)

        if response:
            server_socket.sendto(response, client_address)


if __name__ == "__main__":
    main()

import socket
import sys

# Header IP simplificado en bytes (20 bytes en total):
#   bytes 0-3:   dirección IP de destino (a.b.c.d, un byte por número)
#   bytes 4-5:   puerto de destino (int de 2 bytes)
#   byte 6:      TTL (int de 1 byte, entre 0 y 255)
#   bytes 7-10:  ID (int de 4 bytes)
#   bytes 11-14: offset en bytes (int de 4 bytes)
#   bytes 15-18: tamaño del mensaje en bytes (int de 4 bytes)
#   byte 19:     FLAG (1 si quedan fragmentos después de este, 0 si es el último)
#   bytes 20-:   mensaje
IP_SIZE = 4
PORT_SIZE = 2
TTL_SIZE = 1
ID_SIZE = 4
OFFSET_SIZE = 4
LENGTH_SIZE = 4
FLAG_SIZE = 1
HEADER_SIZE = IP_SIZE + PORT_SIZE + TTL_SIZE + ID_SIZE + OFFSET_SIZE + LENGTH_SIZE + FLAG_SIZE
BUFFER_SIZE = 65535

# Round-robin: para cada área de la red (red, puerto inicial, puerto final) se
# guarda el índice de la próxima ruta que se debe usar.
round_robin_index = {}


def parse_packet(IP_packet):
    """Convierte un paquete IP en bytes a un diccionario."""
    if len(IP_packet) < HEADER_SIZE:
        raise ValueError("El paquete es más corto que el header")
    ip = ".".join(str(number) for number in IP_packet[0:4])
    port = int.from_bytes(IP_packet[4:6], "big")
    ttl = IP_packet[6]
    packet_id = int.from_bytes(IP_packet[7:11], "big")
    offset = int.from_bytes(IP_packet[11:15], "big")
    size = int.from_bytes(IP_packet[15:19], "big")
    flag = IP_packet[19]
    # El mensaje se guarda en bytes: un fragmento puede cortar un carácter UTF-8.
    message = IP_packet[HEADER_SIZE:HEADER_SIZE + size]
    return {
        "ip": ip,
        "port": port,
        "ttl": ttl,
        "id": packet_id,
        "offset": offset,
        "size": size,
        "flag": flag,
        "message": message,
    }


def create_packet(parsed_IP_packet):
    """Convierte un diccionario como el de parse_packet a un paquete IP en bytes."""
    header = bytes(int(number) for number in parsed_IP_packet["ip"].split("."))
    header += parsed_IP_packet["port"].to_bytes(PORT_SIZE, "big")
    header += parsed_IP_packet["ttl"].to_bytes(TTL_SIZE, "big")
    header += parsed_IP_packet["id"].to_bytes(ID_SIZE, "big")
    header += parsed_IP_packet["offset"].to_bytes(OFFSET_SIZE, "big")
    header += parsed_IP_packet["size"].to_bytes(LENGTH_SIZE, "big")
    header += parsed_IP_packet["flag"].to_bytes(FLAG_SIZE, "big")
    return header + parsed_IP_packet["message"]


def packet_to_str(parsed_IP_packet):
    """Representa un paquete en el formato legible IP;puerto;TTL;ID;offset;tamaño;FLAG;mensaje."""
    return "{};{};{};{};{};{};{};{}".format(
        parsed_IP_packet["ip"],
        parsed_IP_packet["port"],
        parsed_IP_packet["ttl"],
        parsed_IP_packet["id"],
        parsed_IP_packet["offset"],
        parsed_IP_packet["size"],
        parsed_IP_packet["flag"],
        parsed_IP_packet["message"].decode(errors="replace"),
    )


def ip_to_int(ip):
    """Convierte una IP a.b.c.d en un entero de 32 bits."""
    a, b, c, d = (int(number) for number in ip.split("."))
    return (a << 24) | (b << 16) | (c << 8) | d


def ip_in_network(ip, network):
    """Indica si la IP pertenece a la red en notación CIDR (por ejemplo 127.0.0.1/24).

    Si la red no indica prefijo, se considera una sola IP (/32).
    """
    if "/" in network:
        network_ip, prefix = network.split("/")
        prefix = int(prefix)
    else:
        network_ip, prefix = network, 32
    # La máscara tiene "prefix" bits en 1 a la izquierda y el resto en 0.
    mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
    return ip_to_int(ip) & mask == ip_to_int(network_ip) & mask


def check_routes(routes_file_name, destination_address):
    """Retorna (next_hop_address, MTU) para llegar a destination_address.

    Las rutas se revisan en orden. La primera línea cuya red y rango de puertos
    contiene al destino define el área de la red; todas las líneas de esa misma
    área son rutas posibles y se alternan con round-robin. Si una línea no
    indica MTU, el enlace no tiene límite (MTU = None). Retorna None si ninguna
    ruta contiene al destino.
    """
    destination_ip, destination_port = destination_address
    area = None
    routes = []

    with open(routes_file_name) as routes_file:
        for line in routes_file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            network, first_port, last_port, next_hop_ip, next_hop_port = fields[:5]
            mtu = int(fields[5]) if len(fields) > 5 else None
            line_area = (network, int(first_port), int(last_port))
            if area is None:
                in_network = ip_in_network(destination_ip, network)
                in_ports = line_area[1] <= destination_port <= line_area[2]
                if in_network and in_ports:
                    area = line_area
            if area is not None and line_area == area:
                routes.append(((next_hop_ip, int(next_hop_port)), mtu))

    if area is None:
        return None

    # Se usa la ruta que toca en esta área y se avanza al siguiente índice.
    index = round_robin_index.get(area, 0) % len(routes)
    round_robin_index[area] = (index + 1) % len(routes)
    return routes[index]


def fragment_IP_packet(IP_packet, MTU):
    """Divide un paquete IP (o un fragmento) en fragmentos de tamaño total <= MTU.

    Retorna una lista con al menos un elemento.
    """
    if MTU is None or len(IP_packet) <= MTU:
        return [IP_packet]
    if MTU <= HEADER_SIZE:
        raise ValueError(f"El MTU {MTU} no deja espacio para datos (header de {HEADER_SIZE} bytes)")

    parsed_IP_packet = parse_packet(IP_packet)
    message = parsed_IP_packet["message"]
    chunk_size = MTU - HEADER_SIZE
    fragments = []
    for start in range(0, len(message), chunk_size):
        chunk = message[start:start + chunk_size]
        is_last = start + chunk_size >= len(message)
        fragment = dict(parsed_IP_packet)
        # El offset es relativo al datagrama original, no al fragmento.
        fragment["offset"] = parsed_IP_packet["offset"] + start
        fragment["size"] = len(chunk)
        # El último trozo conserva el FLAG del paquete que se fragmenta: si
        # este ya era un fragmento intermedio, después siguen otros fragmentos.
        fragment["flag"] = parsed_IP_packet["flag"] if is_last else 1
        fragment["message"] = chunk
        fragments.append(create_packet(fragment))
    return fragments


def reassemble_IP_packet(fragment_list):
    """Re-ensambla un paquete IP a partir de sus fragmentos (en cualquier orden).

    Un paquete sin fragmentar tiene offset 0 y FLAG 0. Retorna None si
    faltan fragmentos.
    """
    fragments = sorted((parse_packet(fragment) for fragment in fragment_list), key=lambda f: f["offset"])

    # El fragmento con FLAG 0 es el último e indica el largo del mensaje original.
    total_size = None
    for fragment in fragments:
        if fragment["flag"] == 0:
            total_size = fragment["offset"] + fragment["size"]
    if total_size is None:
        return None

    message = b""
    for fragment in fragments:
        end = fragment["offset"] + fragment["size"]
        if end <= len(message):
            # Fragmento repetido: sus bytes ya están en el mensaje.
            continue
        if fragment["offset"] > len(message):
            # Falta un fragmento entre lo que ya se tiene y este.
            return None
        message += fragment["message"][len(message) - fragment["offset"]:]
    if len(message) != total_size:
        return None

    packet = dict(fragments[0])
    packet["offset"] = 0
    packet["size"] = total_size
    packet["flag"] = 0
    packet["message"] = message
    return create_packet(packet)


def main():
    if len(sys.argv) != 4:
        print("Uso: python3 router.py router_IP router_puerto router_rutas.txt")
        sys.exit(1)

    router_ip = sys.argv[1]
    router_port = int(sys.argv[2])
    routes_file_name = sys.argv[3]
    router_address = (router_ip, router_port)

    router_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    router_socket.bind(router_address)
    print(f"Router escuchando en {router_address} con la tabla de rutas {routes_file_name}", flush=True)

    # Fragmentos recibidos que van dirigidos a este router, agrupados por ID.
    received_fragments = {}

    while True:
        IP_packet, _ = router_socket.recvfrom(BUFFER_SIZE)
        try:
            parsed_IP_packet = parse_packet(IP_packet)
        except ValueError:
            continue
        packet_str = packet_to_str(parsed_IP_packet)
        destination_address = (parsed_IP_packet["ip"], parsed_IP_packet["port"])

        if parsed_IP_packet["ttl"] <= 0:
            print(f"Se recibió paquete {packet_str} con TTL 0", flush=True)
            continue

        if destination_address == router_address:
            packet_id = parsed_IP_packet["id"]
            received_fragments.setdefault(packet_id, []).append(IP_packet)
            reassembled = reassemble_IP_packet(received_fragments[packet_id])
            if reassembled is not None:
                del received_fragments[packet_id]
                print(parse_packet(reassembled)["message"].decode(errors="replace"), flush=True)
            continue

        route = check_routes(routes_file_name, destination_address)
        if route is None:
            print(f"No hay rutas hacia {destination_address} para paquete {packet_str}", flush=True)
            continue
        next_hop, mtu = route

        # El TTL disminuye en 1 antes de hacer forward.
        parsed_IP_packet["ttl"] -= 1
        IP_packet = create_packet(parsed_IP_packet)
        print(
            f"redirigiendo paquete {packet_to_str(parsed_IP_packet)} con destino final "
            f"{destination_address} desde {router_address} hacia {next_hop}",
            flush=True,
        )
        try:
            fragments = fragment_IP_packet(IP_packet, mtu)
        except ValueError as error:
            print(f"No se puede enviar paquete {packet_str}: {error}", flush=True)
            continue
        if len(fragments) > 1:
            print(f"  fragmentado en {len(fragments)} fragmentos para el enlace con MTU {mtu}:", flush=True)
            for fragment in fragments:
                print(f"    {packet_to_str(parse_packet(fragment))}", flush=True)
        for fragment in fragments:
            router_socket.sendto(fragment, next_hop)


if __name__ == "__main__":
    main()

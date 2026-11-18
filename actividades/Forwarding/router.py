import socket
import sys

# Header IP simplificado en bytes:
#   bytes 0-3: dirección IP de destino (a.b.c.d, un byte por número)
#   bytes 4-5: puerto de destino (int de 2 bytes)
#   byte 6:    TTL (int de 1 byte, entre 0 y 255)
#   bytes 7-:  mensaje
IP_SIZE = 4
PORT_SIZE = 2
TTL_SIZE = 1
HEADER_SIZE = IP_SIZE + PORT_SIZE + TTL_SIZE
BUFFER_SIZE = 65535

# Round-robin: para cada área de la red (red, puerto inicial, puerto final) se
# guarda el índice de la próxima ruta que se debe usar.
round_robin_index = {}


def parse_packet(IP_packet):
    """Convierte un paquete IP en bytes a un diccionario."""
    if len(IP_packet) < HEADER_SIZE:
        raise ValueError("El paquete es más corto que el header")
    ip = ".".join(str(number) for number in IP_packet[0:IP_SIZE])
    port = int.from_bytes(IP_packet[IP_SIZE:IP_SIZE + PORT_SIZE], "big")
    ttl = IP_packet[IP_SIZE + PORT_SIZE]
    message = IP_packet[HEADER_SIZE:].decode()
    return {"ip": ip, "port": port, "ttl": ttl, "message": message}


def create_packet(parsed_IP_packet):
    """Convierte un diccionario como el de parse_packet a un paquete IP en bytes."""
    ip_bytes = bytes(int(number) for number in parsed_IP_packet["ip"].split("."))
    port_bytes = parsed_IP_packet["port"].to_bytes(PORT_SIZE, "big")
    ttl_bytes = parsed_IP_packet["ttl"].to_bytes(TTL_SIZE, "big")
    return ip_bytes + port_bytes + ttl_bytes + parsed_IP_packet["message"].encode()


def packet_to_str(parsed_IP_packet):
    """Representa un paquete en el formato legible IP;puerto;TTL;mensaje."""
    return "{};{};{};{}".format(
        parsed_IP_packet["ip"],
        parsed_IP_packet["port"],
        parsed_IP_packet["ttl"],
        parsed_IP_packet["message"],
    )


def ip_to_int(ip):
    """Convierte una IP a.b.c.d en un entero de 32 bits."""
    a, b, c, d = (int(number) for number in ip.split("."))
    return (a << 24) | (b << 16) | (c << 8) | d


def ip_in_network(ip, network):
    """Indica si la IP pertenece a la red en notación CIDR (por ejemplo 127.0.0.1/24)."""
    network_ip, prefix = network.split("/")
    prefix = int(prefix)
    # La máscara tiene "prefix" bits en 1 a la izquierda y el resto en 0.
    mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
    return ip_to_int(ip) & mask == ip_to_int(network_ip) & mask


def check_routes(routes_file_name, destination_address):
    """Retorna el par (next_hop_IP, next_hop_puerto) para llegar a destination_address.

    Las rutas se revisan en orden. La primera línea cuya red y rango de puertos
    contiene al destino define el área de la red; todas las líneas de esa misma
    área son rutas posibles y se alternan con round-robin. Retorna None si
    ninguna ruta contiene al destino.
    """
    destination_ip, destination_port = destination_address
    area = None
    gateways = []

    with open(routes_file_name) as routes_file:
        for line in routes_file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            network, first_port, last_port, next_hop_ip, next_hop_port = line.split()
            line_area = (network, int(first_port), int(last_port))
            if area is None:
                in_network = ip_in_network(destination_ip, network)
                in_ports = line_area[1] <= destination_port <= line_area[2]
                if in_network and in_ports:
                    area = line_area
            if area is not None and line_area == area:
                gateways.append((next_hop_ip, int(next_hop_port)))

    if area is None:
        return None

    # Se usa la ruta que toca en esta área y se avanza al siguiente índice.
    index = round_robin_index.get(area, 0) % len(gateways)
    round_robin_index[area] = (index + 1) % len(gateways)
    return gateways[index]


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
            print(parsed_IP_packet["message"], flush=True)
            continue

        next_hop = check_routes(routes_file_name, destination_address)
        if next_hop is None:
            print(f"No hay rutas hacia {destination_address} para paquete {packet_str}", flush=True)
            continue

        # El TTL disminuye en 1 antes de hacer forward.
        parsed_IP_packet["ttl"] -= 1
        print(
            f"redirigiendo paquete {packet_to_str(parsed_IP_packet)} con destino final "
            f"{destination_address} desde {router_address} hacia {next_hop}",
            flush=True,
        )
        router_socket.sendto(create_packet(parsed_IP_packet), next_hop)


if __name__ == "__main__":
    main()

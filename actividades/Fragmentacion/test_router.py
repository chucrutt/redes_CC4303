import router

# Paso 1: parse_packet y create_packet con el nuevo header.
# Paquete 127.0.0.1;8885;10;347;0;5;0;hola! escrito a mano byte por byte.
IP_packet_v1 = (
    bytes([127, 0, 0, 1])           # IP
    + bytes([0x22, 0xB5])           # puerto 8885
    + bytes([10])                   # TTL
    + bytes([0, 0, 0x01, 0x5B])     # ID 347
    + bytes([0, 0, 0, 0])           # offset 0
    + bytes([0, 0, 0, 5])           # tamaño 5
    + bytes([0])                    # FLAG 0
    + "hola!".encode()
)
parsed_IP_packet = router.parse_packet(IP_packet_v1)
IP_packet_v2 = router.create_packet(parsed_IP_packet)
print("Header de", router.HEADER_SIZE, "bytes")
print("parse_packet:", parsed_IP_packet)
print("IP_packet_v1 == IP_packet_v2 ? {}".format(IP_packet_v1 == IP_packet_v2))

# Paso 2: check_routes retorna la ruta y su MTU.
print()
print("check_routes con MTU:")
for routes_file_name, destination in (
    ("rutas/rutas_R1_v3_mtu.txt", ("127.0.0.1", 8885)),
    ("rutas/rutas_R2_v3_mtu.txt", ("127.0.0.1", 8885)),
    ("rutas/rutas_R2_v3_mtu.txt", ("127.0.0.1", 8885)),
    ("rutas/rutas_R5_v3_mtu.txt", ("127.0.0.1", 8881)),
    ("rutas/rutas_R5_v3_mtu.txt", ("127.0.0.1", 8881)),
    ("rutas/rutas_R1_v3_mtu.txt", ("127.0.0.1", 9000)),
):
    print(f"  {routes_file_name} {destination} -> {router.check_routes(routes_file_name, destination)}")


def make_packet(packet_id, message):
    message = message.encode()
    return router.create_packet({
        "ip": "127.0.0.1", "port": 8885, "ttl": 10, "id": packet_id,
        "offset": 0, "size": len(message), "flag": 0, "message": message,
    })


# Paso 3: fragment_IP_packet.
print()
packet_150 = make_packet(1, "x" * (150 - router.HEADER_SIZE))
print("Paquete de", len(packet_150), "bytes:")
for mtu in (200, 150, 100, 50):
    fragments = router.fragment_IP_packet(packet_150, mtu)
    sizes = [len(fragment) for fragment in fragments]
    print(f"  MTU {mtu}: {len(fragments)} fragmento(s), tamaños {sizes}")
print("Fragmentos con MTU 100:")
for fragment in router.fragment_IP_packet(packet_150, 100):
    print("  ", router.packet_to_str(router.parse_packet(fragment))[:60])
print("Re-fragmentar el primer fragmento (MTU 100) para un enlace con MTU 50:")
first_fragment = router.fragment_IP_packet(packet_150, 100)[0]
for fragment in router.fragment_IP_packet(first_fragment, 50):
    print("  ", router.packet_to_str(router.parse_packet(fragment))[:60])

# Paso 5: fragmentar y re-ensamblar.
print()
message = "Este mensaje es bastante largo para que deba fragmentarse varias veces en el camino."
IP_packet_v1 = make_packet(2, message)
for mtu in (100, 50, 30):
    fragment_list = router.fragment_IP_packet(IP_packet_v1, mtu)
    IP_packet_v2 = router.reassemble_IP_packet(fragment_list)
    print(f"MTU {mtu} ({len(fragment_list)} fragmentos): IP_packet_v1 = IP_packet_v2 ? {IP_packet_v1 == IP_packet_v2}")

fragment_list = router.fragment_IP_packet(IP_packet_v1, 50)
second_level = [piece for fragment in fragment_list for piece in router.fragment_IP_packet(fragment, 30)]
print(f"Re-fragmentado de MTU 50 a 30 ({len(second_level)} fragmentos), en desorden: "
      f"{router.reassemble_IP_packet(second_level[::-1]) == IP_packet_v1}")
print("Lista incompleta (falta un fragmento):", router.reassemble_IP_packet(fragment_list[:1] + fragment_list[2:]))
print("Solo el primer fragmento:", router.reassemble_IP_packet(fragment_list[:1]))
print("Paquete sin fragmentar:", router.reassemble_IP_packet([IP_packet_v1]) == IP_packet_v1)

import router

# Test parte II, paso 1: parse_packet y create_packet con TTL.
# Paquete 127.0.0.1;8881;10;hola escrito a mano byte por byte.
IP_packet_v1 = bytes([127, 0, 0, 1]) + bytes([0x22, 0xB1]) + bytes([10]) + "hola".encode()
parsed_IP_packet = router.parse_packet(IP_packet_v1)
IP_packet_v2 = router.create_packet(parsed_IP_packet)
print("parse_packet:", parsed_IP_packet)
print("IP_packet_v1 == IP_packet_v2 ? {}".format(IP_packet_v1 == IP_packet_v2))

# Test paso 6: check_routes con las tablas del ejemplo 2 (R1 - R2 - R3).
print()
print("check_routes ejemplo 2:")
tests = [
    ("rutas/rutas_R1_v2.txt", ("127.0.0.1", 8882)),
    ("rutas/rutas_R1_v2.txt", ("127.0.0.1", 8883)),
    ("rutas/rutas_R2_v2.txt", ("127.0.0.1", 8881)),
    ("rutas/rutas_R2_v2.txt", ("127.0.0.1", 8883)),
    ("rutas/rutas_R3_v2.txt", ("127.0.0.1", 8881)),
    ("rutas/rutas_R1_v2.txt", ("127.0.0.1", 8884)),
    ("rutas/rutas_R2_v2.txt", ("127.0.0.1", 8884)),
]
for routes_file_name, destination in tests:
    print(f"  {routes_file_name} {destination} -> {router.check_routes(routes_file_name, destination)}")

# Test paso 8: round-robin en R2 de la red de 5 routers.
print()
print("Round-robin en R2 (rutas_R2_v3.txt) hacia R5:")
print("  ", [router.check_routes("rutas/rutas_R2_v3.txt", ("127.0.0.1", 8885)) for _ in range(4)])

# Test paso 8, test 2: round-robin independiente por área en R2 de la red de 7 routers.
print("Round-robin en R2 (rutas_R2_v4.txt), alternando destinos R5 y R1:")
for destination_port in (8885, 8881, 8885, 8881, 8885, 8881):
    next_hop = router.check_routes("rutas/rutas_R2_v4.txt", ("127.0.0.1", destination_port))
    print(f"   destino {destination_port} -> {next_hop}")

# Test paso 9: ruta default.
print("Ruta default (rutas_R1_v5.txt):")
for destination in (("127.0.0.1", 8885), ("127.0.0.1", 9000), ("8.8.8.8", 53)):
    print(f"   {destination} -> {router.check_routes('rutas/rutas_R1_v5.txt', destination)}")

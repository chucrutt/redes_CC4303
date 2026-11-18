import socket
import sys
import time

import router

# Paso 7: envía a un router los fragmentos de dos paquetes con distinto ID,
# en orden, en desorden e intercalando los ID, directamente al router destino.
# Uso: python3 test_reensamblaje.py IP_router puerto_router
destination = (sys.argv[1], int(sys.argv[2]))
MTU = 40


def make_packet(packet_id, message):
    message = message.encode()
    return router.create_packet({
        "ip": destination[0], "port": destination[1], "ttl": 10, "id": packet_id,
        "offset": 0, "size": len(message), "flag": 0, "message": message,
    })


sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send(fragments, label):
    print(f"{label}: " + ", ".join(
        f"(ID {router.parse_packet(f)['id']}, offset {router.parse_packet(f)['offset']})" for f in fragments))
    for fragment in fragments:
        sender_socket.sendto(fragment, destination)
        time.sleep(0.05)
    time.sleep(0.3)


for round_number, (id_a, id_b) in enumerate(((10, 20), (11, 21), (12, 22)), start=1):
    fragments_a = router.fragment_IP_packet(make_packet(id_a, f"Primer mensaje (ronda {round_number}), dividido en fragmentos."), MTU)
    fragments_b = router.fragment_IP_packet(make_packet(id_b, f"Segundo mensaje (ronda {round_number}), con otro ID."), MTU)
    if round_number == 1:
        send(fragments_a, "En orden, ID A")
        send(fragments_b, "En orden, ID B")
    elif round_number == 2:
        send(fragments_a[::-1], "En desorden, ID A")
        send([fragments_b[1], fragments_b[0]] + fragments_b[2:][::-1], "En desorden, ID B")
    else:
        interleaved = []
        for index in range(max(len(fragments_a), len(fragments_b))):
            interleaved += fragments_b[index:index + 1] + fragments_a[::-1][index:index + 1]
        send(interleaved, "Intercalando ID A y B")
sender_socket.close()

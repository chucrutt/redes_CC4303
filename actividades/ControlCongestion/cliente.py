import sys
import time

import SocketTCP

if len(sys.argv) < 3:
    print("Uso: python3 cliente.py <host> <puerto> [stop_and_wait|go_back_n] [--sin-cc] < archivo", file=sys.stderr)
    sys.exit(1)

address = (sys.argv[1], int(sys.argv[2]))
mode = sys.argv[3] if len(sys.argv) > 3 else "go_back_n"
# El archivo llega por entrada estándar; se carga completo en memoria.
message = sys.stdin.read().encode()

client_socketTCP = SocketTCP.SocketTCP()
client_socketTCP.set_congestion_control("--sin-cc" not in sys.argv)
client_socketTCP.connect(address)

start = time.time()
client_socketTCP.send(message, mode=mode)
elapsed = time.time() - start
segments_sent = client_socketTCP.number_of_sent_segments

client_socketTCP.close()
print(f"STATS cliente: tiempo_envio={elapsed:.3f}s segmentos_enviados={segments_sent}", file=sys.stderr)

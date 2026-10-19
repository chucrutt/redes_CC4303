import sys

import SocketTCP

BUFF_SIZE = 1024 * 1024

if len(sys.argv) < 3:
    print("Uso: python3 servidor.py <host> <puerto> [stop_and_wait|go_back_n]", file=sys.stderr)
    sys.exit(1)

address = (sys.argv[1], int(sys.argv[2]))
mode = sys.argv[3] if len(sys.argv) > 3 else "go_back_n"
server_socketTCP = SocketTCP.SocketTCP()
server_socketTCP.bind(address)
print(f"Servidor escuchando en {server_socketTCP.local_address}", file=sys.stderr)

connection_socketTCP, new_address = server_socketTCP.accept()
print(f"Conexión establecida en {new_address}", file=sys.stderr)

message = connection_socketTCP.recv(BUFF_SIZE, mode=mode)
# Los ACK se cuentan antes del cierre para medir solo la transferencia.
segments_sent = connection_socketTCP.number_of_sent_segments
connection_socketTCP.recv_close()
print(f"STATS servidor: segmentos_enviados={segments_sent}", file=sys.stderr)

# El contenido del archivo va a salida estándar y el debug a stderr.
print(message.decode(), end="")

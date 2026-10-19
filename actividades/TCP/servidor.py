import sys

import SocketTCP

BUFF_SIZE = 1024 * 1024

if len(sys.argv) != 3:
    print("Uso: python3 servidor.py <host> <puerto>", file=sys.stderr)
    sys.exit(1)

address = (sys.argv[1], int(sys.argv[2]))
server_socketTCP = SocketTCP.SocketTCP()
server_socketTCP.bind(address)
print(f"Servidor escuchando en {server_socketTCP.local_address}", file=sys.stderr)

connection_socketTCP, new_address = server_socketTCP.accept()
print(f"Conexión establecida en {new_address}", file=sys.stderr)

message = connection_socketTCP.recv(BUFF_SIZE)
connection_socketTCP.recv_close()

print(message.decode(), end="")

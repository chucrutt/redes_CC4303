import sys

import SocketTCP

if len(sys.argv) != 3:
    print("Uso: python3 cliente.py <host> <puerto> < archivo", file=sys.stderr)
    sys.exit(1)

address = (sys.argv[1], int(sys.argv[2]))
message = sys.stdin.read().encode()

client_socketTCP = SocketTCP.SocketTCP()
client_socketTCP.connect(address)
client_socketTCP.send(message)
client_socketTCP.close()

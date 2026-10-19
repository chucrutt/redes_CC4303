import sys

import SocketTCP

MODE = sys.argv[1] if len(sys.argv) > 1 else "go_back_n"

address = ("localhost", int(sys.argv[2]) if len(sys.argv) > 2 else 8000)

client_socketTCP = SocketTCP.SocketTCP()
client_socketTCP.connect(address)

# test 1
message = "Mensje de len=16".encode()
client_socketTCP.send(message, mode=MODE)

# test 2
message = "Mensaje de largo 19".encode()
client_socketTCP.send(message, mode=MODE)

# test 3
message = "Mensaje de largo 19".encode()
client_socketTCP.send(message, mode=MODE)

# test 4
message = ("Primera mitad de 21 b" "Segunda mitad de 21 b").encode()
client_socketTCP.send(message, mode=MODE)

# cierre
client_socketTCP.close()
print("Conexión cerrada")

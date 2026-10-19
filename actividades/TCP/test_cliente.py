import SocketTCP

address = ("localhost", 8000)

client_socketTCP = SocketTCP.SocketTCP()
client_socketTCP.connect(address)

# test 1
message = "Mensje de len=16".encode()
client_socketTCP.send(message)

# test 2
message = "Mensaje de largo 19".encode()
client_socketTCP.send(message)

# test 3
message = "Mensaje de largo 19".encode()
client_socketTCP.send(message)

# test 4
message = ("Primera mitad de 21 b" "Segunda mitad de 21 b").encode()
client_socketTCP.send(message)

# cierre
client_socketTCP.close()
print("Conexión cerrada")

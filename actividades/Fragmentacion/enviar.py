import socket
import sys

from router import create_packet

# Envía un paquete IP a la dirección (IP_envío, puerto_envío).
# Uso: python3 enviar.py "IP;puerto;TTL;ID;offset;tamaño;FLAG" "mensaje" IP_envío puerto_envío
# Ejemplo: python3 enviar.py "127.0.0.1;8885;10;347;0;5;0" "hola!" 127.0.0.1 8881
# El primer argumento va entre comillas porque en bash ";" separa comandos.
if len(sys.argv) != 5:
    print('Uso: python3 enviar.py "IP;puerto;TTL;ID;offset;tamaño;FLAG" "mensaje" IP_envío puerto_envío')
    sys.exit(1)

ip, port, ttl, packet_id, offset, size, flag = sys.argv[1].split(";")
message = sys.argv[2].encode()
send_address = (sys.argv[3], int(sys.argv[4]))

if int(size) != len(message):
    print(f"Aviso: el tamaño indicado ({size}) no coincide con el del mensaje ({len(message)}), se usa {len(message)}")

packet = create_packet({
    "ip": ip,
    "port": int(port),
    "ttl": int(ttl),
    "id": int(packet_id),
    "offset": int(offset),
    "size": len(message),
    "flag": int(flag),
    "message": message,
})
sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sender_socket.sendto(packet, send_address)
sender_socket.close()

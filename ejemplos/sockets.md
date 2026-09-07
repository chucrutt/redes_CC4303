# Intro a Sockets

## Socket no orientado a conexión:
Los sockets no orientados a conexión envían mensajes o datos a una dirección de destino sin preocuparse ni verificar si los datos llegaron completos o si es que llegaron. Este tipo de socket queda definido por la 2-tupla (direccion_origen, puerto_origen), pues estos datos bastan para distinguir entre sockets no orientados a conexión.

## Socket orientado a conexión: 
Los sockets orientados a conexión establecen un canal de comunicación entre el origen y el destino. Este canal de comunicación les permite asegurarse de que los datos enviados lleguen completos a su destino. Una vez este canal se establece, los sockets solo se comunicarán entre ellos. Luego, este tipo de sockets quedan definidos por la 4-tupla (direccion_origen, puerto_origen, direccion_destino, puerto_destino).

## Cómo usar sockets en python?
Para usar sockets en Python necesitamos importar la clase socket, la cual se encuentra disponible sin necesidad de descargar librerías extra. Para crear un nuevo socket debemos especificar la familia de direcciones que va a usar el socket para establecer la comunicación y el tipo de comunicación que usará el socket. Para efectos de este curso utilizaremos AF_INET como familia de direcciones pues esta corresponde a direcciones del tipo (IPv4, puerto). En cuanto al tipo de comunicación nos van a interesar las siguientes:

``` python
 import socket

 # con la siguiente línea creamos un socket orientado a conexión
 tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

 # con la siguiente línea creamos un socket NO orientado a conexión
 udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
```

Podemos observar que lo único que cambia al crear un socket orientado a conexión y uno no orientado a conexión es el segundo parámetro que recibe socket para crear un nuevo objeto socket. Esto ocurre porque existe una única clase que se encarga de manejar ambos tipos de socket en Python. Aún así hay métodos que solo son útiles para un tipo de socket y no para el otro.

## Códigos de ejemplo

### Cliente orientado a conexión

``` python

import socket

print('Creando socket - Cliente')

# armamos el socket, los parámetros que recibe el socket indican el tipo de conexión
# socket.SOCK_STREAM = socket orientado a conexión
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Como es un socket orientado a conexión debemos conectarlo a la dirección acordada
address = ('localhost', 5000)
client_socket.connect(address)

# Definimos un mensaje y una secuencia indicando el fin del mensaje (parte de nuestro protocolo inventado)
message = "Hola, este es un mensaje de prueba"
end_of_message = "\n"

# Armamos el mensaje final a enviar y lo pasamos a bytes con encode
send_message = (message + end_of_message).encode()

# enviamos el mensaje a través del socket
print(f"... Mandando el mensaje: {send_message.decode()}")
client_socket.send(send_message)

print("... Mensaje enviado")

# Finalmente esperamos una respuesta
# Para ello debemos definir el tamaño del buffer de recepción
buffer_size = 1024
message = client_socket.recv(buffer_size)

# Pasamos el mensaje de bytes a string
decoded_message = message.decode()

print(f' -> Respuesta del servidor: {decoded_message}')

# cerramos la conexión
client_socket.close()

```

### Servidor orientado a conexión

``` python

import socket


# esta función se encarga de recibir el mensaje completo desde el cliente
# en caso de que el mensaje sea más grande que el tamaño del buffer 'buff_size', esta función va esperar a que
# llegue el resto. Para saber si el mensaje ya llegó por completo, se busca el caracter de fin de mensaje (parte de nuestro protocolo inventado)

def receive_full_message(connection_socket, buff_size, end_sequence):

    # recibimos la primera parte del mensaje
    recv_message = connection_socket.recv(buff_size)
    full_message = recv_message

    # verificamos si llegó el mensaje completo o si aún faltan partes del mensaje
    is_end_of_message = contains_end_of_message(full_message.decode(), end_sequence)

    # entramos a un while para recibir el resto y seguimos esperando información
    # mientras el buffer no contenga secuencia de fin de mensaje
    while not is_end_of_message:
        # recibimos un nuevo trozo del mensaje
        recv_message = connection_socket.recv(buff_size)

        # lo añadimos al mensaje "completo"
        full_message += recv_message

        # verificamos si es la última parte del mensaje
        is_end_of_message = contains_end_of_message(full_message.decode(), end_sequence)

    # removemos la secuencia de fin de mensaje, esto entrega un mensaje en string
    full_message = remove_end_of_message(full_message.decode(), end_sequence)

    # finalmente retornamos el mensaje
    return full_message


def contains_end_of_message(message, end_sequence):
    return message.endswith(end_sequence)


def remove_end_of_message(full_message, end_sequence):
    index = full_message.rfind(end_sequence)
    return full_message[:index]

if __name__ == "__main__":
    # definimos el tamaño del buffer de recepción y la secuencia de fin de mensaje
    buff_size = 4
    end_of_message = "\n"
    server_socket_address = ('localhost', 5000)

    print('Creando socket - Servidor')
    # armamos el socket
    # los parámetros que recibe el socket indican el tipo de conexión
    # socket.SOCK_STREAM = socket orientado a conexión
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # le indicamos al server socket que debe atender peticiones en la dirección address
    # para ello usamos bind
    server_socket.bind(server_socket_address)

    # luego con listen (función de sockets de python) le decimos que puede
    # tener hasta 3 peticiones de conexión encoladas
    # si recibiera una 4ta petición de conexión la va a rechazar
    server_socket.listen(3)

    # nos quedamos esperando a que llegue una petición de conexión
    print('... Esperando clientes')
    while True:
        # cuando llega una petición de conexión la aceptamos
        # y se crea un nuevo socket que se comunicará con el cliente
        new_socket, new_socket_address = server_socket.accept()

        # luego recibimos el mensaje usando la función que programamos
        # esta función entrega el mensaje en string (no en bytes) y sin el end_of_message
        recv_message = receive_full_message(new_socket, buff_size, end_of_message)

        print(f' -> Se ha recibido el siguiente mensaje: {recv_message}')

        # respondemos indicando que recibimos el mensaje
        response_message = f"Se ha sido recibido con éxito el mensaje: {recv_message}"

        # el mensaje debe pasarse a bytes antes de ser enviado, para ello usamos encode
        new_socket.send(response_message.encode())

        # cerramos la conexión
        # notar que la dirección que se imprime indica un número de puerto distinto al 5000
        new_socket.close()
        print(f"conexión con {new_socket_address} ha sido cerrada")

        # seguimos esperando por si llegan otras conexiones
```

### Socket no orientado a conexión

``` python

import socket

# Socket no orientado a conexión
dgram_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Recibir mensajes. Este método nos entrega el mensaje junto a la dirección de origen del mensaje
message, address = dgram_socket.recvfrom(bufsize)

# Enviar mensajes. Este método debe especificar la dirección a la que se va a enviar el mensaje
dgram_socket.sendto(message, address)
```
# ¿Cómo saber a qué Name Server hablarle? Métodos de direccionamiento y enrutamiento

Los servidores DNS suelen tener varias copias en distintas partes del planeta para disminuir los tiempos de respuesta. La idea es que un cliente intentando resolver un nombre de dominio siempre pueda preguntarle al servidor más cercano. Este tipo de comunicación es bastante diferente al que utiliza el protocolo HTTP, el cual se conecta punto a punto, comunicando a un cliente y un servidor particulares. Esto ocurre porque HTTP utiliza unicast para manejar los flujos de tráfico, mientras DNS utiliza anycast.
Tipos de flujos de tráfico

Lo principales tipos de flujo de tráfico son unicast, multicast, broadcast y anycast. Estos no son protocolos sino métodos de direccionamiento y enrutamiento.

Unicast: En unicast el tráfico es punto a punto, es decir, solo dos puntos se están comunicando entre sí. Si hay únicamente dos puntos que se pueden comunicar a la vez unicast es una buena alternativa, sin embargo en casos con más de dos opciones o participantes este sufre problemas de escalabilidad. El protocolo HTTP tiene un flujo de tráfico unicast.

Multicast: Hablamos de que el tráfico es de tipo multicast cuando el flujo de información puede llegar a varios puntos simultáneamente, es decir, llega a un grupo de receptores dentro de la red. Un ejemplo de uso de multicast corresponde a la televisión IP donde la transmisión es enviada a aquellos clientes que estén suscritos.

Broadcast: En el caso de broadcast tenemos que todos los elementos de la red reciben la información siendo enviada, independiente de si están interesados en dicha información o si les es útil. Esto puede generar envíos de datos innecesarios dentro de la red pues los receptores no interesados recibirán y procesarán la información solo para descubrir que no les interesa. Un ejemplo de uso de broadcast ocurre cuando un computador se conecta a una red, por ejemplo Wi-Fi, y necesita que se le asigne una dirección dentro de la red. Dado que el computados no sabe cuál es el dispositivo encargado de asignar las direcciones, este tendrá que comunicarle a toda la red que necesita que se le asigne una dirección.

Anycast: En anycast se tiene que una misma dirección puede ser accesada a través de múltiples dispositivos, de los cuales se elige uno punto para comunicarse con el cliente. Típicamente anycast utiliza criterios de distancia en red para elegir el dispositivo más cercano al cliente para responder. Este tipo de flujo de tráfico es utilizado por los servidores DNS para disminuir el tiempo de respuesta. 

# Registros DNS

Los Resource Records o Registros de Recursos (RRs) corresponden a las unidades de información con la que trabajan los DNS para resolver nombres de dominio. Cada registro contiene el nombre de dominio asociado al RR, tipo, clase, tiempo de vida o Time To Live (TTL), los datos contenidos en el RR y el largo de dichos datos.

Dentro de los servidores DNS, los RRs se encuentran organizados en Zone Files los cuales contienen los RRs asociados a la zona DNS manejada por el servidor. Aquí, una zona DNS corresponde a una porción dentro de la jerarquía del árbol de dominio (usualmente un nodo).

## Campos de un RR

Cada RR contiene la información necesaria para ser utilizada dentro de DNS. Esta información se encuentra almacenada en los siguientes campos:

NAME: Nombre de dominio asociado.

TYPE: Tipo de registro. Indica el tipo de información contenido en el registro, el cual puede ser una dirección IPv4, un servidor de nombre, una redirección, etc.

CLASS: Clase del registro. Para DNS sobre Internet la clase corresponde a IN (Internet, cod. dec. 1), sin embargo existen otras clases como HS (Hesiod, cod. dec. 4) y CH (Chaos, cod.dec. 3).

TTL (Time to Live): Número de segundos durante los cuales el registro es válido.
RDLENGTH (Record Data Length): Largo del segmento RDATA.

RDATA (Record Data): Contiene la información asociada al tipo de registro. Por ejemplo, para un registro tipo A (address), el RDATA contiene la dirección IPv4 asociada al nombre de dominio.

## Tipos de registro DNS

En esta sección vamos listar algunos de los posibles tipos que puede tener un RRs. Esta es una lista acotada y existen muchos otros tipos de registro.

A (Address): Usualmente utilizado para mapear direcciones IP de 32 bits (IPv4) a nombres de dominio. Su código en decimal es 1.

AAAA (IPv6 Adress): Similar al tipo de registro A, es usualmente utiliizado para mapear direcciones IP de 128 bits (IPv6) a nombres de dominio. Su código en decimal es 28.

CNAME (Canonical Name): Indica un alias que apunta a otro nombre de dominio o subdominio, pero nunca a una dirección IP. Su código en decimal es 5.

NS (Name Server): Indica qué servidores de nombre son autoritativos para un dominio o subdominio. Su código en decimal es 2.

SOA (Start Of [a zone of] Authority): Especifica información autoritativa sobre una zona DNS. Dentro de esta información se encuentra especificado cuál es el servidor de nombre primario. Su código en decimal es 6.

# DNS programado con sockets (Headers DNS)

DNS está documentado en el "Request for Comments" (cómo se hacen los estándares de Internet en IETF) RFC 1035. Todo lo señalado acá está en ese documento.

Todos los mensajes de DNS utilizan el mismo formato:

+---------------------+
|        Header       |
+---------------------+
|       Question      | dominio a consultar
+---------------------+
|        Answer       | Resource Records (RRs) respondiendo la pregunta que haremos
+---------------------+
|      Authority      | RRs que corresponden a una respuesta autorizada
+---------------------+
|      Additional     | RRs con información adicional
+---------------------+

Debemos notar que el campo Additional no siempre se llena. Un ejemplo en que dicho campo es utilizado es en el caso en que la raíz que sabe cual es el NS de .cl y, aprovechando que lo conoce, nos dice cuál es su nombre y su IP. Sin embargo, como es un servidor que está bajo .cl esta no es una respuesta "autorizada".

En los campos vemos que hay un área de Question y uno de Answer. Estos campos serán utilizados por los mensajes de pregunta o Query y de respuesta o Response, los cuales llenarán distintas partes del mensaje. En particular, las preguntas o Queries son las encargadas de llenar el Header.
Query: Header

El encabezado o Header de un mensaje DNS tiene el formato que vemos a continuación. Aquí cada columna que se ve en el diagrama corresponde a un bit, por lo tanto cada línea del Header puede contener 16 bits.

 0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                      ID                       |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|QR|   Opcode  |AA|TC|RD|RA|   Z    |   RCODE   |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    QDCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    ANCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    NSCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    ARCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+

Esta división en 16 columnas está hecha para facilitar la lectura humana del encabezado, sin embargo lo que se observa finalmente es una cadena de 16 bits por cada una de las líneas del diagrama. Los bits que no son relevantes a la consulta (pero sí para la respuesta) se inicializan con el valor 0.  La descripción de todos los campos está disponible en RFC1035 Section 4.1.1.  Los campos que a nosotros nos servirán son los siguientes:

    ID: Corresponde a un número identificador aleatorio de 16 bits. Este mismo ID es usado en la respuesta para saber a qué pregunta corresponde. En esta actividad usaremos como ID el valor 0.

    QR:  Este bit señala si el mensaje es una pregunta (valor 0) o una respuesta (valor 1).

    OPcode: El OPcode corresponde a 4 bits que especifican el tipo de consulta. Nosotros sólo haremos consultas estándar, por lo que nuestro OPcode será 0000.

    TC: Este bit nos señala si el mensaje está truncado (i.e es parte de un mensaje más largo). Nosotros enviaremos mensajes cortos, por lo que nuestro TC será 0.

    RD: Este bit le indica al receptor si queremos usar o no recursión. Aquí recursión se refiere a que le pasamos la responsabilidad al receptor para que haga todas las consultas pertinentes.  En nuestra actividad RD será 0.

    QDCOUNT: Corresponde a un unsigned integer de 16 bits que señala el número de consultas estamos enviando (se puede enviar más de una). En nuestro caso usaremos una (1) por lo que QDCOUNT tomará el valor 1.

Como cada línea del encabezado contiene exactamente 16 bits, podemos expresar sus valores usando hexadecimal para facilitar su lectura.  Considerando los valores que acabamos de discutir nuestro encabezado en hexadecimal se vería como:

+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    00 00                      | -> ID
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    00 00                      | -> QR|   Opcode  |AA|TC|RD|RA|   Z    |   RCODE  
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    00 01                      | -> QDCOUNT
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    00 00                      | -> ANCOUNT
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    00 00                      | -> NSCOUNT
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    00 00                      | -> ARCOUNT
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+

Query data: Question

La sección de consulta o Question contiene uno o más bloques donde cada bloque tiene el siguiente formato:

 0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                                               |
/                     QNAME                     /
/                                               /
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                     QTYPE                     |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                     QCLASS                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+

    QNAME: Este campo contiene el dominio por el que pregunto, por ejemplo: example.com. (noten que siempre lleva un punto al final).  Este campo puede tener las líneas que sean necesarias para escribir el dominio. En cada línea caben 16 bits, por lo tanto en cada línea podemos escribir 2 bytes. Luego para codificar el dominio vamos a seguir los siguientes pasos:
        Pasamos cada palabra del dominio a minúsculas. En este caso quedaría como example.com.
        Agrupamos las cadenas de caracteres omitiendo los puntos y calculamos su largo. En este caso obtenemos las cadenas 'example' de largo 7 y 'com' de largo 3.
        Pasamos cada letra o símbolo a su valor de byte en ASCII. Para el ejemplo tenemos que los valores ASCII en bytes de las letras son: a = 01100001, c = 01100011, e = 01100101, l = 01101100, m = 01101101, p = 01110000, o = 01101111 , x = 01111000 .
        Escribimos cada cadena en líneas de 2 bytes indicando primero el  largo de la cadena de símbolos. Repetimos esto para todas las cadenas. En este ejemplo usaremos una librería para pasar de hexadecimal a binario, por lo que escribiremos cada elemento en hexadecimal. Para nuestro ejemplo obtenemos:

        +---+---+    +----------+----------+
        | 7 | e | -> | 00000111 | 01100101 | = 07 65 (hex)
        +---+---+    +----------+----------+
        | x | a | -> | 01111000 | 01100001 | = 78 61 (hex)
        +---+---+    +----------+----------+
        | m | p | -> | 01101101 | 01110000 | = 6D 70 (hex)
        +---+---+    +----------+----------+
        | l | e | -> | 01101100 | 01100101 | = 6C 65 (hex)
        +---+---+    +----------+----------+
        | 3 | c | -> | 00000011 | 01100011 | = 03 63 (hex)
        +---+---+    +----------+----------+
        | o | m | -> | 01101111 | 0110110  | = 6F 6D (hex)
        +---+---+    +----------+----------+

        Finalmente indicamos el final de QNAME con el byte 0 (hexadecimal 00).

    QTYPE: Indica el tipo de consulta que estamos haciendo. Si consultamos direcciones IP el valor  de QTYPE es 1. Si quisiéramos preguntar sólo por el NameServer (NS) entonces QTYPE es 2.

    QCLASS: Corresponde a la clase que buscamos. Generalmente la clase es tipo IN por lo que su valor será 1.

En nuestro caso, pasando todo nuevamente a hexadecimal, obtendríamos la siguiente sección de consulta :

+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                     07 65                     | -> QNAME
/                     78 61                     /
/                     6D 70                     /
/                     6C 65                     /
/                     03 63                     /
/                     6F 6D                     /
/                     00                        /
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                     00 01                     | -> QTYPE
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                     00 01                     | -> QCLASS
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+

¿Cómo enviamos el mensaje?  - Código

Al igual que los servidores HTTP, los servidores DNS ocupan un puerto reservado, en este caso este corresponde al puerto 53. Para enviar nuestro mensaje DNS podemos usar directamente hexadecimal, o utilizar librerías como dnslib. A continuación veremos un ejemplo usando la librería binascii de Python para pasar de hexadecimal a binario y viceversa, y un ejemplo utilizando dnslib.

    Usando la librería binascii, nuestro código quedaría algo así:
    
    ``` python
    import binascii
    import socket


    def send_dns_message(address, port):
        # Encabezado con ID 0 (00 00 en hexadecimal), preguntamos por example.com
        header = "00 00 00 00 00 01 00 00 00 00 00 00 ".replace(" ","")
        data = "07 65 78 61 6D 70 6C 65 03 63 6F 6D 00 00 01 00 01".replace(" ","")
        message = header + data
        # Lo escribimos así para que se entendiera, lo concatenamos para hacer la cadena de hexadecimales
        server_address = (address, port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # usamos binascii para pasar el mensaje al formato apropiado
            binascii_msg = binascii.unhexlify(message)
            # y lo enviamos
            sock.sendto(binascii_msg, server_address)
            # En data quedará la respuesta a nuestra consulta
            data, _ = sock.recvfrom(4096)
        finally:
            sock.close()
        # Ojo que los datos de la respuesta van en hexadecimal, no en binario
        return binascii.hexlify(data).decode("utf-8")

    print (send_dns_message("1.1.1.1", 53))
    ```

    La misma función usando la librería dnslib (disponible via pip3 install dnslib o descargable desde https://github.com/paulc/dnslib) sería así:

    ``` python
    import socket
    from dnslib import DNSRecord

    def send_dns_message(address, port):
        # Acá ya no tenemos que crear el encabezado porque dnslib lo hace por nosotros, por default pregunta por el tipo A
        qname = "example.com"
        q = DNSRecord.question(qname)
        server_address = (address, port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # lo enviamos, hacemos cast a bytes de lo que resulte de la función pack() sobre el mensaje
            sock.sendto(bytes(q.pack()), server_address)
            # En data quedará la respuesta a nuestra consulta
            data, _ = sock.recvfrom(4096)
            # le pedimos a dnslib que haga el trabajo de parsing por nosotros 
            d = DNSRecord.parse(data)
        finally:
            sock.close()
        # Ojo que los datos de la respuesta van en en una estructura de datos
        return d

    # Es dnslib la que sabe como se debe imprimir la estructura, usa el mismo formato que dig, los datos NO vienen en un string gigante, sino en una estructura de datos
    print (send_dns_message("1.1.1.1", 53))
    ```
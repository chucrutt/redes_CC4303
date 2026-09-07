# Transacciones HTTP

El protocolo HTTP es un protocolo orientado a transacciones, donde cada transacción consta de 4 etapas:

- Abrir la conexión
- Request
- Response
- Cerrar la conexión

Al ser orientado a transacciones, HTTP no maneja estados ni recuerda datos sobre la comunicación pues cada transacción constituye una unidad individual e independiente del resto de las transacciones. Es por esto que si se desea mantener datos sobre una conexión en particular es necesario almacenar dicha información dentro de los headers en forma de cookies.

# Mensajes HTTP

HEAD versus BODY

En las siguientes imágenes podemos ver un ejemplo de request  y un ejemplo de response.

    Request:
    request HTTP
    Response:
     response HTTP

Dentro de estos mensajes el HEAD está separado del BODY por un doble salto de línea de tipo \r\n\r\n. De forma similar cada header (cada línea dentro del HEAD) se separa con un salto de línea simple del tipo \r\n. Luego, desde el punto de vista de su código, los mensajes que acabamos de mostrar en realidad se verían de la siguiente forma.

    Request:
    Request con saltos de línea visibles
    Response:
    Response con saltos de línea visibles

HEAD y "start line"

En el HEAD vamos a encontrar varias líneas indicando información necesaria sobre lo que se está enviando en el mensaje HTTP. La primera línea corresponde a la start line, y luego vienen los headers que indican otras informaciones como el tipo de contenido, el largo de contenido, el host, etc. Los headers posteriores a la start line no tienen en un orden fijo.

        Start line:  corresponde a la primera línea dentro del HEAD y su contenido va a cambiar dependiendo de si el mensaje es response o request. En el caso de una request, la start line indica el método, la dirección donde quiero ejecutar el método y la versión de HTTP. De esta forma, una request GET a la raíz del host (/), con versión HTTP 1.1 se ve de la siguiente manera.

        GET / HTTP/1.1


        En el caso de una response, la start line indica la versión de HTTP, el código de estado y un texto asociado al estado. Luego si recibo una response exitosa, con versión HTTP 1.1, voy a recibir la siguiente start line.

         HTTP/1.1 200 OK

        Headers: Los headers indican información respecto al mensaje como el tipo de contenido, el largo del contenido, el navegador en uso, el host, etc. Estos headers no necesariamente vienen ordenados de una forma en particular y cuando una entidad recibe un mensaje HTTP no necesariamente va a hacer uso de todos los headers que recibió. Algo importante que debemos destacar es que es posible añadir headers personalizados. Para evitar que el nombre de un header personalizado choque con un header estándar se solía recomendar usar el prefijo "X-" antes del nombre del header (ej: X-MiHeader), sin embargo esta recomendación fue deprecada hace algunos años.

¿Cómo saber si ya llegó todo el BODY?

De lo anterior podemos ver que es fácil saber dónde se terminan los headers y dónde comienza el área de datos o BODY, basta con buscar el string \r\n\r\n. Sin embargo, en el área de datos no tenemos un marcador igual de evidente. 

Para saber si ya llegó toda la información dentro del área de datos necesitamos mirar el Content-Length. El header Content-Length indica el largo en bytes de los datos que se están enviando, es decir, el largo en bytes del BODY. Luego, una vez hemos recibido el número de bytes indicado por Content-Length sabemos que ya llegaron todos los datos.

De esta manera, si nos llega un mensaje HTTP cuyo Content-Length es 200, pero el tamaño del BODY es de 150 bytes, tendremos que hacer 'receive' nuevamente para recibir los 50 bytes restantes.
¿Siempre voy a recibir texto o html?

Las páginas web que ven en sus navegadores suelen estar compuestas de al menos HTML el cual puede enviarse como texto plano sin problemas. Sin embargo, la mayoría de las páginas web no se compone únicamente de HTML, si no que además requieren de archivos de diseño (CSS), imágenes, etc. Estos recursos también son enviados a través de mensajes HTTP. Para poder distinguir qué tipo de recurso se está enviando en el área de datos del mensaje debemos observar el Content-Type. Veamos algunos ejemplos.

    El mensaje HTTP contiene HTML:

     Content-Type: text/html

    El mensaje HTTP contiene un CSS:

    Content-Type: text/css

    El mensaje contiene una imagen .png:

    Content-Type: image/png

Además de los valores que vemos aquí, Content-Type puede indicar otros tipos de contenidos como .ppt, .json, .odt, etc. 

# Conexiones persistentes

Al usar el protocolo HTTP se utilizan sockets orientados a conexión y estas conexiones pueden o no ser persistentes. Una conexión persistente es aquella que reutiliza un socket de conexión para enviar varios datos entre el origen y el destino, mientras que una conexión no persistente es aquella que se cierra una vez fue utilizada, es decir, cada vez que se desea enviar o recibir datos se debe reestablecer la conexión ¿Por qué nos interesaría evitar reestablecer la conexión constantemente? Porque tanto establecer como cerrar una conexión es costoso en términos del tiempo utilizado.

En HTTP/1.0 es posible manejar el tipo y estado de las conexiones a través del header "connection", utilizando "connection: keep-alive" le indicamos al interlocutor que deseamos mantener viva la conexión para ser reutilizada, mientras que "connection: close" indica que esta debe cerrarse. Debemos notar que si un servidor permite conexiones persistentes, estas se mantendrán abiertas hasta que el cliente cierre la conexión o que la conexión expire por timeout.

En HTTP/1.1 las conexiones son persistentes por default y es necesario enviar de forma explícita un "connection: close" para indicar que la conexión debe cerrarse luego de la transacción. Una diferencia importante de HTTP/1.0 con HTTP/1.1, es que en esta versión el servidor tiene la opción de cerrar conexiones inactivas incluso si no ha recibido "connection: close", mientras que en HTTP/1.0 esta opción no existía.

Una ventaja de utilizar conexiones persistentes en HTTP es que estas permiten enviar todos los assets necesarios para cargar una página web estableciendo la conexión una única vez, ahorrando tiempos de apertura y cierre de conexión lo cual disminuye el tiempo de carga de los recursos. Sin embargo, mantener una conexión persistente también requiere utilizar (y mantener ocupados) más recursos del sistema, lo cual podría significar una desventaja para servidores con mucho tráfico. 
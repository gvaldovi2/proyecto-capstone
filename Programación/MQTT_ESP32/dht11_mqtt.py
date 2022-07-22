'''
 * Envio de datos a NodeRed
 * por:  Gonzalo Valdovinos Chacón
         Julio Cesar Cerecedo Márquez
         Francisco Javier Merino Muñoz
 * Fecha: 26 de junio de 2022
 * Ultima modificacion: 19 de Julio de 2022
 * 
 * Este programa envia y recibe valores a través de MQTT 
 * para que sean recuperados por NodeRed y exista un 
 * protocolo de comunicacion con Raspberry.
 * 
'''

#Bibliotecas
import time
#from simple import MQTTClient
import ubinascii
import machine
import micropython
import network
import esp
esp.osdebug(None)
import gc
gc.collect()
import dht
from machine import Pin
import _thread


#####Del renglon 30 al 237 es el código del MQTTClient
try:
    import usocket as socket
except:
    import socket
import ustruct as struct
from ubinascii import hexlify

class MQTTException(Exception):
    pass

class MQTTClient:

    def __init__(self, client_id, server, port=0, user=None, password=None, keepalive=0,
                 ssl=False, ssl_params={}):
        if port == 0:
            port = 8883 if ssl else 1883
        self.client_id = client_id
        self.sock = None
        self.server = server
        self.port = port
        self.ssl = ssl
        self.ssl_params = ssl_params
        self.pid = 0
        self.cb = None
        self.user = user
        self.pswd = password
        self.keepalive = keepalive
        self.lw_topic = None
        self.lw_msg = None
        self.lw_qos = 0
        self.lw_retain = False

    def _send_str(self, s):
        self.sock.write(struct.pack("!H", len(s)))
        self.sock.write(s)

    def _recv_len(self):
        n = 0
        sh = 0
        while 1:
            b = self.sock.read(1)[0]
            n |= (b & 0x7f) << sh
            if not b & 0x80:
                return n
            sh += 7

    def set_callback(self, f):
        self.cb = f

    def set_last_will(self, topic, msg, retain=False, qos=0):
        assert 0 <= qos <= 2
        assert topic
        self.lw_topic = topic
        self.lw_msg = msg
        self.lw_qos = qos
        self.lw_retain = retain

    def connect(self, clean_session=True):
        self.sock = socket.socket()
        addr = socket.getaddrinfo(self.server, self.port)[0][-1]
        self.sock.connect(addr)
        if self.ssl:
            import ussl
            self.sock = ussl.wrap_socket(self.sock, **self.ssl_params)
        premsg = bytearray(b"\x10\0\0\0\0\0")
        msg = bytearray(b"\x04MQTT\x04\x02\0\0")

        sz = 10 + 2 + len(self.client_id)
        msg[6] = clean_session << 1
        if self.user is not None:
            sz += 2 + len(self.user) + 2 + len(self.pswd)
            msg[6] |= 0xC0
        if self.keepalive:
            assert self.keepalive < 65536
            msg[7] |= self.keepalive >> 8
            msg[8] |= self.keepalive & 0x00FF
        if self.lw_topic:
            sz += 2 + len(self.lw_topic) + 2 + len(self.lw_msg)
            msg[6] |= 0x4 | (self.lw_qos & 0x1) << 3 | (self.lw_qos & 0x2) << 3
            msg[6] |= self.lw_retain << 5

        i = 1
        while sz > 0x7f:
            premsg[i] = (sz & 0x7f) | 0x80
            sz >>= 7
            i += 1
        premsg[i] = sz

        self.sock.write(premsg, i + 2)
        self.sock.write(msg)
        #print(hex(len(msg)), hexlify(msg, ":"))
        self._send_str(self.client_id)
        if self.lw_topic:
            self._send_str(self.lw_topic)
            self._send_str(self.lw_msg)
        if self.user is not None:
            self._send_str(self.user)
            self._send_str(self.pswd)
        resp = self.sock.read(4)
        assert resp[0] == 0x20 and resp[1] == 0x02
        if resp[3] != 0:
            raise MQTTException(resp[3])
        return resp[2] & 1

    def disconnect(self):
        self.sock.write(b"\xe0\0")
        self.sock.close()

    def ping(self):
        self.sock.write(b"\xc0\0")

    def publish(self, topic, msg, retain=False, qos=0):
        pkt = bytearray(b"\x30\0\0\0")
        pkt[0] |= qos << 1 | retain
        sz = 2 + len(topic) + len(msg)
        if qos > 0:
            sz += 2
        assert sz < 2097152
        i = 1
        while sz > 0x7f:
            pkt[i] = (sz & 0x7f) | 0x80
            sz >>= 7
            i += 1
        pkt[i] = sz
        #print(hex(len(pkt)), hexlify(pkt, ":"))
        self.sock.write(pkt, i + 1)
        self._send_str(topic)
        if qos > 0:
            self.pid += 1
            pid = self.pid
            struct.pack_into("!H", pkt, 0, pid)
            self.sock.write(pkt, 2)
        self.sock.write(msg)
        if qos == 1:
            while 1:
                op = self.wait_msg()
                if op == 0x40:
                    sz = self.sock.read(1)
                    assert sz == b"\x02"
                    rcv_pid = self.sock.read(2)
                    rcv_pid = rcv_pid[0] << 8 | rcv_pid[1]
                    if pid == rcv_pid:
                        return
        elif qos == 2:
            assert 0

    def subscribe(self, topic, qos=0):
        assert self.cb is not None, "Subscribe callback is not set"
        pkt = bytearray(b"\x82\0\0\0")
        self.pid += 1
        struct.pack_into("!BH", pkt, 1, 2 + 2 + len(topic) + 1, self.pid)
        #print(hex(len(pkt)), hexlify(pkt, ":"))
        self.sock.write(pkt)
        self._send_str(topic)
        self.sock.write(qos.to_bytes(1, "little"))
        while 1:
            op = self.wait_msg()
            if op == 0x90:
                resp = self.sock.read(4)
                #print(resp)
                assert resp[1] == pkt[2] and resp[2] == pkt[3]
                if resp[3] == 0x80:
                    raise MQTTException(resp[3])
                return

    # Wait for a single incoming MQTT message and process it.
    # Subscribed messages are delivered to a callback previously
    # set by .set_callback() method. Other (internal) MQTT
    # messages processed internally.
    def wait_msg(self):
        res = self.sock.read(1)
        self.sock.setblocking(True)
        if res is None:
            return None
        if res == b"":
            raise OSError(-1)
        if res == b"\xd0":  # PINGRESP
            sz = self.sock.read(1)[0]
            assert sz == 0
            return None
        op = res[0]
        if op & 0xf0 != 0x30:
            return op
        sz = self._recv_len()
        topic_len = self.sock.read(2)
        topic_len = (topic_len[0] << 8) | topic_len[1]
        topic = self.sock.read(topic_len)
        sz -= topic_len + 2
        if op & 6:
            pid = self.sock.read(2)
            pid = pid[0] << 8 | pid[1]
            sz -= 2
        msg = self.sock.read(sz)
        self.cb(topic, msg)
        if op & 6 == 2:
            pkt = bytearray(b"\x40\x02\0\0")
            struct.pack_into("!H", pkt, 2, pid)
            self.sock.write(pkt)
        elif op & 6 == 4:
            assert 0

    # Checks whether a pending message from server is available.
    # If not, returns immediately with None. Otherwise, does
    # the same processing as wait_msg.
    def check_msg(self):
        self.sock.setblocking(False)
        return self.wait_msg()
    

#####Datos para la conexión con el Router#####
ssid = 'TP-Link_A552'
password = '17052726'


######Ip del Servidor donde está corriendo el servidor MQTT####
mqtt_server = '192.168.0.33'

client_id = ubinascii.hexlify(machine.unique_id())

###Nombre del Tópico donde se publicará la Temperatura y la Humedad#####
topic_pub = b'codigoIoT/ProyectoCapstone/Temperatura'

##
topic_sub = b'codigoIoT/ProyectoCapstone/Cams'
#topic_sub = b'codigoIoT/ProyectoCapstone/Cam1'
#topic_sub2 = b'codigoIoT/ProyectoCapstone/Cam2'
cont=0

ultimo_mensaje = 0
intervalo_mensajes = 10

##Configurar los pines de los semáforos
##Pines donde está conectado el Semáforo 1
ledRojoS1pin=12
ledAmarilloS1pin=14
ledVerdeS1pin=27

pinRS1 = Pin(ledRojoS1pin, Pin.OUT)
pinAS1 = Pin(ledAmarilloS1pin, Pin.OUT)
pinVS1 = Pin(ledVerdeS1pin, Pin.OUT)
pinRS1.value(0)
pinAS1.value(0)
pinVS1.value(0)
semaforo1 = 'APAGADO'

##Pines donde está conectado el Semáforo 2
ledRojoS2pin=26
ledAmarilloS2pin=25
ledVerdeS2pin=33

pinRS2 = Pin(ledRojoS2pin, Pin.OUT)
pinAS2 = Pin(ledAmarilloS2pin, Pin.OUT)
pinVS2 = Pin(ledVerdeS2pin, Pin.OUT)
pinRS2.value(0)
pinAS2.value(0)
pinVS2.value(0)
semaforo2 = 'APAGADO'

#Conectar el ESP32 a la red
station = network.WLAN(network.STA_IF)

station.active(True)
station.connect(ssid, password)

while station.isconnected() == False:
  print('.',end='')

print('Conexion exitosa')
print(station.ifconfig())


##Pin donde está conectado el Sensor DHT11##
sensor = dht.DHT11(Pin(13))

#Configurar la función que utilizará el hilo para contar
def cuenta(n,q,name):
    contar=1
    while contar<=n:
        #print('Contar:',contar)
        contar+=1
        q.append(contar)
        print('q:',q)
        time.sleep(1) 

##Es la función que recibe los datos de la IA
def sub_cam(topic, msg):
    print('sub:',(topic, msg))
    msg = msg.decode()
    msg = msg.split(",")
    carrosCam1,carrosCam2 = msg[0],msg[1]
    print('Cam1:',carrosCam1,'Cam2:',carrosCam2)
    tiempoS1 = carrosCam1*3
    global cont,q
    cont+=1
    print('Contador:',cont)
    if carrosCam1>=carrosCam2 :
        #Poner Semáforo1 en Verde            
        if cont==1:
            pinVS2.value(0)
            pinRS2.value(0)
            pinAS2.value(1)
            time.sleep(3)
            #q = []
            #_thread.start_new_thread(cuenta,(tiempoS1,q,'contar1'))
            
        #print('Longitud:',len(q))        
        pinVS1.value(1)
        pinRS1.value(0)
        pinAS1.value(0)
        pinRS2.value(1)
        pinVS2.value(0)
        pinAS2.value(0)
            
    else:
        #Poner Semáforo2 en Verde
        if cont==1:
            pinVS1.value(0)
            pinRS1.value(0)
            pinAS1.value(1)
            time.sleep(3)            
        
        pinVS2.value(1)
        pinRS2.value(0)
        pinAS2.value(0)
        pinRS1.value(1)
        pinVS1.value(0)        
        pinAS1.value(0)
  
 
##Función para conexión con el Servidor MQTT###
def conectar_a_MQTT():
  global client_id, mqtt_server
  #print(client_id)
  client = MQTTClient(client_id, mqtt_server)
  ##
  client.set_callback(sub_cam)
  client.connect()
  ##
  client.subscribe(topic_sub)
  #client.subscribe(topic_sub2)
  
  print('Conectado a %s broker MQTT' % mqtt_server)
  print('Semáforos en Rojo')
  pinRS1.value(1)
  pinRS2.value(1)
  return client

def reconectar():
  print('Fallo de conexion con broker MQTT. Reconectando...')
  time.sleep(10)
  machine.reset()

try:
  client = conectar_a_MQTT()
except OSError as e:
  reconectar()

while True:
    try:
        ##Verifica si hay mensajes publicados en el que se está subscrito
        client.check_msg()
        ##Publica los valores del sensor de Temperatura y humedad
        if (time.time() - ultimo_mensaje) > intervalo_mensajes:
            sensor.measure()
            temperatura = sensor.temperature()
            humedad = sensor.humidity()
            msg = (b'{0:3.1f},{1:3.1f}'.format(temperatura, humedad))
            print('{0:3.1f},{1:3.1f}'.format(temperatura, humedad))            
            client.publish(topic_pub, msg)
            ultimo_mensaje = time.time()
    except OSError as e:
        reconectar()
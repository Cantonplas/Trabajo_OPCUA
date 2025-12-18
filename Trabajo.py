import time
import threading
import json
import socket
import signal
from asyncua.sync import Client, Server


#-----------Clase de datos compartidos entre hilos con threading.Lock-----------#
class SharedData:
    def __init__(self):
        self.lock = threading.Lock()
        self.counter = 0
        self.random = 0.0
        self.senoidal = 0.0

    def update_data(self, counter, random, senoidal):
        with self.lock:
            self.counter = counter
            self.random = random
            self.senoidal = senoidal

    def get_senoidal(self):
        with self.lock:
            return self.senoidal

    def get_udp_data(self):
        with self.lock:
            return {'counter': self.counter, 'random': self.random}

#---------Thread que se conecta a Prosys OPC UA Simulator-------------#

def opcua_client_thread(shared_data, endpoint_url, stop_event):
    client = Client(endpoint_url)
    try:
        client.connect()
        print(f"[Hilo 1] Cliente conectado a Prosys: {endpoint_url}")
        
        root = client.nodes.root        
        node_counter = root.get_child([f"0:Objects", f"3:Simulation", f"3:Counter"])
        node_random = root.get_child([f"0:Objects", f"3:Simulation", f"3:Random"])
        node_senoidal = root.get_child([f"0:Objects", f"3:Simulation", f"3:Senoidal"])

        while not stop_event.is_set():
            val_counter = node_counter.read_value()
            val_random = node_random.read_value()
            val_senoidal = node_senoidal.read_value()

            shared_data.update_data(val_counter, val_random, val_senoidal)
            time.sleep(0.05)

    except Exception as e:
        print(f"[Hilo 1] Error: {e}")
    finally:
        try:
            client.disconnect()
        except:
            pass

#---------Thread que actúa como servidor OPC UA-------------#

def opcua_server_thread(shared_data, ip, port, stop_event):
    server = Server()
    endpoint = f"opc.tcp://{ip}:{port}/trabajo_EOII/server/"
    server.set_endpoint(endpoint)
    
    uri = "http://trabajo.EOII"
    idx = server.register_namespace(uri)
    
    myobj = server.nodes.objects.add_object(idx, "PythonBridge")
    var_senoidal = myobj.add_variable(idx, "Senoidal", 0.0)
    var_senoidal.set_writable()
    
    server.start()
    print(f"[Hilo 2] Servidor OPC UA listo en: {endpoint}")
    
    try:
        while not stop_event.is_set():
            valor_actual = shared_data.get_senoidal()
            var_senoidal.write_value(valor_actual)
            time.sleep(0.1)
    except Exception as e:
        print(f"[Hilo 2] Error: {e}")
        time.sleep(1)
    finally:
        try:
            server.stop()
            time.sleep(1)
        except Exception:
            pass

#---------Thread que actúa como puente UDP-------------#

def udp_bridge_thread(shared_data, target_ip, target_port, stop_event):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"[Hilo 3] Enviando UDP a {target_ip}:{target_port}")
    
    try:
        while not stop_event.is_set():
            data = shared_data.get_udp_data()
            
            json_msg = json.dumps(data)
            
            sock.sendto(json_msg.encode('utf-8'), (target_ip, target_port))
            
            time.sleep(0.05)
            
    except Exception as e:
        print(f"[Hilo 3] Error: {e}")
    finally:
        sock.close()


if __name__ == "__main__":
    #---------Macros para conexiones-------------#
    PROSYS_ENDPOINT = "opc.tcp://Blaze_obeso:53530/OPCUA/SimulationServer"
    
    UDP_IP = "127.0.0.1" 
    TCP_IP = "0.0.0.0"
    UDP_PORT = 9000
    TCP_PORT = 4840
    
    datos = SharedData()
    stop_event = threading.Event()

    # Detener el programa con Contrl + C
    def _handle_signal(signum, frame):
        print(f"Señal recibida ({signum}), deteniendo...")
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    try:
        signal.signal(signal.SIGTERM, _handle_signal)
    except Exception:
        pass

    t1 = threading.Thread(target=opcua_client_thread, args=(datos, PROSYS_ENDPOINT, stop_event), daemon=True)
    t2 = threading.Thread(target=opcua_server_thread, args=(datos, TCP_IP, TCP_PORT, stop_event), daemon=True)
    t3 = threading.Thread(target=udp_bridge_thread, args=(datos, UDP_IP, UDP_PORT, stop_event), daemon=True)
    
    t1.start()
    t2.start()
    t3.start()


#---------Parar el programa-------------#
    try:
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        print("Deteniendo programa...")
        stop_event.set()

    stop_event.set()
    t1.join(timeout=2)
    t2.join(timeout=2)
    t3.join(timeout=2)
    print("Programa detenido...")
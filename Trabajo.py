import time
import threading
from asyncua.sync import Client

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

def opcua_client_thread(shared_data, endpoint_url):
    client = Client(endpoint_url)
    try:
        client.connect()
        print(f"Cliente conectado a: {endpoint_url}")
        
        root = client.nodes.root
        
        node_counter = root.get_child(["0:Objects", "3:Simulation", "3:Counter"])
        node_random = root.get_child(["0:Objects", "3:Simulation", "3:Random"])
        node_senoidal = root.get_child(["0:Objects", "3:Simulation", "3:Senoidal"])

        while True:
            val_counter = node_counter.read_value()
            val_random = node_random.read_value()
            val_senoidal = node_senoidal.read_value()

            shared_data.update_data(val_counter, val_random, val_senoidal)
            
            # print(f"[Cliente] Leido -> Counter: {val_counter} | Random: {val_random:.2f} | Senoidal: {val_senoidal:.2f}")
            
            time.sleep(0.1) 

    except Exception as e:
        print(f"Error en Cliente OPC UA: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    PROSYS_ENDPOINT = "opc.tcp://Blaze_obeso:53530/OPCUA/SimulationServer"
    
    datos_compartidos = SharedData()
    
    hilo_cliente = threading.Thread(target=opcua_client_thread, args=(datos_compartidos, PROSYS_ENDPOINT))
    hilo_cliente.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        hilo_cliente.join()
        print("Deteniendo prueba...")
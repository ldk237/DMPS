import socket
import threading
import json
import os
import sys
import time

# ----------------------------
# CONFIG
# ----------------------------
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 6000

clients = {}   # {ip: socket} côté serveur
next_octet = 2 # DHCP pour IP virtuelles (192.168.1.x)


# ----------------------------
# SERVER PART
# ----------------------------
def allocate_ip():
    """Attribue la prochaine IP libre du pool 192.168.1.x"""
    global next_octet
    ip = f"192.168.1.{next_octet}"
    next_octet += 1
    return ip

def broadcast_file(sender_ip, filename, data):
    """Réplique le fichier à toutes les machines sauf celle qui l'a envoyé"""
    for ip, conn in clients.items():
        if ip != sender_ip:
            msg = {
                "type": "file",
                "from": sender_ip,
                "filename": filename,
                "size": len(data),
                "data": data.decode("latin1", errors="ignore")
            }
            conn.sendall((json.dumps(msg) + "\n").encode())

def handle_client(conn, addr):
    buf = b""
    ip = None
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                msg = json.loads(line.decode())

                if msg["type"] == "register":
                    # DHCP : attribuer IP
                    ip = allocate_ip()
                    clients[ip] = conn
                    print(f"[SERVER] Machine attribuée: {ip}")
                    ack = {"type": "register_ack", "ip": ip}
                    conn.sendall((json.dumps(ack) + "\n").encode())

                elif msg["type"] == "file":
                    print(f"[SERVER] Reçu {msg['filename']} ({msg['size']} o) de {msg['from']}")
                    broadcast_file(msg["from"], msg["filename"], msg["data"].encode("latin1"))
    finally:
        if ip and ip in clients:
            del clients[ip]
        conn.close()
        print(f"[SERVER] Machine {ip} déconnectée")

def run_server():
    print(f"[SERVER] Cloud server écoute sur {SERVER_HOST}:{SERVER_PORT}")
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((SERVER_HOST, SERVER_PORT))
    srv.listen()
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


# ----------------------------
# MACHINE PART
# ----------------------------
class Machine:
    def __init__(self):
        self.sock = socket.create_connection((SERVER_HOST, SERVER_PORT))
        # demander une IP
        self.sock.sendall((json.dumps({"type": "register"}) + "\n").encode())
        ack = self._recv_line()
        self.ip = ack["ip"]
        print(f"[CLIENT] Machine connectée avec IP: {self.ip}")
        threading.Thread(target=self.listen_server, daemon=True).start()

    def _recv_line(self):
        buf = b""
        while True:
            chunk = self.sock.recv(4096)
            if not chunk:
                return None
            buf += chunk
            if b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                return json.loads(line.decode())

    def listen_server(self):
        buf = b""
        while True:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                msg = json.loads(line.decode())
                if msg["type"] == "file":
                    filename = f"copy_{msg['filename']}"
                    data = msg["data"].encode("latin1")
                    with open(filename, "wb") as f:
                        f.write(data)
                    print(f"[{self.ip}] Copie reçue: {filename} ({msg['size']} o)")

    def create_file(self, filename, size):
        data = os.urandom(size)
        with open(filename, "wb") as f:
            f.write(data)
        msg = {
            "type": "file",
            "from": self.ip,
            "filename": filename,
            "size": size,
            "data": data.decode("latin1", errors="ignore")
        }
        self.sock.sendall((json.dumps(msg) + "\n").encode())
        print(f"[{self.ip}] Fichier {filename} ({size} o) créé et envoyé au serveur")

    def read_file(self, filename):
        """Lire le fichier local et l’afficher en hexadécimal"""
        try:
            with open(filename, "rb") as f:
                data = f.read()
            print(f"[{self.ip}] Contenu de {filename} ({len(data)} octets) :")
            print(data.hex(" "))  # affichage hexadécimal
        except FileNotFoundError:
            print(f"[{self.ip}] Erreur: fichier {filename} introuvable")


# ----------------------------
# SHELL INTERACTIF MULTI-MACHINES
# ----------------------------
def cloud_shell(machines: dict):
    current = None
    while True:
        cmd = input("(cloud)> ").strip()
        if cmd.startswith("use"):
            _, ip = cmd.split()
            if ip in machines:
                current = machines[ip]
                print(f"[SHELL] Contrôle basculé sur {ip}")
            else:
                print(f"[SHELL] Machine {ip} inconnue")
        elif cmd.startswith("create"):
            if current:
                _, fname, ssize = cmd.split()
                current.create_file(fname, int(ssize))
            else:
                print("[SHELL] Sélectionne d'abord une machine avec 'use <ip>'")
        elif cmd.startswith("read"):
            if current:
                _, fname = cmd.split()
                current.read_file(fname)
            else:
                print("[SHELL] Sélectionne d'abord une machine avec 'use <ip>'")
        elif cmd == "list":
            print("Machines disponibles:", ", ".join(machines.keys()))
        elif cmd == "exit":
            break
        else:
            print("Commandes: list, use <ip>, create <nom> <taille>, read <nom>, exit")


# ----------------------------
# MAIN: tout en un seul terminal
# ----------------------------
if __name__ == "__main__":
    # lancer le serveur dans un thread
    threading.Thread(target=run_server, daemon=True).start()
    time.sleep(1)

    # démarrer 2 machines automatiquement
    m1 = Machine()
    m2 = Machine()

    # stocker les machines par IP
    machines = {m1.ip: m1, m2.ip: m2}

    print("\nTape 'list' pour voir les machines")
    print("Tape 'use <ip>' pour choisir une machine à contrôler")
    print("Tape 'create <nom> <taille>' pour créer un fichier sur la machine courante")
    print("Tape 'read <nom>' pour lire le contenu d’un fichier sur la machine courante")
    print("Tape 'exit' pour quitter.\n")

    cloud_shell(machines)
import socket
import threading

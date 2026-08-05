import threading
import json
import socket
import time

class Controller(threading.Thread):
    '''
    Listens for frontend commands and dispatches to Channels.
    '''
    def __init__(self, channels, host="0.0.0.0", port=8084):
        super().__init__(daemon=True)
        self.channels = channels
        self.host = host
        self.port = port
        self.stop_flag = threading.Event()

    def handle_command(self, cmd):
        action = cmd["action"]
        if action == "list":
            ret = {}
            for name, ch in self.channels.items():
                if ch.display is None:
                    continue
                ret[name] = [ch.backend.name, ch.can_control, ch.units, ch.display, ch.algorithm]

            ret = json.dumps(ret)
            print(repr(ret))
            return ret

        elif action == "ping":
            return '0'

        ch = self.channels[cmd["channel"]]

        if action == "setpoint":
            ch.set_setpoint(cmd["value"])
            return '0'

        elif action == "manual":
            '''
            for i in range(91):
                volt_out = 9.0 - i*0.1
                ch.set_manual(volt_out)
                time.sleep(1800)
            '''
            ch.set_manual(cmd["value"])
            return '0'

        elif action == "off":
            ch.off()
            return '0'
        
        return '1'

    def run(self):
        with socket.socket() as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen()
            print("[Client] Ready for commands...")

            while not self.stop_flag.is_set():
                try:
                    s.settimeout(0.1)
                    conn, addr = s.accept()
                except socket.timeout:
                    continue

                with conn:
                    #data = conn.recv(1024).decode("ascii")

                    buf = ""
                    while "\n" not in buf:
                        chunk = conn.recv(1024).decode("ascii")
                        if not chunk:
                            break
                        buf += chunk

                    data = buf.strip()
                    cmd = json.loads(data)

                    if cmd["action"] != "ping":
                        print("[Client] Received:", data)


                    try:
                        result = self.handle_command(cmd)
                    except Exception as e:
                        print(f"[Client] ERROR: {e}")
                        result = "1"
                    conn.sendall((result + "\n").encode("ascii"))


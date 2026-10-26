import socket
import json
import time

MAX_RETRIES = 3
RETRY_DELAY = 0.1

class RemoteController:

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def send(self, payload):

        msg = json.dumps(payload) + "\n"

        with socket.socket() as s:
            s.settimeout(2)

            s.connect((self.host, self.port))
            s.sendall(msg.encode("ascii"))

            #response = s.recv(1024).decode("ascii").strip()

            buf = ""
            while "\n" not in buf:
                chunk = s.recv(1024).decode("ascii")
                if not chunk:
                    break
                buf += chunk

            response = buf.strip()

            if response == "1":
                raise ValueError("Command failed")

            return response

    def send_retry(self, payload):

        for i in range(MAX_RETRIES):
            try:
                return self.send(payload)
            except Exception:
                if i == MAX_RETRIES-1:
                    raise
                time.sleep(RETRY_DELAY)


    # API wrappers
    def ping(self):
        payload = {
            "channel": None,
            "action": "ping",
            "value": None
        }

        self.send_retry(payload)

    def get_channels(self):
        payload = {
            "channel": None,
            "action": "list",
            "value": None
        }
        
        ret = self.send_retry(payload)
        if isinstance(ret, str):
            ret = json.loads(ret)

        print(ret)
        return ret

    def set_setpoint(self, channel, value):

        payload = {
            "channel": channel,
            "action": "setpoint",
            "value": value
        }

        self.send_retry(payload)


    def set_manual(self, channel, value):

        payload = {
            "channel": channel,
            "action": "manual",
            "value": value
        }

        self.send_retry(payload)


    def off(self, channel):

        payload = {
            "channel": channel,
            "action": "off"
        }

        self.send_retry(payload)

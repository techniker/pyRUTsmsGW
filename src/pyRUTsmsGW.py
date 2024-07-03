# Abstraction of the Teltonika HTTP Post/Get SMS API to MQTT
# Bjoern Heller <tec att sixtopia.net >

import requests
import paho.mqtt.client as mqtt
import json
import time
import threading

class MobileMessaging:
    def __init__(self, ip, username, password):
        self.base_url = f"http://{ip}/cgi-bin/"
        self.username = username
        self.password = password

    def _make_request(self, endpoint, params=None):
        if params is None:
            params = {}
        params.update({'username': self.username, 'password': self.password})
        
        try:
            print(f"Making request to {self.base_url + endpoint} with params {params}")
            response = requests.get(self.base_url + endpoint, params=params)
            response.raise_for_status()  # Raise an error for bad status codes
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {response.text}")
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None

    def view_messages_list(self):
        return self._make_request("sms_list")

    def read_message(self, number):
        return self._make_request("sms_read", {'number': number})

    def send_message(self, number, text):
        return self._make_request("sms_send", {'number': number, 'text': text})

    def send_message_to_group(self, group, text):
        return self._make_request("sms_send", {'group': group, 'text': text})

    def view_messages_total(self):
        return self._make_request("sms_total")

    def delete_message(self, number):
        return self._make_request("sms_delete", {'number': number})

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe("smsgw01/command")

def on_message(client, userdata, msg):
    print(f"Received message: {msg.topic} {msg.payload.decode()}")
    command = msg.payload.decode().split(':')[0]
    args = msg.payload.decode().split(':')[1:]

    if command == "get_sms_message_list":
        result = messaging.view_messages_list()
    elif command.startswith("read_sms_message_"):
        message_id = int(command.split('_')[-1])
        result = messaging.read_message(message_id)
    elif command == "send_sms_message":
        phone_number, text = args[0].split('+', 1)
        result = messaging.send_message(phone_number, text)
    elif command == "send_sms_message_to_group":
        group_name, text = args[0].split('+', 1)
        result = messaging.send_message_to_group(group_name, text)
    elif command == "read_sms_totalmsg":
        result = messaging.view_messages_total()
    elif command.startswith("delete_sms_message_"):
        message_id = int(command.split('_')[-1])
        result = messaging.delete_message(message_id)
    else:
        result = {"error": "Unknown command"}

    client.publish("smsgw01/response", json.dumps(result))

def parse_message_list(response_text):
    messages = []
    if response_text:
        parts = response_text.strip().split('------------------------------')
        for part in parts:
            if part.strip():
                message_data = {}
                for line in part.strip().split('\n'):
                    key, value = line.split(':', 1)
                    message_data[key.strip().lower()] = value.strip()
                messages.append(message_data)
    return messages

def check_new_messages():
    processed_messages = set()
    while True:
        response_text = messaging.view_messages_list()
        messages = parse_message_list(response_text)
        for message in messages:
            message_index = int(message.get('index', -1))
            if message_index not in processed_messages:
                date = message.get('date', '')
                sender = message.get('sender', '')
                text = message.get('text', '')
                status = message.get('status', '')
                incoming_message = f"{date}+{sender}+{text}+{status}"
                client.publish("smsgw01/incoming", incoming_message)
                # Delete the message after publishing
                delete_response = messaging.delete_message('0')
                if delete_response and "OK" in delete_response:
                    processed_messages.add('0')
        time.sleep(5)

if __name__ == "__main__":
    ip = ""
    username = "user1"
    password = "password"

    messaging = MobileMessaging(ip, username, password)

    mqtt_broker = ""
    mqtt_port = 1883
    mqtt_user = ""
    mqtt_pass = ""

    client = mqtt.Client()
    client.username_pw_set(mqtt_user, mqtt_pass)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(mqtt_broker, mqtt_port, 60)

    # Start the MQTT loop in a separate thread
    mqtt_thread = threading.Thread(target=client.loop_forever)
    mqtt_thread.start()

    # Start checking for new messages
    check_new_messages()
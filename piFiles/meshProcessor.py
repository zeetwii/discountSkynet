import meshtastic # needed for meshtastic
import meshtastic.serial_interface # needed for physical connection to meshtastic
from pubsub import pub # needed for meshtastic connection
from openai import OpenAI # needed for openAI
import yaml # needed for config
import time # needed for sleep
import pika # needed for rabbit

class MeshProcessor:
    def __init__(self):

        self.detectedObjects = ""
            
        # load config settings
        with open("./configs/billing.yaml", "r") as ymlfile:
            config = yaml.safe_load(ymlfile)

        # load openAI keys into client
        self.client = OpenAI(api_key=config["openai"]["API_KEY"])

        # load context settings
        with open("./configs/context.yaml", "r") as ctxfile:
            context = yaml.safe_load(ctxfile)

        self.personality = context["llm"]["PERSONALITY"]

        # set up RabbitMQ
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.channel = self.connection.channel()

        # Declare all the queues we will listen to or use
        self.channel.queue_declare(queue='cameraOutput')

        self.channel.basic_consume(queue='cameraOutput', on_message_callback=self.cameraCallback, auto_ack=True)

        # set up meshtastic
        pub.subscribe(self.onReceive, "meshtastic.receive.text")
        pub.subscribe(self.onConnection, "meshtastic.connection.established")
        # By default will try to find a meshtastic device, otherwise provide a device path like /dev/ttyUSB0


        interface = meshtastic.serial_interface.SerialInterface()

    def cameraCallback(self, ch, method, properties, body):
            
        self.detectedObjects = body.decode()
        #print(self.detectedObjects)


    def onReceive(self, packet, interface): # called when a packet arrives
        #print(f"Received: {packet}")
        
        print(f"User ID: {packet['from']} \nMessage: {packet['decoded']['text']}")

        completion = self.client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"{str(self.personality)}"},
            {"role": "system", "content": f"{str(self.detectedObjects)}"},
            {"role": "user", "content": f"{packet['decoded']['text']}"}
        ]
        )

        output = str(completion.choices[0].message.content)
        print("")
        print(output)
        
        interface.sendText(text=f'{output}', destinationId=packet['from']) # echo the message back to sender

    def onConnection(self, interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
        # defaults to broadcast, specify a destination ID if you wish
        #interface.sendText("hello mesh")
        print(f"Connected to device")

    def startListening(self):
        """
        Starts listening to the message queues
        """

        print("Beginning RabbitMQ listener")
        self.channel.start_consuming()

if __name__ == '__main__':
    meshP = MeshProcessor()

    meshP.startListening()


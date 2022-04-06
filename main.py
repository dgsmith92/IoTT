import time
import json
import xml
import argparse
from os.path import exists
from sys import argv
import asyncio
import asyncio_mqtt
from aiocoap import Context, Code, resource, error
from aiocoap import Message as coapMessage
import socket
import aio_pika
import aio_pika.abc
from aiohttp import web
from gpiozero import CPUTemperature
import aiohttp


def get_ip_address():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.168.0.10", 80))  # Forces it to find a valid route on the 192.168.0.0/24 subnet rather than the class A c2 subnet
    except OSError as e:
        print("Could not find a valid route on the 192.168.0/24 Network:")
        print(e)
        print("Quitting...")
        quit(0)

    return sock.getsockname()[0]


class Temperature(resource.Resource):

    def __init__(self):
        self.temperature = CPUTemperature()

    async def render_get(self, request):
        payload = self.getTemperature().encode('ascii')
        return coapMessage(payload=payload)

    def render_put(self):
        raise error.MethodNotAllowed

    def getTemperature(self):
        return str(self.temperature.temperature)


def writeMessage(content, destination, protocol, translator=None, commands=None):
    messageDict = {"destination": destination, "onwardProtocol": protocol, "translator": translator, "content": content, "commands":commands}
    message = json.dumps(messageDict)
    return message
    # self = IoTTMessage()
    # if translator:
    #     if translator == IP:
    #         self.destination = destination
    #     else:
    #         self.destination = translator
    # else:
    #     self.destination = destination
    # self.onwardProtocol = protocol

class IoTTMessage:
    def __init__(self):
        pass




    def read(self, message, sourceProtocol):
        self = IoTTMessage()
        self.sourceProtocol = sourceProtocol
        fileType = self.extractFileType()
        self.content = self.extractContent()
        self.destination, self.source, self.onwardProtocol, originatingProtocol = self.extractMetadata()
        self.commands = self.extractCommands()

    def extractContent(self):
        # TODO finish me
        content = ""
        return content

    def extractFileType(self):
        fileType = None
        if self.sourceProtocol == "CoAP":
            fileType = self.typeHint

        return fileType

    def extractMetadata(self):
        # TODO finish me
        destination = ""
        source = ""
        onwardProtocol = ""
        originatingProtocol = ""
        return destination, source, onwardProtocol, originatingProtocol

    def extractCommands(self):
        commands = []
        if commands:
            return commands
        else:
            return None


class Translator:

    def __init__(self, port):
        self.port = port


class CoapTranslator(Translator):
    def __init__(self, port):
        super().__init__(port)
        self.site = resource.Site()
        self.protocol = Context.create_server_context(self.site)

    async def AddResource(self, new_resource, uri):
        await self.site.add_resource(path=[uri], resource=new_resource)

    async def RemoveResource(self, path):
        await self.site.remove_resource(path)

    async def sendMessage(self, method, dest_uri):
        if method == "GET":
            request = coapMessage(code=Code.GET, uri=dest_uri)
            try:
                response = await self.protocol.request(request).response
            except Exception as e:
                print('Failed to fetch resource:')
                print(e)
            else:
                print('Result: %s\n%r'%(response.code, response.payload))
        elif method == "POST":
            pass
        elif method == "PUT":
            pass
        elif method == "DELETE":
            pass
        else:
            if debug:
                print("Invalid CoAP request type. GET, POST, PUT and DELETE are valid.")

    async def respondMessage(self):
        pass

    async def listen(self):
        pass


class MqttTranslator(Translator):
    pass


class AmqpTranslator(Translator):
    pass


class HttpTranslator(Translator):
    def __init__(self, port=80):
        super().__init__(port)


class Client:

    def __init__(self, port):
        self.port = port


class CoapClient(Client):
    def __init__(self, port=5683):
        super().__init__(port)
        self.site = None
        self.protocol = None

    @classmethod
    async def create(cls, port=5683, site=None):
        self = CoapClient(port)
        self.protocol = None
        if site:
            self.site = site
        else:
            self.site = resource.Site()
        self.protocol = await Context.create_server_context(self.site, bind=(IP, self.port))
        return self

    def AddResource(self, new_resource, uri):
        self.site.add_resource(path=[uri], resource=new_resource)
        if debug:
            print("Added resource")

    async def RemoveResource(self, path):
        await self.site.remove_resource(path)

    async def request(self, method, dest_uri):
        start_time = time.time()
        if method == "GET":
            request = coapMessage(code=Code.GET, uri=dest_uri)
            try:
                response = await self.protocol.request(request).response
            except Exception as e:
                print('Failed to fetch resource:')
                print(e)
            else:
                finishTime = time.time()
                timesCoap.append(finishTime-start_time)
                print('Result: {}\n{}'.format(response.code, response.payload))
        elif method == "POST":
            pass
        elif method == "PUT":
            pass
        elif method == "DELETE":
            pass
        else:
            if debug:
                print("Invalid CoAP request type. GET, POST, PUT and DELETE are valid.")

    async def respondMessage(self):
        pass

    async def listen(self):
        pass


class MqttClient(Client):
    def __init__(self, port):
        super().__init__(port)
        self.client = None

    @classmethod
    async def create(cls, broker, port=1883):
        self = MqttClient(port)
        self.client = asyncio_mqtt.Client(hostname=broker, username="user", password="pass", port=port)
        await self.client.connect()
        print("Mqtt Client created")
        return self

    def request(self, method, dest_uri):
        pass

    async def publish(self, topic, payload):
        await self.client.publish(topic, payload.encode())

    async def subscribe(self, topic):
        print("subscriber started")
        async with self.client.filtered_messages(topic) as messages:
            await self.client.subscribe(topic)
            async for message in messages:
                print("{} - MQTT".format(message.payload.decode()))

    def addChannel(self, topic):
        pass

    def removeChannel(self, topic):
        pass

    def unsubscribe(self, topic):
        pass

    def close(self):
        pass


class AmqpClient(Client):

    def __init__(self, port):
        super().__init__(port)
        self.connection = None

    @classmethod
    async def create(cls, exchange, port=5672):
        self = AmqpClient(port)
        self.connection = await aio_pika.connect_robust(exchange)

        return self

    def request(self, method, dest_uri):
        pass

    async def publish(self, queue_name, payload):
        channel: aio_pika.abc.AbstractChannel = await self.connection.channel()
        await channel.default_exchange.publish(aio_pika.Message(body=payload.encode()), routing_key=queue_name)

    async def add_queue(self, queue_name):
        pass

    def remove_queue(self, queue_name):
        pass

    async def subscribe(self, queue_name):
        print("subscriber started amqp")
        channel: aio_pika.abc.AbstractChannel = await self.connection.channel()
        queue: aio_pika.abc.AbstractQueue = await channel.declare_queue(queue_name, auto_delete=True)

        async with queue.iterator() as queue_iterator:
            async for message in queue_iterator:
                async with message.process():
                    print(message.body)

    def unsubscribe(self, queue_name):
        pass

    async def close(self):
        await self.connection.close()


class HttpClient(Client):
    def __init__(self, port=80):
        super().__init__(port)

    async def request(self, requestType, uri, payload=None):
        async with aiohttp.ClientSession() as session:
            if requestType.upper() == "GET":
                startTime = time.time()
                async with session.get(uri) as response:
                    finishTime = time.time()
                    timesHttp.append(finishTime-startTime)
                    print(response.status)
                    print(await response.text())
            elif requestType.upper() == "POST":
                async with session.post(uri, data=payload) as response:
                    print(response.status)
                    print(await response.text())
            elif requestType.upper() == "PUT":
                async with session.put(uri, data=payload) as response:
                    print(response.status)
                    print(await response.text())
            elif requestType.upper() == "DELETE":
                async with session.delete(uri) as response:
                    print(response.status)
                    print(await response.text())
            elif requestType.upper() == "HEAD":
                async with session.head(uri) as response:
                    print(response.status)
                    print(await response.text())
            elif requestType.upper() == "OPTIONS":
                async with session.options(uri) as response:
                    print(response.status)
                    print(await response.text())
            elif requestType.upper() == "PATCH":
                async with session.patch(uri, data=payload) as response:
                    print(response.status)
                    print(await response.text())


class HttpServer(Client):

    def __init__(self, port=80):
        super().__init__(port)
        self.site = None

    @classmethod
    async def create(cls, port=80):
        self = HttpServer(port)
        self.httpServer = web.Application()
        self.httpServer.add_routes([web.get('/temp', self.handle_temperature)])
        self.runner = web.AppRunner(self.httpServer)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, IP, 80)
        return self

    async def handle_temperature(self, request):
        return web.Response(text=str(temperature.getTemperature()))

    async def run(self):
        print("test - running http server")
        await self.site.start()

    def add_resource(self):
        pass


async def runPublishLoop(pubSubClient):
    print("loop started")
    await asyncio.sleep(10)
    for counter in range(10):
        await pubSubClient.publish("temp", temperature.getTemperature())
        print("publishing temperature")
        await asyncio.sleep(5)


async def processMessage(message: IoTTMessage):
    if message.commands is not None and message.destination == IP:
        for command in message.commands:
            loop.create_task(command)


async def main():
    # HTTP
    httpClient = HttpClient()

    httpServer = await HttpServer.create()
    httpTranslator = HttpTranslator()
    #await httpServer.run()
    # CoAP
    siteRoot = resource.Site()
    siteRoot.add_resource(['temp'], temperature)

    coapClient = await CoapClient.create(site=siteRoot)
    # AMQP
    amqpClient = await AmqpClient.create("amqp://user:pass@192.168.0.101/")
    # MQTT
    mqttClient = await MqttClient.create("192.168.0.101")
    if args.x:
        print(writeMessage(temperature.getTemperature(), "10.0.10.4", "AMQP", "10.0.10.1", ["EnableMQTTPublish 5 5"]))
        # await asyncio.gather(amqpClient.subscribe("temp"), coapClient.request('GET', 'coap://192.168.0.101/temp'), httpClient.request("GET", "http://192.168.0.101/temp"), mqttClient.subscribe("temp"))
    else:
        await asyncio.gather(asyncio.get_running_loop().create_future(), httpServer.run(), runPublishLoop(amqpClient), runPublishLoop(mqttClient))


# Set location for any default files
defaultConfig = "config_client.json"

# Setup argument parser to accept overrides given in the command line
parser = argparse.ArgumentParser(description='TODO add description')
parser.add_argument('-C', '--Config', dest='configFile', type=open,
                    help='Optionally overwrites the hardcoded default config file.')
parser.add_argument('-D', '--Debug', dest='debug', action='store_true', default=False,
                    help='Setting this flag enables debug messages, otherwise they default to off.')

parser.add_argument('--enableTranslator', dest='translatorEnable', type=bool, choices=[True, False],
                    help='Gives the device a translator role, when False, a client role is assumed')
parser.add_argument('--translatorAddress', dest='translatorAddress', type=str,
                    help='An override IP address for a client to use to reach a translator. Ignored if given '
                         'translator role')

parser.add_argument('--enableCoAP', dest='coapEnable', type=bool, choices=[True, False], help='Enables CoAP')
parser.add_argument('--enableCoAPObserve', dest='coapObserve', type=bool, choices=[True, False],
                    help='Enables CoAP Observe Support')
parser.add_argument('--enableHTTP', dest='httpEnable', type=bool, choices=[True, False],
                    help='Enables HTTP Client/Server')
parser.add_argument('--enableHTTPS', dest='httpsEnable', type=bool, choices=[True, False],
                    help='Enables HTTPS support for the HTTP server. Not yet implemented and will require the HTTP '
                         'server is enabled')
parser.add_argument('--HTTPSOnly', dest='httpsOnly', type=bool, choices=[True, False],
                    help='Disables plaintext HTTP for the HTTP server')
parser.add_argument('--enableAMQP', dest='amqpEnable', type=bool, choices=[True, False], help='Enables AMQP')
parser.add_argument('--AMQPExchangeAddress', dest='amqpAddress', type=str,
                    help='An override IP address for an AMQP Exchange server to use.')
parser.add_argument('--enableMQTT', dest='mqttEnable', type=bool, choices=[True, False], help='Enables MQTT')
parser.add_argument('--MQTTBrokerAddress', dest='mqttAddress', type=str,
                    help='An override IP address for an AMQP Exchange server to use.')
parser.add_argument('-X', dest='x', action='store_true', default=False)

# TODO Add override arguments
args = None
try:
    args = parser.parse_args()
except FileNotFoundError:
    print("Filepath for Config file invalid")
    exit()

debug = args.debug

# Initialise variables that are later changed in if statements
client = False
translator = False
CoAP_Enable = False
CoAP_Consume = False
CoAP_Provide = False
CoAP_Observe = False
MQTT_Enable = False
MQTT_Consume = False
MQTT_Provide = False
AMQP_Enable = False
AMQP_Consume = False
AMQP_Provide = False
HTTP_Enable = False
HTTPS_Enable = False
HTTPS_Only = False
HTTP_Consume = False
HTTP_Provide = False
MQTT_brokerAddress = ""
AMQP_exchangeAddress = ""
provider = False
consumer = False


if not (args.configFile or exists(defaultConfig)):
    print("-- No config specified and no default found. Using built in default --")
    # TODO set default values
    CoAP_Enable = True
    CoAP_Consume = False
    CoAP_Provide = True
    CoAP_Observe = False
    MQTT_Enable = True
    MQTT_Consume = True
    MQTT_Provide = False
    AMQP_Enable = False
    AMQP_Consume = False
    AMQP_Provide = False
    HTTP_Enable = False
    HTTPS_Enable = False
    HTTPS_Only = False
    HTTP_Consume = False
    HTTP_Provide = False
    MQTT_brokerAddress = "10.0.10.1"
    AMQP_exchangeAddress = "10.0.10.1"

else:
    if args.configFile:
        if debug:
            print('Using provided config: {}'.format(args.configFile.name))
        configFile = args.configFile

    else:
        if debug:
            print("Using default config")
        configFile = open(defaultConfig)

    # TODO get values from config file in use - Confirm all cases are covered
    config = json.load(configFile)
    if config['debugPrint']:
        debug = True
        print('debug enabled by config file')
    role = config['role']
    translatorAddress = config['translatorAddress']
    if config['protocols']:
        for protocol in config['protocols']:
            if protocol['name'] == 'CoAP':
                if protocol['enabled']:
                    CoAP_Enable = True
                    if protocol.get('options', False).get('observeSupport', False):
                        CoAP_Observe = True
                    if protocol.get('options', False).get('consume', False):
                        CoAP_Consume = True
                    if protocol.get('options', False).get('provide', False):
                        CoAP_Provide = True
            elif protocol['name'] == 'MQTT':
                if protocol['enabled']:
                    MQTT_Enable = True
                    if protocol.get('options', False).get('brokerAddress', False):
                        MQTT_brokerAddress = protocol.get('options').get('brokerAddress')
                        if debug:
                            print("MQTT Broker address set to {}".format(MQTT_brokerAddress))
                    else:
                        print('--WARNING MQTT is enabled but no broker address is specified')
                    if protocol.get('options', False).get('consume', False):
                        MQTT_Consume = True
                    if protocol.get('options', False).get('provide', False):
                        MQTT_Provide = True
            elif protocol['name'] == 'AMQP':
                if protocol['enabled']:
                    AMQP_Enable = True
                    if protocol.get('options', False).get('exchangeAddress', False):
                        AMQP_exchangeAddress = protocol.get('options').get('exchangeAddress')
                        if debug:
                            print("AMQP Exchange address set to {}".format(AMQP_exchangeAddress))
                    else:
                        print('--WARNING AMQP is enabled but no exchange address is specified')
                    if protocol.get('options', False).get('consume', False):
                        AMQP_Consume = True
                    if protocol.get('options', False).get('provide', False):
                        AMQP_Provide = True
            elif protocol['name'] == 'HTTP':
                if protocol['enabled']:
                    HTTP_Enable = True
                    if protocol.get('options', False).get('HTTPS', False):
                        HTTPS_Enable = True
                    if protocol.get('options', False).get('HTTPSOnly', False):
                        HTTPS_Only = True
                    if protocol.get('options', False).get('consume', False):
                        HTTP_Consume = True
                    if protocol.get('options', False).get('provide', False):
                        HTTP_Provide = True
            else:
                print('--WARNING\tInvalid Protocol name "{}" found in config file. Skipping this protocol. If this is '
                      'unexpected check the configuration and consider restarting the program.'.format(protocol['name']))
    if role == "Client":
        client = True
    elif role == "Translator":
        translator = True
    if config['debugPrint']:
        debug = True
        print('debug enabled by config file')
# TODO process and apply override arguments
if len(argv) == 1:  # If True then no options given, skip checking which overrides have been selected for efficiency
    if debug:
        print("No options given")
else:  # At least one override has been given (inclusive of config files), find and apply these
    if debug:
        print('Applying overrides')
# TODO import correct packages for given options
if debug:
    print('Importing packages')

# Perform imports, initialise variables and any one time code before triggering async event loop
if not (translator or client):
    print("--ERROR neither client or translator role specified. Quitting.")
    quit(1)
if translator and client:
    print("--ERROR both client and translator role specified. Quitting.")
    quit(1)

protocols = []
IP = get_ip_address()
temperature = Temperature()
timesCoap = []
timesHttp = []
loop = asyncio.get_event_loop()
asyncio.run(main())

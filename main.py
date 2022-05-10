import time
import json
import weakref
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
from urllib.parse import urlparse


def get_ip_address():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.168.0.10",
                      80))  # Forces it to find a valid route on the 192.168.0.0/24 subnet rather than the class A c2 subnet
    except OSError as e:
        print("Could not find a valid route on the 192.168.0/24 Network:")
        print(e)
        print("Quitting...")
        quit(0)

    return sock.getsockname()[0]


def writeMessage(content, destination, onwardProtocol, messageType, sendTime, translatorAddress=None, commands=None):
    messageDict = {"destination": destination, "onwardProtocol": onwardProtocol, "translator": translatorAddress,
                   "messageType": messageType, "content": content, "commands": commands, "sendTime": sendTime}
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


def readMessage(jsonMessage):
    messageDict = json.loads(jsonMessage)
    return messageDict


class messageProcessor:
    def __init__(self, parent):
        self.parent = weakref.proxy(parent)

    async def processMessage(self, payload):
        payload = payload.decode()
        message = readMessage(payload)

        # print(message.get("content"))
        # print(IP)

        if message.get("destination") == IP:
            if message.get("commands"):
                pass
                # for command in message.get("commands"):
                #     await loop.create_task(command)
            print("{} - {}".format(message.get("content"), message.get("onwardProtocol")))
            elapsedTime = time.time() - message.get("sendTime")  # TODO record elapsed time values  # TODO add send times to messages so that elapsed time can be calculated
            return elapsedTime
        if message.get("messageType") == "request":
            if message.get("onwardProtocol") == "AMQP":
                response = ""
            elif message.get("onwardProtocol") == "MQTT":
                response = ""
            elif message.get("onwardProtocol") == "HTTP":
                response = await self.parent.httpClient.request("GET", message.get("destination"),
                                                                payload=message.get("content"))
            elif message.get("onwardProtocol") == "CoAP":
                response = await translators.get("CoAP").request(message)
            else:
                response = "--Error invalid onward protocol"
                print(response)
            return response
        elif message.get("messageType") == "response":
            if message.get("onwardProtocol") == "AMQP":
                response = ""
            elif message.get("onwardProtocol") == "MQTT":
                response = ""
            elif message.get("onwardProtocol") == "HTTP":
                response = ""
                # response = await self.parent.httpClient.request("GET", message.get("destination"), payload=payload)
            elif message.get("onwardProtocol") == "CoAP":
                print(payload)
                response = ""
                # response = await self.parent.coapClient.request(message)
            else:
                response = "--Error invalid onward protocol"
                print(response)
            return response
        else:
            response = "--Error invalid messageType in payload JSON"
            print(response)


class Temperature(resource.Resource):

    def __init__(self):
        self.temperature = CPUTemperature()

    async def render_get(self, request):
        # payload = (self.getTemperature() + " CoAP").encode('ascii')
        payload = (writeMessage(self.getTemperature(), CLIENT_ADDRESS, "CoAP", "response", time.time(), commands=["AMQPPublishStart"])).encode('ascii')
        # print(payload)
        return coapMessage(payload=payload)

    async def render_put(self):
        raise error.MethodNotAllowed

    def getTemperature(self):
        return str(self.temperature.temperature)


class TranslatedCoAPResource(messageProcessor, resource.Resource):
    def __init__(self, onWardProtocol, parent, subscriber=None):
        super().__init__(parent)
        if subscriber:
            pass
        self.subscriber = subscriber
        self.content = ""
        self.onwardProtocol = onWardProtocol

    async def render_get(self, request):
        if self.onwardProtocol == "http":
            self.content = await self.parent.httpClient.request("GET", "http://" + SERVER_ADDRESS + "/temp")
            self.content = self.content.encode('ascii')
        elif self.onwardProtocol == "amqp":
            self.content = await self.subscriber.get_content()
            self.content = self.content.encode('ascii')
        elif self.onwardProtocol == "mqtt":
            self.content = await self.subscriber.get_content()
            self.content = self.content.encode('ascii')
        elif self.onwardProtocol == "coap":
            self.content = await self.parent.coapClient.request("GET", "coap://" + SERVER_ADDRESS + "/temp")
        else:
            self.content = await self.processMessage(request)  # TODO get payload from endpoint
        return coapMessage(payload=self.content)

    async def subscribe(self):
        pass  # TODO add code to call a subscriber to dynamically update content

    async def render_put(self):
        raise error.MethodNotAllowed


class IoTTSubscriber(messageProcessor):
    def __init__(self, parent, messageProtocol, topic):  # Requires a weakref proxy to reuse the already initialised pub/sub clients to create a subscriber
        super().__init__(parent)
        self.content = ""
        self.client = None
        self.topic = topic
        print(messageProtocol)
        if messageProtocol == "mqtt":
            self.mqtt = True
            self.amqp = False
        elif messageProtocol == "amqp":
            self.mqtt = False
            self.amqp = True
        else:
            print("ERROR, invalid message protocol given for use with IoTTSubscriber. '{}' given.".format(messageProtocol))
            self.mqtt = False
            self.amqp = False

    @classmethod
    async def create(cls, parent, messageProtocol, topic):
        self = IoTTSubscriber(parent, messageProtocol, topic)

        return self

    async def subscribe(self):

        if self.mqtt:
            self.client = asyncio_mqtt.Client(hostname=TRANSLATOR_ADDRESS, username="user", password="pass", port=1883)
            await self.client.connect()
            print("subscriber starting for {} on mqtt".format(self.topic))
            async with self.client.filtered_messages(self.topic) as messages:
                await self.client.subscribe(self.topic)
                async for message in messages:
                    self.content = message.payload.decode()
                    # print("Updated MQTT value to {}".format(self.content))

        if self.amqp:
            self.client = self.parent.amqpClient
            print("subscriber started for {} on amqp".format(self.topic))
            channel: aio_pika.abc.AbstractChannel = await self.client.connection.channel()
            queue: aio_pika.abc.AbstractQueue = await channel.declare_queue(self.topic, auto_delete=True)

            async with queue.iterator() as queue_iterator:
                async for message in queue_iterator:
                    async with message.process():
                        self.content = message.body.decode()
                        # print("Updated AMQP value to {}".format(self.content))

    async def get_content_http(self, request):
        return web.Response(text=self.content)

    async def get_content(self):
        return self.content


class IoTTPublisher(messageProcessor):
    def __init__(self):
        pass

# class IoTTMessage:
#     def __init__(self):
#         pass
#
#     def read(self, message, sourceProtocol):
#         self = IoTTMessage()
#         self.sourceProtocol = sourceProtocol
#         fileType = self.extractFileType()
#         self.content = self.extractContent()
#         self.destination, self.source, self.onwardProtocol, originatingProtocol = self.extractMetadata()
#         self.commands = self.extractCommands()
#
#     def extractContent(self):
#         # TODO finish me
#         content = ""
#         return content
#
#     def extractFileType(self):
#         fileType = None
#         if self.sourceProtocol == "CoAP":
#             fileType = self.typeHint
#
#         return fileType
#
#     def extractMetadata(self):
#         # TODO finish me
#         destination = ""
#         source = ""
#         onwardProtocol = ""
#         originatingProtocol = ""
#         return destination, source, onwardProtocol, originatingProtocol
#
#     def extractCommands(self):
#         commands = []
#         if commands:
#             return commands
#         else:
#             return None


class Translator:

    def __init__(self, port):
        self.port = port

    @classmethod
    async def create(cls):
        ports = None
        self = Translator(ports)

        self.mqttClient = await MqttTranslator.create(self, "192.168.0.101")
        self.amqpClient = await AmqpTranslator.create(self, "amqp://user:pass@192.168.0.101/")

        siteRoot = resource.Site()
        mqttSub = await IoTTSubscriber.create(self, "mqtt", "temp")
        asyncio.create_task(mqttSub.subscribe())
        mqttRes = TranslatedCoAPResource("mqtt", self, mqttSub)
        siteRoot.add_resource(['mqtt'], mqttRes)
        amqpSub = await IoTTSubscriber.create(self, "amqp", "temp")
        asyncio.create_task(amqpSub.subscribe())
        amqpRes = TranslatedCoAPResource("amqp", self, amqpSub)
        siteRoot.add_resource(['amqp'], amqpRes)
        httpRes = TranslatedCoAPResource("http", self)
        siteRoot.add_resource(["http"], httpRes)
        coapRes = TranslatedCoAPResource("coap", self)
        siteRoot.add_resource(["coap"], coapRes)
        self.coapClient = await CoapClient.create(self, site=siteRoot)

        self.httpClient = HttpClient(self)
        self.httpServer = await HttpTranslator.create(self)
        return self

    async def register_resource(self, response_protocol, uri):
        print(uri)
        scheme, location, path, _, _, _ = urlparse(uri)
        print(scheme)
        createdResource = ""
        if response_protocol == "http":
            if scheme == "amqp" or scheme == "mqtt":
                print("path: '{}'".format(path[1:]))
                subscriber = await IoTTSubscriber.create(self, scheme, path[1:])
                asyncio.create_task(subscriber.subscribe())
                self.httpServer.httpServer.router._frozen = False  # TODO This line and the line 2 lines later are a bodgy hack, using a wildcard is safer
                try:
                    self.httpServer.httpServer.add_routes([web.get('/' + location + '/' + scheme + path, subscriber.get_content_http)])
                except RuntimeError:
                    pass
                self.httpServer.httpServer.router._frozen = True
                createdResource = 'http://' + get_ip_address() + '/' + location + '/' + scheme + path
            else:
                self.httpServer.httpServer.router._frozen = False  # TODO This line and the line 2 lines later are a bodgy hack, using a wildcard is safer
                self.httpServer.httpServer.add_routes([web.get('/' + location + '/' + scheme + path, self.httpServer.handle_translation)])
                self.httpServer.httpServer.router._frozen = True
                createdResource = 'http://' + get_ip_address() + '/' + location + '/' + scheme + path
        elif response_protocol == "coap":
            createdResource = "CoAP Selected"
        elif response_protocol == "mqtt":
            pass
        elif response_protocol == "amqp":
            pass
        else:
            return False, ""

        return True, createdResource


class CoapTranslator(messageProcessor):
    def __init__(self, parent, port=5683):
        super().__init__(parent)
        self.port = port
        self.site = None
        self.protocol = None

    @classmethod
    async def create(cls, parent, port=5683, site=None):
        self = CoapTranslator(parent, port=port)
        self.protocol = None
        if site:
            self.site = site
        else:
            self.site = resource.Site()
        self.protocol = await Context.create_server_context(self.site, bind=(IP, self.port))
        return self

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
                print('Result: %s\n%r' % (response.code, response.payload))
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


class MqttTranslator(messageProcessor):
    def __init__(self, parent, port):
        super().__init__(parent)
        self.port = port
        self.client = None

    @classmethod
    async def create(cls, parent, broker, port=1883):
        self = MqttTranslator(parent, port=port)
        self.client = asyncio_mqtt.Client(hostname=broker, username="user", password="pass", port=port)
        await self.client.connect()
        print("Mqtt Client created")
        return self

    def request(self, method, dest_uri):
        pass

    async def publish(self, topic, payload):
        payload = self.parent.coapClient.sendMessage("GET", ) + " MQTT"
        await self.client.publish(topic, payload.encode())

    async def subscribe(self, topic):
        print("subscriber started")
        async with self.client.filtered_messages(topic) as messages:
            await self.client.subscribe(topic)
            async for message in messages:
                # print("{} - MQTT".format(message.payload.decode()))
                pass

    def addChannel(self, topic):
        pass

    def removeChannel(self, topic):
        pass

    def unsubscribe(self, topic):
        pass

    def close(self):
        pass


class AmqpTranslator(messageProcessor):

    def __init__(self, parent, port):
        super().__init__(parent)
        self.port = port
        self.connection = None

    @classmethod
    async def create(cls, parent, exchange, port=5672):
        self = AmqpTranslator(parent, port=port)
        self.connection = await aio_pika.connect_robust(exchange)

        return self

    def request(self, method, dest_uri):
        pass

    async def publish(self, queue_name, payload):
        channel: aio_pika.abc.AbstractChannel = await self.connection.channel()
        payload = payload + " AMQP"
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


class HttpTranslator(messageProcessor):

    def __init__(self, parent, port=80):
        super().__init__(parent)
        self.parent = weakref.proxy(parent)
        self.port = port
        self.site = None

    @classmethod
    async def create(cls, parent, port=80):
        self = HttpTranslator(parent, port=port)
        self.httpServer = web.Application()
        # self.httpServer.add_routes([web.get('/' + SERVER_ADDRESS + '/http/temp', self.handle_translation)])
        self.httpServer.add_routes([web.get('/service', self.service)])
        self.httpServer.add_routes([web.put('/service/register_resource', self.register_resource)])
        self.runner = web.AppRunner(self.httpServer)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, IP, 80)
        return self

    async def handle_translation(self, request):
        requestedResource = str(request).split()[2]
        if requestedResource.split('/')[2] == "coap":
            payload = await self.parent.coapClient.request("GET", "coap://" + SERVER_ADDRESS + "/temp")
            payload = payload.decode()
        elif requestedResource.split('/')[2] == "http":
            payload = await self.parent.httpClient.request("GET", "http://" + SERVER_ADDRESS + "/temp")
        elif requestedResource.split('/')[2] == "amqp":
            pass
        else:
            print(requestedResource)
            print("ERROR - Invalid resource requested for translation")
        return web.Response(text=str(payload))

    async def register_resource(self, request):
        if request.body_exists:
            body = await request.read()
            success, resp = await self.parent.register_resource("http", body.decode())
            print(resp)
            print(success)
        return web.Response(text=str(resp))

    async def service(self, request):
        return web.Response(text="This is a summy service message to increase server load")
    async def run(self):
        print("test - running http server")
        await self.site.start()


class Client:

    def __init__(self, ports=None):
        self.ports = ports

    @classmethod
    async def create(cls):
        ports = None
        self = Client(ports)
        siteRoot = resource.Site()
        siteRoot.add_resource(['temp'], temperature)
        self.coapClient = await CoapClient.create(self, site=siteRoot)
        self.mqttClient = await MqttClient.create(self, "192.168.0.101")
        self.amqpClient = await AmqpClient.create(self, "amqp://user:pass@192.168.0.101/")
        self.httpClient = HttpClient(self)
        self.httpServer = await HttpServer.create(self)
        return self


class CoapClient(messageProcessor):
    def __init__(self, parent, port=5683):
        super().__init__(parent)
        self.port = port
        self.site = None
        self.protocol = None

    @classmethod
    async def create(cls, parent, port=5683, site=None):
        self = CoapClient(parent, port=port)
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
                timesCoap.append(finishTime - start_time)
                # print(response.payload)
                if str(response.payload).startswith("b'b\\'"):
                    response.payload = response.payload[2:-1]

                sendtime = await self.processMessage(response.payload)
                sendTimes.append(sendtime)
                return response.payload
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


class MqttClient(messageProcessor):
    def __init__(self, parent, port):
        super().__init__(parent)
        self.protocolType = "MQTT"
        self.port = port
        self.client = None

    @classmethod
    async def create(cls, parent, broker, port=1883):
        self = MqttClient(parent, port=port)
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
                self.parent.processMessage("{}".format(message.payload.decode()))



    def addChannel(self, topic):
        pass

    def removeChannel(self, topic):
        pass

    def unsubscribe(self, topic):
        pass

    def close(self):
        pass


class AmqpClient(messageProcessor):

    def __init__(self, parent, port):
        self.protocolType = "AMQP"
        self.parent = weakref.proxy(parent)
        self.port = port
        self.connection = None

    @classmethod
    async def create(cls, parent, exchange, port=5672):
        self = AmqpClient(parent, port=port)
        self.connection = await aio_pika.connect_robust(exchange)

        return self

    def request(self, method, dest_uri):
        pass

    async def publish(self, queue_name, payload):
        channel: aio_pika.abc.AbstractChannel = await self.connection.channel()
        await channel.default_exchange.publish(aio_pika.Message(body=payload.encode()), routing_key=queue_name)
        await channel.close()

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


class HttpClient(messageProcessor):
    def __init__(self, parent, port=80):
        self.parent = weakref.proxy(parent)
        self.port = port

    async def request(self, requestType, uri, payload=None):
        start_time = time.time()
        async with aiohttp.ClientSession() as session:
            if requestType.upper() == "GET":
                startTime = time.time()
                async with session.get(uri) as response:
                    finishTime = time.time()
                    timesHttp.append(finishTime - startTime)
                    if debug:
                        print(response.status)
                    finish_time = time.time()
                    elapsed_time = finish_time - start_time
                    timesHttp.append(elapsed_time)
                    return await response.text()
            elif requestType.upper() == "POST":
                async with session.post(uri, data=payload) as response:
                    print(response.status)
                    print(await response.text())
            elif requestType.upper() == "PUT":
                async with session.put(uri, data=payload) as response:
                    print(response.status)
                    addr = await response.text()
                    return addr
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


class HttpServer(messageProcessor):

    def __init__(self, parent, port=80):
        super().__init__(parent)
        self.parent = weakref.proxy(parent)
        self.port = port
        self.site = None

    @classmethod
    async def create(cls, parent, port=80):
        self = HttpServer(parent, port=port)
        self.httpServer = web.Application()
        self.httpServer.add_routes([web.get('/temp', self.handle_temperature)])
        self.runner = web.AppRunner(self.httpServer)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, IP, 80)
        return self

    async def handle_temperature(self, request):
        payload = (writeMessage(temperature.getTemperature(), "192.168.0.115", "HTTP", "response", time.time(),
                                commands=["AMQPPublishStart"])).encode('ascii')
        return web.Response(text=str(payload))
        #return web.Response(text=str(temperature.getTemperature() + " HTTP"))

    async def run(self):
        print("test - running http server")
        await self.site.start()

    def add_resource(self):
        pass


async def runPublishLoop(pubSubClient):
    print("loop started")
    await asyncio.sleep(0.1)
    while True:
        payload = (writeMessage(temperature.getTemperature(), CLIENT_ADDRESS, pubSubClient.protocolType, "response", time.time(), commands=["AMQPPublishStart"]))
        await pubSubClient.publish("temp", payload)
        print("publishing temperature")
        await asyncio.sleep(0.1)


async def main():
    # # HTTP
    # httpClient = HttpClient()
    #
    # httpServer = await HttpServer.create()
    # httpTranslator = HttpTranslator()
    # # await httpServer.run()
    # # CoAP
    # siteRoot = resource.Site()
    # siteRoot.add_resource(['temp'], temperature)
    #
    # coapClient = await CoapClient.create(site=siteRoot)
    # # AMQP
    # amqpClient = await AmqpClient.create("amqp://user:pass@192.168.0.101/")
    # # MQTT
    # mqttClient = await MqttClient.create("192.168.0.101")
    global sendTimes, timesCoap, timesHttp

    if args.x:
        IoTTClient = await Client.create()
        # await asyncio.gather(IoTTClient.amqpClient.subscribe("temp"),
        #                      IoTTClient.coapClient.request('GET', 'coap://192.168.0.101/temp'),
        #                      IoTTClient.httpClient.request("GET", "http://192.168.0.101/temp"),
        #                      IoTTClient.mqttClient.subscribe("temp"))
        txt = await asyncio.gather(IoTTClient.coapClient.request('GET', 'coap://' + TRANSLATOR_ADDRESS + '/mqtt'))
        await asyncio.sleep(0.1)
        txt = await asyncio.gather(IoTTClient.coapClient.request('GET', 'coap://' + TRANSLATOR_ADDRESS + '/amqp'))
        await asyncio.sleep(0.1)



        addr = await IoTTClient.httpClient.request('PUT', "http://" + TRANSLATOR_ADDRESS + '/service/register_resource', payload="mqtt://" + SERVER_ADDRESS + "/temp")
        print(addr)
        await asyncio.sleep(1)
        resp = await IoTTClient.httpClient.request('GET', addr)
        print(resp)
        addr = await IoTTClient.httpClient.request('PUT', "http://" + TRANSLATOR_ADDRESS + '/service/register_resource', payload="amqp://" + SERVER_ADDRESS + "/temp")
        print(addr)
        await asyncio.sleep(1)
        resp = await IoTTClient.httpClient.request('GET', addr)
        print(resp)
        addr = await IoTTClient.httpClient.request('PUT', "http://" + TRANSLATOR_ADDRESS + '/service/register_resource', payload="http://" + SERVER_ADDRESS + "/temp")
        resp = await IoTTClient.httpClient.request('GET', addr)
        print(resp)
        addr = await IoTTClient.httpClient.request('PUT', "http://" + TRANSLATOR_ADDRESS + '/service/register_resource', payload="coap://" + SERVER_ADDRESS + "/temp")
        resp = await IoTTClient.httpClient.request('GET', addr)
        print(resp)
        for _ in range(100):

            await asyncio.gather(IoTTClient.httpClient.request('GET', 'http://' + TRANSLATOR_ADDRESS + '/' + SERVER_ADDRESS + '/coap/temp'))
            await asyncio.sleep(0.1)
            await asyncio.gather(IoTTClient.coapClient.request('GET', 'coap://' + TRANSLATOR_ADDRESS + '/coap'))
            await asyncio.sleep(0.1)
            await asyncio.gather(IoTTClient.coapClient.request('GET', 'coap://' + TRANSLATOR_ADDRESS + '/mqtt'))
            await asyncio.sleep(0.1)
            await asyncio.gather(IoTTClient.coapClient.request('GET', 'coap://' + TRANSLATOR_ADDRESS + '/amqp'))
            await asyncio.sleep(0.1)
            await asyncio.gather(IoTTClient.coapClient.request('GET', 'coap://' + TRANSLATOR_ADDRESS + '/http'))
            await asyncio.sleep(0.1)
            await asyncio.gather(IoTTClient.httpClient.request('GET', 'http://' + TRANSLATOR_ADDRESS + '/' + SERVER_ADDRESS + '/mqtt/temp'))
            await asyncio.sleep(0.1)

        print("sendTimes {}".format(sendTimes))
        print("timesCoap {}".format(timesCoap))
        print("timesHttp {}".format(timesHttp))
        sendTimes = []
        timesCoap = []
        timesHttp = []

        for _ in range(100):
            await asyncio.gather(IoTTClient.coapClient.request('GET', 'coap://' + TRANSLATOR_ADDRESS + '/http'))
            await asyncio.sleep(0.1)
            await asyncio.gather(IoTTClient.httpClient.request('GET', 'http://' + TRANSLATOR_ADDRESS + '/' + SERVER_ADDRESS + '/http/temp'))
            await asyncio.sleep(0.1)

        print("sendTimes {}".format(sendTimes))
        print("timesCoap {}".format(timesCoap))
        print("timesHttp {}".format(timesHttp))
    elif args.t:
        IoTTTranslator = await Translator.create()
        await asyncio.gather(IoTTTranslator.httpServer.run(),
                             IoTTTranslator.mqttClient.subscribe("temp"))

    elif args.l:
        IoTTClient = await Client.create()
        load = 10000
        while True:
            await asyncio.sleep(1/load)
            asyncio.create_task(IoTTClient.httpClient.request("GET", 'http://' + TRANSLATOR_ADDRESS + '/service'))

    else:
        IoTTClient = await Client.create()
        await asyncio.gather(asyncio.get_running_loop().create_future(), IoTTClient.httpServer.run(),
                             runPublishLoop(IoTTClient.amqpClient), runPublishLoop(IoTTClient.mqttClient))


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
parser.add_argument('-T', dest='t', action='store_true', default=False)
parser.add_argument('-L', dest='l', action='store_true', default=False)

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
                      'unexpected check the configuration and consider restarting the program.'.format(
                    protocol['name']))
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

sendTimes = []

SERVER_ADDRESS = "192.168.0.103"
CLIENT_ADDRESS = "192.168.0.115"
TRANSLATOR_ADDRESS = "192.168.0.101"

protocols = []
IP = get_ip_address()
temperature = Temperature()
timesCoap = []
timesHttp = []
loop = asyncio.get_event_loop()
translators = {}
asyncio.run(main())

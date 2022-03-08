import time
import json
import argparse
from os.path import exists
from sys import argv
import asyncio


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

if CoAP_Enable:
    if translator:
        from translators.CoAP import Outbound as COAP_OUTPUT
        from translators.CoAP import Inbound as COAP_INPUT
    elif client:
        from clients.CoAP import Provider as COAP_OUTPUT
        from clients.CoAP import Consumer as COAP_INPUT
    CoAP_Input = COAP_INPUT()
    CoAP_Output = COAP_OUTPUT()
if MQTT_Enable:
    if translator:
        from translators.MQTT import Outbound as MQTT_OUTPUT
        from translators.MQTT import Inbound as MQTT_INPUT
    elif client:
        from clients.MQTT import Provider as MQTT_OUTPUT
        from clients.MQTT import Consumer as MQTT_INPUT
    MQTT_Input = MQTT_INPUT()
    MQTT_Output = MQTT_OUTPUT()
if AMQP_Enable:
    if translator:
        from translators.AMQP import Outbound as AMQP_OUTPUT
        from translators.AMQP import Inbound as AMQP_INPUT
    elif client:
        from clients.AMQP import Provider as AMQP_OUTPUT
        from clients.AMQP import Consumer as AMQP_INPUT
    AMQP_Input = AMQP_INPUT()
    AMQP_Output = AMQP_OUTPUT()
if HTTP_Enable:
    if translator:
        from translators.HTTP import Outbound as HTTP_OUTPUT
        from translators.HTTP import inbound as HTTP_INPUT
    elif client:
        from clients.HTTP import Provider as HTTP_OUTPUT
        from clients.HTTP import Consumer as HTTP_INPUT  # TODO Find HTTP/S library that provides needed features for this project
    HTTP_Input = HTTP_INPUT()
    HTTP_Output = HTTP_OUTPUT()
if translator:
    import translators.core as core
if client:
    import clients.core as core
if any([CoAP_Provide, MQTT_Provide, AMQP_Provide, HTTP_Provide]):
    provider = True
    from gpiozero import CPUTemperature
    temperature = CPUTemperature()

# Shamelessly stolen from documentation to test CoAP functionality
# https://aiocoap.readthedocs.io/en/latest/examples.html
# DO NOT USE OR SUBMIT THIS CODE




import logging
import asyncio

from aiocoap import *

logging.basicConfig(level=logging.INFO)

async def main():
    protocol = await Context.create_client_context()

    request = Message(code=GET, uri='coap://192.168.0.104/temp')

    try:
        response = await protocol.request(request).response
    except Exception as e:
        print('Failed to fetch resource:')
        print(e)
    else:
        print('Result: %s\n%r'%(response.code, response.payload))

if __name__ == "__main__":
    asyncio.run(main())
#    asyncio.get_event_loop().run_forever()  # Test fix as per SO thread

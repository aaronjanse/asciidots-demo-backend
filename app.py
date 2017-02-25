import asyncio
import websockets

import threading
import time

import os

from dots import __main__ as dots_inter_file

number_of_sockets = 0


async def handle_sockets(websocket, path):
    global number_of_sockets

    number_of_sockets += 1

    print("Socket Count: {0}".format(number_of_sockets))

    if number_of_sockets > 25:
        await websocket.send("Sorry, too many people are connected to the server.")

        number_of_sockets -= 1
        return

    pending_txt = ''
    pending_input = False

    input_result = 0
    input_done = False

    finished = False

    # I am purposefully ignoring the text parameter
    def input_func(text):
        nonlocal pending_input
        nonlocal input_done
        nonlocal input_result

        while pending_input:
            time.sleep(0.1)

        pending_input = True
        input_done = False

        while not input_done:
            time.sleep(0.1)

        pending_input = False

        if input_result == '':
            input_result = '0'

        return input_result

    def response_func(text_='', newline=True):
        nonlocal pending_txt

        if text_ is None:
            text = ''
        else:
            text = text_

        text = str(text)

        if newline:
            text += '\n'

        pending_txt += text

    def run_interpreter():
        nonlocal finished

        try:
            dots_interpreter.run()
        except Exception as e:
            print('error caught!')
            print(str(e))

        finished = True

    dots_inter = None
    inter_thread = None

    stopping = False

    while True:
        message = await websocket.recv()

        tokens = message.split(';')

        instruction = tokens[0]

        if instruction == 'run':
            if len(tokens) < 2:
                continue

            program = ';'.join(tokens[1:]).split('\n')

            program = [li if len(li) > 0 else ' ' for li in program]

            dots_interpreter = None

            try:
                dots_interpreter = dots_inter_file.DotsInterpreter(program, logging_func=response_func, input_func=input_func)
            except Exception as e:
                await websocket.send('---Starting---\n')

                await websocket.send('error during preprocessing!\n')
                await websocket.send('(stacktrace hidden due to cross origin security reasons)\n')
                await websocket.send('>>> try to see if there are any problems with things such as lines starting with \'%\'\n')

                finished = True

                continue

            inter_thread = threading.Thread(target=run_interpreter, daemon=True)

            inter_thread.start()

            await websocket.send('---Starting---\n')
        elif instruction == 'stop' or (finished and pending_txt == ''):
            if dots_interpreter is not None:
                dots_interpreter.terminate()

                inter_thread.join()

            pending_txt = ''

            await websocket.send('---Stopped---\n\n')

            finished = False
        elif instruction == 'update':
            if stopping:
                stopping = False
            elif pending_input and not input_done:
                await websocket.send('input;')

                input_result = await websocket.recv()
                input_done = True
            elif pending_txt != '':
                await websocket.send('out;' + pending_txt)

                pending_txt = ''
    # except websockets.exceptions.ConnectionClosed as e:
    #     print('exception caught:')
    #     print(e)
    #     dots_interpreter.terminate()
    #     inter_thread.join()

    number_of_sockets -= 1

print('Starting server...')
start_server = websockets.serve(handle_sockets, '0.0.0.0', int(os.environ['PORT']) or 5000)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()

print('Server Running!')

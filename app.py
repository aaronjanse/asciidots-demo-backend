import asyncio
import websockets

import threading
import time

#### Backend Server ####

import os

os.chdir('./asciidots')

from asciidots.dots.environement import Env
from asciidots.dots.interpreter import AsciiDotsInterpreter
from asciidots.dots.callbacks import IOCallbacksStorageConstructor

import ssl

number_of_sockets = 0


def nop(*args, **kwargs):
    pass


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

    interpreter = None
    interpreter_thread = None

    def input_func():
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

    def on_microtick(dot):
        nonlocal interpreter
        nonlocal pending_txt

        time.sleep(0.05)  # small delay for autostep

        debug_lines = 80

        d_l = []
        for idx in reversed(range(len(interpreter.env.dots))):
            d = interpreter.env.dots[idx]
            if not d.state.is_dead():
                d_l.append((d.pos.x, d.pos.y))

        special_char = False

        last_blank = False

        display_y = 0

        pending_txt += ';start_debug;'

        for y in range(len(interpreter.env.world.map)):
            if display_y > debug_lines - 2:
                break

            if len(''.join(interpreter.env.world.map[y]).rstrip()) < 1:
                if last_blank:
                    continue
                else:
                    last_blank = True
            else:
                last_blank = False

            for x in range(len(interpreter.env.world.map[y])):
                char = interpreter.env.world.map[y][x]

                if char == ' ':
                    pending_txt += ' '
                elif (x, y) in d_l:
                    pending_txt += '\033[0;31m' + char + '\033[0m'  # Red
                elif char.isLibWarp():
                    pending_txt += '\033[0;32m' + char + '\033[0m'  # Green
                elif char.isWarp():
                    pending_txt += '\033[0;33m' + char + '\033[0m'  # Yellow
                elif char in '#@~' or char.isOper():
                    pending_txt += '\033[0;34m' + char + '\033[0m'  # Blue
                elif char != '\n':
                    pending_txt += char  # White

            pending_txt += '\n'
            display_y += 1

        pending_txt += ';end_debug;'

    def run_interpreter():
        nonlocal finished

        try:
            interpreter.run()
        except websockets.exceptions.ConnectionClosed as e:
            pass
        except Exception as e:
            print('error caught!')
            print('--- start error message ---')
            # print(e.__dict__)
            raise e
            print('--- end error message ---')

        finished = True

    stopping = False

    try:
        while True:
            message = await websocket.recv()

            tokens = message.split(';')

            instruction = tokens[0]

            if instruction == 'run':
                if len(tokens) < 2:
                    continue

                program = ';'.join(tokens[1:]).split('\n')

                program = [li if len(li) > 0 else ' ' for li in program]
                program = '\n'.join(program)

                if interpreter is not None:
                    await websocket.send('---Stopping---\n')
                    interpreter.terminate()

                    interpreter_thread.join()

                pending_txt = ''

                await websocket.send('---Starting---\n')

                io_callbacks = IOCallbacksStorageConstructor(
                    get_input=input_func, on_output=response_func, on_finish=nop, on_error=nop, on_microtick=on_microtick)

                try:
                    env = Env()
                    env.io = io_callbacks
                    interpreter = AsciiDotsInterpreter(
                        env, program, './asciidots', run_in_parallel=True)
                except Exception as e:
                    io_callbacks.on_finish()

                    await websocket.send('error during preprocessing!\n')
                    await websocket.send('(stacktrace hidden due to cross origin security reasons)\n')
                    await websocket.send(str(e))
                    print(e)
                    await websocket.send('>>> try to see if there are any problems with things such as lines starting with \'%\'\n')

                    finished = True

                interpreter_thread = threading.Thread(
                    target=run_interpreter, daemon=True)

                interpreter_thread.start()

            elif instruction == 'stop' or (finished and pending_txt == ''):
                if interpreter is not None:
                    interpreter.terminate()

                    interpreter_thread.join()

                pending_txt = ''

                await websocket.send('---Stopped---\n\n')

                finished = False
            elif instruction == 'update':
                if stopping:
                    stopping = False
                elif pending_txt != '':
                    if len(pending_txt) > 2**16:
                        # Way too much text. We will cut some of it out to help reduce bandwidth
                        pending_txt = pending_txt[128:] + \
                            '...' + pending_txt[:128]
                        print('---output clipped!---')

                    await websocket.send('out;' + pending_txt)

                    pending_txt = ''
                elif pending_input and not input_done:
                    await websocket.send('input;')

                    got_result = False

                    while not got_result:
                        input_result = await websocket.recv()

                        if input_result != 'update;':
                            input_done = True
                            got_result = True
    except websockets.exceptions.ConnectionClosed as e:
        if interpreter is not None:
            interpreter.terminate()
            interpreter_thread.join()
    except Exception as e:
        print('exception caught:')
        print(str(e))

        if interpreter is not None:
            interpreter.terminate()
            interpreter_thread.join()

        print('terminated thread')

    number_of_sockets -= 1

print('Starting server...')

port = 5000

try:
    port = os.environ['PORT']
except:
    pass

start_server = websockets.serve(handle_sockets, '0.0.0.0', int(port))

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()

print('Server Running!')

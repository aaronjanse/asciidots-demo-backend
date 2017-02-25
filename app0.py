from flask import Flask, request
from flask_sockets import Sockets

import threading


app = Flask(__name__, static_url_path='')
sockets = Sockets(app)

message = ""

number_of_sockets = 0


def log_callback_custom(ws, txt):
    # print("callback")
    message = txt


@sockets.route('/interpret')
def handler_socket(ws):
    global number_of_sockets

    number_of_sockets += 1

    if number_of_sockets > 5:
        if number_of_sockets < 15:
            ws.send("Sorry, too many interpreters running on the server")

        number_of_sockets -= 1
        return

    dots_interpreter = None
    t = None

    while not ws.closed:
        message = ws.receive()

        print(message)

        tokens = message.split(';')

        instruction, args = tokens[0], tokens[1:]

        if len(args) != 1:
            continue

        arg = args[0]

        if instruction == 'run':
            program = arg.split('\n')

            def response_func(text, newline=True):
                if newline:
                    text += '\n'

                ws.send(text)

            dots_interpreter = DotsInterpreter(program, logging_func=response_func)

            t = threading.Thread(target=dots_interpreter.run, daemon=True)

            t.start()

            ws.send('---Starting---')
        elif instruction == 'stop':
            dots_interpreter.terminate()

            t.join()

            ws.send('---Stopped---')

        # print(message.split('\n'))

        # main([], auto=True, deflines=message.split('\n'), callback=log_callback_custom)
        # ws.send("Hi")

    number_of_sockets -= 1


@app.route('/')
def root():
    return app.send_static_file('index.html')


if __name__ == "__main__":
    # app.run()
    if True:
        from gevent import pywsgi
        from geventwebsocket.handler import WebSocketHandler
        server = pywsgi.WSGIServer(('', 5000), app, handler_class=WebSocketHandler)
        server.serve_forever()

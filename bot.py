import websocket, json


SOCKET = "wss://stream.binance.com:9443/ws/btcusdt@kline_1m"
#SOCKET = "ws://echo.websocket.org/"

def on_open(ws):
    print("opened connection")
    
def on_close(ws, test, testing):
    print("closed connection")
def on_message(ws, message):
    print("received message")
    json_message = json.loads(message)
    print(json_message["e"])
    
websocket.enableTrace(True)

ws = websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message)
ws.run_forever()

# import websocket
# try:
#     import thread
# except ImportError:
#     import _thread as thread
# import time

# def on_message(ws, message):
#     print(message)

# def on_error(ws, error):
#     print(error)

# def on_close(ws):
#     print("### closed ###")

# def on_open(ws):
#     def run(*args):
#         for i in range(3):
#             time.sleep(1)
#             ws.send("Hello %d" % i)
#         time.sleep(1)
#         ws.close()
#         print("thread terminating...")
#     thread.start_new_thread(run, ())

# if __name__ == "__main__":
#     websocket.enableTrace(True)
#     ws = websocket.WebSocketApp("ws://echo.websocket.org/",
#                               on_open = on_open,
#                               on_message = on_message,
#                               on_error = on_error,
#                               on_close = on_close)

#     ws.run_forever()
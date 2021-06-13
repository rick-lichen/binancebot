# -*- coding: utf-8 -*-
"""tradingbot.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1vCV3vdVekahBPB5khrcmxPufUbXXNVoE
"""

# pip install websocket_client

# #For TA Lib
# url = 'https://anaconda.org/conda-forge/libta-lib/0.4.0/download/linux-64/libta-lib-0.4.0-h516909a_0.tar.bz2'
# !curl -L $url | tar xj -C /usr/lib/x86_64-linux-gnu/ lib --strip-components=1
# url = 'https://anaconda.org/conda-forge/ta-lib/0.4.19/download/linux-64/ta-lib-0.4.19-py37ha21ca33_2.tar.bz2'
# !curl -L $url | tar xj -C /usr/local/lib/python3.7/dist-packages/ lib/python3.7/site-packages/talib --strip-components=3

# pip install python-binance

import websocket, talib, json, pprint, talib, numpy as np
from binance.client import Client
from binance.enums import *
from datetime import datetime
import pync
import sys


INTERVAL = "1m"
TRADE_SYMBOL = "maticusdt"

SOCKET = "wss://stream.binance.com:9443/ws/"+TRADE_SYMBOL+"@kline_"+INTERVAL
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
BB_PERIOD = 20
BB_STD = 2
STOP_LOSS = 0.1

bought_price = None

TRADE_QUANTITY = 8


API_KEY = "ARs15CFBgEaUaHYCbtlkHooZ7zDAR7uCatdznUmvlfp0LADVPa0tjXVoVDol6MIg"
API_SECRET = "K9yioiGEimDd36RMQn4Qizt3OzDuzMOAkQhXKF38mX46wP63YAYghsufa3X8zodV"

closes = []
in_position = False

client = Client(API_KEY, API_SECRET, tld="com")

#strategy metrics 
# last_upper = 0
# last_lower = 0
# last_rsi = 0
def order(side, quantity, symbol, order_type = ORDER_TYPE_MARKET):
    global bought_price
    try: 
        print("sending order for ")
        print(symbol)
        response = client.create_order(symbol= symbol, side= side, type = order_type, quantity = quantity)
        print(response)
        if response["status"] == "FILLED" and response["side"] == "BUY":
            print("Buy Filled")
            for fills_list in response["fills"]:
                #order successful
                bought_price = fills_list["price"]
                print("bought_price = {}".format(bought_price))
    except Exception as e:
        print(e)
        sys.exit() #terminate program
        return False
    return True

def calcBB(np_closes):
  #bollinger bands
  global last_upper, last_lower
  upperband, middleband, lowerband = talib.BBANDS(np_closes, timeperiod=BB_PERIOD, nbdevup=BB_STD, nbdevdn=BB_STD, matype=0) #2stdev, simple moving average
  last_upper = upperband[-1]
  last_lower = lowerband[-1]
  print("Last upperband = {}, lowerband = {}".format(last_upper, last_lower))

def calcRSI(np_closes):
  #RSI
  global last_rsi
  rsi = talib.RSI(np_closes, RSI_PERIOD)
  #print("RSI so far = {} ".format(rsi))
  last_rsi = rsi[-1]
  print("Last RSI = {}".format(last_rsi))

def getData():
  global closes
  klines = client.get_historical_klines(TRADE_SYMBOL.upper(), INTERVAL, "20m ago UTC")
  closing = []
  for candles in klines:
    closing.append(candles[4])
  print(closing)
  closes = np.append(closing, closes)  #add historical data to closes global variable
def checkStrat(current):
    global in_position, bought_price, STOP_LOSS
    if len(closes) > RSI_PERIOD and len(closes) > BB_PERIOD:

        if not in_position:
            if last_rsi < RSI_OVERSOLD and float(current) < last_lower:
                print("BUY!!")
                #binance logic
                pync.notify('Buy condition fulfilled')
                order_succeeded = order(SIDE_BUY, TRADE_QUANTITY, str.upper(TRADE_SYMBOL))
                if order_succeeded:
                    in_position = True
                else:
                    sys.exit() #terminate program
        else:
            #Check stop loss
            if float(current) <= float(bought_price)*(1-STOP_LOSS):
                print("STOP LOSS!!")
                #binance logic
                pync.notify('Stop loss condition fulfilled')
                order_succeeded = order(SIDE_SELL, TRADE_QUANTITY, str.upper(TRADE_SYMBOL))
                if order_succeeded:
                    in_position = False
                else:
                    sys.exit() #terminate program
            elif last_rsi > RSI_OVERBOUGHT and float(current) > last_upper:
                print("SELL!!")
                #binance logic
                pync.notify('Sell condition fulfilled')
                order_succeeded = order(SIDE_SELL, TRADE_QUANTITY, str.upper(TRADE_SYMBOL))
                if order_succeeded:
                    in_position = False
                else:
                    sys.exit() #terminate program

def on_open(ws):
    print("opened connection")
    getData()
def on_close(ws):
    print("closed connection")
def on_message(ws, message):
    #every 2000ms, this code will execute
    global closes
    json_message = json.loads(message)
    #pprint.pprint(json_message)

    #Parsing message
    candle = json_message["k"]
    is_candle_closed = candle["x"]
    close = candle["c"] #note that this should(?) also be the current price
    checkStrat(close)

    if is_candle_closed:
      #every TIME_INTERVAL, this will be executed
      print(datetime.now())
      print("candle closed at {}".format(close))
      closes = np.append(closes, float(close)) 
      np_closes = np.array(closes).astype(float)
      #calculate new metrics
      calcRSI(np_closes)
      calcBB(np_closes)

      
#websocket.enableTrace(True)
ws = websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message)
ws.run_forever()
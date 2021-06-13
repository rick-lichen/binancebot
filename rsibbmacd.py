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

#packages:
# python-binance
# TA-Lib
# numpy
# websocket_client

import websocket, talib, json, pprint, talib, numpy as np
from binance.client import Client
from binance.enums import *
from datetime import datetime
# import pync
import sys
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore


cred = credentials.Certificate("binance-7548e-firebase-adminsdk-cyqoy-1705d26e47.json")
firebase_admin.initialize_app(cred)


db = firestore.client()

collection_ref = db.collection(u'trades')



INTERVAL = "1m"
TRADE_SYMBOL = "maticusdt"

SOCKET = "wss://stream.binance.com:9443/ws/"+TRADE_SYMBOL+"@kline_"+INTERVAL
#strategy config
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
BB_PERIOD = 20
BB_STD = 2

STOP_LOSS = 0.1
bought_price = None
sold_price = None
TRADE_QUANTITY = 9
# test_order = False


API_KEY = "ARs15CFBgEaUaHYCbtlkHooZ7zDAR7uCatdznUmvlfp0LADVPa0tjXVoVDol6MIg"
API_SECRET = "K9yioiGEimDd36RMQn4Qizt3OzDuzMOAkQhXKF38mX46wP63YAYghsufa3X8zodV"

closes = []
in_position = False

client = Client(API_KEY, API_SECRET, tld="com")

#strategy metrics 
last_upper = 0
last_lower = 0
last_rsi = 0
last_macd = 0

def order(side, quantity, symbol, order_type = ORDER_TYPE_MARKET):
    global bought_price
    try: 
        print("sending order for ", symbol)
        response = client.create_order(symbol= symbol, side= side, type = order_type, quantity = quantity)
        print(response)
        if response["status"] == "FILLED":
            #record trade in firestore database
            for fills_list in response["fills"]:
                #order successful
                collection_ref.add({
                    u'time': response["transactTime"], 
                    u'symbol': response["symbol"],
                    u'order_id': response["orderId"],
                    u'type': response["type"],
                    u'side': response["side"],
                    u'price': fills_list["price"],
                    u'quantity': fills_list["qty"],
                    u'commission': fills_list["commission"],
                    u'commission_asset': fills_list["commissionAsset"],
                    u'trade_id': fills_list["tradeId"]})
                if response["side"] == "BUY":
                    print("Buy Filled")
                    bought_price = fills_list["price"]
                    print("bought_price = {}".format(bought_price))
                elif response["side"] == "SELL":
                    print("Sell Filled")
                    sold_price = fills_list["price"]
                    print("sold_price= {}".format(sold_price))
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

def calcMACDCross(np_closes):
    #MACD
    global last_macd
    macd, macdsignal, macdhist = talib.MACD(np_closes, fastperiod=12, slowperiod=26, signalperiod=9) #standard MACD settings
    #MACD crosses signal from below (bullish)
    if macd[-1] > macdsignal[-1] and macd[-2] < macdsignal[-2] :
        last_macd = 1.0
    elif macd[-1] < macdsignal[-1] and macd[-2] > macdsignal[-2]:
        last_macd = -1.0
    else:
        last_macd = 0
    print("Last MACD = {}".format(macd[-1]))
    print("Last signal = {}".format(macdsignal[-1]))
    print("Last MACDCross = {}".format(last_macd))

def getData():
    global closes, TRADE_QUANTITY, in_position, bought_price
    #get historical klines
    klines = client.get_historical_klines(TRADE_SYMBOL.upper(), INTERVAL, "40m ago UTC")
    closing = []
    for candles in klines:
        closing.append(candles[4])      #append closing price to closing array
    closes = np.append(closing, closes)  #add historical data to closes global variable
    #get historical trades
    query = collection_ref.order_by(
        u'time', direction=firestore.Query.DESCENDING).limit(1)
    docs = query.stream()
    has_history = False
    for doc in docs:
        #if it enters here, it's not empty
        has_history = True
        historical_trades = doc.to_dict()
        print("Historical Trades: ", historical_trades)
        if historical_trades["side"] == "BUY":
            print("Previously bought into a trade!")
            in_position = True
            TRADE_QUANTITY = float(historical_trades["quantity"]) #quantity = most recent trade to close it out
            bought_price = float(historical_trades["price"])
        elif historical_trades["side"] == "SELL":
            print("Previously sold a trade. Not in position")
    if not has_history:
        print("No historical trades found")
    

def checkStrat(current):
    global in_position, bought_price, STOP_LOSS
    if len(closes) >= 40:    # if have enough historical data needed for MACD
        if not in_position:
            print("checking for buy condition")
            if last_macd > 0.0 or (last_rsi < RSI_OVERSOLD and float(current) < last_lower):
                print("BUY!!")
                #binance logic
                # pync.notify('Buy condition fulfilled')
                # print('\a', end='', flush=True) #plays sound?
                order_succeeded = order(SIDE_BUY, TRADE_QUANTITY, str.upper(TRADE_SYMBOL))
                if order_succeeded:
                    in_position = True
                else:
                    sys.exit() #terminate program
        else:
            #Check stop loss
            print("checking for sell condition")
            if float(current) <= float(bought_price)*(1-STOP_LOSS):
                print("STOP LOSS!!")
                #binance logic
                # pync.notify('Stop loss condition fulfilled')
                order_succeeded = order(SIDE_SELL, TRADE_QUANTITY, str.upper(TRADE_SYMBOL))
                if order_succeeded:
                    in_position = False
                else:
                    sys.exit() #terminate program
            elif last_macd < 0.0:
                print("SELL!!")
                #binance logic
                # pync.notify('Sell condition fulfilled')
                # print('\a', end='', flush=True) #plays sound?
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
    if is_candle_closed:
      #every TIME_INTERVAL, this will be executed
      print(datetime.now())
      print("candle closed at {}".format(close))
      closes = np.append(closes, float(close)) 
      np_closes = np.array(closes).astype(float)
      #calculate new metrics
      calcRSI(np_closes)
      calcBB(np_closes)
      calcMACDCross(np_closes)
      checkStrat(close)

      
#websocket.enableTrace(True)
ws = websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message)
ws.run_forever()
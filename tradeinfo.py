import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

#database
cred = credentials.Certificate("binance-7548e-firebase-adminsdk-cyqoy-1705d26e47.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
collection_ref = db.collection(u'trades')
doc = collection_ref.get()
print("number of trades = ", len(doc))
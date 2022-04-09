# Import dependencies
import time
import pyodbc
from OpenSSL import crypto
import string
import random
from zeep import Client
import os
import logging.config
import requests
import json
import urllib.parse

# Set variables
StoredID = 0

# Import private key
key_file = open("/run/secrets/keyfile", "r")
key = key_file.read()
key_file.close()
pkey = crypto.load_privatekey(crypto.FILETYPE_PEM, key)

# Load SOAP Client
zeepclient = Client("https://wecr.sepay.nl/v2/wecr.asmx?WSDL")

if os.environ['Messaging'] == 'msteams':
    headers = {'Content-Type': 'application/json'}

# Debug
if os.environ['DEBUG'] == True:
    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'verbose': {
                'format': '%(name)s: %(message)s'
            }
        },
        'handlers': {
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'verbose',
            },
        },
        'loggers': {
            'zeep.transports': {
                'level': 'DEBUG',
                'propagate': True,
                'handlers': ['console'],
            },
        }
    })

server = os.environ['SQLServer']
database = os.environ['SQLDatabase']
username = os.environ['SQLUser']
password = os.environ['SQLPassword']

cnxn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+ password)
cursor = cnxn.cursor()

while True:

    time.sleep(1)

    # Grab last entry from Payment, and print the DocumentID, PaymentTypeID and Amount
    cursor.execute("SELECT DocumentID, PaymentTypeID, Amount FROM "+database+".dbo.Payment ORDER BY DocumentID DESC")
    row = cursor.fetchone()

    if StoredID == 0:
        StoredID = row[0]
    
    else:
        if StoredID < row[0]:
            StoredID = row[0]

            if row[1] == os.environ['PaymentID']:
                
                # Start Transaction
                while True:
                
                    # Convert Amount into string with 2 decimals, as required by the API
                    ConvertedAmount = "{:.2f}".format(row[2])

                    # Generate TransactionRef
                    TransactionRef = ''.join(random.choices(string.ascii_uppercase + string.digits, k=9))

                    # Create Signature
                    SignatureData = f"0;2;{os.environ['SepayLogin']};{str(os.environ['SID'])};{TransactionRef};{str(row[0])};{ConvertedAmount};"
                    SignatureSign = crypto.sign(pkey, SignatureData, "sha256")

                    RequestResult = Client.service.StartTransaction(key_index=0, version="2", login=os.environ['SepayLogin'], sid=os.environ['SID'], transactionref=TransactionRef, merchantref=str(row[0]), amount=ConvertedAmount, signature=SignatureSign)

                    # Check status code and retry if neccesary 
                    match RequestResult["status"]:
                        case "00":
                            if os.environ['Messaging'] == 'msteams':
                                payload = json.dumps('"{"@type":"MessageCard","@context":"http://schema.org/extensions","themeColor":"f7dda4","summary":"Nieuwe transactie: '+TransactionRef+'","title":"Nieuwe transactie: '+TransactionRef+'","sections":[{"facts":[{"name":"Transactienummer","value":"'+TransactionRef+'"},{"name":"SID","value":"'+os.environ['SID']+'"},{"name":"Betalingskenmerk","value":"'+str(row[0])+'"},{"name":"Bedrag","value":"'+ConvertedAmount+'"}]}]}')
                                response = requests.request("POST", os.environ['MSTeamsURL'], headers=headers, data=payload)
                            break
                        case "01":
                            print("Some of the required fields are missing: "+ RequestResult['message'])
                            break
                        case "02":
                            print("Signature failed")
                            break
                        case "04":
                            print("Invalid parameters, retrying...")
                            continue
                        case "06":
                            print("Duplicate request")
                            break
                        case "07":
                            print("Terminal not active or not enabled and/or authorized for transactions through WECR")
                            break
                        case "11":
                            print("Pending request for this terminal.")
                            break
                        case "99":
                            print("Undefined error")
                            break

                # Get Transaction Status
                SignatureData = f"0;2;{os.environ['SepayLogin']};{str(os.environ['SID'])};{TransactionRef}"
                SignatureSign = crypto.sign(pkey, SignatureData, "sha256")

                while True:
                    time.sleep(2)

                    RequestResult = Client.service.StartTransaction(key_index=0, version="2", login=os.environ['SepayLogin'], sid=os.environ['SID'], transactionref=TransactionRef, signature=SignatureSign)

                    match RequestResult["status"]:
                        case "00":
                            if os.environ['Messaging'] == 'msteams':
                                encodedurl = urllib.parse.quote(RequestResult["ticket"])
                                payload = json.dumps('{"@type":"MessageCard","@context":"http://schema.org/extensions","themeColor":"f7dda4","summary":"Transactie geslaagd: '+TransactionRef+'","title":"Transactie geslaagd: '+TransactionRef+'","sections":[{"facts":[{"name":"Transactienummer","value":"'+TransactionRef+'"},{"name":"SID","value":"'+os.environ['SID']+'"},{"name":"Betalingskenmerk","value":"'+str(row[0])+'"},{"name":"Bedrag","value":"'+ConvertedAmount+'"},{"name":"Datum","value":"'+RequestResult["transactiontime"]+'"},{"name":"Kaart","value":"'+RequestResult["brand"]+'"}]}],"potentialAction":[{"@type":"OpenUri","name":"Print Bon","targets":[{"os":"windows","uri":"http://127.0.0.1:6543/?data='+encodedurl+'"}]}]}')
                                response = requests.request("POST", os.environ['MSTeamsURL'], headers=headers, data=payload)
                            continue
                        case "01":
                            print("Some of the required fields are missing: "+ RequestResult['message'])
                            break
                        case "02":
                            print("Signature failed")
                            break
                        case "04":
                            print("Invalid parameters, retrying...")
                            continue
                        case "07":
                            print("Terminal not active or not enabled and/or authorized for transactions through WECR")
                            break
                        case "13":
                            print("Transaction failed")
                            break
                        case "14":
                            print("This transaction was canceled. Reason:" + RequestResult['message'])
                            break
                        case "15":
                            print("Transaction is not finished and has not been canceled yet")
                            continue
                        case "17":
                            print("Transaction already in progress, cannot be canceled anymore")
                            continue
                        case "99":
                            print("Undefined error")
                            break
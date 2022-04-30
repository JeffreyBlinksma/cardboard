# Import dependencies
import time
import pyodbc
import string
import random
from zeep import Client
import os
import logging.config
import requests
import json
import urllib.parse
import gettext
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization 
from cryptography import x509
import cryptography.exceptions

# Set variables
StoredID = 0
TransactionerrorCodes = json.load(open("./lang/Transactionerror/en_US.json"))

# Set the local directory
localedir = './locale'

# Set up your magic function
translate = gettext.translation('appname', localedir, fallback=True)
_ = translate.gettext

# Import private key
with open("/run/secrets/keyfile", "rb") as f:
    pkey = serialization.load_pem_private_key(
        f.read(),
        password=None,
        backend=default_backend()
    )

# Import other pubkeys
with open("./pubkeys/sepay.pem", "rb") as f:
    sepaypubkey = x509.load_pem_x509_certificate(f.read()).public_key()

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
username = os.environ['SQLUsername']
password = os.environ['SQLPassword']

cnxn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+password)
cursor = cnxn.cursor()

while True:

    time.sleep(1)

    # Grab last entry from Payment, and print the DocumentID, PaymentTypeID and Amount
    cursor.execute("SELECT DocumentID, PaymentTypeID, Amount FROM dbo.Payment ORDER BY DocumentID DESC")
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
                    SignatureData = f"0;2;{str(os.environ['MijnSepayUsername'])};{str(int(os.environ['SID']))};{TransactionRef};{str(row[0])};{ConvertedAmount};"
                    SignatureSign = pkey.sign(SignatureData.encode(), padding.PKCS1v15(), hashes.SHA256())

                    RequestResult = zeepclient.service.StartTransaction(key_index=0, version="2", login=os.environ['MijnSepayUsername'], sid=int(os.environ['SID']), transactionref=TransactionRef, merchantref=str(row[0]), amount=ConvertedAmount, signature=SignatureSign)

                    ResponseSignatureData = f"{RequestResult['key_index']};{RequestResult['version']};{RequestResult['login']};{RequestResult['sid']};{RequestResult['transactionref']};{RequestResult['merchantref']};{RequestResult['amount']};{RequestResult['status']};{RequestResult['message']};{RequestResult['terminalip']};{RequestResult['terminalport']}"
                    try:
                        sepaypubkey.verify(RequestResult["signature"], str.encode(ResponseSignatureData), padding.PKCS1v15(), hashes.SHA256())
                    except cryptography.exceptions.InvalidSignature:
                        print("Received signature invalid.")
                        break

                    # Check status code and retry if neccesary 
                    match RequestResult["status"]:
                        case "00":
                            if os.environ['Messaging'] == 'msteams':
                                payload = json.dumps('"{"@type":"MessageCard","@context":"http://schema.org/extensions","themeColor":"f7dda4","summary":"'+_("New Transaction")+': '+TransactionRef+'","title":"'+_("New Transaction")+': '+TransactionRef+'","sections":[{"facts":[{"name":"'+_("Transaction ID")+'","value":"'+TransactionRef+'"},{"name":"SID","value":"'+os.environ['SID']+'"},{"name":"'+_("Payment ID")+'","value":"'+str(row[0])+'"},{"name":"'+_("Amount")+'","value":"'+ConvertedAmount+'"}]}]}')
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
                SignatureData = f"0;2;{str(os.environ['MijnSepayUsername'])};{str(int(os.environ['SID']))};{TransactionRef}"
                SignatureSign = pkey.sign(SignatureData.encode(), padding.PKCS1v15(), hashes.SHA256())

                if RequestResult["status"] == "00":

                    while True:
                        time.sleep(2)

                        RequestResult = zeepclient.service.StartTransaction(key_index=0, version="2", login=os.environ['MijnSepayUsername'], sid=int(os.environ['SID']), transactionref=TransactionRef, signature=SignatureSign)

                        ResponseSignatureData = f"{RequestResult['key_index']};{RequestResult['version']};{RequestResult['login']};{RequestResult['sid']};{RequestResult['transactionref']};{RequestResult['merchantref']};{RequestResult['amount']};{RequestResult['transactiontime']};{RequestResult['transactionerror']};{RequestResult['transactionresult']};{RequestResult['status']};{RequestResult['message']};{RequestResult['brand']};{RequestResult['ticket']}"
                        try:
                            sepaypubkey.verify(RequestResult["signature"], str.encode(ResponseSignatureData), padding.PKCS1v15(), hashes.SHA256())
                        except cryptography.exceptions.InvalidSignature:
                            print("Received signature invalid.")
                            break

                        match RequestResult["status"]:
                            case "00":
                                if os.environ['Messaging'] == 'msteams':
                                    encodedurl = urllib.parse.quote(RequestResult["ticket"])
                                    payload = json.dumps('{"@type":"MessageCard","@context":"http://schema.org/extensions","themeColor":"f7dda4","summary":"'+_("Transaction succeeded")+': '+TransactionRef+'","title":'+_("Transaction succeeded")+': '+TransactionRef+'","sections":[{"facts":[{"name":"'+_("Transaction ID")+'","value":"'+TransactionRef+'"},{"name":"SID","value":"'+os.environ['SID']+'"},{"name":"'+_("Payment ID")+'","value":"'+str(row[0])+'"},{"name":"'+_("Amount")+'","value":"'+ConvertedAmount+'"},{"name":"'+_("Amount")+'","value":"'+RequestResult["transactiontime"]+'"},{"name":"'+_("Brand")+'","value":"'+RequestResult["brand"]+'"}]}],"potentialAction":[{"@type":"OpenUri","name":"'+_("Print Receipt")+'","targets":[{"os":"windows","uri":"http://127.0.0.1:6543/?data='+encodedurl+'"}]}]}')
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
                            case "07":
                                print("Terminal not active or not enabled and/or authorized for transactions through WECR")
                                break
                            case "13":
                                print("Transaction failed")
                                if os.environ['Messaging'] == 'msteams':
                                    encodedurl = urllib.parse.quote(RequestResult["ticket"])
                                    payload = json.dumps('{"@type":"MessageCard","@context":"http://schema.org/extensions","themeColor":"f7dda4","summary":"'+_("Transaction Failed")+': '+TransactionRef+'","title":"'+_("Transaction Failed")+': '+TransactionRef+'","sections":[{"facts":[{"name":"'+_("Transaction ID")+'","value":"'+TransactionRef+'"},{"name":"SID","value":"'+str(int(os.environ['SID']))+'"},{"name":"'+_("Payment ID")+'","value":"'+str(row[0])+'"},{"name":"'+_("Amount")+'","value":"'+ConvertedAmount+'"},{"name":"'+_("Date")+'","value":"'+RequestResult["transactiontime"]+'"},{"name":"'+_("Brand")+'","value":"'+RequestResult["brand"]+'"},{"name":"'+_("Message")+'","value":"'+RequestResult["message"]+'"},{"name":"'+_("Reason")+'","value":"'+TransactionerrorCodes[str(int(RequestResult["transactionerror"]))]+'"}]}]}')
                                    response = requests.request("POST", os.environ['MSTeamsURL'], headers=headers, data=payload)
                                break
                            case "14":
                                print("This transaction was canceled. Reason:" + RequestResult['message'])
                                if os.environ['Messaging'] == 'msteams':
                                    encodedurl = urllib.parse.quote(RequestResult["ticket"])
                                    payload = json.dumps('{"@type":"MessageCard","@context":"http://schema.org/extensions","themeColor":"f7dda4","summary":"'+_("Transaction Canceled")+': '+TransactionRef+'","title":"'+_("Transaction Canceled")+': '+TransactionRef+'","sections":[{"facts":[{"name":"'+_("Transaction ID")+'","value":"'+TransactionRef+'"},{"name":"SID","value":"'+str(int(os.environ['SID']))+'"},{"name":"'+_("Payment ID")+'","value":"'+str(row[0])+'"},{"name":"'+_("Amount")+'","value":"'+ConvertedAmount+'"},{"name":"'+_("Date")+'","value":"'+RequestResult["transactiontime"]+'"},{"name":"'+_("Message")+'","value":"'+RequestResult["message"]+'"}]}]}')
                                    response = requests.request("POST", os.environ['MSTeamsURL'], headers=headers, data=payload)
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

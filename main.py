# Import dependencies
import time
import pyodbc
from OpenSSL import crypto
import string
import random
from zeep import Client
import os
import logging.config
import pymsteams
import asyncio

# Set variables
StoredID = 0

# Import private key
key_file = open("/configs/key.pem", "r")
key = key_file.read()
key_file.close()
pkey = crypto.load_privatekey(crypto.FILETYPE_PEM, key)

# Load SOAP Client
zeepclient = Client("https://wecr.sepay.nl/v2/wecr.asmx?WSDL")

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

# Import MS Teams Logging
if os.environ['LoggingService'] == 'msteams':
    loopteamsrequest = asyncio.get_event_loop()
    msteamsrequest = pymsteams.async_connectorcard(os.environ['TeamsURL'])
    msteamsrequest.color('0798D0')

    loopteamsresponse = asyncio.get_event_loop()
    msteamsresponse = pymsteams.async_connectorcard(os.environ['TeamsURL'])
    msteamsresponse.color('0798D0')

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

    if StoredID < row[0]:
        StoredID = row[0]

        if row[1] == os.environ['PaymentID']:
            
            while True:
            
                    # Convert Amount into string with 2 decimals, as required by the API
                ConvertedAmount = "{:.2f}".format(row[2])

                # Generate TransactionRef
                TransactionRef = ''.join(random.choices(string.ascii_uppercase + string.digits, k=9))

                # Notify of transaction in Teams
                msteamsrequest.title('Nieuwe transactie: ' + TransactionRef)
                msteamsrequest.text("**Login: **"+os.environ['SepayLogin']+"<br />\
                    **SID: **"+os.environ['SID']+"<br />\
                    **Login: **"+os.environ['SepayLogin']+"<br />\
                    **Referentie: **"+os.environ['TransactionRef']+"<br />\
                    **Document: **"+str(row[0])+"<br />\
                    **Bedrag: **"+ConvertedAmount)
                loopteamsrequest.run_until_complete(msteamsrequest.send())
                # Create Signature
                SignatureData = f"0;2;{os.environ['SepayLogin']};{str(os.environ['SID'])};{TransactionRef};{str(row[0])};{ConvertedAmount};"
                SignatureSign = crypto.sign(pkey, SignatureData, "sha256")

                RequestResult = Client.service.StartTransaction(key_index=0, version="2", login=os.environ['SepayLogin'], sid=os.environ['SID'], transactionref=TransactionRef, merchantref=str(row[0]), amount=ConvertedAmount, signature=SignatureSign)

                # Check status code and retry if neccesary 
                match RequestResult["status"]:
                    case 0:
                        break
                    case 1:
                        print("Some of the required fields are missing: "+ RequestResult['message'])
                        msteamsresponse.title('Mislukte transactie: ' + TransactionRef)
                        msteamsresponse.text("**Login: **"+os.environ['SepayLogin']+"<br />\
                            **SID: **"+os.environ['SID']+"<br />\
                            **Login: **"+os.environ['SepayLogin']+"<br />\
                            **Referentie: **"+os.environ['TransactionRef']+"<br />\
                            **Document: **"+str(row[0])+"<br />\
                            **Foutcode: **"+RequestResult['status'])+"<br />\
                            **Foutmelding: **"+RequestResult['message']
                        loopteamsresponse.run_until_complete(msteamsresponse.send())
                        break
                    case 2:
                        print("Signature failed")
                        msteamsresponse.title('Mislukte transactie: ' + TransactionRef)
                        msteamsresponse.text("**Login: **"+os.environ['SepayLogin']+"<br />\
                            **SID: **"+os.environ['SID']+"<br />\
                            **Login: **"+os.environ['SepayLogin']+"<br />\
                            **Referentie: **"+os.environ['TransactionRef']+"<br />\
                            **Document: **"+str(row[0])+"<br />\
                            **Foutcode: **"+RequestResult['status'])+"<br />\
                            **Foutmelding: **"+RequestResult['message']
                        loopteamsresponse.run_until_complete(msteamsresponse.send())
                        break
                    case 4:
                        print("Invalid parameters, retrying...")
                        continue
                    case 6:
                        print("Duplicate request")
                        msteamsresponse.title('Mislukte transactie: ' + TransactionRef)
                        msteamsresponse.text("**Login: **"+os.environ['SepayLogin']+"<br />\
                            **SID: **"+os.environ['SID']+"<br />\
                            **Login: **"+os.environ['SepayLogin']+"<br />\
                            **Referentie: **"+os.environ['TransactionRef']+"<br />\
                            **Document: **"+str(row[0])+"<br />\
                            **Foutcode: **"+RequestResult['status'])+"<br />\
                            **Foutmelding: **"+RequestResult['message']
                        loopteamsresponse.run_until_complete(msteamsresponse.send())
                        break
                    case 7:
                        print("Terminal not active or not enabled and/or authorized for transactions through WECR")
                        msteamsresponse.title('Mislukte transactie: ' + TransactionRef)
                        msteamsresponse.text("**Login: **"+os.environ['SepayLogin']+"<br />\
                            **SID: **"+os.environ['SID']+"<br />\
                            **Login: **"+os.environ['SepayLogin']+"<br />\
                            **Referentie: **"+os.environ['TransactionRef']+"<br />\
                            **Document: **"+str(row[0])+"<br />\
                            **Foutcode: **"+RequestResult['status'])+"<br />\
                            **Foutmelding: **"+RequestResult['message']
                        loopteamsresponse.run_until_complete(msteamsresponse.send())
                        break
                    case 11:
                        print("Pending request for this terminal.")
                        msteamsresponse.title('Mislukte transactie: ' + TransactionRef)
                        msteamsresponse.text("**Login: **"+os.environ['SepayLogin']+"<br />\
                            **SID: **"+os.environ['SID']+"<br />\
                            **Login: **"+os.environ['SepayLogin']+"<br />\
                            **Referentie: **"+os.environ['TransactionRef']+"<br />\
                            **Document: **"+str(row[0])+"<br />\
                            **Foutcode: **"+RequestResult['status'])+"<br />\
                            **Foutmelding: **"+RequestResult['message']
                        loopteamsresponse.run_until_complete(msteamsresponse.send())
                        break
                    case 99:
                        print("Undefined error")
                        msteamsresponse.title('Mislukte transactie: ' + TransactionRef)
                        msteamsresponse.text("**Login: **"+os.environ['SepayLogin']+"<br />\
                            **SID: **"+os.environ['SID']+"<br />\
                            **Login: **"+os.environ['SepayLogin']+"<br />\
                            **Referentie: **"+os.environ['TransactionRef']+"<br />\
                            **Document: **"+str(row[0])+"<br />\
                            **Foutcode: **"+RequestResult['status'])+"<br />\
                            **Foutmelding: **"+RequestResult['message']
                        loopteamsresponse.run_until_complete(msteamsresponse.send())
                        break
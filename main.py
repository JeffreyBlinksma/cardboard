# Import dependencies
from asyncore import write
import time
import pyodbc
import string
import random
import os
import logging.config
import json
import gettext
from cardterminals.sepay import *

# Set variables
StoredID = 0
TransactionerrorCodes = json.load(open("./lang/Transactionerror/en_US.json"))

# Set the local directory
localedir = './locale'

# Set up your magic function
translate = gettext.translation('appname', localedir, fallback=True)
_ = translate.gettext

# Debug
if os.environ['DEBUG'] == "true":
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

cnxn = pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+password+';TrustServerCertificate=yes')
cursor = cnxn.cursor()
cursor.execute('SET NOCOUNT ON')

# Prepare Database if not prepared yet
cursor.execute("""BEGIN TRANSACTION
                    IF NOT EXISTS (
                        SELECT * 
                        FROM   sys.columns 
                        WHERE  object_id = OBJECT_ID(N'dbo.Payment') 
                        AND name = 'TransactionID'
                    )
                    ALTER TABLE dbo.Payment ADD
                        TransactionID varchar(255) NULL,
                        TransactionDateTime datetime NULL,
                        TransactionStatus int NULL,
                        TransactionError nvarchar(MAX) NULL,
                        TransactionCard nvarchar(512) NULL,
                        TransactionTicket nvarchar(MAX) NULL,
                        TransactionTerminalType nvarchar(512) NULL,
                        TransactionTerminalIP varchar(15) NULL,
                        TransactionTerminalPort int NULL""")
cnxn.commit()

# Send translation files
cursor.execute("""
                    BEGIN TRANSACTION
                    IF NOT EXISTS (
                        SELECT * 
                        FROM INFORMATION_SCHEMA.TABLES 
                        WHERE TABLE_SCHEMA = 'dbo' 
                        AND TABLE_NAME = 'CardboardClientTranslations'
                    )
                    CREATE TABLE dbo.CardboardClientTranslations
                        (
                        lang nchar(10) NULL,
                        main varbinary(MAX) NULL
                        )  ON [PRIMARY]
                        TEXTIMAGE_ON [PRIMARY]
                    ALTER TABLE dbo.CardboardClientTranslations SET (LOCK_ESCALATION = TABLE)
                    """)
cnxn.commit()

while True:

    time.sleep(1)

    # Grab last entry from Payment, and print the DocumentID, PaymentTypeID and Amount
    cursor.execute("SELECT Id, PaymentTypeID, Amount, TransactionStatus FROM dbo.Payment ORDER BY DocumentID DESC")
    row = cursor.fetchone()

    if str(row[1]) == os.environ['PaymentID']:

        if row[3] == None:

            # Generate TransactionRef
            TransactionRef = ''.join(random.choices(string.ascii_uppercase + string.digits, k=9))

            # Stage 1
            while True:

                # Start Transaction
                stage1Interaction = stage1(TransactionRef, row[0], row[2])

                if stage1Interaction["success"] == True:
                    cursor.execute("UPDATE dbo.Payment SET TransactionID = ?, TransactionStatus = 2, TransactionTerminalType = ?, TransactionTerminalIP = ?, TransactionTerminalPort = ? WHERE Id = ?", TransactionRef, "sepay", stage1Interaction["terminalip"], stage1Interaction["terminalport"], row[0])
                    cnxn.commit()
                    break

                elif stage1Interaction["success"] == False:
                    cursor.execute("UPDATE dbo.Payment SET TransactionID = ?, TransactionStatus = 4 WHERE Id = ?", TransactionRef, row[0])
                    cnxn.commit()
                    break
            
            # Stage 2
            if stage1Interaction["success"] == True:
                while True:

                    # Get Transaction Status
                    stage2Interaction = stage2(TransactionRef)
                    if stage2Interaction["success"] == True and stage2Interaction["transactionstatus"] == "succeeded":
                        cursor.execute("UPDATE dbo.Payment SET TransactionStatus = 1, TransactionDateTime = ?, TransactionCard = ?, TransactionTicket = ? WHERE Id = ?", stage2Interaction["transactiontime"], stage2Interaction["brand"], stage2Interaction["receipt"], row[0])
                        cnxn.commit()
                        break
                    
                    elif stage2Interaction["success"] == True and stage2Interaction["transactionstatus"] == "inprogressnoinfo":
                        cursor.execute("UPDATE dbo.Payment SET TransactionStatus = 2 WHERE Id = ?", row[0])
                        cnxn.commit()

                    elif stage2Interaction["success"] == True and stage2Interaction["transactionstatus"] == "inprogress":
                        try:
                            if stage2Interaction["receipt"] != None:
                                cursor.execute("UPDATE dbo.Payment SET TransactionStatus = 2, TransactionDateTime = ?, TransactionCard = ?, TransactionTicket = ? WHERE Id = ?", stage2Interaction["transactiontime"], stage2Interaction["brand"], stage2Interaction["receipt"], row[0])
                                cnxn.commit()
                            else:
                                cursor.execute("UPDATE dbo.Payment SET TransactionStatus = 2, TransactionDateTime = ?, TransactionCard = ? WHERE Id = ?", stage2Interaction["transactiontime"], stage2Interaction["brand"], row[0])
                                cnxn.commit()
                        except KeyError:
                                cursor.execute("UPDATE dbo.Payment SET TransactionStatus = 2, TransactionDateTime = ?, TransactionCard = ? WHERE Id = ?", stage2Interaction["transactiontime"], stage2Interaction["brand"], row[0])
                                cnxn.commit()
                    
                    elif stage2Interaction["success"] == True and stage2Interaction["transactionstatus"] == "failed":
                        cursor.execute("UPDATE dbo.Payment SET TransactionStatus = 3, TransactionError = ? WHERE Id = ?", stage2Interaction["error"], row[0])
                        cnxn.commit()
                        break

                    elif stage2Interaction["success"] == True and stage2Interaction["transactionstatus"] == "canceled":
                        cursor.execute("UPDATE dbo.Payment SET TransactionStatus = 5 WHERE Id = ?", row[0])
                        cnxn.commit()
                        break

                    elif stage2Interaction["success"] == False:
                        cursor.execute("UPDATE dbo.Payment SET TransactionStatus = 4 WHERE Id = ?", row[0])
                        cnxn.commit()
                        break

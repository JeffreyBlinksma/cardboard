# Import dependencies
import time
import pyodbc
import string
import random
import logging.config
import json
import gettext
from cardterminals.sepay import *
import re

# Functions
def receiptGenerator80mm(ticket):
    datasplit = re.split('(\@RS)|(\@LF)|(\@SS)|(\@SM)|(\@SL)|(\@HT)|(\@AR)|(\@AM)|(\@@)|(       )', ticket)
    datatoprint = list(filter(None, datasplit))
    LineCounter = 0
    TabAmount = 0
    InternalNoteData = r"""{\rtf1\ansi\ansicpg1252\deff0\nouicompat\deflang1043\deflangfe1043\deftab709{\fonttbl{\f0\fswiss\fprq2\fcharset0 Tahoma;}}
    {\*\generator Riched20 10.0.22000}{\*\mmathPr\mnaryLim0\mdispDef1\mwrapIndent1440 }\viewkind4\uc1 
    \pard\widctlpar\slmult1\tqc\tx1985\tqr\tx3969\f0\fs18"""
    for x in datatoprint:
        print(LineCounter)
        print(x)
        if datatoprint[LineCounter] == '@RS':
            InternalNoteData += "\\b0\\fs18\ql "
            TabAmount = 0
        elif datatoprint[LineCounter] == '@LF':
            InternalNoteData += "\par\n"
            TabAmount = 0
        elif datatoprint[LineCounter] == '@SS':
            InternalNoteData += "\\b0\\fs18 "
        elif datatoprint[LineCounter] == '@SM':
            InternalNoteData += "\\b0\\fs20 "
        elif datatoprint[LineCounter] == '@SL':
            InternalNoteData += "\\b\\fs22 "
        elif datatoprint[LineCounter] == '@HT':
            InternalNoteData += "\\tab "
        elif datatoprint[LineCounter] == '@AR':
            if TabAmount == 0:
                InternalNoteData += "\\tab\\tab "
                TabAmount = 2
            elif TabAmount == 1:
                InternalNoteData += "\\tab "
                TabAmount = 2
            elif TabAmount == 2:
                InternalNoteData += ""
        elif datatoprint[LineCounter] == '@AM':
            if TabAmount == 0:
                InternalNoteData += "\\tab "
                TabAmount = 1
            else:
                InternalNoteData += ""
        elif datatoprint[LineCounter] == '@@':
            InternalNoteData += "@"
        elif datatoprint[LineCounter] == '       ':
            InternalNoteData += "\par\n"
            TabAmount = 0
        else:
            InternalNoteData += datatoprint[LineCounter]
        LineCounter = LineCounter + 1
    InternalNoteData += "}"
    print(InternalNoteData)
    return InternalNoteData

def receiptGeneratorA4(ticket):
    datasplit = re.split('(\@RS)|(\@LF)|(\@SS)|(\@SM)|(\@SL)|(\@HT)|(\@AR)|(\@AM)|(\@@)|(       )', ticket)
    datatoprint = list(filter(None, datasplit))
    LineCounter = 0
    TabAmount = 0
    InternalNoteData = r"""{\rtf1\ansi\ansicpg1252\deff0\nouicompat\deflang1043\deflangfe1043\deftab709{\fonttbl{\f0\fswiss\fprq2\fcharset0 Arial;}}
    {\*\generator Riched20 10.0.22000}{\*\mmathPr\mnaryLim0\mdispDef1\mwrapIndent1440 }\viewkind4\uc1 
    \pard\widctlpar\slmult1\tqc\tx1715\tqr\tx3430\f0\fs16"""
    for x in datatoprint:
        print(LineCounter)
        print(x)
        if datatoprint[LineCounter] == '@RS':
            InternalNoteData += "\\b0\\fs16\ql "
            TabAmount = 0
        elif datatoprint[LineCounter] == '@LF':
            InternalNoteData += "\par\n"
            TabAmount = 0
        elif datatoprint[LineCounter] == '@SS':
            InternalNoteData += "\\b0\\fs16 "
        elif datatoprint[LineCounter] == '@SM':
            InternalNoteData += "\\b\\fs16 "
        elif datatoprint[LineCounter] == '@SL':
            InternalNoteData += "\\b\\fs16 "
        elif datatoprint[LineCounter] == '@HT':
            InternalNoteData += "\\tab "
        elif datatoprint[LineCounter] == '@AR':
            if TabAmount == 0:
                InternalNoteData += "\\tab\\tab "
                TabAmount = 2
            elif TabAmount == 1:
                InternalNoteData += "\\tab "
                TabAmount = 2
            elif TabAmount == 2:
                InternalNoteData += ""
        elif datatoprint[LineCounter] == '@AM':
            if TabAmount == 0:
                InternalNoteData += "\\tab "
                TabAmount = 1
            else:
                InternalNoteData += ""
        elif datatoprint[LineCounter] == '@@':
            InternalNoteData += "@"
        elif datatoprint[LineCounter] == '       ':
            InternalNoteData += "\par\n"
            TabAmount = 0
        else:
            InternalNoteData += datatoprint[LineCounter]
        LineCounter = LineCounter + 1
    InternalNoteData += "}"
    print(InternalNoteData)
    return InternalNoteData


# Set variables
StoredID = 0

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

while True:

    time.sleep(1)

    # Grab last entry from Payment, and print the DocumentID, PaymentTypeID and Amount
    cursor.execute("SELECT Id, PaymentTypeID, Amount, TransactionStatus, DocumentID FROM dbo.Payment ORDER BY DocumentID DESC")
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
                        receipt80mm = receiptGenerator80mm(stage2Interaction["receipt"])
                        receiptA4 = receiptGeneratorA4(stage2Interaction["receipt"])
                        cursor.execute("UPDATE dbo.Document SET CardTerminalReceipt = ?, CardTerminalInvoiceReceipt = ? WHERE Id = ?", receipt80mm, receiptA4, row[4])
                        cnxn.commit()
                        break
                    
                    elif stage2Interaction["success"] == True and stage2Interaction["transactionstatus"] == "inprogressnoinfo":
                        cursor.execute("UPDATE dbo.Payment SET TransactionStatus = 2 WHERE Id = ?", row[0])
                        cnxn.commit()

                    elif stage2Interaction["success"] == True and stage2Interaction["transactionstatus"] == "inprogress":
                        try:
                            if stage2Interaction["receipt"] != None:
                                cursor.execute("UPDATE dbo.Payment SET TransactionStatus = 2, TransactionDateTime = ?, TransactionCard = ?, TransactionTicket = ? WHERE Id = ?", stage2Interaction["transactiontime"], stage2Interaction["brand"], stage2Interaction["receipt"], row[0])
                                receipt80mm = receiptGenerator80mm(stage2Interaction["receipt"])
                                receiptA4 = receiptGeneratorA4(stage2Interaction["receipt"])
                                cursor.execute("UPDATE dbo.Document SET CardTerminalReceipt = ?, CardTerminalInvoiceReceipt = ? WHERE Id = ?", receipt80mm, receiptA4, row[4])
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

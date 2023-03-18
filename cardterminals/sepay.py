import cryptography.exceptions
import os
import time
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization 
from cryptography import x509
from zeep import Client as zeepclient
from dateutil import parser
import hashlib
import base64

# Set up gettext for the domain errors with the locale directory in the root of the project with the locale set in env variable lang
import gettext
gettext.bindtextdomain("errors", os.path.join(os.path.dirname(__file__), "..", "locales"))
gettext.textdomain("errors")
_ = gettext.gettext

# Import private key
with open("/run/secrets/sepaykeyfile", "rb") as f:
#with open("robinsmediateam-sepay-x5.pem", "rb") as f:
    pkey = serialization.load_pem_private_key(
        f.read(),
        password=None,
        backend=default_backend()
    )

# Import other pubkeys
with open(os.path.join(os.path.dirname(__file__), "pubkeys", "sepay.pem"), "rb") as f:
    sepaypubkey = x509.load_pem_x509_certificate(f.read()).public_key()

# Load SOAP Client
zeepclient = zeepclient("https://wecr.sepay.nl/v2/wecr.asmx?WSDL")

def stage1(TransactionRef, MerchantRef, Amount):
    while True:
        # Convert Amount into string with 2 decimals, as required by the API
        convertedAmount = "{:.2f}".format(Amount)

        # Create Signature
        signatureData = f"0;2;{str(os.environ['MijnSepayUsername'])};{str(int(os.environ['SID']))};{TransactionRef};{MerchantRef};{convertedAmount};"
        signatureSign = pkey.sign(signatureData.encode(), padding.PKCS1v15(), hashes.SHA256())

        stage1Request = zeepclient.service.StartTransaction(key_index=0, version="2", login=os.environ['MijnSepayUsername'], sid=int(os.environ['SID']), transactionref=TransactionRef, merchantref=str(MerchantRef), amount=convertedAmount, signature=signatureSign)
            
        print(stage1Request["signature"])
        ResponseSignatureData = f"{stage1Request['key_index']};{stage1Request['version']};{stage1Request['login']};{stage1Request['sid']};{stage1Request['transactionref']};{stage1Request['merchantref'] or ''};{'{:.2f}'.format(stage1Request['amount'])};{stage1Request['status']};{stage1Request['message'] or ''};{stage1Request['terminalip'] or ''};{stage1Request['terminalport'] or ''}"
        try:
            sepaypubkey.verify(base64.b64decode(stage1Request["signature"]), ResponseSignatureData.encode(), padding.PKCS1v15(), hashes.SHA256())
        except cryptography.exceptions.InvalidSignature:
            print("Received signature invalid.")
            return {"success": False, "inform": True, "error": "Received signature failed"}

        # Check status code and retry if neccesary 
        match stage1Request["status"]:
            case "00":
                return {"success": True, "terminalip": stage1Request['terminalip'], "terminalport": stage1Request['terminalport']}
            case "01":
                print("Some of the required fields are missing: "+ stage1Request['message'])
                return {"success": False, "error": "Some of the required fields are missing: "+ stage1Request['message']}
            case "02":
                print("Signature failed")
                return {"success": False, "inform": True, "error": "Signature failed"}
            case "04":
                print("Invalid parameters, retrying...")
                continue
            case "06":
                print("Duplicate request")
                return {"success": False, "inform": False}
            case "07":
                print("Terminal not active or not enabled and/or authorized for transactions through WECR")
                return {"success": False, "inform": True, "error": "Terminal not active or not enabled and/or authorized for transactions through WECR"}
            case "11":
                print("Pending request for this terminal.")
                return {"success": False, "inform": False}
            case _:
                print("Undefined error")
                return {"success": False, "inform": True, "error": "Undefined error"}

def stage2(TransactionRef):
    signatureData = f"0;2;{str(os.environ['MijnSepayUsername'])};{str(int(os.environ['SID']))};{TransactionRef};0"
    signatureSign = pkey.sign(signatureData.encode(), padding.PKCS1v15(), hashes.SHA256())

    while True:
        time.sleep(2)
        stage2Request = zeepclient.service.GetTransactionStatus(key_index=0, version="2", login=os.environ['MijnSepayUsername'], sid=int(os.environ['SID']), transactionref=TransactionRef, timeout=0, signature=signatureSign)

        ResponseSignatureData = f"{stage2Request['key_index']};{stage2Request['version']};{stage2Request['login']};{stage2Request['sid']};{stage2Request['transactionref']};{stage2Request['merchantref'] or ''};{'{:.2f}'.format(stage2Request['amount'])};{stage2Request['transactiontime'] or ''};{stage2Request['transactionerror'] or ''};{stage2Request['transactionresult'] or ''};{stage2Request['status']};{stage2Request['message'] or ''};{stage2Request['brand'] or ''};{stage2Request['ticket'] or ''}"
        print(ResponseSignatureData)
        try:
            sepaypubkey.verify(base64.b64decode(stage2Request["signature"]), ResponseSignatureData.encode(), padding.PKCS1v15(), hashes.SHA256())
        except cryptography.exceptions.InvalidSignature:
            print("Received signature invalid.")
            return {"success": False, "inform": True, "error": "Received signature failed"}

        match stage2Request["status"]:
            case "00":
                return {"success": True, "transactionstatus": "succeeded", "transactiontime": iso_to_datetime(stage2Request['transactiontime']), "brand": stage2Request['brand'], "receipt": stage2Request['ticket']}
            case "01":
                print("Some of the required fields are missing: "+ stage2Request['message'])
                return {"success": False, "inform": False}
            case "02":
                print("Signature failed")
                return {"success": False, "inform": True, "error": "Signature failed"}
            case "04":
                print("Invalid parameters, retrying...")
                continue
            case "07":
                print("Terminal not active or not enabled and/or authorized for transactions through WECR")
                return {"success": False, "inform": True, "error": "Terminal not active or not enabled and/or authorized for transactions through WECR"}
            case "13":
                print("Transaction failed")
                if stage2Request['transactionresult'] == None:
                    return {"success": True, "transactionstatus": "failed", "error": _(stage2Request['transactionerror'])}
                else:
                    errorString = _(stage2Request['transactionerror']) + " " + _(stage2Request['transactionresult'])
                    return {"success": True, "transactionstatus": "failed", "error": errorString}
            case "14":
                print("This transaction was canceled. Reason:" + stage2Request['message'])
                return {"success": True, "transactionstatus": "canceled"}
            case "15":
                print("Transaction is not finished and has not been canceled yet")
                return {"success": True, "transactionstatus": "inprogressnoinfo"}
            case "17":
                return {"success": True, "transactionstatus": "inprogress", "transactiontime": iso_to_datetime(stage2Request['transactiontime']), "brand": stage2Request['brand']}
            case "99":
                print("Undefined error")
                return {"success": False, "inform": False}


# convert iso time to datetime using dateutil
def iso_to_datetime(iso_time):
    return parser.parse(iso_time)

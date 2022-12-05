#App container
FROM python:3.10.4-alpine3.15@sha256:2cca1fb3c699208f929afd487be37ddc97c531648c404f3df78fb25a0ff344a2

ENV ACCEPT_EULA=Y
#Run apk add with no caching && install MS SQL ODBC Driver v18
RUN \
    apk add --no-cache curl gnupg &&\
    curl -O https://download.microsoft.com/download/8/6/8/868e5fc4-7bfe-494d-8f9d-115cbcdb52ae/msodbcsql18_18.1.2.1-1_amd64.apk &&\
    curl -O https://download.microsoft.com/download/8/6/8/868e5fc4-7bfe-494d-8f9d-115cbcdb52ae/msodbcsql18_18.1.2.1-1_amd64.sig &&\
    curl https://packages.microsoft.com/keys/microsoft.asc  | gpg --import - &&\
    gpg --verify -v msodbcsql18_18.1.2.1-1_amd64.sig msodbcsql18_18.1.2.1-1_amd64.apk &&\
    apk add --allow-untrusted msodbcsql18_18.1.2.1-1_amd64.apk &&\
    rm msodbcsql18_18.1.2.1-1_amd64.apk &&\
    curl https://files.pythonhosted.org/packages/80/cc/5d602c4326af9993f891eab1f25bd967f89785efc08a773353564cab2f01/pyodbc-4.0.35-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl -o pyodbc-4.0.35-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl &&\
    pip install pyodbc-4.0.35-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl &&\
    rm pyodbc-4.0.35-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl &&\
    apk del curl gnupg

#install other redependencies and copy application
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt
COPY pubkeys /app/pubkeys
COPY lang /app/lang
COPY main.py .
ENV PYTHONUNBUFFERED 1
CMD ["python", "main.py"]

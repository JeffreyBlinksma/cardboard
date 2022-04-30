FROM python:3.10.4-bullseye@sha256:58ab94abb421ddfbfa4b2318c41ac89b72ed7f76795fb15e9318f3c44a1e8895 AS builder
RUN apt-get update &&\
    apt-get install -y build-essential unixodbc-dev &&\
    python -m pip wheel --wheel-dir /tmp/wheelhouse pyodbc==4.0.32 &&\
    python -m pip wheel --no-binary :all: --wheel-dir /tmp/wheelhouse cffi

FROM python:3.10.4-alpine3.15@sha256:2cca1fb3c699208f929afd487be37ddc97c531648c404f3df78fb25a0ff344a2

ENV ACCEPT_EULA=Y
RUN \
    apk add --no-cache curl gnupg &&\
    curl -O https://download.microsoft.com/download/b/9/f/b9f3cce4-3925-46d4-9f46-da08869c6486/msodbcsql18_18.0.1.1-1_amd64.apk &&\
    curl -O https://download.microsoft.com/download/b/9/f/b9f3cce4-3925-46d4-9f46-da08869c6486/msodbcsql18_18.0.1.1-1_amd64.sig &&\
    curl https://packages.microsoft.com/keys/microsoft.asc  | gpg --import - &&\
    gpg --verify -v msodbcsql18_18.0.1.1-1_amd64.sig msodbcsql18_18.0.1.1-1_amd64.apk &&\
    apk add --allow-untrusted msodbcsql18_18.0.1.1-1_amd64.apk &&\
    rm msodbcsql18_18.0.1.1-1_amd64.apk &&\
    apk del curl gnupg

COPY --from=builder /tmp/wheelhouse /tmp/wheelhouse
RUN ls /tmp/wheelhouse && pip install --find-links=/tmp/wheelhouse pyodbc==4.0.32 cffi
RUN pip install cryptography==36.0.2 zeep==4.1.0
WORKDIR /app
COPY pubkeys /app/pubkeys
COPY lang /app/lang
COPY main.py .
ENV PYTHONUNBUFFERED 1
CMD ["python", "main.py"]
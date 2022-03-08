FROM python:3.10.2-slim@sha256:b26fe89c9cb999342e176038fc12e461536eca8cb9d185d0a60501de32937be6

# Setup dependencies for pyodbc
RUN \
  export ACCEPT_EULA='Y' && \
  export MYSQL_CONNECTOR='mysql-connector-odbc-8.0.28-linux-glibc2.12-x86-64bit' && \
  export MYSQL_CONNECTOR_CHECKSUM='003a5e45830f103fa303743179e20fb6' && \
  apt-get update && \
  apt-get install -y curl build-essential unixodbc-dev g++ apt-transport-https wget && \
#  gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 0x467b942d3a79bd29 && \
  #
  # Install pyodbc db drivers for MSSQL, PG and MySQL
  curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
  curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
#  curl -L -o ${MYSQL_CONNECTOR}.tar.gz https://dev.mysql.com/get/Downloads/Connector-ODBC/8.0/${MYSQL_CONNECTOR}.tar.gz && \
#  curl -L -o ${MYSQL_CONNECTOR}.tar.gz.asc https://downloads.mysql.com/archives/gpg/\?file\=${MYSQL_CONNECTOR}.tar.gz\&p\=10 && \
#  gpg --verify ${MYSQL_CONNECTOR}.tar.gz.asc && \
#  echo "${MYSQL_CONNECTOR_CHECKSUM} ${MYSQL_CONNECTOR}.tar.gz" | md5sum -c - && \
  wget http://ftp.debian.org/debian/pool/main/g/glibc/multiarch-support_2.28-10_amd64.deb &&\
  apt-get install ./multiarch-support_2.28-10_amd64.deb &&\
  apt-get update && \
#  gunzip ${MYSQL_CONNECTOR}.tar.gz && tar xvf ${MYSQL_CONNECTOR}.tar && \
#  cp ${MYSQL_CONNECTOR}/bin/* /usr/local/bin && cp ${MYSQL_CONNECTOR}/lib/* /usr/local/lib && \
#  myodbc-installer -a -d -n "MySQL ODBC 8.0 Driver" -t "Driver=/usr/local/lib/libmyodbc8w.so" && \
#  myodbc-installer -a -d -n "MySQL ODBC 8.0" -t "Driver=/usr/local/lib/libmyodbc8a.so" && \
  apt-get install -y msodbcsql17 odbc-postgresql && \
  #
  # Update odbcinst.ini to make sure full path to driver is listed
  sed 's/Driver=psql/Driver=\/usr\/lib\/x86_64-linux-gnu\/odbc\/psql/' /etc/odbcinst.ini > /tmp/temp.ini && \
  mv -f /tmp/temp.ini /etc/odbcinst.ini && \
  # Install dependencies
  pip install --upgrade pip && \
  pip install pyodbc==4.0.32 && \
  # Cleanup build dependencies
  rm -rf ${MYSQL_CONNECTOR}* && \
  apt-get remove -y curl apt-transport-https debconf-utils g++ gcc rsync unixodbc-dev build-essential gnupg2 wget && \
  apt-get autoremove -y && apt-get autoclean -y

WORKDIR /app

COPY requirements.txt .
# Install dependencies
RUN pip install -r requirements.txt

COPY main.py .

CMD ["python", "main.py"]

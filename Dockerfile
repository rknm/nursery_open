FROM python:3.9
COPY requirements.txt .

RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

WORKDIR /src
COPY /streamlit /src
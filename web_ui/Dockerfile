FROM python:3.6.7
ADD . /app/
WORKDIR /app/
RUN pip3 install -r requirements.txt
ENTRYPOINT ["python3", "./add_device_webapp.py"]

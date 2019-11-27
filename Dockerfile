FROM python:3.7

RUN pip install python-telegram-bot 
RUN pip install steam

RUN mkdir /app
ADD . /app
WORKDIR /app

CMD python /app/steam_status_bot.py

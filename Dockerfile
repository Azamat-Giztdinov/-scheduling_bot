FROM python:3

COPY requirements.txt /app/tgbot/requirements.txt

WORKDIR /app/tgbot

RUN pip install --upgrade pip setuptools
RUN pip install -r requirements.txt

CMD python bot.py
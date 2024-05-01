FROM docker.io/library/python:3.12-alpine@sha256:ef097620baf1272e38264207003b0982285da3236a20ed829bf6bbf1e85fe3cb as build

RUN apk update && apk add --no-cache build-base libffi-dev
WORKDIR /usr/app
RUN python -m venv /usr/app/venv
ENV PATH="/usr/app/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM docker.io/library/python:3.12-alpine@sha256:ef097620baf1272e38264207003b0982285da3236a20ed829bf6bbf1e85fe3cb

RUN addgroup -S python && adduser -S python -G python

RUN mkdir /usr/app && chown python:python /usr/app

WORKDIR /usr/app

COPY --chown=python:python --from=build /usr/app/venv ./venv
COPY --chown=python:python ./src .

USER python

ENV PATH="/usr/app/venv/bin:$PATH"

CMD [ "python3", "/usr/app/autounsubscriber/AutoUnsubscriber.py" ]

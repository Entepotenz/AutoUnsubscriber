FROM docker.io/library/python:3.13-alpine@sha256:f9d772b2b40910ee8de2ac2b15ff740b5f26b37fc811f6ada28fce71a2542b0e as build

RUN apk update && apk add --no-cache build-base libffi-dev
WORKDIR /usr/app
RUN python -m venv /usr/app/venv
ENV PATH="/usr/app/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM docker.io/library/python:3.13-alpine@sha256:f9d772b2b40910ee8de2ac2b15ff740b5f26b37fc811f6ada28fce71a2542b0e

RUN addgroup -S python && adduser -S python -G python

RUN mkdir /usr/app && chown python:python /usr/app

WORKDIR /usr/app

COPY --chown=python:python --from=build /usr/app/venv ./venv
COPY --chown=python:python ./src .

USER python

ENV PATH="/usr/app/venv/bin:$PATH"

CMD [ "python3", "/usr/app/autounsubscriber/AutoUnsubscriber.py" ]

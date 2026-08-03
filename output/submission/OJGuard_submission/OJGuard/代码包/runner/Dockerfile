FROM docker.m.daocloud.io/library/alpine:3.20

RUN apk add --no-cache g++ python3 \
    && adduser -D -u 10001 runner
COPY entrypoint.py /opt/ojguard/entrypoint.py
RUN chmod 0555 /opt/ojguard/entrypoint.py

USER 10001:10001
ENTRYPOINT ["python3", "/opt/ojguard/entrypoint.py"]

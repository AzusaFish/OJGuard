FROM docker.m.daocloud.io/library/eclipse-temurin:17-jdk-alpine

ARG JAVA_EXECUTION_MODE=normal
RUN apk add --no-cache python3 \
    && adduser -D -u 10001 runner \
    && mkdir -p /opt/ojguard \
    && printf '%s' "$JAVA_EXECUTION_MODE" > /opt/ojguard/java-mode
COPY entrypoint.py /opt/ojguard/entrypoint.py
RUN chmod 0555 /opt/ojguard/entrypoint.py /opt/ojguard/java-mode

USER 10001:10001
ENTRYPOINT ["python3", "/opt/ojguard/entrypoint.py"]

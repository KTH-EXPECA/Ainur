FROM alpine:latest

COPY ping.sh /ping.sh
WORKDIR /
RUN chmod +x /ping.sh

ENTRYPOINT ["/ping.sh"]
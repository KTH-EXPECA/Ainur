FROM alpine:latest

RUN apk add --no-cache bash

COPY ping.sh /ping.sh
WORKDIR /
RUN chmod +x /ping.sh

ENTRYPOINT ["/ping.sh"]
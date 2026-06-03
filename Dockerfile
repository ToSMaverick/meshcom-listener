FROM golang:1.26.3-bookworm AS builder
WORKDIR /app

COPY go.mod go.sum* ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

COPY . .
RUN --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /meshcom-listener ./cmd/meshcom-listener

FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /
COPY --from=builder /meshcom-listener /meshcom-listener

VOLUME ["/data"]
EXPOSE 1799/udp

ENTRYPOINT ["/meshcom-listener"]
CMD ["serve"]

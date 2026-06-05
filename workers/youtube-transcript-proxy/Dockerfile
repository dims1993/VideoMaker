FROM python:3.12-slim
WORKDIR /app
COPY proxy_server.py .
ENV TRANSCRIPT_PROXY_HOST=0.0.0.0
EXPOSE 8787
CMD ["python", "proxy_server.py"]

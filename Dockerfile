FROM python:3.11.3-slim

RUN groupadd -r myLowPrivilegeUser && useradd -r -g myLowPrivilegeUser myLowPrivilegeUse

USER root

WORKDIR /application

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /home/myLowPrivilegeUser/.cache/dconf /tmp/runtime-myLowPrivilegeUser && \
    chown -R myLowPrivilegeUser:myLowPrivilegeUser /home/myLowPrivilegeUser /tmp/runtime-myLowPrivilegeUser && \
    chmod 700 /tmp/runtime-myLowPrivilegeUser

ENV HOME=/home/myLowPrivilegeUser
ENV XDG_RUNTIME_DIR=/tmp/runtime-myLowPrivilegeUser
ENV TRANSFORMERS_CACHE=/home/myLowPrivilegeUser/.cache/huggingface/transformers

USER myLowPrivilegeUser

COPY models /home/myLowPrivilegeUser/.cache/huggingface/transformers

COPY /application ./application

EXPOSE 9005

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "6", "-b", "0.0.0.0:9005", "--timeout", "300", "application.llm_guard_api.app.app:create_app"]

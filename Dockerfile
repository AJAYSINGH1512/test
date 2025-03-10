FROM python:3.11.3-slim

# Create user & group correctly
RUN groupadd -r myLowPrivilegeUser && useradd -r -g myLowPrivilegeUser myLowPrivilegeUser


USER root

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip uninstall llm_guard -y

# Install Spacy models
RUN python -m spacy download en_core_web_sm && \
    python -m spacy download zh_core_web_sm
    
# Ensure models are in the right directory
RUN python -c "import spacy; print(spacy.util.get_package_path('en_core_web_sm'))"



# Create necessary directories and set permissions
RUN mkdir -p /home/myLowPrivilegeUser/.cache/huggingface/hub && \
    mkdir -p /tmp/runtime-myLowPrivilegeUser && \
    chown -R myLowPrivilegeUser:myLowPrivilegeUser /home/myLowPrivilegeUser /tmp/runtime-myLowPrivilegeUser && \
    chmod -R 755 /home/myLowPrivilegeUser/.cache/huggingface && \
    chmod 700 /tmp/runtime-myLowPrivilegeUser
    
# Set Spacy environment variable (just in case)
ENV SPACY_DATA=/usr/local/lib/python3.11/site-packages

# Set Environment Variables
ENV HOME=/home/myLowPrivilegeUser
ENV XDG_RUNTIME_DIR=/tmp/runtime-myLowPrivilegeUser
ENV HF_HOME=/home/myLowPrivilegeUser/.cache/huggingface
ENV HF_HUB_CACHE=/home/myLowPrivilegeUser/.cache/huggingface/hub
ENV HF_HUB_OFFLINE=1

# Switch to the low-privilege user
USER myLowPrivilegeUser

WORKDIR /application

# Copy model files as root first
COPY --chown=myLowPrivilegeUser:myLowPrivilegeUser models /home/myLowPrivilegeUser/.cache/huggingface/hub


# Switch to the low-privilege user
USER myLowPrivilegeUser

# Copy application files (after switching users)
COPY --chown=myLowPrivilegeUser:myLowPrivilegeUser /application ./application

# Expose port
EXPOSE 9005

ENV PYTHONPATH="/application"

# Start the application using Gunicorn and Uvicorn
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "6", "-b", "0.0.0.0:9005", "--timeout", "300", "application.llm_guard_api.app.app:create_app"]

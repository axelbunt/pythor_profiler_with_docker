FROM debian:bullseye

# Install system dependencies
RUN apt-get update && apt-get install -y \
    lldb \
    python3 \
    python3-pip \
    python3-dbg \
    libpython3.9-dbg \
    build-essential \
    git \
    curl \
    procps

WORKDIR /app
COPY . .

# Install requirements
RUN pip install -r requirements.txt

# Adding automatic import of the cpython-lldb extension to LLDB
RUN echo "command script import cpython_lldb" >> /root/.lldbinit && chmod +x /root/.lldbinit

ENTRYPOINT ["bash"]

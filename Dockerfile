FROM debian:bullseye

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

RUN pip install -r requirements.txt

# Install the cpython_lldb extension and allow it to be loaded automatically on start of a new LLDB session
RUN echo "command script import cpython_lldb" >> /root/.lldbinit && chmod +x /root/.lldbinit

ENTRYPOINT ["bash"]

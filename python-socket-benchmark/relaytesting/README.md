Run this in one terminal:

    python3 upstream_server.py

In another terminal, run:

    python3 asyncrelay.py

In another terminal, run:

    nc 127.0.0.1 5558
    
You should see the message from the upstream server relayed every second.
    
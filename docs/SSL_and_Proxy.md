# DIDComm mediator Proxy and SSL configuration guide

Dockerfile exposes 3 tcp ports:

- **80/http** internal nginx port for non-secure communication: administrative purposes from local network, for example 
- **443/https** internal nginx port to provide services all over internet
- **8000/http** port for extended usage, if you prefer use external proxy/load-balancing service

This application has user-friendly admin pages to help configuration of SSL out-og-the-box.
Let's consider three cases

### Case-1: you already have SSL **cert** and **cert_key** files
Imagine you have certificate file **cert.pem** and certificate secret file **privkey.pem**
that placed in directory ```/var/my_certs```
Then docker-compose configuration seems like this:

    ```

    ...
    app:
        ...
        environment:
          ...
          - CERT_FILE=/certs/cert.pem  # if you use certbot, prefer to set fullchain.pem
          - CERT_KEY_FILE=/certs/privkey.pem
          ...
        volumes:
          - /var/my_certs:/certs    # mount directory with cert files into docker container
        ports:
          - "80:80"     # nginx running in container will route all http:// requests to https://
          - "443:443"   # nginx will server SSL connections and proxy to Mediator application
    ...

    ```
    
### Case-2: you don't have SSL **cert** and **cert_key** files, and you want to automate certs update via [Let's Encrypt](https://letsencrypt.org/)
To enable this option you should set env var **ACME_DIR** that point to mounted volume.
This docker based application uses ```certbot``` utility with ```webroot``` mechanism,
see details [here](https://certbot.eff.org/docs/using.html?highlight=webroot#webroot).
Nginx is using as local webserver. You should have write permissions for **ACME_DIR**

**Important:** Let's Encrypt checks if you are owner of the domain, so you should run application on live server
with pre-configured **DNS** record (for example **A** record with binding IP address)

    ```

    ...
    app:
        ...
        environment:
          ...
          - ACME_DIR=/acme
          ...
        volumes:
          - /var/my_acme:/acme    # mount directory for webroot mechanism of Let's Encrypt certbot
        ports:
          - "80:80"     # nginx running in container will handle ACME requests for cert issuing
          - "443:443"   # nginx will server SSL connections and proxy to Mediator application
    ...

    ```

### Case-3: you are going to run **Mediator app** behind external proxy (Kubernetes or Multi-Tower approach with external load balancer)
Example configuration for Nginx and web app published on 8000 port to avoid traffic overheads - external 
proxy will communicate with application directly: 

    ```
    server {
        server_name <your server name, for example: myserver.com>;
        listen 443 ssl;
        ssl_certificate         /certs/cert.pem;
        ssl_certificate_key     /certs/privkey.pem;
        ssl_protocols           TLSv1 TLSv1.1 TLSv1.2;

        # 
        location /ws {
                proxy_pass <address of web-application, for example: http://localhost:8000>;
                proxy_http_version 1.1;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection "Upgrade";
                
                # By default, the connection will be closed if the proxied server does not 
                # transmit any data within 60 seconds
                # proxy_read_timeout 60;  
        }
        location /polling {
                proxy_set_header Host $http_host;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
                proxy_pass <address of web-application, for example: http://localhost:8000>;
                # It is better to increase read timeout for long-polling recipients
                proxy_read_timeout 3600;
        }
        location / {
                proxy_set_header Host $http_host;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
                proxy_pass <address of web-application, for example: http://localhost:8000>;
        }
    }
    ```

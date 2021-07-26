# DIDComm mediator Proxy and SSL configuration guide

Dockerfile exposes 3 tcp ports:

- **80/http** internal nginx port for non-secure communication: administrative purposes from local network, for example 
- **443/https** internal nginx port to provide services all over internet
- **8000/http** port for extended usage, if you prefer use external proxy/load-balancing service

This application has user-friendly admin pages to help configuration of SSL out-og-the-box.
Let's consider three cases

### Case-1: you already have SSL **cert** and **cert_key** files
    
### Case-2: you don't have SSL **cert** and **cert_key** files, and you want to automate certs update via [Let's Encrypt](https://letsencrypt.org/)  
### Case-3: you are going to run **Mediator app** behind external proxy (Kubernetes or Multi-Tower approach with external load balancer)
Example configuration for Nginx: 

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
        location / {
                proxy_set_header Host $http_host;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
                proxy_pass <address of web-application, for example: http://localhost:8000>;
        }
    }
    ```

### 安装Gunicorn+Uvicorn
```shell
[root@AIOps ~]# cd /it_network/network_tickets
[root@AIOps network_tickets]# source .venv/bin/activate
(.venv) [root@AIOps network_tickets]# pip install uvicorn gunicorn uvloop

```

### 创建组和用户
```shell
# 创建 www-data 组（若已存在会报错，可忽略）
sudo groupadd --system www-data

# 创建 www-data 用户，不创建家目录，登录 shell 设为 /sbin/nologin
sudo useradd \
  --system \
  --no-create-home \
  --shell /sbin/nologin \
  --gid www-data \
  www-data

# 把项目目录的所有权赋给 www-data
sudo chown -R www-data:www-data /it_network/network_tickets

```

### 创建服务
```shell
sudo tee /etc/systemd/system/network_tickets.service << 'EOF'
[Unit]
Description=Gunicorn with UvicornWorker for network_tickets
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/it_network/network_tickets
Environment="PATH=/it_network/network_tickets/.venv/bin"

ExecStart=/bin/bash -c "source /it_network/network_tickets/.venv/bin/activate && python -m gunicorn network_tickets.asgi:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 4 --timeout 120"

Restart=always

[Install]
WantedBy=multi-user.target
EOF
```

### 启动服务
```shell
sudo systemctl daemon-reload
sudo systemctl restart network_tickets.service
sudo systemctl status  network_tickets.service

```

### 服务状态
```shell
● network_tickets.service - Gunicorn with UvicornWorker for network_tickets
     Loaded: loaded (/etc/systemd/system/network_tickets.service; enabled; preset: disabled)
     Active: active (running) since Wed 2025-05-07 10:20:47 CST; 2s ago
   Main PID: 2329420 (python)
      Tasks: 5 (limit: 408002)
     Memory: 144.1M
        CPU: 501ms
      CGroup: /system.slice/network_tickets.service
              ├─2329420 /it_network/network_tickets/.venv/bin/python -m gunicorn qytdjg.asgi:application -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --workers 4 --timeout 120
              ├─2329425 /it_network/network_tickets/.venv/bin/python -m gunicorn qytdjg.asgi:application -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --workers 4 --timeout 120
              ├─2329426 /it_network/network_tickets/.venv/bin/python -m gunicorn qytdjg.asgi:application -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --workers 4 --timeout 120
              ├─2329427 /it_network/network_tickets/.venv/bin/python -m gunicorn qytdjg.asgi:application -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --workers 4 --timeout 120
              └─2329428 /it_network/network_tickets/.venv/bin/python -m gunicorn qytdjg.asgi:application -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --workers 4 --timeout 120

```
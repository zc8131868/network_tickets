#### 安装filebeat
```shell
wget https://artifacts.elastic.co/downloads/beats/filebeat/filebeat-7.8.1-x86_64.rpm

rpm -ivh filebeat-7.8.1-x86_64.rpm
```

#### 激活apache模块
```shell
[root@Apache_PHP yum.repos.d]# cd /etc/filebeat/modules.d/

[root@Apache_PHP modules.d]# ls
activemq.yml.disabled     cyberark.yml.disabled          icinga.yml.disabled     mssql.yml.disabled            pensando.yml.disabled    suricata.yml.disabled
apache.yml.disabled       cylance.yml.disabled           iis.yml.disabled        mysqlenterprise.yml.disabled  postgresql.yml.disabled  system.yml.disabled
auditd.yml.disabled       elasticsearch.yml.disabled     imperva.yml.disabled    mysql.yml.disabled            proofpoint.yml.disabled  threatintel.yml.disabled
aws.yml.disabled          envoyproxy.yml.disabled        infoblox.yml.disabled   nats.yml.disabled             rabbitmq.yml.disabled    tomcat.yml.disabled
azure.yml.disabled        f5.yml.disabled                iptables.yml.disabled   netflow.yml.disabled          radware.yml.disabled     traefik.yml.disabled
barracuda.yml.disabled    fortinet.yml.disabled          juniper.yml.disabled    netscout.yml.disabled         redis.yml.disabled       zeek.yml.disabled
bluecoat.yml.disabled     gcp.yml.disabled               kafka.yml.disabled      nginx.yml.disabled            santa.yml.disabled       zoom.yml.disabled
cef.yml.disabled          googlecloud.yml.disabled       kibana.yml.disabled     o365.yml.disabled             snort.yml.disabled       zscaler.yml.disabled
checkpoint.yml.disabled   google_workspace.yml.disabled  logstash.yml.disabled   okta.yml.disabled             snyk.yml.disabled
cisco.yml.disabled        gsuite.yml.disabled            microsoft.yml.disabled  oracle.yml.disabled           sonicwall.yml.disabled
coredns.yml.disabled      haproxy.yml.disabled           misp.yml.disabled       osquery.yml.disabled          sophos.yml.disabled
crowdstrike.yml.disabled  ibmmq.yml.disabled             mongodb.yml.disabled    panw.yml.disabled             squid.yml.disabled

[root@Apache_PHP modules.d]# mv apache.yml.disabled apache.yml
```

#### 修改配置文件
```shell
[root@Apache_PHP filebeat]# pwd
/etc/filebeat

[root@Apache_PHP filebeat]# ls
fields.yml  filebeat.reference.yml  filebeat.yml  filebeat.yml-bak  modules.d

[root@Apache_PHP filebeat]# mv filebeat.yml filebeat.yml-bak

[root@Apache_PHP filebeat]# vim filebeat.yml

~~~具体内容如下~~~
# /etc/filebeat/modules.d下的apache.yml,只需要去掉disabled即可
# 路径: /etc/filebeat
filebeat.config:
  modules:
    path: ${path.config}/modules.d/*.yml
    reload.enabled: false

processors:
  - add_cloud_metadata: ~
  - add_docker_metadata: ~

output.elasticsearch:
  hosts: ["https://elasticsearch.qytopensource.com:9200"]
  index: qytang-apache-%{+yyyy.MM.dd}
  username: "elastic"
  password: "Cisc0123"
  ssl.certificate_authorities: ["/usr/share/filebeat/config/certs/ca.cer"]

setup.template.name: "qytang-apache"
setup.template.pattern: "qytang-apache-*"
setup.ilm.enabled: false

```

### 添加/etc/hosts
```shell
192.168.1.100 elasticsearch.qytopensource.com

```

### 创建ca.cer
```shell script
mkdir -p /usr/share/filebeat/config/certs/
cat >/usr/share/filebeat/config/certs/ca.cer <<EOF
-----BEGIN CERTIFICATE-----
MIIFmDCCA4CgAwIBAgIUGIHWBkOg0CY6+IMPV7gjR3sVFhwwDQYJKoZIhvcNAQEN
BQAwUjELMAkGA1UEBhMCQ04xEDAOBgNVBAgTB2JlaWppbmcxEDAOBgNVBAcTB2Jl
aWppbmcxDzANBgNVBAoTBnF5dGFuZzEOMAwGA1UEAxMFcXl0Y2EwHhcNMjMwNTEz
MDM0MDAwWhcNNDMwNTA4MDM0MDAwWjBSMQswCQYDVQQGEwJDTjEQMA4GA1UECBMH
YmVpamluZzEQMA4GA1UEBxMHYmVpamluZzEPMA0GA1UEChMGcXl0YW5nMQ4wDAYD
VQQDEwVxeXRjYTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAOZeyoLC
NByJi10DY/K7o9YOEue8plaF16hQ4YRzBUdPky/xeE1uDMNjtSP8iLVCo1aW6DfV
bsIhS6UNM/aeJtWtwLdDfSbvDIAH0k44sH2I6Vjg/Lh2sodcR+o9A7Ckcp/wBvGN
en5L5U8Bh0Q6xmCFbNoT3gioB/EFgM/Isbfr7NHx0eXMD5O8hENPLhn/LWp+Clu9
03luYmTfc5bJTABm8WBmWZU8IOxGZdgH76Y9jMfcm4wnTeARKD8S9ZxC8Slc0TWf
lW6OEToIhRpZ5zdlx+9V7UXLWwJRvVtpGodMos4hG3vUM5Dbi/axr87Q67+co9VQ
VxpZFFu2O3Uj+PyvOXz9ieEiO+7CmwJ1txbPWOwK6u+WiGpqWyKSJHRG939njNmS
OTrcJFJv/7hRuISe+OjuOc923ltur/dQ99BjWsisVIuPvXX26xLkynyPpShhmE7k
MDIIfcqIZHZFZ8T4MNYM/uvmx0EY8H5BuRJ58WdGvKkWJlC5T5oc3GUS1GXrwoi7
HtI9tp5r1IO8FbfKF6HiBz5ioiOdp8bS90vprwVXPWUNs79AIpTlkZi+fR7EYEMt
LMw8xfVmQd8m0c0EeGwhebFJxF45zAVGe2B+KH7MjBoENMIJNR+nY7cgDLCsMxJj
zhvt3MH1cFNbICy+J6JBAjhnXj0WUt16Lq+3AgMBAAGjZjBkMA4GA1UdDwEB/wQE
AwIBBjASBgNVHRMBAf8ECDAGAQH/AgECMB0GA1UdDgQWBBR7vyHTHkA7f/B2y9jf
u3r17XguGDAfBgNVHSMEGDAWgBR7vyHTHkA7f/B2y9jfu3r17XguGDANBgkqhkiG
9w0BAQ0FAAOCAgEAB33mMU0u0KSZhUt14b/wRKATouKKyF9OiS+91TFIpfJQMhO3
Vw0FFRNIUrwlw/j0S36ruONss+KOAF3IsGKp9KorxEvoX5xcuMFVDiljfNvjipRR
mdQMFDNUSZzinyKF9DOUTYbJLkyyuOAeQXxR90q2ltn59MFIeDjNXVnTV/ykpEKD
ZGv5vY+ricYvJCSzPUyvNFr59nX7RXcaCxJvFZxfvTbclW/DFZm6Sv+vo7lYCtOW
xLIMg2puQlYT4KVZwn6mEBYhKCkp24IqdiiMGUvrNOu299mwuoeEqO2VNoFoSnkF
0niYp8uSH/VFUvEilzJcUxbGa11sw4meBqt59oPCi+dycoUmySDBCWeGqumgZp52
VlL829JNMhx1Kp5bxSEwjZnXPTVovJ3RcQa7TovcFLCalbl28Dm6h/Vn25VIBEGa
zUW2XiGac7sGql+KKph+0bu5a8EDSJOEmWjPWcyCKzQj/8l14iqjgu0zQpJ+X+2k
Yb00hUi4gjpblbi/smoWo9UAQszw9Y+ZY6sPvR8qiIaCHUv10d4rmCxXqJai55cg
y94bXK5AmrQtxGPYasrJ8VbaD+PUW2srvG3ZssUMQAMPaBTLzh3kUVQ12li02oRV
8kg1crH49CMf61gKBT084IhYZPYP5ChfsWoONJWcSmH4J3dQtDbqKIgY/uo=
-----END CERTIFICATE-----
EOF

```

#### 激活filebeat
```shell
systemctl enable filebeat
systemctl start filebeat

```

#### 查看filebeat状态
```shell
systemctl status filebeat
```
